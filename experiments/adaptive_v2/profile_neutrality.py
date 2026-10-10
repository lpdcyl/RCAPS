"""Check that passive resource profiling leaves short-run execution unchanged."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("trace_sha256", "output_throughput_tokens_per_s", "ttft_p95_s",
          "tpot_p95_s", "completion_fraction", "backlog_at_window_end",
          "route_counts")


def main() -> None:
    report = {}
    for scenario in ("single", "multi"):
        for method in ("rcaps_v2", "rcaps_v2_fixed_structure"):
            path = Path(scenario) / "seed0" / f"{method}.json"
            before = json.loads((ROOT / "benchmarks/v2_smoke" / path).read_text())
            after = json.loads((ROOT / "benchmarks/v2_smoke_profiled" / path).read_text())
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
