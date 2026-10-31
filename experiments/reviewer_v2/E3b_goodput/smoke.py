"""Short protocol smoke for all five E3b methods on both topologies."""
from __future__ import annotations

import json
from pathlib import Path

from .evaluate import METHODS, evaluate

HERE = Path(__file__).resolve().parent


def main():
    rows = []
    for case, load in (("single", 350), ("multi", 160)):
        trace = None
        cohort = None
        for method in METHODS:
            row = evaluate(case, load, method, 100,
                           warmup=12, measurement=60, tail_cap=120)
            good = row["goodput"]
            samples = row["drain"]["query_samples"]
            identity = sorted((x["arrival_s"], x["input_tokens"], x["output_tokens"])
                              for x in samples)
            if trace is None:
                trace, cohort = row["trace_sha256"], identity
            if row["trace_sha256"] != trace or identity != cohort:
                raise RuntimeError("Unmatched E3b smoke trace: " + case + " " + method)
            if (good["measurement_arrivals"] != len(samples) or
                    good["completed_by_tail"] + good["right_censored"] != len(samples) or
                    good["gpu_busy_seconds_measurement_and_tail"] <= 0 or
                    good["deployed_gpu_count"] <= 0):
                raise RuntimeError("Bad E3b smoke accounting: " + case + " " + method)
            tiers = [good["tiers"][x] for x in ("strict", "medium", "loose")]
            if ([x["qualified_requests"] for x in tiers] !=
                    sorted(x["qualified_requests"] for x in tiers) or
                    [x["qualified_output_tokens"] for x in tiers] !=
                    sorted(x["qualified_output_tokens"] for x in tiers)):
                raise RuntimeError("Bad SLO tier monotonicity")
            rows.append(dict(case=case, load=load, method=method,
                trace_sha256=trace, solution_sha256=row["solution_sha256"],
                sim_cluster_sha256=row["sim_cluster_sha256"],
                measurement_arrivals=len(samples),
                right_censored=good["right_censored"],
                gpu_busy_seconds=good["gpu_busy_seconds_measurement_and_tail"],
                goodput={name: good["tiers"][name]["goodput_tokens_per_s"]
                         for name in ("strict", "medium", "loose")}))
    output = dict(passed=True, warmup_s=12, measurement_s=60,
                  tail_cap_s=120, rows=rows)
    HERE.joinpath("SMOKE_AUDIT.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print("E3b goodput smoke passed:", len(rows), "windows", flush=True)


if __name__ == "__main__":
    main()
