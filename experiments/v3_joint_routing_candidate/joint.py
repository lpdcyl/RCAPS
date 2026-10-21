"""Choose a V3-style placement together with the M3 prompt edge set.

This is an independent, bounded candidate. M1 and the released V3 code are
read-only. Short planning traces are used only by M2; independent traces are
reserved for validation. Decode keeps the prompt route and KV locality.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import time
import traceback
from collections import Counter
from functools import partial
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
from rcaps.v3.placement import (digest, measure, normalize, objective, save,
                                signature, validate)
from rcaps.v3.resource_graph import LayerCompatibilityDag, from_simulator
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.search import neighbors
from rcaps.v3.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
INPUTS = ROOT / "rcaps/v3/planning_inputs.json"
CASES = {"C1_single": ("single", 700.0), "C1_multi": ("multi", 320.0)}
PLANNING_SEED = 100
VALIDATION_SEEDS = (0, 1, 2)
PLANNING_SECONDS = 300
VALIDATION_SECONDS = 1800
MAX_NEIGHBOR_SCORES = 96
MIN_EXTRA_EDGE_USES = 2
ARRIVAL_MODES = ("uniform", "burst")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def case_inputs(case: str) -> tuple[TopologyModel, Path, Path]:
    item = read(INPUTS)[case]
    physical = ROOT / item["physical"]
    template = ROOT / item["template"]
    if digest(physical) != item["physical_sha256"] or digest(template) != item["template_sha256"]:
        raise ValueError("Frozen resource input hash changed")
    return TopologyModel(physical), physical, template


def canonical_edges(state: dict, dag: LayerCompatibilityDag) -> frozenset:
    """Retain canonical replica chains and all physical segment transitions."""
    segments = normalize(state)["segments"]
    edges = set()
    for segment in segments:
        for replica in segment["replicas"]:
            edges.update(zip(replica, replica[1:]))
    edges.add(("source", segments[0]["replicas"][0][0]))
    edges.update((replica[-1], "sink") for replica in segments[-1]["replicas"])
    for left, right in zip(segments, segments[1:]):
        edges.update((a[-1], b[0]) for a in left["replicas"]
                     for b in right["replicas"] if (a[-1], b[0]) in dag.edge_set)
    if not edges <= dag.edge_set:
        raise ValueError("Canonical edge is absent from the legal M1 DAG")
    verify_edges(dag, edges)
    return frozenset(edges)


def verify_edges(dag: LayerCompatibilityDag, edges) -> None:
    selected = frozenset(edges)
    if not selected <= dag.edge_set:
        raise ValueError("Selected path set contains an illegal edge")
    reduced = LayerCompatibilityDag(dag.spans, tuple(selected), dag.layers)
    if reduced.path_count() < 1:
        raise ValueError("Selected path set has no full layer route")
    # Every deployed GPU must remain on a complete source-to-sink route.
    forward = {"source"}
    backward = {"sink"}
    for _ in range(len(dag.spans) + 2):
        forward.update(b for a, b in selected if a in forward)
        backward.update(a for a, b in selected if b in backward)
    if not set(dag.spans) <= forward & backward:
        raise ValueError("Path selection strands a deployed GPU")


def observed_edge_counts(route_counts: dict[str, int], dag: LayerCompatibilityDag) -> Counter:
    """Convert simulator GPU UIDs (placement ID + 2) back to M1 IDs."""
    counts: Counter = Counter()
    for route, amount in route_counts.items():
        uids = [int(part) - 2 for part in route.split("-") if part]
        if not uids:
            continue
        edges = [("source", uids[0]), *zip(uids, uids[1:]), (uids[-1], "sink")]
        for edge in edges:
            if edge not in dag.edge_set:
                raise ValueError(f"Observed route used an illegal M1 edge: {edge}")
            counts[edge] += amount
    return counts


def selective_edges(state: dict, dag: LayerCompatibilityDag,
                    route_counts: dict[str, int]) -> frozenset:
    """Keep the safe canonical backbone plus edges M3 actually used twice."""
    backbone = canonical_edges(state, dag)
    observed = observed_edge_counts(route_counts, dag)
    selected = backbone | {edge for edge, uses in observed.items()
                           if uses >= MIN_EXTRA_EDGE_USES}
    verify_edges(dag, selected)
    return frozenset(selected)


class SelectedPathM3(GraphModeledQueueAwareDagScheduler):
    """Unchanged live M3 cost and Decode semantics with an allowed DAG subgraph."""

    def __init__(self, simulator, *, allowed_edges: frozenset):
        super().__init__(simulator)
        self.allowed_edges = allowed_edges

    def _allow_placement_edge(self, left_uid: int, right_uid: int) -> bool:
        if self.execution_dag is None:
            self.execution_dag = from_simulator(self.simulator)
        left = "source" if left_uid == self.simulator.source_node.node_uid else left_uid
        right = "sink" if right_uid == self.simulator.sink_node.node_uid else right_uid
        return (left, right) in self.allowed_edges and (left, right) in self.execution_dag.edge_set


def runtime_edges(edges: frozenset) -> frozenset:
    return frozenset((a if isinstance(a, str) else a + 2,
                      b if isinstance(b, str) else b + 2) for a, b in edges)


def edges_digest(edges: frozenset) -> str:
    values = sorted((str(a), str(b)) for a, b in edges)
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def arrival_trace(offered: float, duration: int, seed: int, mode: str):
    """Preserve request sizes and order while concentrating arrivals in time."""
    if mode == "uniform":
        return None
    if mode != "burst":
        raise ValueError(f"Unknown arrival mode {mode}")
    original = OnlineRequestFeeder(cluster_token_throughput=offered,
                                   start_time=0, duration=duration, seed=seed).trace
    def warp(t: float) -> float:
        if t < duration * 4 / 15:
            return t / 0.8
        if t < duration * 3 / 5:
            return duration / 3 + (t - duration * 4 / 15) / 2
        return duration / 2 + (t - duration * 3 / 5) / 0.8
    result = [(warp(t), tokens_in, tokens_out)
              for t, tokens_in, tokens_out in original]
    if any(not 0 <= t < duration for t, _, _ in result):
        raise ValueError("Burst trace exceeds fixed window")
    return result


def prepare(case: str) -> dict:
    model, physical, template = case_inputs(case)
    item = read(INPUTS)[case]
    reference = measure(model, item["reference_state"])
    topology = CASES[case][0]
    frozen = ROOT / "rcaps/v3_layouts" / topology
    frozen_record = read(frozen / "placement.json")
    frozen_state = normalize(frozen_record["state"])
    validate(model, frozen_state)
    candidates = [("released_v3", frozen_state, frozen)]
    single = ROOT / "experiments/m2_multistage_candidate/layouts" / case / "single_any"
    if single.exists():
        candidates.append(("single_boundary", normalize(read(single / "placement.json")["state"]), single))
    seen = {signature(state) for _, state, _ in candidates}
    scored = []
    evaluated = 0
    for _, candidate in itertools.islice(neighbors(model, frozen_state), MAX_NEIGHBOR_SCORES):
        key = signature(candidate)
        if key in seen:
            continue
        seen.add(key)
        metrics = measure(model, candidate)
        scored.append((objective(metrics, reference), key, candidate))
        evaluated += 1
    if scored:
        _, _, state = min(scored, key=lambda row: (row[0], row[1]))
        directory = HERE / "layouts" / case / "local_neighbor"
        save(model, template, state, directory,
             {"candidate_variant": "joint_route_local_neighbor", "case": case,
              "static_candidates_scored": evaluated})
        candidates.append(("local_neighbor", state, directory))
    distinct = {}
    entries = []
    for label, state, directory in candidates:
        checked = validate(model, state)
        solution = directory / "solution.ini"
        cluster = directory / "simulator_cluster.ini"
        key = (digest(solution), digest(cluster))
        if key in distinct:
            continue
        distinct[key] = label
        entries.append({"label": label, "layout": relative(directory),
                        "solution_sha256": key[0], "sim_cluster_sha256": key[1],
                        "static_score": objective(measure(model, state), reference),
                        "widths": [len(s["replicas"]) for s in state["segments"]],
                        "full_edges": len(checked["dag"].edges),
                        "full_paths": checked["dag"].path_count(),
                        "canonical_edges": len(canonical_edges(state, checked["dag"])),
                        "canonical_paths": LayerCompatibilityDag(
                            checked["dag"].spans,
                            tuple(canonical_edges(state, checked["dag"])),
                            checked["dag"].layers).path_count()})
    result = {"case": case, "physical": relative(physical),
              "physical_sha256": digest(physical), "template_sha256": digest(template),
              "planning_seed": PLANNING_SEED, "planning_seconds": PLANNING_SECONDS,
              "validation_seeds": VALIDATION_SEEDS,
              "validation_seconds": VALIDATION_SECONDS,
              "local_neighbor_scores": evaluated, "layouts": entries}
    write(HERE / "plans" / f"{case}.json", result)
    return result


def result_path(case: str, entry: dict, mask: str, seed: int,
                duration: int, arrival_mode: str,
                allowed: frozenset) -> Path:
    directory = HERE / "runs" / case / entry["label"] / mask
    if mask == "observed_safe":
        directory /= edges_digest(allowed)[:12]
    if arrival_mode == "burst":
        directory /= "burst"
    return directory / f"seed{seed}_{duration}s.json"


def run_cell(case: str, entry: dict, mask: str, seed: int,
             duration: int, allowed: frozenset,
             arrival_mode: str = "uniform") -> dict:
    model, physical, _ = case_inputs(case)
    directory = ROOT / entry["layout"]
    state = read(directory / "placement.json")["state"]
    dag = validate(model, state)["dag"]
    verify_edges(dag, allowed)
    output = result_path(case, entry, mask, seed, duration, arrival_mode, allowed)
    identity = {"case": case, "layout_label": entry["label"], "mask": mask,
                "seed": seed, "duration_s": duration, "offered_tokens_per_s": CASES[case][1],
                "physical_sha256": digest(physical),
                "solution_sha256": digest(directory / "solution.ini"),
                "sim_cluster_sha256": digest(directory / "simulator_cluster.ini"),
                "allowed_edges_sha256": edges_digest(allowed),
                "arrival_mode": arrival_mode}
    if output.exists():
        row = read(output)
        if all(row.get(key, "uniform" if key == "arrival_mode" else None) == value
               for key, value in identity.items()):
            return row
        raise ValueError(f"Existing result identity changed: {output}")
    started = time.perf_counter()
    try:
        row = fixed_window_run(
            CASES[case][0], "queue_dag", CASES[case][1], duration, 0, seed,
            directory / "solution.ini", directory / "simulator_cluster.ini",
            physical_cluster=physical, machine_counts=model.machine_counts,
            scheduler_factory=partial(SelectedPathM3,
                                      allowed_edges=runtime_edges(allowed)),
            compact=True, record_query_samples=True,
            trace_override=arrival_trace(CASES[case][1], duration, seed,
                                         arrival_mode))
        if row["arrivals"] != len(row["query_samples"]):
            raise ValueError("Incomplete query samples")
        row["status"] = "completed"
    except Exception as error:
        row = {"status": "failed", "error": repr(error),
               "traceback": traceback.format_exc()}
    row.update(identity)
    row["wall_s"] = time.perf_counter() - started
    write(output, row)
    return row


def online_score(row: dict, baseline: dict) -> float:
    """Predeclared route-aware M2 criterion, never computed from held-out runs."""
    if row.get("status") != "completed":
        return math.inf
    fields = ("ttft_p95_s", "tpot_p95_s", "output_throughput_tokens_per_s")
    if any(not row.get(key) or not baseline.get(key) for key in fields):
        return math.inf
    completion = row["completion_fraction"]
    return (0.40 * row["ttft_p95_s"] / baseline["ttft_p95_s"]
            + 0.35 * row["tpot_p95_s"] / baseline["tpot_p95_s"]
            + 0.25 * baseline["output_throughput_tokens_per_s"]
            / row["output_throughput_tokens_per_s"]
            + 2.0 * (baseline["completion_fraction"] - completion))


def plan(case: str) -> dict:
    info = read(HERE / "plans" / f"{case}.json")
    model, _, _ = case_inputs(case)
    entries = info["layouts"]
    pilot = {}
    for entry in entries:
        state = read(ROOT / entry["layout"] / "placement.json")["state"]
        dag = validate(model, state)["dag"]
        full = frozenset(dag.edges)
        for arrival_mode in ARRIVAL_MODES:
            pilot[entry["label"], arrival_mode] = run_cell(
                case, entry, "full", PLANNING_SEED,
                PLANNING_SECONDS, full, arrival_mode)
    baseline = {mode: pilot["released_v3", mode] for mode in ARRIVAL_MODES}
    if any(row.get("status") != "completed" for row in baseline.values()):
        raise RuntimeError("Released V3 planning control failed")
    scores = []
    for entry in entries:
        label = entry["label"]
        state = read(ROOT / entry["layout"] / "placement.json")["state"]
        dag = validate(model, state)["dag"]
        masks = {"full": frozenset(dag.edges),
                 "canonical": canonical_edges(state, dag)}
        full_rows = [pilot[label, mode] for mode in ARRIVAL_MODES]
        if all(row.get("status") == "completed" for row in full_rows):
            route_counts = Counter()
            for row in full_rows:
                route_counts.update(row["route_counts"])
            masks["observed_safe"] = selective_edges(
                state, dag, route_counts)
        for mask, allowed in masks.items():
            scenario_scores = {}
            results = {}
            for arrival_mode in ARRIVAL_MODES:
                row = (pilot[label, arrival_mode] if mask == "full" else
                       run_cell(case, entry, mask, PLANNING_SEED,
                                PLANNING_SECONDS, allowed, arrival_mode))
                scenario_scores[arrival_mode] = online_score(row, baseline[arrival_mode])
                results[arrival_mode] = {
                    "path": relative(result_path(case, entry, mask, PLANNING_SEED,
                                                 PLANNING_SECONDS, arrival_mode, allowed)),
                    "sha256": digest(result_path(case, entry, mask, PLANNING_SEED,
                                                 PLANNING_SECONDS, arrival_mode, allowed))}
            scores.append({"layout": label, "mask": mask,
                           "score": max(scenario_scores.values()),
                           "scenario_scores": scenario_scores,
                           "allowed_edges": sorted((str(a), str(b)) for a, b in allowed),
                           "allowed_edges_sha256": edges_digest(allowed),
                           "allowed_paths": LayerCompatibilityDag(
                               dag.spans, tuple(allowed), dag.layers).path_count(),
                           "results": results})
    finite = [row for row in scores if math.isfinite(row["score"])]
    if not finite:
        raise RuntimeError("No route-aware candidate completed the planning trace")
    winner = min(finite, key=lambda row: (row["score"], row["layout"], row["mask"]))
    result = {"case": case, "selection_seed": PLANNING_SEED,
              "selection_duration_s": PLANNING_SECONDS,
              "criterion": "worst of uniform and burst: 0.40 TTFT ratio + 0.35 TPOT ratio + 0.25 inverse throughput ratio + 2x paired completion deficit",
              "candidates": scores, "winner": winner}
    write(HERE / "plans" / f"{case}_selected.json", result)
    return result


def parity(case: str) -> dict:
    """Check that an unrestricted adapter exactly preserves released M3."""
    info = read(HERE / "plans" / f"{case}.json")
    entry = next(row for row in info["layouts"] if row["label"] == "released_v3")
    model, _, _ = case_inputs(case)
    state = read(ROOT / entry["layout"] / "placement.json")["state"]
    dag = validate(model, state)["dag"]
    comparisons = []
    for mask, allowed, source in (
        ("full", frozenset(dag.edges),
         ROOT / "experiments/v3_release/smoke" / CASES[case][0] /
         "seed100/rcaps_v3.json"),
        ("canonical", canonical_edges(state, dag),
         ROOT / "experiments/v3_pathspace_ablation/runs/smoke" /
         case / "seed100.json")):
        fresh = run_cell(case, entry, mask, 100, 60, allowed)
        frozen = read(source)
        fields = ("trace_sha256", "solution_sha256", "sim_cluster_sha256",
                  "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                  "completion_fraction", "backlog_at_window_end", "route_counts")
        mismatches = {key: (fresh.get(key), frozen.get(key)) for key in fields
                      if fresh.get(key) != frozen.get(key)}
        comparisons.append({"mask": mask, "source": relative(source),
                            "source_sha256": digest(source),
                            "passed": fresh.get("status") == "completed" and not mismatches,
                            "mismatches": mismatches})
    runtime_files = (HERE / "joint.py", ROOT / "rcaps/v3/scheduler.py",
                     ROOT / "rcaps/v3/resource_graph.py",
                     ROOT / "rcaps/v3/queue_cost.py",
                     ROOT / "rcaps/v3/online_scheduler.py",
                     ROOT / "benchmarks/fixed_window.py")
    result = {"case": case, "passed": all(row["passed"] for row in comparisons),
              "comparisons": comparisons,
              "runtime_sha256": {relative(path): digest(path) for path in runtime_files}}
    write(HERE / "parity" / f"{case}.json", result)
    if not result["passed"]:
        raise ValueError(f"M3 parity failed for {case}")
    return result


def reused_formal(case: str, entry: dict, mask: str, seed: int,
                  allowed: frozenset) -> tuple[dict, Path] | None:
    audit_file = HERE / "parity" / f"{case}.json"
    if not audit_file.exists() or not read(audit_file)["passed"]:
        return None
    audit = read(audit_file)
    if any(digest(ROOT / path) != expected
           for path, expected in audit["runtime_sha256"].items()):
        raise ValueError("M3 parity audit predates a runtime or adapter change")
    model, physical, _ = case_inputs(case)
    directory = ROOT / entry["layout"]
    state = read(directory / "placement.json")["state"]
    dag = validate(model, state)["dag"]
    source = None
    if entry["label"] == "released_v3" and mask == "full" and allowed == frozenset(dag.edges):
        source = ROOT / "benchmarks/runs" / CASES[case][0] / f"seed{seed}/rcaps_v3.json"
    elif (entry["label"] == "released_v3" and mask == "canonical" and
          allowed == canonical_edges(state, dag)):
        source = ROOT / "experiments/v3_pathspace_ablation/runs/formal" / case / f"seed{seed}.json"
    elif entry["label"] == "single_boundary" and mask == "full" and allowed == frozenset(dag.edges):
        old_layout = ROOT / "experiments/m2_multistage_candidate/layouts" / case / "single_a100"
        if (digest(directory / "solution.ini") == digest(old_layout / "solution.ini") and
                digest(directory / "simulator_cluster.ini") == digest(old_layout / "simulator_cluster.ini")):
            source = ROOT / "experiments/m2_multistage_candidate/runs/formal" / case / f"seed{seed}/single_a100.json"
    if source is None or not source.exists():
        return None
    row = read(source)
    expected = {"duration_s": VALIDATION_SECONDS, "seed": seed,
                "warmup_s": 0, "offered_tokens_per_s": CASES[case][1],
                "evaluation_protocol": "fixed_window_no_tail_drain",
                "physical_cluster_sha256": digest(physical),
                "solution_sha256": digest(directory / "solution.ini"),
                "sim_cluster_sha256": digest(directory / "simulator_cluster.ini")}
    if any(row.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Historical formal window identity mismatch: {source}")
    result = dict(row)
    result["status"] = "completed"
    result["reused_source"] = relative(source)
    result["reused_source_sha256"] = digest(source)
    return result, source


def validation(case: str) -> dict:
    info = read(HERE / "plans" / f"{case}.json")
    selected = read(HERE / "plans" / f"{case}_selected.json")
    model, _, _ = case_inputs(case)
    chosen = selected["winner"]
    winner_entry = next(row for row in info["layouts"] if row["label"] == chosen["layout"])
    baseline_entry = next(row for row in info["layouts"] if row["label"] == "released_v3")
    candidate_edges = frozenset(tuple((int(value) if value.isdecimal() else value)
                                       for value in edge)
                                for edge in chosen["allowed_edges"])
    rows = []
    for seed in VALIDATION_SEEDS:
        for arrival_mode in ARRIVAL_MODES:
            for label, entry, allowed in (
                ("released_v3", baseline_entry, frozenset(validate(
                    model, read(ROOT / baseline_entry["layout"] / "placement.json")["state"])["dag"].edges)),
                ("joint_candidate", winner_entry, candidate_edges)):
                mask = "full" if label == "released_v3" else chosen["mask"]
                reused = (reused_formal(case, entry, mask, seed, allowed)
                          if arrival_mode == "uniform" else None)
                if reused is None:
                    row = run_cell(case, entry, mask, seed, VALIDATION_SECONDS,
                                   allowed, arrival_mode)
                    source = result_path(case, entry, mask, seed,
                                         VALIDATION_SECONDS, arrival_mode, allowed)
                else:
                    row, source = reused
                rows.append({"arm": label, "seed": seed, "arrival_mode": arrival_mode,
                         "status": row["status"],
                         "result": relative(source), "result_sha256": digest(source),
                         "reused": reused is not None,
                         "trace_sha256": row.get("trace_sha256"),
                         "throughput": row.get("output_throughput_tokens_per_s"),
                         "ttft_p95_s": row.get("ttft_p95_s"),
                         "tpot_p95_s": row.get("tpot_p95_s"),
                         "completion": row.get("completion_fraction"),
                         "backlog": row.get("backlog_at_window_end"),
                         "used_paths": len(row.get("route_counts", {}))})
    for seed in VALIDATION_SEEDS:
        for arrival_mode in ARRIVAL_MODES:
            pair = [row for row in rows if row["seed"] == seed and
                    row["arrival_mode"] == arrival_mode]
            if len(pair) == 2 and all(row["status"] == "completed" for row in pair):
                if pair[0]["trace_sha256"] != pair[1]["trace_sha256"]:
                    raise ValueError(f"Paired trace mismatch for seed {seed}/{arrival_mode}")
    result = {"case": case, "winner": chosen, "rows": rows}
    write(HERE / "validation" / f"{case}.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "plan", "parity", "validate"))
    parser.add_argument("--case", choices=CASES, required=True)
    args = parser.parse_args()
    value = {"prepare": prepare, "plan": plan, "parity": parity,
             "validate": validation}[args.phase](args.case)
    print(json.dumps({"phase": args.phase, "case": args.case,
                      "winner": value.get("winner"),
                      "layouts": value.get("layouts"),
                      "rows": value.get("rows")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
