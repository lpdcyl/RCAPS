"""Rerun short paired traces to check profiling leaves execution unchanged."""

from __future__ import annotations

from pathlib import Path
import json

from benchmarks.fixed_window import run
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler
from rcaps.v2_method import layout


ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("trace_sha256", "output_throughput_tokens_per_s", "ttft_p95_s",
          "tpot_p95_s", "completion_fraction", "backlog_at_window_end",
          "route_counts")


def main() -> None:
    report = {}
    for scenario in ("single", "multi"):
        for method in ("rcaps_v2", "rcaps_v2_fixed_structure"):
            solution, cluster = layout(method, scenario, ROOT)
            offered = 700.0 if scenario == "single" else 320.0
            common = dict(name=scenario, method="queue_dag", offered=offered,
                          duration=60, warmup=0, seed=0, solution=solution,
                          sim_cluster=cluster,
                          scheduler_factory=QueueAwareDagScheduler,
                          compact=True, record_query_samples=True)
            before = run(**common, profile_resources=False)
            after = run(**common, profile_resources=True)
            matches = {field: before[field] == after[field] for field in FIELDS}
            if not all(matches.values()) or not after.get("gpu_queue_request_s"):
                raise ValueError(f"Profiling changed the short run: {scenario} {method}")
            report[f"{scenario}_{method}"] = {
                "duration_s": before["duration_s"], "seed": before["seed"],
                "field_matches": matches,
                "profile_has_gpu_queue": True,
            }
    target = Path(__file__).resolve().parent / "profile_neutrality.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
