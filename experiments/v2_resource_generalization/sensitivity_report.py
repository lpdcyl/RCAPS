"""Audit the uniform 600-second development load sweep."""

from __future__ import annotations

import json
from pathlib import Path

from .prepare import HERE, ROOT
from .run_sensitivity import JOBS


FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completion_fraction", "backlog_at_window_end")


def summarize() -> dict:
    output = {"protocol": "600 s, zero warmup, development seed 100; same trace within case/load",
              "cases": {}}
    for case, (loads, methods) in JOBS.items():
        output["cases"][case] = {}
        physical_hashes = set()
        layouts_by_method: dict[str, set[str]] = {method: set() for method in methods}
        for offered in loads:
            records = {}
            for method in methods:
                path = (HERE / "runs" / case / "600s" / f"load{offered:g}" /
                        "seed100" / f"{method}.json")
                item = json.loads(path.read_text(encoding="utf-8"))
                if (item["seed"] != 100 or item["duration_s"] != 600 or
                        item["warmup_s"] != 0 or
                        item["offered_tokens_per_s"] != offered):
                    raise ValueError(f"Protocol mismatch: {path}")
                records[method] = {"path": str(path.relative_to(ROOT)),
                                   "trace_sha256": item["trace_sha256"],
                                   "physical_sha256": item["physical_sha256"],
                                   "solution_sha256": item["solution_sha256"],
                                   "metrics": {key: item[key] for key in FIELDS}}
                physical_hashes.add(item["physical_sha256"])
                layouts_by_method[method].add(item["solution_sha256"])
            if len({row["trace_sha256"] for row in records.values()}) != 1:
                raise ValueError(f"Trace mismatch: {case} load {offered:g}")
            output["cases"][case][f"{offered:g}"] = records
        if len(physical_hashes) != 1 or any(len(hashes) != 1 for hashes in layouts_by_method.values()):
            raise ValueError(f"Physical topology or layout changed within load sweep: {case}")
    return output


if __name__ == "__main__":
    output = summarize()
    path = HERE / "sensitivity_summary.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(path)
