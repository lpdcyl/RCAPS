"""One-shot campaign collector; stops after completion or a preserved failure."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from .build_report import campaign_complete, campaign_halted

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    previous = None
    while True:
        states = {}
        for name in ("v4_formal", "v4_external", "v4_recovery"):
            p = ROOT / "experiments" / name / "index.json"
            if not p.exists() and name == "v4_recovery":
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            states[name] = {"queue_status": data["queue_status"],
                            "completed": sum(x["status"] == "completed" for x in data["jobs"].values()),
                            "failed": [k for k,v in data["jobs"].items() if v["status"] == "failed"]}
        marker = json.dumps(states, sort_keys=True)
        complete = campaign_complete(states)
        failed = campaign_halted(states)
        if marker != previous:
            command = [sys.executable, "-m", "experiments.v4_paper.build_report"]
            if complete:
                command += ["--require-complete", "--plots"]
            result = subprocess.run(command, cwd=ROOT, check=False)
            if result.returncode:
                raise SystemExit("Report verification failed; see collector log")
            previous = marker
        if complete or failed:
            print("CAMPAIGN_COMPLETED" if complete else "CAMPAIGN_FAILURE_RETAINED", flush=True)
            return
        time.sleep(15)


if __name__ == "__main__": main()
