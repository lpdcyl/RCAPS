"""Check official single-cluster deployment and both scheduler parity endpoints."""
import json
import math
from pathlib import Path

from benchmarks.fixed_window import run
from experiments.v5_core_supplement.adapters import HelixPlus, SetupProbe
from experiments.reviewer_v2.E2a_helix_tuning.adapters import factory
from .run import paths
from experiments.reviewer_v2.E2a_helix_tuning.run import sha

HERE = Path(__file__).resolve().parent
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "backlog_at_window_end")


def measure(load, seed, priority, batch, baseline=None):
    physical, solution, cluster = paths()
    if baseline == "helix":
        method, maker, probe = "helix", None, None
    elif baseline == "helix_plus":
        method, maker, probe = "queue_dag", HelixPlus, SetupProbe()
    else:
        method, maker, probe = "queue_dag", factory(priority, batch, 0.9, 0.6), SetupProbe()
    return run("single", method, load, 60, 0, seed, solution, cluster,
               physical_cluster=physical, scheduler_factory=maker,
               compact=True, phase_link_probe=probe)


def main():
    rows = []
    physical, solution, cluster = paths()
    for load in (350, 700):
        base00 = measure(load, 100, False, False, "helix")
        base11 = measure(load, 100, True, True, "helix_plus")
        for priority, batch in ((False, False), (False, True),
                                (True, False), (True, True)):
            row = measure(load, 100, priority, batch)
            base = base00 if not priority and not batch else (
                base11 if priority and batch else None)
            if base:
                assert row["trace_sha256"] == base["trace_sha256"]
                for metric in METRICS:
                    a, b = row[metric], base[metric]
                    if a is None or b is None:
                        assert a is b, (load, metric, a, b)
                    elif isinstance(a, float):
                        assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10), (
                            load, priority, batch, metric, a, b)
                    else:
                        assert a == b, (load, priority, batch, metric, a, b)
            rows.append(dict(load=load, seed=100, priority=priority, batch=batch,
                             trace_sha256=row["trace_sha256"],
                             parity_passed=base is not None,
                             **{metric: row[metric] for metric in METRICS}))
    audit = dict(passed=True, rows=rows, physical_sha256=sha(physical),
                 solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster))
    HERE.joinpath("SMOKE_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Corrected single-cluster smoke passed", flush=True)


if __name__ == "__main__":
    main()
