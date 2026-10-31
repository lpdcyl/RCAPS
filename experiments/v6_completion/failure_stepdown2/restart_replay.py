"""Replay workers interrupted by the 2026-10-29 computer restart."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from experiments.v5_core_supplement.run import now, read, sha, write
from experiments.v6_completion.failure_stepdown import evaluate

HERE = Path(__file__).resolve().parent / "restart_replay"
KEYS = ("30b_multi_rate525/HHplus/seed3", "30b_multi_rate525/V4/seed3")


def main() -> None:
    manifest = read(Path(__file__).resolve().parent / "formal/manifest.json")
    jobs = {job["key"]: job for job in manifest["jobs"]}
    for key in KEYS:
        job = jobs[key]
        folder = HERE / "runs" / key
        folder.mkdir(parents=True, exist_ok=True)
        try:
            row = evaluate(job)
            row.update(status="completed", job=job,
                       manifest_sha256=sha(Path(__file__).resolve().parent / "formal/manifest.json"),
                       replayed_at=now())
            write(folder / "result.json", row)
            print("END", key, "completed", flush=True)
        except BaseException as error:
            write(folder / "failure.json", dict(status="failed", job=job,
                  error=repr(error), traceback=traceback.format_exc(),
                  manifest_sha256=sha(Path(__file__).resolve().parent / "formal/manifest.json"),
                  replayed_at=now()))
            print("END", key, "failed", repr(error), flush=True)


if __name__ == "__main__":
    main()
