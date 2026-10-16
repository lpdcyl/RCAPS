"""Run independent formal windows in parallel, then build the paired index."""

from __future__ import annotations

import argparse
import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

from .placement import HERE
from .prepare import VARIANTS
from .run import FORMAL_CASES, _run_one, _smoke_gate


def tasks(audit: dict) -> list[tuple[str, str, int]]:
    output = []
    for case in FORMAL_CASES:
        seen = set()
        for variant in VARIANTS:
            row = audit[case]["variants"][variant]
            if row["status"] != "feasible":
                continue
            deployment = (row["solution_sha256"], row["sim_cluster_sha256"])
            if deployment in seen:
                continue
            seen.add(deployment)
            output.extend((case, variant, seed) for seed in (0, 1, 2))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("workers must be positive")
    audit = json.loads((HERE / "offline_audit.json").read_text(encoding="utf-8"))
    _smoke_gate(audit)
    planned = tasks(audit)
    status_path = HERE / "parallel_formal_status.json"
    status = {"planned": [list(task) for task in planned], "completed": {},
              "failed": {}, "workers": args.workers}
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        pending = {executor.submit(_run_one, "formal", *task): task
                   for task in planned}
        for future in as_completed(pending):
            task = pending[future]
            key = "/".join(map(str, task))
            try:
                path = future.result()
                status["completed"][key] = str(path)
                print("passed", key, flush=True)
            except Exception:
                status["failed"][key] = traceback.format_exc()
                print("failed", key, flush=True)
            status["elapsed_s"] = time.perf_counter() - started
            temporary = status_path.with_suffix(".json.part")
            temporary.write_text(json.dumps(status, indent=2) + "\n",
                                 encoding="utf-8")
            temporary.replace(status_path)
    print(f"{len(status['completed'])}/{len(planned)} windows complete", flush=True)
    if status["failed"]:
        raise RuntimeError("Some formal windows failed; see parallel_formal_status.json")


if __name__ == "__main__":
    main()
