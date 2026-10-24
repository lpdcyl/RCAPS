"""Check raw formal results independently of the summary/winner calculation.

Pending cells are reported explicitly. No metrics are imputed or overwritten.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import itertools
import json
import math
from datetime import datetime, timezone

from experiments.v3_path_crossover.run import (
    CELLS, FORMAL_SEEDS, HERE, LOADS, NETWORKS, PROTOCOL, check_frozen,
    digest, load_context, read, write,
)


def percentile95(values):
    if not values:
        return None
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    low = int(position)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)


def trace_from_samples(samples):
    ordered = sorted(samples.items(), key=lambda item: (item[1]["arrival_s"], int(item[0])))
    return [(round(sample["arrival_s"], 9), sample["input_tokens"], sample["output_tokens"])
            for _uid, sample in ordered]


def trace_hash(trace):
    return hashlib.sha256(json.dumps(trace, separators=(",", ":")).encode()).hexdigest()


def validate_result(row, frozen, load, network, cell, seed):
    issues = []

    def require(condition, message):
        if not condition:
            issues.append(message)

    def same(actual, expected, message):
        if actual is None or expected is None:
            require(actual is expected, message)
        else:
            require(isinstance(actual, (int, float)) and math.isfinite(actual)
                    and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), message)

    expected = {
        "experiment": PROTOCOL["experiment"], "phase": "formal_isolated",
        "topology": "C1_multi", "scenario": "multi", "method": "queue_dag",
        "load_label": load, "network_profile": network, "path_space": cell,
        "seed": seed, "duration_s": 1800, "warmup_s": 0,
        "offered_tokens_per_s": LOADS[load], "crosslink_capacity_factor": NETWORKS[network],
        "evaluation_protocol": "fixed_window_no_tail_drain", "pythonhashseed": "0",
        "python_version": frozen["python"], "numpy_version": frozen["numpy"],
    }
    for key in ("protocol_sha256", "physical_sha256", "solution_sha256",
                "sim_cluster_sha256", "placement_sha256", "sources_sha256"):
        expected[key] = frozen[key]
    expected["physical_cluster_sha256"] = frozen["physical_sha256"]
    for key, value in expected.items():
        require(row.get(key) == value, f"identity mismatch: {key}")

    samples = row.get("query_samples", {})
    require(len(samples) == row.get("arrivals"), "request sample count differs from arrivals")
    for uid, sample in samples.items():
        require(0 <= sample["arrival_s"] < 1800, f"arrival outside window: {uid}")
        require(isinstance(sample["completed"], bool), f"invalid completion flag: {uid}")
        require(sample["input_tokens"] > 0 and 0 < sample["output_tokens"] <= 1000,
                f"token lengths exceed the registered KV reservation contract: {uid}")
        for metric in ("ttft_s", "tpot_s"):
            value = sample[metric]
            require(value is None or (math.isfinite(value) and value >= 0),
                    f"invalid {metric}: {uid}")
        if sample["completed"]:
            require(sample["ttft_s"] is not None, f"completed request lacks TTFT: {uid}")
            if sample["output_tokens"] >= 2:
                require(sample["tpot_s"] is not None, f"completed request lacks TPOT: {uid}")
    require(trace_hash(trace_from_samples(samples)) == row.get("trace_sha256"),
            "trace hash cannot be reconstructed from raw request samples")
    ttfts = [s["ttft_s"] for s in samples.values() if s["ttft_s"] is not None]
    tpots = [s["tpot_s"] for s in samples.values() if s["tpot_s"] is not None]
    require(len(ttfts) == row.get("first_tokens_in_window"), "TTFT sample count mismatch")
    require(len(tpots) == row.get("queries_with_tpot_samples"), "TPOT sample count mismatch")
    same(row.get("ttft_p95_s"), percentile95(ttfts), "P95 TTFT differs from request samples")
    same(row.get("tpot_p95_s"), percentile95(tpots), "P95 TPOT differs from request samples")
    complete = sum(s["completed"] for s in samples.values())
    completed_samples = [s for s in samples.values() if s["completed"]]
    e2es = [s["ttft_s"] + (s["output_tokens"] - 1) * (s["tpot_s"] or 0)
            for s in completed_samples]
    same(row.get("e2e_p95_s"), percentile95(e2es), "P95 E2E differs from completed request samples")
    require(row.get("backlog_at_window_start") == 0, "nonzero initial backlog")
    require(row.get("backlog_at_window_end") == len(samples) - complete, "backlog conservation fails")
    same(row.get("completion_fraction"), complete / len(samples) if samples else None,
         "completion fraction differs from request samples")
    same(row.get("completed_request_throughput_per_s"), complete / 1800,
         "request throughput differs from completed requests")
    # This simulator finishes one token per decode request.
    same(row.get("output_throughput_tokens_per_s"), row["paper_decode_request_count"] / 1800,
         "output throughput differs from completed decode token events")
    require(sum(s["output_tokens"] for s in completed_samples) <= row["paper_decode_request_count"]
            <= sum(s["output_tokens"] for s in samples.values()),
            "completed decode token count violates request token bounds")
    require(complete <= row["kv_admission"]["admitted"] <= len(samples),
            "KV admission count violates request count bounds")
    require(len(row["path_records"]) == row["kv_admission"]["admitted"],
            "admitted prompt route record count mismatch")

    capacities, peaks = row["kv_capacity"], row["kv_peak_reserved"]
    require(bool(capacities), "missing KV capacities")
    for uid, peak in peaks.items():
        require(uid in capacities and 0 <= peak <= capacities.get(uid, -1),
                f"KV reservation exceeds capacity: {uid}")
    same(row["kv_peak_fraction"], max((v / capacities[k] for k, v in peaks.items()), default=0),
         "KV peak fraction differs from per-GPU reservations")
    links = {link["link_uid"]: link for link in row["scaled_links"]}
    require(len(links) == len(row["scaled_links"]) == len(frozen["scaled_links"]),
            "network intervention link count mismatch")
    for nominal in frozen["scaled_links"]:
        link = links.get(nominal["link_uid"])
        require(link is not None, f"missing network link: {nominal['link_uid']}")
        if link is not None:
            for key, target in (("nominal_Bps", nominal["nominal_Bps"]),
                                ("effective_Bps", nominal["nominal_Bps"] * NETWORKS[network]),
                                ("latency_s", nominal["latency_s"])):
                same(link[key], target, f"network intervention mismatch: {nominal['link_uid']}/{key}")
    batches = row["decode_batches"]
    same(batches["mean_batch"], batches["decode_tokens"] / batches["executions"],
         "decode batch mean mismatch")
    require(0 <= batches["single_share"] <= 1, "decode single-batch share outside [0,1]")
    return issues


def validate_matrix():
    frozen = check_frozen()
    context = load_context()
    # Re-generate the public workload from each registered seed, in this
    # validator process only. This also catches consistently mislabeled seeds.
    from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
    expected_traces = {}
    for load, seed in itertools.product(LOADS, FORMAL_SEEDS):
        with contextlib.redirect_stdout(io.StringIO()):
            feeder = OnlineRequestFeeder(cluster_token_throughput=LOADS[load],
                                         start_time=0, duration=1800, seed=seed)
        trace = [(round(t, 9), prompt, output) for t, prompt, output in feeder.trace]
        expected_traces[f"{load}/seed{seed}"] = {
            "trace_sha256": trace_hash(trace), "arrivals": len(trace)}
    rows, missing, invalid, files = {}, [], {}, {}
    expected = list(itertools.product(LOADS, NETWORKS, CELLS, FORMAL_SEEDS))
    for load, network, cell, seed in expected:
        key = f"{load}/{network}/{cell}/seed{seed}"
        path = HERE / "runs/formal_isolated" / load / network / f"{cell}_seed{seed}.json"
        if not path.exists():
            missing.append(key)
            continue
        try:
            row = read(path)
            issues = validate_result(row, frozen, load, network, cell, seed)
            expected_trace = expected_traces[f"{load}/seed{seed}"]
            if any(row.get(k) != value for k, value in expected_trace.items()):
                issues.append("request trace differs from regenerated registered seed workload")
            allowed = (context["canonical_edges"] if cell == "canonical" else
                       context["partial_edges"] if cell == "partial" else
                       frozenset((a if isinstance(a, str) else a + 2,
                                  b if isinstance(b, str) else b + 2)
                                 for a, b in context["full_dag"].edge_set))
            for route in row["route_counts"]:
                vertices = ["source"] + [int(uid) for uid in route.split("-")] + ["sink"]
                if any(edge not in allowed for edge in zip(vertices, vertices[1:])):
                    issues.append(f"observed route leaves registered path space: {route}")
            if issues:
                invalid[key] = issues
            rows[(load, network, cell, seed)] = row
            files[path.relative_to(HERE).as_posix()] = digest(path)
        except (ValueError, KeyError, TypeError, ZeroDivisionError) as error:
            invalid[key] = [repr(error)]
    pairing = {}
    for load, seed in itertools.product(LOADS, FORMAL_SEEDS):
        group = [row for (l, _n, _c, s), row in rows.items() if l == load and s == seed]
        hashes = {row["trace_sha256"] for row in group}
        sample_inputs = [{uid: (s["arrival_s"], s["input_tokens"], s["output_tokens"])
                          for uid, s in row["query_samples"].items()} for row in group]
        matched = len(hashes) <= 1 and all(s == sample_inputs[0] for s in sample_inputs)
        pairing[f"{load}/seed{seed}"] = {"available": len(group), "expected": 6,
                                      "complete": len(group) == 6,
                                      "matched": matched if len(group) >= 2 else None}
        if not matched:
            invalid[f"{load}/seed{seed}/pairing"] = ["request traces differ across paired conditions"]
    failure_files = sorted(p.relative_to(HERE).as_posix()
                           for p in (HERE / "runs/formal_isolated").rglob("*.failure.json"))
    extra_files = sorted(str(p.relative_to(HERE)) for p in (HERE / "runs/formal_isolated").rglob("*.json")
                         if p.relative_to(HERE).as_posix() not in files and not p.name.endswith(".failure.json"))
    return {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "expected_cells": len(expected), "available_cells": len(rows),
            "complete": not missing and not invalid and not failure_files and not extra_files,
            "valid_available_results": not invalid, "missing": missing, "invalid": invalid,
            "failure_files": failure_files, "unrecognized_result_files": extra_files,
            "pairing": pairing, "expected_traces": expected_traces,
            "inputs_sha256": files, "protocol_sha256": frozen["protocol_sha256"],
            "classification": "simulation_only", "cross_model_integrity_review": "unavailable"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="Check available results while the official matrix is running.")
    args = parser.parse_args()
    result = validate_matrix()
    write(HERE / "validation.json", result)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("inputs_sha256", "missing")}, indent=2, ensure_ascii=False))
    if result["invalid"] or result["failure_files"] or result["unrecognized_result_files"]:
        raise SystemExit(1)
    if not result["complete"] and not args.allow_incomplete:
        raise SystemExit("Formal matrix incomplete; no complete crossover claim is permitted.")


if __name__ == "__main__":
    main()
