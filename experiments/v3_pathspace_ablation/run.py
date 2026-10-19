"""Compare canonical segment routes with V3's full compatible DAG.

The placement, live route price, decode path, transfer batching, physical
resources and request trace are identical. Only the prompt's allowed edge set
changes. Released V3 records are read and audited, never overwritten.
"""

from __future__ import annotations

import argparse
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.analysis import path_use
from experiments.m2_multistage_candidate.placement import digest, validate
from experiments.m2_multistage_candidate.prepare import files
from rcaps.v3.topology import TopologyModel
from rcaps.v3.resource_graph import LayerCompatibilityDag, from_simulator
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = ("C1_single", "C1_multi")
LOADS = {"C1_single": 700.0, "C1_multi": 320.0}
SEEDS = (0, 1, 2)
SOURCE = ROOT / "experiments/v3_release"
RUNTIME = ("rcaps/v3/resource_graph.py", "rcaps/v3/scheduler.py",
           "rcaps/v3/routing.py", "rcaps/v3/queue_cost.py",
           "rcaps/v3/online_scheduler.py", "benchmarks/fixed_window.py")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    part.replace(path)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def layout(case: str) -> Path:
    return ROOT / "rcaps/v3_layouts" / case.removeprefix("C1_")


def canonical_edges(state: dict, full: LayerCompatibilityDag) -> frozenset:
    """Keep every physical inter-segment transition, but no replica switching
    within a segment. Segment replica lists define the canonical pipelines.
    """
    segments = state["segments"]
    edges = set()
    for segment in segments:
        for replica in segment["replicas"]:
            edges.update(zip(replica, replica[1:]))
    edges.update(("source", replica[0]) for replica in segments[0]["replicas"])
    edges.update((replica[-1], "sink") for replica in segments[-1]["replicas"])
    for left, right in zip(segments, segments[1:]):
        for a in left["replicas"]:
            for b in right["replicas"]:
                edge = (a[-1], b[0])
                if edge in full.edge_set:
                    edges.add(edge)
    if not edges <= full.edge_set:
        raise ValueError("Canonical route has a nonphysical or layer-incompatible edge")
    reduced = LayerCompatibilityDag(full.spans, tuple(sorted(edges, key=str)), full.layers)
    if reduced.path_count() == 0:
        raise ValueError("Canonical route set has no complete execution path")
    return frozenset(edges)


class CanonicalGraphDagScheduler(GraphModeledQueueAwareDagScheduler):
    """V3 M3 with the same costs and tie order, restricted to canonical edges."""

    def __init__(self, simulator, *, allowed_edges: frozenset):
        super().__init__(simulator)
        self.allowed_edges = allowed_edges

    def _allow_placement_edge(self, left_uid: int, right_uid: int) -> bool:
        if self.execution_dag is None:
            self.execution_dag = from_simulator(self.simulator)
        left = ("source" if left_uid == self.simulator.source_node.node_uid
                else left_uid)
        right = ("sink" if right_uid == self.simulator.sink_node.node_uid
                 else right_uid)
        return ((left, right) in self.execution_dag.edge_set and
                (left, right) in self.allowed_edges)


def audit() -> dict:
    from experiments.v3_release.verify import snapshot
    manifest = read(SOURCE / "manifest.json")
    if snapshot() != manifest:
        raise ValueError("Frozen V3 manifest drifted")
    result = {"runtime_sha256": {p: digest(ROOT / p) for p in RUNTIME},
              "adapter_sha256": digest(HERE / "run.py"), "cases": {}}
    for case in CASES:
        physical, _, topology = files(case)
        model = TopologyModel(physical)
        deployment = layout(case)
        record = read(deployment / "placement.json")
        checked = validate(model, record["state"])
        full = checked["dag"]
        allowed = canonical_edges(record["state"], full)
        reduced = LayerCompatibilityDag(full.spans, tuple(allowed), full.layers)
        frozen = manifest["layouts"][topology]
        if digest(physical) != frozen["physical_sha256"] or \
                digest(deployment / "solution.ini") != frozen["solution_sha256"] or \
                digest(deployment / "simulator_cluster.ini") != frozen["sim_cluster_sha256"]:
            raise ValueError(f"Frozen layout or physical resource changed: {case}")
        result["cases"][case] = {
            "physical": rel(physical), "physical_sha256": digest(physical),
            "solution_sha256": digest(deployment / "solution.ini"),
            "sim_cluster_sha256": digest(deployment / "simulator_cluster.ini"),
            "full_edges": len(full.edges), "full_paths": full.path_count(),
            "canonical_edges": len(allowed), "canonical_paths": reduced.path_count(),
            "allowed_edges": sorted((str(a), str(b)) for a, b in allowed)}
    write(HERE / "audit.json", result)
    return result


def run_one(case: str, seed: int, phase: str) -> str:
    audited = read(HERE / "audit.json")
    if audited["adapter_sha256"] != digest(HERE / "run.py"):
        raise ValueError("Path-space adapter changed since audit")
    info = audited["cases"][case]
    physical, _, topology = files(case)
    deployment = layout(case)
    state = read(deployment / "placement.json")["state"]
    checked = validate(TopologyModel(physical), state)
    offset = 2  # The exported solution.ini uses compute_node_{gpu_id + 2}.
    allowed = frozenset((a if isinstance(a, str) else a + offset,
                         b if isinstance(b, str) else b + offset)
                        for a, b in canonical_edges(state, checked["dag"]))
    duration = 60 if phase == "smoke" else 1800
    output = HERE / "runs" / phase / case / f"seed{seed}.json"
    identity = {"case": case, "seed": seed, "phase": phase,
                "scenario": topology, "offered_tokens_per_s": LOADS[case],
                "duration_s": duration, "warmup_s": 0,
                "evaluation_protocol": "fixed_window_no_tail_drain",
                "physical_sha256": info["physical_sha256"],
                "solution_sha256": info["solution_sha256"],
                "sim_cluster_sha256": info["sim_cluster_sha256"],
                "adapter_sha256": audited["adapter_sha256"],
                "allowed_canonical_paths": info["canonical_paths"],
                "query_samples_schema": 1}
    if output.exists():
        row = read(output)
        matches = all(row.get(k) == v for k, v in identity.items())
        if not matches:
            migration_file = SOURCE / "metadata_migration.json"
            parity_file = SOURCE / "module_migration_parity.json"
            if migration_file.exists() and parity_file.exists():
                migration = read(migration_file)["records"]
                entry = migration.get(rel(output), {})
                parity = read(parity_file)
                matches = (entry.get("current_sha256") == digest(output) and
                           any(item["case"] == case and item["cell"] == "canonical" and
                               item["status"] == "exact_match_after_module_migration" and
                               item["reference_sha256"] == digest(
                                   HERE / "runs/smoke" / case / "seed100.json")
                               for item in parity) and
                           all(row.get(k) == v for k, v in identity.items()
                               if k != "adapter_sha256"))
        if matches:
            return rel(output)
        raise ValueError(f"Existing run identity changed: {output}")
    import contextlib
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                topology, "queue_dag", LOADS[case], duration, 0, seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=phase == "formal", compact=True,
                record_query_samples=True, physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=partial(CanonicalGraphDagScheduler,
                                          allowed_edges=allowed))
            row.update(identity)
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError("Incomplete query samples")
            row["path_use_audit"] = path_use(case, "multi_any", row)
            if row["path_use_audit"]["cross_replica_requests"]:
                raise ValueError("Canonical scheduler used a cross-replica path")
            write(output, row)
        except Exception:
            traceback.print_exc(file=log)
            raise
    return rel(output)


def run_phase(phase: str, workers: int) -> dict:
    audit()
    if phase == "formal":
        smoke = read(HERE / "smoke_index.json")
        if smoke["failures"] or len(smoke["jobs"]) != len(CASES):
            raise ValueError("Smoke gate has not passed")
    seeds = (100,) if phase == "smoke" else SEEDS
    result = {"phase": phase, "jobs": {}, "failures": {}}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(run_one, case, seed, phase): (case, seed)
                for case in CASES for seed in seeds}
        for future in as_completed(jobs):
            case, seed = jobs[future]
            key = f"{case}/seed{seed}"
            try:
                path = ROOT / future.result()
                row = read(path)
                result["jobs"][key] = {"source": rel(path), "sha256": digest(path),
                                        "trace_sha256": row["trace_sha256"],
                                        "status": "passed"}
                print("PASS", key, flush=True)
            except Exception as exc:
                result["jobs"][key] = {"status": "failed", "error": repr(exc)}
                result["failures"][key] = repr(exc)
                print("FAIL", key, repr(exc), flush=True)
            write(HERE / f"{phase}_index.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("audit", "smoke", "formal"), required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.phase == "audit":
        print(json.dumps(audit(), indent=2))
    else:
        print(json.dumps(run_phase(args.phase, args.workers)["failures"], indent=2))


if __name__ == "__main__":
    main()
