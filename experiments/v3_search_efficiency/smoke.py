"""Check that valid budgeted Helix exports initialize and route online requests."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from benchmarks.fixed_window import run

from .worker import sha256, write_json


HERE = Path(__file__).resolve().parent
CASES = {
    "C1_single": ("single", 700.0, "helix_ilp_budgeted"),
    "C1_multi": ("multi", 320.0, "helix_ilp_budget300"),
}


def main() -> None:
    rows = {}
    for case, (scenario, offered, label) in CASES.items():
        source = HERE / "runs" / case / label / "rep0"
        solution, cluster = source / "ilp_sol.ini", source / "simulator_cluster.ini"
        row = {"case": case, "scenario": scenario, "label": label,
               "offered_tokens_per_s": offered, "duration_s": 60,
               "warmup_s": 0, "seed": 100,
               "solution_sha256": sha256(solution),
               "sim_cluster_sha256": sha256(cluster)}
        try:
            result = run(scenario, "helix", offered, 60, 0, 100, solution,
                         cluster, compact=True, record_query_samples=True)
            row["status"] = "passed"
            row["result"] = result
        except Exception as error:
            row["status"] = "failed"
            row["error"] = repr(error)
            row["traceback"] = traceback.format_exc()
        rows[case] = row
        write_json(HERE / "smoke" / f"{case}.json", row)
        print(case, row["status"], flush=True)
    write_json(HERE / "smoke_index.json", rows)


if __name__ == "__main__":
    main()
