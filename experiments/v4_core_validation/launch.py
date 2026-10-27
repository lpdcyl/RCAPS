"""Launch the registered queue with the exact frozen interpreter spelling."""
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    frozen = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    env = os.environ.copy()
    env.update(frozen["environment"]["env"])
    tag = time.strftime("%Y%m%d_%H%M%S")
    logpath, errpath = HERE / f"queue_{tag}.log", HERE / f"queue_{tag}.err"
    with logpath.open("x", encoding="utf-8") as stdout, errpath.open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen([frozen["environment"]["executable"], "-u",
            "-X", "faulthandler", "-m", "experiments.v4_core_validation.run_compatible", "--phase", "queue"],
            cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW)
    record = dict(pid=process.pid, tag=tag, log=str(logpath), err=str(errpath),
                  interpreter=frozen["environment"]["executable"])
    with (HERE / f"launcher_{tag}.json").open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
