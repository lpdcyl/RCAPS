"""Helix Separate Pipelines (SP) with one paired global request trace.

The artifact runs A100/L4/T4 subclusters separately. Here every request in the
common full-load trace is assigned to exactly one subcluster using the artifact's
relative per-subcluster offered-load settings. Each uses its original layout
and Naive scheduler; metrics are pooled over the original global query IDs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
from simulator.event_simulator.utils import BASE_QUERY_UID

NAME = "separate"
DESCRIPTION = "Helix artifact Separate Pipelines with original Naive scheduling and paired trace"
GROUPS = ("a100", "l4", "t4")
MACHINES = {"a100": {"A100": 4}, "l4": {"L4": 8}, "t4": {"T4": 12}}


def layout(scenario: str, root: Path) -> tuple[Path, Path]:
    if scenario not in ("single", "multi"):
        raise ValueError(scenario)
    manifest = root / "experiments" / "helix_additional_baselines" / "layouts" / f"sp_{scenario}.json"
    return manifest, manifest


def _load_manifest(path: Path, scenario: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["scenario"] != scenario or set(manifest["groups"]) != set(GROUPS):
        raise ValueError("SP manifest scenario or groups mismatch")
    for group in GROUPS:
        entry = manifest["groups"][group]
        if entry["weight"] <= 0:
            raise ValueError(f"SP group {group} has nonpositive weight")
        for kind in ("physical", "profile", "solution", "sim_cluster"):
            source = root / entry[kind]["path"]
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry[kind]["sha256"]:
                raise ValueError(f"SP {group} {kind} differs from audited artifact")
    return manifest


def _partition(trace: list[tuple[float, int, int]], weights: dict[str, float]):
    assigned = {group: [] for group in GROUPS}
    tokens = {group: 0 for group in GROUPS}
    for index, (arrival, prompt, output) in enumerate(trace):
        group = min(GROUPS, key=lambda item: (len(assigned[item]) / weights[item], GROUPS.index(item)))
        assigned[group].append((index, arrival, prompt, output))
        tokens[group] += prompt + output
    if sorted(index for rows in assigned.values() for index, *_ in rows) != list(range(len(trace))):
        raise AssertionError("SP trace partition lost or duplicated requests")
    return assigned, tokens


def evaluate(scenario: str, offered: float, duration: int, warmup: int,
             seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run

    if solution != sim_cluster:
        raise ValueError("SP uses one aggregate layout manifest")
    manifest = _load_manifest(solution, scenario)
    root = Path(__file__).resolve().parents[1]
    feeder = OnlineRequestFeeder(cluster_token_throughput=offered,
                                 start_time=0, duration=duration, seed=seed)
    trace = feeder.trace
    weights = {group: manifest["groups"][group]["weight"] for group in GROUPS}
    partition, assigned_tokens = _partition(trace, weights)
    trace_sha256 = hashlib.sha256(json.dumps(
        [(round(t, 9), prompt, output) for t, prompt, output in trace],
        separators=(",", ":")).encode()).hexdigest()
    rows = {}
    distributions = {}
    samples = {}
    route_counts = {}
    for group in GROUPS:
        entry = manifest["groups"][group]
        paths = {kind: root / entry[kind]["path"]
                 for kind in ("physical", "profile", "solution", "sim_cluster")}
        selected = partition[group]
        result = run(scenario, NAME, offered * weights[group] / sum(weights.values()),
                     duration, warmup, seed, paths["solution"], paths["sim_cluster"],
                     compact=True, physical_cluster=paths["physical"],
                     record_query_samples=True, machine_counts=MACHINES[group],
                     machine_profile=paths["profile"], allow_force_set=True,
                     include_distributions=True,
                     trace_override=[(t, prompt, output)
                                     for _, t, prompt, output in selected])
        distributions[group] = result.pop("_distributions")
        if result["arrivals"] != len(selected) or len(result["query_samples"]) != len(selected):
            raise AssertionError(f"SP {group} result omitted a request")
        for local_index, (global_index, t, prompt, output) in enumerate(selected):
            local_id = str(BASE_QUERY_UID + local_index)
            sample = result["query_samples"][local_id]
            if (abs(sample["arrival_s"] - t) > 1e-9 or
                    sample["input_tokens"] != prompt or sample["output_tokens"] != output):
                raise AssertionError(f"SP {group} query identity mismatch")
            samples[str(BASE_QUERY_UID + global_index)] = sample
        for route, count in result["route_counts"].items():
            route_counts[f"{group}/{route}"] = count
        result.pop("query_samples")
        rows[group] = result
    if len(samples) != len(trace):
        raise AssertionError("SP global sample set is incomplete")
    values = lambda field: [s[field] for s in samples.values() if s[field] is not None]
    p95 = lambda field: float(np.percentile(values(field), 95)) if values(field) else None
    window = duration - warmup
    completed = sum(s["completed"] for s in samples.values())
    pooled = {key: [value for group in GROUPS
                    for value in distributions[group][key]]
              for key in ("e2e", "paper_prompt", "paper_decode")}
    if len(pooled["e2e"]) != completed:
        raise AssertionError("SP pooled completion count differs from query samples")
    if (sum(row["first_tokens_in_window"] for row in rows.values()) != len(values("ttft_s")) or
            sum(row["queries_with_tpot_samples"] for row in rows.values()) != len(values("tpot_s"))):
        raise AssertionError("SP pooled latency counts differ from query samples")
    pooled_p95 = lambda key: float(np.percentile(pooled[key], 95)) if pooled[key] else None
    return {
        "scenario": scenario, "method": NAME, "solution": str(solution),
        "sim_cluster": str(sim_cluster), "offered_tokens_per_s": offered,
        "duration_s": duration, "warmup_s": warmup, "seed": seed,
        "arrivals": len(trace), "evaluation_protocol": "fixed_window_no_tail_drain",
        "python_version": sys.version.split()[0], "numpy_version": np.__version__,
        "trace_sha256": trace_sha256,
        "output_throughput_tokens_per_s": sum(
            row["output_throughput_tokens_per_s"] for row in rows.values()),
        "completed_request_throughput_per_s": completed / window,
        "ttft_p95_s": p95("ttft_s"), "tpot_p95_s": p95("tpot_s"),
        "e2e_p95_s": pooled_p95("e2e"),
        "completion_fraction": completed / len(trace) if trace else None,
        "backlog_at_window_start": sum(row["backlog_at_window_start"] for row in rows.values()),
        "backlog_at_window_end": len(trace) - completed,
        "first_tokens_in_window": len(values("ttft_s")),
        "queries_with_tpot_samples": len(values("tpot_s")),
        "paper_prompt_request_p95_s": pooled_p95("paper_prompt"),
        "paper_decode_request_p95_s": pooled_p95("paper_decode"),
        "paper_prompt_request_count": sum(row["paper_prompt_request_count"] for row in rows.values()),
        "paper_decode_request_count": sum(row["paper_decode_request_count"] for row in rows.values()),
        "route_counts": dict(sorted(route_counts.items())),
        "query_samples": dict(sorted(samples.items(), key=lambda item: int(item[0]))),
        "sp_allocation": {group: {"requests": len(partition[group]),
                                  "offered_tokens": assigned_tokens[group],
                                  "artifact_weight": weights[group],
                                  "component_trace_sha256": rows[group]["trace_sha256"],
                                  "component_solution_sha256": entry["solution"]["sha256"]}
                          for group, entry in manifest["groups"].items()},
        "sp_components": {group: {key: value for key, value in row.items()
                                  if key not in ("route_counts", "solution", "sim_cluster")}
                          for group, row in rows.items()},
        "sp_manifest_sha256": hashlib.sha256(solution.read_bytes()).hexdigest(),
    }
