"""Conditional fixed-size Prompt transfer chunk control (MoLink-related)."""

from __future__ import annotations

import argparse
import contextlib
import traceback
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel

from .chunking import PromptTransferChunkHook
from .run import (HERE, MID, ROOT, SEEDS, collect, digest, layout, paired,
                  read, result_path, source_hashes, trace_for, trigger_condition, write)


def path_for(phase, variant, load, seed, chunk_bytes):
    label = "huge_chunk" if chunk_bytes >= 10**14 else "chunk_1MiB"
    return (HERE / "runs" / "chunk" / phase / variant / label /
            f"load{load}_seed{seed}.json")


def run_chunk(phase, variant, load, seed, duration, chunk_bytes):
    physical, solution, cluster, scenario = layout("C1_multi", variant)
    output = path_for(phase, variant, load, seed, chunk_bytes)
    identity = {"phase": phase, "variant": variant, "load": load,
                "seed": seed, "duration_s": duration, "chunk_bytes": chunk_bytes,
                "solution_sha256": digest(solution),
                "sim_cluster_sha256": digest(cluster),
                "physical_sha256": digest(physical),
                "base_source_sha256": source_hashes(),
                "chunking_sha256": digest(HERE / "chunking.py"),
                "runner_sha256": digest(HERE / "chunk_run.py")}
    if output.exists():
        old = read(output)
        if all(old.get(key) == value for key, value in identity.items()):
            return old
        raise ValueError(f"Existing chunk result changed identity: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    hook = PromptTransferChunkHook(chunk_bytes)
    print(f"START chunk/{phase}/{variant}/load{load}/seed{seed}", flush=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", load, duration, 0, seed,
                solution, cluster, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=GraphModeledQueueAwareDagScheduler,
                trace_override=trace_for(load, duration, seed),
                phase_link_probe=hook)
            row.update(identity)
            write(output, row)
            return row
        except Exception as exc:
            write(output.with_suffix(".failure.json"),
                  {**identity, "error": repr(exc), "traceback": traceback.format_exc()})
            raise


def smoke():
    plain = read(result_path("smoke", "C1_multi", "k1", "baseline_plain", MID, 1))
    huge = run_chunk("smoke", "k1", MID, 1, 60, 10**15)
    fields = ("trace_sha256", "route_counts", "arrivals",
              "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
              "completion_fraction", "backlog_at_window_end")
    mismatch = {field: [plain[field], huge[field]] for field in fields
                if plain[field] != huge[field]}
    small = run_chunk("smoke", "k1", MID, 1, 60, 1_048_576)
    write(HERE / "chunk_smoke.json", {"parity_passed": not mismatch,
         "mismatch": mismatch, "small_chunk_completed": True,
         "small_chunk_stats": small["phase_link_profile"]})
    if mismatch:
        raise AssertionError(f"Large-chunk no-op changed baseline: {mismatch}")
    print("Chunk smoke passed.")


def run_formal(duration):
    if not read(HERE / "chunk_smoke.json")["parity_passed"]:
        raise RuntimeError("Chunk smoke parity gate failed")
    analysis, results = collect()
    passed, evidence = trigger_condition(analysis, results)
    if not passed:
        print(f"Chunk control skipped by preregistered gate: {evidence}")
        return
    phase = "formal" if duration == 600 else "confirm"
    rows = []
    for variant in ("k1", "k3"):
        for seed in SEEDS:
            chunk = run_chunk(phase, variant, MID, seed, duration, 1_048_576)
            baseline_phase = "formal" if duration == 600 else "confirm"
            base_path = result_path(baseline_phase, "C1_multi", variant,
                                    "baseline", MID, seed)
            if not base_path.exists():
                raise FileNotFoundError(base_path)
            base = read(base_path)
            if chunk["trace_sha256"] != base["trace_sha256"]:
                raise AssertionError("Chunk and baseline traces differ")
            rows.append({"variant": variant, "seed": seed, "duration_s": duration,
                         "baseline_tpot_p95_s": base["tpot_p95_s"],
                         "chunk_tpot_p95_s": chunk["tpot_p95_s"],
                         "baseline_ttft_p95_s": base["ttft_p95_s"],
                         "chunk_ttft_p95_s": chunk["ttft_p95_s"],
                         "baseline_throughput_tok_s": base["output_throughput_tokens_per_s"],
                         "chunk_throughput_tok_s": chunk["output_throughput_tokens_per_s"],
                         "baseline_backlog": base["backlog_at_window_end"],
                         "chunk_backlog": chunk["backlog_at_window_end"],
                         "common_completed": paired(base, chunk),
                         "chunk_stats": chunk["phase_link_profile"]})
    write(HERE / f"chunk_{phase}_analysis.json", {"rows": rows,
        "interpretation": "Fixed 1 MiB transfer chunks are a MoLink-related causal control, "
                          "not a novel method claim."})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal", "confirm"), required=True)
    args = parser.parse_args()
    if args.phase == "smoke":
        smoke()
    elif args.phase == "formal":
        run_formal(600)
    else:
        run_formal(1800)


if __name__ == "__main__":
    main()
