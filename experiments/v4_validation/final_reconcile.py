"""One final reconciliation of retained attempts; never run/retry simulations."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

import numpy as np

from experiments.v4_paper.build_report import collect
from experiments.v4_validation.summarize import METRICS, check

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def identity(row):
    return [(round(q["arrival_s"], 9), q["input_tokens"], q["output_tokens"])
            for q in sorted(row["query_samples"].values(), key=lambda q: q["arrival_s"])]


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-8)


def main():
    destination = HERE / "final_reconciliation.json"
    if destination.exists():
        raise RuntimeError("Final reconciliation already exists; inspect it rather than repeat automatically.")
    checks, problems, raw, attempts, intervals = [], [], {}, [], []

    def verify(ok, name, detail=None):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        if not ok:
            problems.append({"check": name, "detail": detail})

    # Existing reader verifies every historical result/index before exposing rows.
    old, provenance, old_states = collect()
    manifests = [ROOT / "experiments" / x / "manifest.json" for x in
                 ["v4_formal", "v4_external", "v4_recovery", "v4_recovery2"]]
    manifests += [HERE / f"{x}_manifest.json" for x in ["external", "diagnostic", "neighbor"]]
    source_records = []
    for path in manifests:
        manifest = read(path)
        for category in ["sources_sha256", "anchor_controls_sha256", "original_failure_files_sha256"]:
            for name, expected in manifest.get(category, {}).items():
                source = ROOT / name
                actual = digest(source) if source.exists() else None
                verify(actual == expected, "frozen_input_hash", name)
                source_records.append({"manifest": path.relative_to(ROOT).as_posix(),
                                       "source": name, "sha256": actual, "expected": expected})
    protocol = read(HERE / "external_continuation_protocol.json")
    verify(digest(HERE / "external_continue.py") == protocol["source_sha256"], "continuation_source_hash")
    verify(digest(HERE / "external_index.json") == protocol["original_index_sha256"], "original_failure_index_retained")
    campaigns = [
        ("external", "external_runs", ["external_index.json", "external_continue_index.json"]),
        ("diagnostic", "diagnostic_runs", ["diagnostic_index.json"]),
        ("neighbor", "neighbor_runs", ["neighbor_index.json"]),
    ]
    coverage, missing, failed_without_hash = {}, [], []
    for campaign, folder, indexes in campaigns:
        manifest_path = HERE / f"{campaign}_manifest.json"
        manifest = read(manifest_path)
        jobs = {j["key"]: j for j in manifest["jobs"]}
        seen = set()
        counts = Counter()
        for index_name in indexes:
            index_path = HERE / index_name
            index = read(index_path)
            if "manifest_sha256" in index:
                verify(index["manifest_sha256"] == digest(manifest_path), "index_manifest_hash", index_name)
            for key, entry in index["jobs"].items():
                verify(key in jobs and key not in seen, "registered_unique_attempt", f"{campaign}/{key}")
                seen.add(key)
                counts[entry["status"]] += 1
                record = {"campaign": campaign, "key": key, "status": entry["status"], "index": index_name}
                start, end = entry.get("started_at"), entry.get("finished_at")
                if start and end:
                    intervals.extend([(datetime.fromisoformat(start), 1), (datetime.fromisoformat(end), -1)])
                else:
                    verify(False, "terminal_attempt_timestamps", record)
                result_path = HERE / folder / key / "result.json"
                failure_path = result_path.with_name("failure.json")
                if entry["status"] == "completed":
                    verify(result_path.exists() and not failure_path.exists(), "success_artifact_exclusive", key)
                    row = read(result_path)
                    sha = digest(result_path)
                    verify(sha == entry.get("result_sha256"), "result_hash", key)
                    verify(row["job"] == jobs[key], "job_identity", key)
                    verify(row["manifest_sha256"] == digest(manifest_path), "result_manifest_hash", key)
                    verify(row["environment"] == manifest["environment"], "environment_identity", key)
                    verify(not check(row), "metric_resource_invariants", {"key": key, "errors": check(row)})
                    trace = identity(row)
                    reconstructed = hashlib.sha256(json.dumps(trace, separators=(",", ":")).encode()).hexdigest()
                    verify(reconstructed == row["trace_sha256"], "trace_reconstructed_from_requests", key)
                    completed = sum(q["completed"] for q in row["query_samples"].values())
                    verify(row["arrivals"] - completed == row["backlog_at_window_end"], "completion_backlog_accounting", key)
                    verify(close(completed / row["arrivals"], row["completion_fraction"]), "completion_fraction", key)
                    for source, metric in [("ttft_s", "ttft_p95_s"), ("tpot_s", "tpot_p95_s")]:
                        values = [q[source] for q in row["query_samples"].values() if q.get(source) is not None]
                        verify(bool(values) and close(float(np.percentile(values, 95)), row[metric]), "request_percentile", {"key": key, "metric": metric})
                    verify(close(sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"],
                                 row["gpu_seconds_per_output_token"]), "gpu_work_accounting", key)
                    if campaign == "neighbor":
                        verify(row["comparison_identity"] == manifest["identity"], "neighbor_mechanism_identity", key)
                    record.update(source=result_path.relative_to(ROOT).as_posix(), sha256=sha,
                                  right_censored_queries=row["arrivals"] - completed,
                                  query_count=row["arrivals"], duration_s=row["duration_s"])
                    raw[campaign, key] = row
                elif entry["status"] == "failed":
                    verify(failure_path.exists() and not result_path.exists(), "failure_artifact_exclusive", key)
                    failure = read(failure_path)
                    sha = digest(failure_path)
                    expected = entry.get("failure_sha256")
                    if expected:
                        verify(sha == expected, "failure_hash", key)
                    else:
                        failed_without_hash.append(f"{campaign}/{key}")
                    record.update(source=failure_path.relative_to(ROOT).as_posix(), sha256=sha,
                                  error=failure.get("error", failure.get("exit_code")),
                                  prior_index_hash_available=bool(expected))
                else:
                    verify(False, "attempt_terminal", record)
                attempts.append(record)
        absent = sorted(set(jobs) - seen)
        missing.extend({"campaign": campaign, "key": k} for k in absent)
        verify(not absent, "registered_coverage", campaign)
        coverage[campaign] = {"registered": len(jobs), **dict(counts), "missing": len(absent)}
    concurrency = peak = 0
    for _, change in sorted(intervals):
        concurrency += change
        peak = max(peak, concurrency)
    verify(peak <= 2 and concurrency == 0, "maximum_two_simulation_workers", peak)

    report = read(HERE / "validation_results.json")
    verify(len(raw) == report["successful_validated_windows"], "report_success_count")
    verify(sum(a["status"] == "failed" for a in attempts) == len(report["failures"]), "report_failure_count")
    windows = {}
    for w in report["windows"]:
        row = read(ROOT / w["source"])
        verify(digest(ROOT / w["source"]) == w["sha256"], "report_window_hash", w["source"])
        windows[w["condition"], w["scenario"], w["load"], w["cell"], w["seed"]] = row
    paired_sources = []
    for pair in report["paired"]:
        condition, scenario, load, comparator = (pair[k] for k in ["condition", "scenario", "load", "comparator"])
        for entry in pair["seeds"]:
            seed = entry["seed"]
            other = windows[condition, scenario, load, comparator, seed]
            full = (old[scenario, load, "v4", seed] if condition in ["external", "neighbor"]
                    else windows[condition, scenario, load, "v4", seed])
            verify(identity(full) == identity(other), "paired_request_identity", [condition, scenario, load, comparator, seed])
            verify(full["duration_s"] == other["duration_s"], "paired_observation_horizon", [condition, scenario, load, comparator, seed])
            for metric, expected in entry["relative_full_over_comparator"].items():
                value = full[metric] / other[metric] - 1 if other[metric] else None
                verify(value is None if expected is None else close(value, expected), "paired_delta", [condition, scenario, load, comparator, seed, metric])
            if condition == "neighbor":
                for field in ["solution", "sim_cluster", "physical_cluster_sha256"]:
                    verify(full[field] == other[field], "neighbor_common_placement", [scenario, load, seed, field])
                verify(full["admission"]["allowed_edges"] == other["admission"]["allowed_edges"], "neighbor_common_admitted_edges", [scenario, load, seed])
            source = full.get("_source")
            paired_sources.append({"condition": condition, "scenario": scenario, "load": load,
                                   "comparator": comparator, "seed": seed, "trace_sha256": full["trace_sha256"],
                                   "historical_full_source": source,
                                   "historical_full_sha256": digest(ROOT / source) if source else None})
        if pair["complete"]:
            verify(sorted(s["seed"] for s in pair["seeds"]) == [0, 1, 2], "complete_pair_seeds")
            for metric, expected in pair["paired_mean_relative"].items():
                verify(close(mean(s["relative_full_over_comparator"][metric] for s in pair["seeds"]), expected), "paired_mean", [condition, scenario, load, comparator, metric])

    primary, primary_pairs = [], []
    for scenario, loads in [("single", [350, 700]), ("multi", [160, 320])]:
        for load in loads:
            for cell in ["v4", "helix", "swarm", "separate"]:
                rows = [old.get((scenario, load, cell, s)) for s in [0, 1, 2]]
                if any(r is None for r in rows):
                    continue
                primary.append({"scenario": scenario, "load": load, "cell": cell,
                                "metrics": {m: mean(r[m] for r in rows) for m in METRICS},
                                "sources": [{"seed": s, "source": r["_source"], "sha256": digest(ROOT / r["_source"])} for s, r in enumerate(rows)]})
                if cell != "v4":
                    full = [old[scenario, load, "v4", s] for s in [0, 1, 2]]
                    for a, b in zip(full, rows):
                        verify(identity(a) == identity(b), "primary_external_request_identity", [scenario, load, cell])
                    primary_pairs.append({"scenario": scenario, "load": load, "comparator": cell,
                                          "paired_mean_relative": {m: mean(a[m] / b[m] - 1 for a, b in zip(full, rows)) for m in METRICS if all(r[m] for r in rows)}})
    static = read(HERE / "static_audit.json")
    for case in static["cases"]:
        verify(case["status"] == "passed", "M1_structural_case", [case["scenario"], case["cell"]])
        for name, expected in case["input_hashes"].items():
            verify(digest(ROOT / name) == expected, "M1_input_hash", name)
    cohorts = [r for (c, k), r in raw.items() if c == "diagnostic" and r["job"]["condition"] == "cohort_tail"]
    for row in cohorts:
        cohort = row["cohort"]
        verify(cohort["completed"] and cohort["right_censored_queries"] == 0 and cohort["target_output_tokens"] == cohort["produced_output_tokens"], "cohort_token_conservation", row["job"]["key"])
    value = {"generated_at": datetime.now(timezone.utc).isoformat(), "status": "passed" if not problems else "issues_found",
             "scope": "Executor source/data reconciliation, not independent external peer review or hardware validation.",
             "coverage": coverage, "successful_windows": len(raw), "failed_windows": sum(a["status"] == "failed" for a in attempts),
             "missing_windows": missing, "right_censored_success_windows": sum(a.get("right_censored_queries", 0) > 0 for a in attempts),
             "complete_cohort_windows": len(cohorts), "peak_simulation_workers": peak,
             "checks_passed": sum(c["passed"] for c in checks), "checks_failed": len(problems),
             "problems": problems, "checks": checks, "source_records": source_records, "attempts": attempts,
             "paired_sources": paired_sources, "primary_external_groups": primary, "primary_external_pairs": primary_pairs,
             "failed_artifacts_without_prior_index_hash": failed_without_hash,
             "uncompleted_hardware_calibration": True,
             "pre_final_report_sha256": digest(HERE / "validation_results.json")}
    save(destination, value)
    print(json.dumps({k: value[k] for k in ["status", "coverage", "successful_windows", "failed_windows", "missing_windows", "right_censored_success_windows", "complete_cohort_windows", "peak_simulation_workers", "checks_passed", "checks_failed", "problems", "primary_external_pairs"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
