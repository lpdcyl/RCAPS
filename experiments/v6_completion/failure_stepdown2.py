"""Second, fixed boundary grid after the first lower-token campaign."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, read, relative, sha, write
from experiments.v6_completion import failure_stepdown as first
from experiments.v6_completion.campaign_queue import queue, worker

HERE = Path(__file__).resolve().parent / "failure_stepdown2"
MODULE = "experiments.v6_completion.failure_stepdown2"
MODES = (
    ("70b_single_prompt1p5_rate350", "single", 1.5, 350),
    ("70b_multi_prompt1p5_rate160", "multi", 1.5, 160),
    ("30b_multi_rate525", "multi", 0, 525),
)


def register(phase: str, workers: int):
    assert phase in ("smoke", "formal")
    target = HERE / phase / "manifest.json"
    if target.exists():
        manifest = read(target)
        check(manifest)
        return manifest

    previous = HERE.parent / "failure_stepdown"
    prior_index = read(previous / "formal/index.json")
    assert prior_index["status"] == "terminal"
    assert read(previous / "FINAL_AUDIT.json")["passed"]
    assert all(prior_index["jobs"][f"30b_multi_rate630/V4/seed{seed}"]["status"] == "failed"
               for seed in range(5))
    assert all(prior_index["jobs"][f"70b_{scenario}_prompt2_rate{rate}/{cell}/seed{seed}"]["status"] == "failed"
               for scenario, rate in (("single", 350), ("multi", 160))
               for cell in (("HH", "HHplus", "V4") if scenario == "single" else ("HH", "HHplus"))
               for seed in range(5))

    sources = dict(read(previous / "formal/manifest.json")["sources_sha256"])
    sources[relative(Path(__file__))] = sha(Path(__file__))
    check({"sources_sha256": sources})
    duration, seeds = (60, (100,)) if phase == "smoke" else (1800, tuple(range(5)))
    jobs = [dict(key=f"{mode}/{cell}/seed{seed}", mode=mode,
                 model="30B" if scale == 0 else "70B", scenario=scenario,
                 prompt_scale=scale, target_rate=rate, cell=cell, seed=seed,
                 duration=duration)
            for mode, scenario, scale, rate in MODES
            for seed in seeds for cell in first.CELLS]
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs, worker_limit=workers,
                    timeout_wall_s=14400, sources_sha256=sources,
                    prior_manifest_sha256=sha(previous / "formal/manifest.json"),
                    prior_index_sha256=sha(previous / "formal/index.json"),
                    protocol="60s smoke or 1800s formal, zero warmup, no drain, seeds 0..4",
                    decision="Fixed 1.5x-prompt and 525-token/s grid after all-seed failure at previous points",
                    conditions={mode: dict(model="30B" if scale == 0 else "70B",
                                           scenario=scenario, prompt_scale=scale,
                                           target_offered_tokens_per_s=rate)
                                for mode, scenario, scale, rate in MODES},
                    failure_policy="One attempt per key; preserve original and prior follow-up failures",
                    environment=dict(executable=sys.executable, env=ENV))
    write(target, manifest)
    return manifest


def report():
    first.HERE = HERE
    first.MODES = MODES
    first.report()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
    elif args.worker:
        worker(HERE, args.phase, args.worker, first.evaluate)
    else:
        queue(HERE, MODULE, args.phase, args.workers, register, report)


if __name__ == "__main__":
    main()
