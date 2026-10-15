"""Compare evaluator ranking with online outcomes across three load levels."""

from __future__ import annotations

import json
import argparse
import time
from pathlib import Path
from statistics import mean

from experiments.v2_core_ablations.modeling import static_metrics, score_static
from experiments.v2_core_ablations.report import spearman_agreement
from experiments.v2_method_comparisons.placement import static_measure
from rcaps.placement import adaptive
from rcaps.placement.partition import scenario
from rcaps.placement.topology import TopologyModel

from .run_one import HERE, SOURCE, candidates


def online(candidate: str, offered: float, seed: int) -> tuple[Path, dict]:
    if offered == 700.0:
        path = SOURCE / "diagnostic_runs/single" / candidate / f"seed{seed}.json"
    else:
        path = HERE / "runs" / f"load{offered:g}" / candidate / f"seed{seed}.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def ranked(seeds: tuple[int, ...] = (100,)) -> dict:
    model = TopologyModel(scenario("single")[0])
    manifest = json.loads((SOURCE / "modeling_candidates/single.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in manifest["entries"]}
    ids = candidates()
    reference_state = adaptive.reference_state(model, "single")
    ref_compute = static_metrics(model, reference_state, communication=False)
    ref_static = static_measure(model, reference_state)
    output = {"scenario": "single", "duration_s": 600, "seeds": seeds,
              "candidate_ids": ids, "loads": {}}
    for offered in (350.0, 525.0, 700.0):
        raw = {cid: {seed: online(cid, offered, seed) for seed in seeds}
               for cid in ids}
        trace_hashes = {}
        arrival_counts = {}
        for seed in seeds:
            hashes = {raw[cid][seed][1]["trace_sha256"] for cid in ids}
            arrivals = {raw[cid][seed][1]["arrivals"] for cid in ids}
            if len(hashes) != 1 or len(arrivals) != 1:
                raise ValueError(f"Paired trace mismatch at load {offered}, seed {seed}")
            trace_hashes[seed] = next(iter(hashes))
            arrival_counts[seed] = next(iter(arrivals))
        for cid, by_seed in raw.items():
            for seed, (path, record) in by_seed.items():
                if (record["seed"] != seed or record["duration_s"] != 600 or
                        record["warmup_s"] != 0 or
                        record["offered_tokens_per_s"] != offered):
                    raise ValueError(f"Protocol mismatch: {path}")
        gap = 600.0 / mean(arrival_counts.values())
        event_arrivals = tuple(i * gap for i in range(6))
        ref_event = adaptive.measure(model, reference_state,
                                     arrivals_s=event_arrivals)
        rows = []
        timings = {kind: [] for kind in ("compute_only", "static_resource", "event_dag")}
        for cid in ids:
            state = by_id[cid]["state"].copy()
            state["lengths"] = {int(k): v for k, v in state["lengths"].items()}
            scores = {}
            t0 = time.perf_counter()
            scores["compute_only"] = score_static(
                static_metrics(model, state, communication=False), ref_compute)
            timings["compute_only"].append(1000 * (time.perf_counter() - t0))
            t0 = time.perf_counter()
            scores["static_resource"] = adaptive.objective(
                static_measure(model, state), ref_static)
            timings["static_resource"].append(1000 * (time.perf_counter() - t0))
            t0 = time.perf_counter()
            scores["event_dag"] = adaptive.objective(
                adaptive.measure(model, state, arrivals_s=event_arrivals), ref_event)
            timings["event_dag"].append(1000 * (time.perf_counter() - t0))
            online_by_seed = {seed: {key: record[key] for key in
                                    ("output_throughput_tokens_per_s", "ttft_p95_s",
                                     "tpot_p95_s", "completion_fraction",
                                     "backlog_at_window_end")}
                              for seed, (_, record) in raw[cid].items()}
            keys = next(iter(online_by_seed.values()))
            rows.append({"candidate_id": cid, "scores": scores,
                         "online": {key: mean(values[key] for values in
                                              online_by_seed.values()) for key in keys},
                         "online_by_seed": online_by_seed,
                         "paths": {seed: str(path) for seed, (path, _) in
                                   raw[cid].items()}})
        agreement = {}
        selected = {}
        for evaluator in timings:
            scores = [row["scores"][evaluator] for row in rows]
            agreement[evaluator] = {
                key: spearman_agreement(scores, [row["online"][key]
                                                 for row in rows], direction)
                for key, direction in (("output_throughput_tokens_per_s", "higher"),
                                       ("ttft_p95_s", "lower"),
                                       ("tpot_p95_s", "lower"))}
            winner = min(rows, key=lambda row: (row["scores"][evaluator],
                                                row["candidate_id"]))
            selected[evaluator] = {"candidate_id": winner["candidate_id"],
                                   "online": winner["online"]}
        output["loads"][f"{offered:g}"] = {
            "arrivals_by_seed": arrival_counts, "trace_sha256_by_seed": trace_hashes,
            "surrogate_arrival_gap_s": gap,
            "scoring_mean_ms": {key: mean(values) for key, values in timings.items()},
            "spearman_agreement": agreement, "selected": selected,
            "rows": rows}
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[100])
    seeds = tuple(parser.parse_args().seeds)
    output = ranked(seeds)
    target = HERE / ("summary.json" if len(seeds) == 1 else "summary_two_seeds.json")
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(target)
