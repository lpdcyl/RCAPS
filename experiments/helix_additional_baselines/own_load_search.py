"""Find each method's L90 on a frozen offered-load grid using development seeds."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from benchmarks.registry import METHODS


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
GRIDS = {
    "single": (100, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 900),
    "multi": (40, 60, 80, 100, 120, 140, 160, 200, 240, 280, 320, 360, 400),
}
METHOD_NAMES = ("helix", "swarm", "separate", "rcaps_v2")
SEEDS = (100, 101)
COMPLETION_FLOOR = 0.90


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def inspect_run(path: Path, scenario: str, method: str,
                offered: int, seed: int) -> dict:
    log = path.with_suffix(".log")
    if not path.is_file():
        tail = (log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:]
                if log.is_file() else [])
        return {"status": "failed", "log": str(log.relative_to(ROOT)),
                "log_sha256": sha(log) if log.is_file() else None,
                "last_log_line": tail[0] if tail else None}
    result = json.loads(path.read_text(encoding="utf-8"))
    solution, cluster = METHODS[method].layout(scenario, ROOT)
    expected = {
        "system": method, "scenario": scenario, "seed": seed,
        "offered_tokens_per_s": float(offered), "duration_s": 1800,
        "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
        "query_samples_schema": 1,
        "solution_sha256": sha(solution), "sim_cluster_sha256": sha(cluster),
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError(f"{path}: {key} differs from search protocol")
    if len(result.get("query_samples", {})) != result["arrivals"]:
        raise ValueError(f"{path}: incomplete query identities")
    return {"status": "complete", "result": str(path.relative_to(ROOT)),
            "result_sha256": sha(path),
            "completion_fraction": result["completion_fraction"],
            "backlog_at_window_end": result["backlog_at_window_end"],
            "arrivals": result["arrivals"],
            "output_throughput_tokens_per_s": result["output_throughput_tokens_per_s"],
            "ttft_p95_s": result["ttft_p95_s"],
            "tpot_p95_s": result["tpot_p95_s"]}


def probe(scenario: str, method: str, offered: int, base: Path) -> dict:
    run_dir = base / method / f"load{offered}"
    record_path = run_dir / "probe.json"
    if record_path.is_file():
        return json.loads(record_path.read_text(encoding="utf-8"))
    command = [sys.executable, "-m", "benchmarks.run",
               "--methods", method, "--scenarios", scenario,
               "--seeds", *(str(seed) for seed in SEEDS),
               "--offered-single", str(offered), "--offered-multi", str(offered),
               "--duration", "1800", "--warmup", "0", "--workers", "2",
               "--results-dir", str(run_dir / "results")]
    print(f"START {scenario}/{method} offered={offered}", flush=True)
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               check=False)
    wall = time.perf_counter() - started
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "runner.log").write_text(completed.stdout, encoding="utf-8")
    seeds = {str(seed): inspect_run(run_dir / "results" / scenario /
                                    f"seed{seed}" / f"{method}.json",
                                    scenario, method, offered, seed)
             for seed in SEEDS}
    passed = all(row["status"] == "complete" and
                 row["completion_fraction"] >= COMPLETION_FLOOR
                 for row in seeds.values())
    record = {"scenario": scenario, "method": method, "offered_tokens_per_s": offered,
              "seeds": seeds, "passed_l90": passed, "runner_exit_code": completed.returncode,
              "wall_s": wall, "command": command}
    save(record_path, record)
    print(f"END {scenario}/{method} offered={offered} pass={passed} "
          f"completions={[round(s.get('completion_fraction', -1), 4) for s in seeds.values()]} "
          f"wall={wall:.1f}s", flush=True)
    return record


def search(scenario: str) -> None:
    base = HERE / "own_load_development" / scenario
    output = base / "selection.json"
    state = {"protocol": "1800 s, zero warmup; seeds 100/101; both complete "
                         "and each completion >= 0.90; own load = 0.75 * L90_grid",
             "scenario": scenario, "grid": GRIDS[scenario], "methods": {}}
    if output.is_file():
        state = json.loads(output.read_text(encoding="utf-8"))
        if (state["scenario"] != scenario or tuple(state["grid"]) != GRIDS[scenario]):
            raise ValueError("Existing selection uses a different grid")
    for method in METHOD_NAMES:
        if state["methods"].get(method, {}).get("status") in (
                "selected", "grid_ceiling", "no_grid_load_passed"):
            print(f"SKIP {scenario}/{method}: selected", flush=True)
            continue
        grid = GRIDS[scenario]
        lower, upper = -1, len(grid)
        tested = {}
        while upper - lower > 1:
            index = (lower + upper) // 2
            record = probe(scenario, method, grid[index], base)
            tested[str(grid[index])] = {"passed_l90": record["passed_l90"],
                                        "wall_s": record["wall_s"],
                                        "completion_by_seed": {
                                            seed: row.get("completion_fraction")
                                            for seed, row in record["seeds"].items()}}
            if record["passed_l90"]:
                lower = index
            else:
                upper = index
            state["methods"][method] = {"status": "searching", "tested": tested,
                                        "passing_index": lower,
                                        "failing_index": upper}
            save(output, state)
        if lower < 0:
            selected = {"status": "no_grid_load_passed", "tested": tested}
        else:
            selected = {"status": ("grid_ceiling" if lower == len(grid) - 1
                                   else "selected"),
                        "tested": tested, "l90_grid_tokens_per_s": grid[lower],
                        "formal_offered_tokens_per_s": 0.75 * grid[lower],
                        "next_grid_tokens_per_s": (grid[lower + 1]
                                                   if lower + 1 < len(grid) else None)}
        state["methods"][method] = selected
        save(output, state)
        print(f"SELECT {scenario}/{method} {selected}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=GRIDS, required=True)
    search(parser.parse_args().scenario)
