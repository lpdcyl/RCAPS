"""Run seeds 0/1/2 at each method's frozen 75%-of-L90 offered load."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
METHODS = ("helix", "swarm", "separate", "rcaps_v2")


def main(scenario: str) -> None:
    selection_file = HERE / "own_load_development" / scenario / "selection.json"
    selection = json.loads(selection_file.read_text(encoding="utf-8"))
    if set(selection["methods"]) != set(METHODS):
        raise ValueError(f"{scenario}: incomplete development selection")
    for method in METHODS:
        choice = selection["methods"][method]
        if choice["status"] not in ("selected", "grid_ceiling"):
            raise ValueError(f"{scenario}/{method}: no valid L90 selection")
        offered = choice["formal_offered_tokens_per_s"]
        output = HERE / "own_load_formal" / scenario / method
        output.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-m", "benchmarks.run",
                   "--methods", method, "--scenarios", scenario,
                   "--seeds", "0", "1", "2", "--offered-single", str(offered),
                   "--offered-multi", str(offered), "--duration", "1800",
                   "--warmup", "0", "--workers", "2", "--results-dir",
                   str(output / "results")]
        print(f"START FORMAL {scenario}/{method} offered={offered}", flush=True)
        started = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                check=False)
        (output / "runner.log").write_text(result.stdout, encoding="utf-8")
        status = {"scenario": scenario, "method": method,
                  "l90_grid_tokens_per_s": choice["l90_grid_tokens_per_s"],
                  "offered_tokens_per_s": offered, "command": command,
                  "exit_code": result.returncode,
                  "wall_s": time.perf_counter() - started}
        (output / "formal_status.json").write_text(
            json.dumps(status, indent=2) + "\n", encoding="utf-8")
        print(f"END FORMAL {scenario}/{method} code={result.returncode} "
              f"wall={status['wall_s']:.1f}s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    main(parser.parse_args().scenario)
