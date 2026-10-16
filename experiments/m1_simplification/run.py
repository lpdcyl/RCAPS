"""Reuse audited formal windows; rerun only windows that cannot be reused."""

from __future__ import annotations

import argparse
import json
import traceback
from contextlib import redirect_stderr, redirect_stdout

from benchmarks.fixed_window import run as fixed_window_run
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler

from .evidence import (HERE, LOADS, SEEDS, SYSTEMS, choose, digest, layout,
                       paired, sources)


def run_local(scenario: str, seed: int, system: str) -> None:
    solution, cluster = layout(scenario, system)
    output, _ = sources(scenario, seed, system)[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    log = output.with_suffix(".log")
    with log.open("w", encoding="utf-8") as stream, redirect_stdout(stream), redirect_stderr(stream):
        print(f"Fallback formal run: {scenario}/seed{seed}/{system}", flush=True)
        try:
            row = fixed_window_run(
                scenario, "queue_dag", LOADS[scenario], 1800, 0, seed,
                solution, cluster, profile_resources=True,
                scheduler_factory=QueueAwareDagScheduler,
                compact=True, record_query_samples=True)
            expected = {"scenario": scenario, "method": "queue_dag", "seed": seed,
                        "offered_tokens_per_s": LOADS[scenario], "duration_s": 1800,
                        "warmup_s": 0,
                        "evaluation_protocol": "fixed_window_no_tail_drain"}
            for key, value in expected.items():
                if row.get(key) != value:
                    raise ValueError(f"Simulator returned different {key}")
            row.update({"system": system, "query_samples_schema": 1,
                        "solution_sha256": digest(solution),
                        "sim_cluster_sha256": digest(cluster)})
            temporary = output.with_suffix(".json.part")
            temporary.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
            temporary.replace(output)
            print(f"Complete: {output}", flush=True)
        except Exception:
            traceback.print_exc(file=stream)
            raise


def ensure_pair(scenario: str, seed: int, *, dry_run: bool) -> dict:
    chosen = {system: choose(scenario, seed, system) for system in SYSTEMS}
    missing = [system for system in SYSTEMS if chosen[system][0] is None]
    if dry_run:
        return {"scenario": scenario, "seed": seed,
                "sources": {system: chosen[system][1]["source_kind"]
                            for system in SYSTEMS},
                "action": "rerun " + ", ".join(missing) if missing else "reuse"}
    for system in missing:
        run_local(scenario, seed, system)
        chosen[system] = choose(scenario, seed, system)
    try:
        paired(chosen["m1_static_candidate"][0], chosen["v2_reference"][0])
    except ValueError:
        # A record may be individually valid yet originate from a different
        # runtime/trace. Recreate both sides as one controlled pair.
        for system in SYSTEMS:
            run_local(scenario, seed, system)
            chosen[system] = choose(scenario, seed, system)
        paired(chosen["m1_static_candidate"][0], chosen["v2_reference"][0])
    return {"scenario": scenario, "seed": seed,
            "sources": {system: chosen[system][1]["source_kind"]
                        for system in SYSTEMS}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", nargs="+", choices=LOADS,
                        default=list(LOADS))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if any(seed not in SEEDS for seed in args.seeds):
        parser.error("Only frozen formal seeds 0, 1, 2 are in scope")
    for scenario in args.scenarios:
        for seed in args.seeds:
            print(json.dumps(ensure_pair(scenario, seed, dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
