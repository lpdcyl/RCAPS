"""Verify the complete three-seed benchmark and write a provenance report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .compare import common_cohort
from .registry import MAIN_METHOD, METHODS
from .run import DEFAULT_RESULTS, ROOT, digest, output_file


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")
SCENARIOS = {"single": 700.0, "multi": 320.0}
SEEDS = (0, 1, 2)


def verify(results_dir: Path) -> dict:
    records = {}
    checks = []
    for scenario, offered in SCENARIOS.items():
        names = [MAIN_METHOD, "helix"]
        for seed in SEEDS:
            group = {}
            for name in names:
                path = output_file(results_dir, scenario, seed, name)
                record = json.loads(path.read_text(encoding="utf-8"))
                solution, cluster = METHODS[name].layout(scenario, ROOT)
                expected = {
                    "system": name, "scenario": scenario, "seed": seed,
                    "offered_tokens_per_s": offered, "duration_s": 1800,
                    "warmup_s": 0, "query_samples_schema": 1,
                    "solution_sha256": digest(solution),
                    "sim_cluster_sha256": digest(cluster),
                }
                for field, value in expected.items():
                    if record.get(field) != value:
                        raise ValueError(f"{path}: mismatched {field}")
                if len(record["query_samples"]) != record["arrivals"]:
                    raise ValueError(f"{path}: incomplete request samples")
                if not 0 <= record["completion_fraction"] <= 1:
                    raise ValueError(f"{path}: invalid completion fraction")
                if any(not math.isfinite(record[metric]) or record[metric] <= 0
                       for metric in METRICS):
                    raise ValueError(f"{path}: invalid metric")
                group[name] = record
                records[path.relative_to(ROOT).as_posix()] = {
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "trace_sha256": record["trace_sha256"],
                    "arrivals": record["arrivals"],
                }
            main = group[MAIN_METHOD]
            for name, record in group.items():
                if (record["trace_sha256"] != main["trace_sha256"] or
                        record["arrivals"] != main["arrivals"]):
                    raise ValueError(f"{scenario} seed {seed}: {name} trace mismatch")
                common_cohort(main, record)
            checks.append({"scenario": scenario, "seed": seed,
                           "trace_sha256": main["trace_sha256"],
                           "arrivals": main["arrivals"],
                           "methods_verified": names})
    return {"status": "passed", "record_count": len(records),
            "expected_record_count": 2 * len(SCENARIOS) * len(SEEDS),
            "checks": checks, "record_sha256": records,
            "arrival_comparison_abs_tolerance_s": 1e-9,
            "metrics": list(METRICS)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "paper" / "V3_THREE_SEED_AUDIT.json")
    args = parser.parse_args()
    report = verify(args.results_dir.resolve())
    if report["record_count"] != report["expected_record_count"]:
        raise ValueError("Unexpected number of benchmark records")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {report['record_count']} records -> {args.output}")


if __name__ == "__main__":
    main()
