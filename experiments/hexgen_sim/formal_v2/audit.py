"""Audit formal HexGen keys and pair them with existing V4/Helix evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REFERENCE = ROOT / "experiments/v5_seed_completion/individual.csv"
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
CELLS = ("V4", "HH", "HHplus")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values: list[float]) -> dict:
    if len(values) != 5:
        raise ValueError("Five paired seeds required")
    s = stdev(values)
    margin = 2.7764451051977987 * s / math.sqrt(5)
    return {"mean": mean(values), "sample_sd": s,
            "ci95_lower": mean(values) - margin,
            "ci95_upper": mean(values) + margin}


def audit() -> dict:
    protocol_path = HERE / "manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source, digest in protocol["sources_sha256"].items():
        if sha(ROOT / source) != digest:
            raise RuntimeError("Frozen source changed: " + source)
    comparison = {}
    with REFERENCE.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["cell"] not in CELLS:
                continue
            key = (row["scenario"], int(row["load"]), int(row["seed"]), row["cell"])
            comparison[key] = row
    jobs = {}
    grouped = defaultdict(list)
    for key, item in protocol["jobs"].items():
        path = HERE / "runs" / key / "result.json"
        failure = HERE / "runs" / key / "failure.json"
        if not path.exists():
            jobs[key] = {"status": "failure" if failure.exists() else "pending",
                         "artifact_sha256": sha(failure) if failure.exists() else None}
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        result = record["result"]
        if record["status"] != "success" or record["protocol_sha256"] != sha(protocol_path):
            raise RuntimeError("Bad result provenance: " + key)
        if (result["trace_sha256"] != item["trace_sha256"]
                or result["arrivals"] != item["requests"]
                or len(result["query_samples"]) != item["requests"]):
            raise RuntimeError("Trace or query count mismatch: " + key)
        if result["evaluation_protocol"] != "fixed_window_no_tail_drain":
            raise RuntimeError("Protocol mismatch: " + key)
        if result["method"] != "hexgen_capacity_safe_v2":
            raise RuntimeError("Admission version mismatch: " + key)
        for admission in result["admission"]:
            if (not 0 <= admission["max_reserved_tokens"] <= admission["kv_budget_tokens"]
                    or admission["kv_budget_tokens"] <= 0):
                raise RuntimeError("KV reservation exceeds capacity: " + key)
        for metric in METRICS:
            value = result[metric]
            if value is None or not math.isfinite(float(value)):
                raise RuntimeError(f"Invalid {metric}: {key}")
        jobs[key] = {"status": "success", "artifact_sha256": sha(path),
                     "trace_sha256": result["trace_sha256"],
                     "admission": result["admission"],
                     "metrics": {metric: result[metric] for metric in METRICS}}
        grouped[(item["scenario"], item["offered"])].append((item["seed"], result))
    groups = {}
    for (case, load), rows in sorted(grouped.items()):
        group_key = f"{case}_load{load}"
        if len(rows) != 5 or {seed for seed, _ in rows} != set(range(5)):
            groups[group_key] = {"status": "incomplete", "success": len(rows), "required": 5}
            continue
        rows.sort()
        summary = {"status": "complete", "seeds": [seed for seed, _ in rows],
                   "hexgen": {metric: stats([result[metric] for _, result in rows])
                              for metric in METRICS}, "paired": {}}
        for cell in CELLS:
            paired = {}
            for metric in METRICS:
                values = []
                for seed, result in rows:
                    reference = comparison.get((case, load, seed, cell))
                    if reference is None or reference["trace_sha256"] != result["trace_sha256"]:
                        break
                    source = ROOT / reference["source"]
                    if not source.is_file() or sha(source) != reference["result_sha256"]:
                        break
                    if not reference[metric]:
                        break
                    values.append(result[metric] - float(reference[metric]))
                if len(values) == 5:
                    paired[metric] = stats(values)
            if paired:
                summary["paired"][cell] = paired
        groups[group_key] = summary
    complete = sum(row["status"] == "complete" for row in groups.values())
    return {"status": "terminal" if all(row["status"] in ("success", "failure")
                                            for row in jobs.values()) else "running",
            "protocol_sha256": sha(protocol_path),
            "reference_csv_sha256": sha(REFERENCE),
            "jobs": jobs, "groups": groups,
            "success_count": sum(row["status"] == "success" for row in jobs.values()),
            "failure_count": sum(row["status"] == "failure" for row in jobs.values()),
            "pending_count": sum(row["status"] == "pending" for row in jobs.values()),
            "complete_five_seed_groups": complete}


if __name__ == "__main__":
    outcome = audit()
    destination = HERE / "FINAL_AUDIT.json"
    destination.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: outcome[key] for key in
                      ("status", "success_count", "failure_count", "pending_count",
                       "complete_five_seed_groups")}, indent=2))
