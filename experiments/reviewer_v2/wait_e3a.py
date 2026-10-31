"""Run the preregistered E3a analysis only after the V4 replay closes."""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
V4 = ROOT / "experiments/v4_paper_seed45"
DEST = HERE / "E3a_pareto"
STATUS = HERE / "status.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def status(value):
    value["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = STATUS.with_suffix(".json.part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATUS)


def main():
    status({"state": "waiting_for_v4_replay"})
    while True:
        if (V4 / "retry_env/FINAL_AUDIT.json").exists():
            original = read(V4 / "index.json")
            retry = read(V4 / "retry_env/index.json")
            audit = read(V4 / "retry_env/FINAL_AUDIT.json")
            if original["status"] == retry["status"] == "terminal" and audit["passed"]:
                break
        time.sleep(30)
    status({"state": "building_e3a"})
    with (DEST / "build.log").open("x", encoding="utf-8") as log:
        code = subprocess.call([sys.executable, str(DEST / "build.py"), "--build"],
                               cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    status({"state": "completed" if code == 0 else "failed", "exit_code": code,
            "audit": str(DEST / "FINAL_AUDIT.json") if code == 0 else None})


if __name__ == "__main__":
    main()
