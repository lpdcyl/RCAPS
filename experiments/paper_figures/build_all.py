"""Rebuild every vector PDF and 300-dpi PNG preview from repository data."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = [HERE / "ccf_integrated_framework.py",
           *sorted(HERE.glob("fig[0-9][0-9]_*.py"))]


def main():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    for script in SCRIPTS:
        subprocess.run([sys.executable, str(script)], cwd=ROOT,
                       env=env, check=True)
    print(f"Built {len(SCRIPTS)} figures")


if __name__ == "__main__":
    main()
