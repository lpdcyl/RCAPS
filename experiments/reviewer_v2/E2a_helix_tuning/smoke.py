"""Reproducible 60-second parity smoke before E2a registration."""
import json
import math
from pathlib import Path

from benchmarks.fixed_window import run
from benchmarks.layout import scenario
from experiments.v5_core_supplement.adapters import HelixPlus, SetupProbe
from experiments.reviewer_v2.E2a_helix_tuning.adapters import factory

HERE = Path(__file__).resolve().parent
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "backlog_at_window_end")


def measure(case, load, seed, priority, batch, baseline=False):
    physical, profile, solution, cluster = scenario(case)
    if baseline == "helix":
        method, maker, probe = "helix", None, None
    elif baseline == "helix_plus":
        method, maker, probe = "queue_dag", HelixPlus, SetupProbe()
    else:
        method, maker, probe = "queue_dag", factory(priority, batch, 0.9, 0.6), SetupProbe()
    return run(case, method, load, 60, 0, seed, solution, cluster,
               physical_cluster=physical, scheduler_factory=maker,
               compact=True, phase_link_probe=probe)


def main():
    rows = []
    for case, load in (("single", 350), ("multi", 160)):
        baseline_00 = measure(case, load, 100, False, False, "helix")
        baseline_11 = measure(case, load, 100, True, True, "helix_plus")
        for priority, batch in ((False, False), (False, True),
                                (True, False), (True, True)):
            row = measure(case, load, 100, priority, batch)
            base = baseline_00 if not priority and not batch else (
                baseline_11 if priority and batch else None)
            if base is not None:
                for metric in METRICS:
                    a, b = row[metric], base[metric]
                    if a is None or b is None:
                        assert a is b, (case, metric, a, b)
                    elif isinstance(a, float):
                        assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10), (
                            case, priority, batch, metric, a, b)
                    else:
                        assert a == b, (case, priority, batch, metric, a, b)
                assert row["trace_sha256"] == base["trace_sha256"]
            rows.append({"scenario": case, "load": load, "priority": priority,
                         "batch": batch, "trace_sha256": row["trace_sha256"],
                         "parity_passed": base is not None,
                         **{metric: row[metric] for metric in METRICS}})
    out = {"passed": True, "duration_s": 60, "seed": 100, "rows": rows}
    HERE.joinpath("SMOKE_AUDIT.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("E2a switch smoke passed: 8 variants, 4 baseline parity checks", flush=True)


if __name__ == "__main__":
    main()
