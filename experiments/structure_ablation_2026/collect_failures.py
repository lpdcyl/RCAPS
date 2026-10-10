"""Preserve failed full-window ablation runs as machine-readable evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> None:
    failures = {}
    for path in sorted((HERE / "logs").glob("*.log")):
        content = path.read_text(encoding="utf-8", errors="replace")
        if "Traceback (most recent call last)" not in content:
            continue
        progress = re.findall(r"progress: (single|multi)/queue_dag, arrivals=(\d+), sim_time=([\d.]+)",
                              content)
        exception = next((line.strip() for line in reversed(content.splitlines())
                          if line.startswith(("AssertionError:", "RuntimeError:",
                                              "ValueError:"))), None)
        failures[path.stem] = {
            "log_file": path.relative_to(HERE).as_posix(),
            "last_logged_progress": ({"scenario": progress[-1][0],
                                      "arrivals": int(progress[-1][1]),
                                      "sim_time_s": float(progress[-1][2])}
                                     if progress else None),
            "exception": exception,
            "complete_1800_s_result": False,
        }
    output = HERE / "failures.json"
    output.write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    print(f"{output}: {len(failures)} failed runs")


if __name__ == "__main__":
    main()
