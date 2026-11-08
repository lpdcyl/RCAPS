"""Single-worker, resumable formal controller; existing artifacts are immutable."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    protocol_path = HERE / "manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    index_path = HERE / "index.json"
    jobs = {}
    for key in protocol["jobs"]:
        result = HERE / "runs" / key / "result.json"
        failure = HERE / "runs" / key / "failure.json"
        if result.exists() and failure.exists():
            raise RuntimeError(f"Conflicting terminal artifacts for {key}")
        if result.exists():
            record = json.loads(result.read_text(encoding="utf-8"))
            if record["status"] != "success" or record["protocol_sha256"] != sha(protocol_path):
                raise RuntimeError(f"Invalid existing result: {key}")
            jobs[key] = {"status": "success", "artifact_sha256": sha(result)}
        elif failure.exists():
            jobs[key] = {"status": "failure", "artifact_sha256": sha(failure)}
        else:
            jobs[key] = {"status": "pending"}
    atomic_json(index_path, {"status": "running", "controller_pid": __import__("os").getpid(),
                             "protocol_sha256": sha(protocol_path), "jobs": jobs})
    for key, record in jobs.items():
        if record["status"] != "pending":
            continue
        started = time.time()
        log_path = HERE / "runs" / key / "worker.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.run([sys.executable, "-m",
                                   "experiments.hexgen_sim.formal_v2.run_key", key],
                                  cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        result = HERE / "runs" / key / "result.json"
        failure = HERE / "runs" / key / "failure.json"
        terminal = result if result.exists() else failure if failure.exists() else None
        jobs[key] = {"status": "success" if result.exists() and proc.returncode == 0
                     else "failure" if failure.exists() else "interrupted",
                     "exit_code": proc.returncode,
                     "duration_wall_s": round(time.time() - started, 3),
                     "log_sha256": sha(log_path),
                     "artifact_sha256": sha(terminal) if terminal else None}
        atomic_json(index_path, {"status": "running", "controller_pid": __import__("os").getpid(),
                                 "protocol_sha256": sha(protocol_path), "jobs": jobs})
        print(f"{key} {jobs[key]['status']} exit={proc.returncode} "
              f"wall={jobs[key]['duration_wall_s']}", flush=True)
        if jobs[key]["status"] == "interrupted":
            break
    status = "terminal" if all(job["status"] in ("success", "failure")
                               for job in jobs.values()) else "interrupted"
    atomic_json(index_path, {"status": status,
                             "finished_utc": datetime.now(timezone.utc).isoformat(),
                             "protocol_sha256": sha(protocol_path), "jobs": jobs})


if __name__ == "__main__":
    main()
