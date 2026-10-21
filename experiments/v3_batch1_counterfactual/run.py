"""Counterfactual: switch off the simulator's one-request decode doubling.

``ModelLayer.get_inference_statistics`` (simulator/event_simulator/model.py
lines 131-132) charges a decode batch holding exactly one request twice its
profiled time. The efficiency claim for slow-link-gated admission rests on
decode batch fragmentation wasting GPU time; part of that waste could be an
artefact of this rule. Here the rule is switched off inside the run process
(the simulator source is not edited), and full-DAG V3 is compared with the
gated rule on C1 single (700) and C2 (160), frozen layouts, seeds 0/1/2.

The route price is the frozen V3 one in both cells, including its own x2
single-token decode coefficient (rcaps/v3/online_scheduler.py:68-69): only
the simulated physics changes.

Phases: test | smoke | formal | report.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from experiments.v3_cycle_pricing.run import (
    FORMAL_SEEDS, ROOT, digest, physical_input, rel, scheduler_factory, write)

HERE = Path(__file__).resolve().parent
GATED = ROOT / "experiments/v3_gated_pathspace/scheduler.py"
CONDITIONS = {"C1_single": 700.0, "C2": 160.0}
CELLS = ("v3", "gated")


def disable_single_decode_doubling() -> None:
    """Remove exactly the extra copy of decode time added for one decode token."""
    from simulator.event_simulator.model import ModelLayer
    from simulator.event_simulator.request import RequestPhase

    if getattr(ModelLayer.get_inference_statistics, "_batch1_counterfactual", False):
        return
    original = ModelLayer.get_inference_statistics

    def get_inference_statistics(self, requests):
        time, vram = original(self, requests)
        if sum(r.phase == RequestPhase.Increment for r in requests) == 1:
            time -= self.get_decode_inference_time(decode_phase_tokens=1)
        return time, vram

    get_inference_statistics._batch1_counterfactual = True
    ModelLayer.get_inference_statistics = get_inference_statistics


def runtime(case: str) -> dict:
    physical, scenario = physical_input(case)
    c1 = case.startswith("C1_")
    layout = ROOT / "rcaps/v3_layouts" / case.removeprefix("C1_")
    return {"physical": physical, "topology": scenario if c1 else "single",
            "profile": None if c1 else ROOT / "examples/simulation/config/machine_profile.ini",
            "solution": layout / "solution.ini", "sim_cluster": layout / "simulator_cluster.ini"}


def builder(case: str, cell: str):
    from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler
    from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
    if cell == "v3":
        return RecordedV3Scheduler
    canonical = scheduler_factory(case, "canonical").keywords["allowed_edges"]
    return partial(SlowLinkGatedScheduler, allowed_edges=canonical)


def run_one(case: str, cell: str, seed: int, duration: int, output: Path) -> str:
    if output.exists():
        return rel(output)
    disable_single_decode_doubling()
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase

    info = runtime(case)
    base = builder(case, cell)
    stats = defaultdict(lambda: [0, 0, 0])

    def factory(simulator):
        for node in simulator.compute_nodes.values():
            original = node.start_execution

            def start_execution(requests, _original=original, _uid=node.node_uid):
                decodes = sum(r.phase == RequestPhase.Increment for r in requests)
                if decodes:
                    record = stats[_uid]
                    record[0] += 1
                    record[1] += decodes
                    record[2] += decodes == 1
                return _original(requests)

            node.start_execution = start_execution
        return base(simulator)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            row = fixed_window.run(
                info["topology"], "queue_dag", CONDITIONS[case], duration, 0, seed,
                info["solution"], info["sim_cluster"], profile_resources=True, compact=True,
                record_query_samples=True, physical_cluster=info["physical"],
                machine_profile=info["profile"],
                machine_counts=TopologyModel(info["physical"]).machine_counts,
                scheduler_factory=factory)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "cell": cell, "seed": seed, "error": repr(error),
                   "traceback": traceback.format_exc()})
            raise
    executions = sum(s[0] for s in stats.values())
    busy = row["gpu_busy_fraction"]
    row.update({"case": case, "cell": cell, "seed": seed, "duration_s": duration,
                "counterfactual": "single_decode_doubling_off",
                "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                "runner_sha256": digest(HERE / "run.py"),
                "gated_scheduler_sha256": digest(GATED),
                "solution_sha256": digest(info["solution"]),
                "sim_cluster_sha256": digest(info["sim_cluster"]),
                "physical_sha256": digest(info["physical"]),
                "gpu_seconds_per_output_token": sum(busy.values()) /
                row["output_throughput_tokens_per_s"],
                "decode_batches": {
                    "executions": executions,
                    "mean_batch": sum(s[1] for s in stats.values()) / max(1, executions),
                    "single_share": sum(s[2] for s in stats.values()) / max(1, executions)}})
    write(output, row)
    return rel(output)


def test() -> None:
    """The wrapper removes the doubling for one decode and nothing else."""
    from simulator.event_simulator.model import ModelLayer
    from simulator.event_simulator.request import RequestPhase

    class Request:
        def __init__(self, phase, length):
            self.phase, self.token_seq_length = phase, length

    class Profile:
        prompt_bs2time = {0: 0.0, 1: 0.01, 512: 0.2}
        prompt_bs2vram = {0: 0.0, 1: 1.0, 512: 2.0}
        decode_bs2time = {0: 0.0, 1: 0.003, 8: 0.004, 64: 0.01}
        decode_bs2vram = {0: 0.0, 1: 1.0, 8: 1.0, 64: 1.0}

    layer = ModelLayer.__new__(ModelLayer)  # profile tables only; no simulator state
    for name in ("prompt_bs2time", "prompt_bs2vram", "decode_bs2time", "decode_bs2vram"):
        setattr(layer, name, getattr(Profile, name))
    one = [Request(RequestPhase.Increment, 1)]
    four = [Request(RequestPhase.Increment, 1) for _ in range(4)]
    mixed = [Request(RequestPhase.Increment, 1), Request(RequestPhase.Initialization, 100)]
    before = [ModelLayer.get_inference_statistics(layer, b) for b in (one, four, mixed)]
    disable_single_decode_doubling()
    after = [ModelLayer.get_inference_statistics(layer, b) for b in (one, four, mixed)]
    assert abs(before[0][0] - 2 * 0.003) < 1e-12 and abs(after[0][0] - 0.003) < 1e-12, (before, after)
    assert after[1] == before[1], "Batches with several decodes must be unchanged"
    assert abs(before[2][0] - after[2][0] - 0.003) < 1e-12, "A single decode beside prompts loses its extra copy"
    assert after[0][1] == before[0][1], "VRAM must be unchanged"
    print("counterfactual wrapper test passed:", before, after)


def jobs(phase: str) -> list:
    if phase == "smoke":
        return [(c, cell, 100, 60, HERE / "runs/smoke" / c / f"{cell}.json")
                for c in CONDITIONS for cell in CELLS]
    return [(c, cell, seed, 1800, HERE / "runs/formal" / c / f"{cell}_seed{seed}.json")
            for seed in FORMAL_SEEDS for c in CONDITIONS for cell in CELLS]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("test", "smoke", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "test":
        test()
        return
    if args.phase == "report":
        from experiments.v3_batch1_counterfactual.report import main as report
        report()
        return
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    if args.phase == "formal" and not (HERE / "protocol.json").exists():
        raise SystemExit("protocol.json must be committed before formal runs")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs(args.phase)}
        for future in as_completed(futures):
            try:
                print("done", future.result(), flush=True)
            except Exception as error:
                print("failed", futures[future][:3], repr(error), flush=True)


if __name__ == "__main__":
    main()
