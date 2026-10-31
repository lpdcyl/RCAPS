"""Select corrected single-cluster Helix parameters using seeds 5 and 6."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from experiments.reviewer_v2.E2a_helix_tuning import run as core
from .run import HERE, check


def main():
    manifest_path = HERE / "tuning/manifest.json"
    index_path = HERE / "tuning/index.json"
    manifest = core.read(manifest_path)
    check(manifest)
    index = core.read(index_path)
    if index["status"] != "terminal" or index["manifest_sha256"] != core.sha(manifest_path):
        raise RuntimeError("Corrected tuning is not terminal or manifest mismatched")
    jobs = {job["key"]: job for job in manifest["jobs"]}
    if len(jobs) != 48 or set(index["jobs"]) != set(jobs):
        raise RuntimeError("Corrected tuning job set mismatch")
    outcomes = defaultdict(dict)
    traces = {}
    errors = Counter()
    from .run import paths
    _, solution, cluster = paths()
    expected_deployment = (core.sha(solution), core.sha(cluster))
    for key, job in jobs.items():
        entry = index["jobs"][key]
        if entry["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal corrected job: " + key)
        source = core.ROOT / entry["source"]
        if core.sha(source) != entry["artifact_sha256"]:
            raise RuntimeError("Corrected artifact hash mismatch: " + key)
        row = core.read(source)
        if row["job"] != job:
            raise RuntimeError("Corrected job identity mismatch: " + key)
        if entry["status"] == "failed":
            errors[row.get("error", row.get("classification", "unknown"))] += 1
            continue
        if (row["status"] != "completed" or row["manifest_sha256"] != core.sha(manifest_path)
                or (row["solution_sha256"], row["sim_cluster_sha256"]) != expected_deployment
                or job["seed"] not in (5, 6)):
            raise RuntimeError("Corrected source provenance mismatch: " + key)
        cond = (job["load"], job["seed"])
        if cond in traces and traces[cond] != row["trace_sha256"]:
            raise RuntimeError("Different trace within corrected condition: " + key)
        traces[cond] = row["trace_sha256"]
        outcomes[(job["load"], core.label(job["params"]))][job["seed"]] = (
            row, entry["source"], entry["artifact_sha256"])
    replay_path = HERE / "failure_replay/manifest.json"
    replay_recovered = 0
    if replay_path.exists():
        replay_manifest = core.read(replay_path)
        check(replay_manifest)
        replay_index_path = HERE / "failure_replay/index.json"
        replay_index = core.read(replay_index_path)
        if (replay_index["status"] != "terminal" or
                replay_index["manifest_sha256"] != core.sha(replay_path) or
                replay_manifest["original_manifest_sha256"] != core.sha(manifest_path) or
                replay_manifest["original_index_sha256"] != core.sha(index_path)):
            raise RuntimeError("Corrected replay provenance mismatch")
        for job in replay_manifest["jobs"]:
            key = job["key"]
            original = index["jobs"][key]
            if original["status"] != "failed":
                raise RuntimeError("Replay key was not originally failed: " + key)
            expected = replay_manifest["original_failures"][key]
            if (expected["source"] != original["source"] or
                    expected["artifact_sha256"] != original["artifact_sha256"] or
                    core.sha(core.ROOT / expected["source"]) != expected["artifact_sha256"]):
                raise RuntimeError("Original corrected failure changed: " + key)
            entry = replay_index["jobs"][key]
            if entry["status"] != "completed":
                continue
            source = core.ROOT / entry["source"]
            if core.sha(source) != entry["artifact_sha256"]:
                raise RuntimeError("Corrected replay hash mismatch: " + key)
            row = core.read(source)
            if (row["job"] != job or row["status"] != "completed" or
                    row["manifest_sha256"] != core.sha(replay_path) or
                    (row["solution_sha256"], row["sim_cluster_sha256"]) != expected_deployment):
                raise RuntimeError("Corrected replay identity mismatch: " + key)
            cond = (job["load"], job["seed"])
            if cond in traces and traces[cond] != row["trace_sha256"]:
                raise RuntimeError("Corrected replay trace mismatch: " + key)
            traces[cond] = row["trace_sha256"]
            outcomes[(job["load"], core.label(job["params"]))][job["seed"]] = (
                row, entry["source"], entry["artifact_sha256"])
            replay_recovered += 1
    selection = {}
    for load in (350, 700):
        default = core.label(dict(priority=True, batch=True, hwm=0.9, ratio=0.6))
        baseline = outcomes[(load, default)]
        if set(baseline) != {5, 6}:
            raise RuntimeError("Corrected default Helix+ incomplete: " + str(load))
        floor = mean(baseline[s][0]["completion_fraction"] for s in (5, 6))
        eligible, grid = [], []
        for params in core.candidates():
            tag = core.label(params)
            group = outcomes[(load, tag)]
            item = dict(candidate=tag, params=params, success_seeds=sorted(group),
                        success_count=len(group))
            if set(group) == {5, 6}:
                completion = mean(group[s][0]["completion_fraction"] for s in (5, 6))
                tpot = mean(group[s][0]["tpot_p95_s"] for s in (5, 6))
                gpu = mean(group[s][0]["gpu_seconds_per_output_token"] for s in (5, 6))
                item.update(mean_completion_fraction=completion, mean_tpot_p95_s=tpot,
                            mean_gpu_seconds_per_output_token=gpu,
                            meets_completion_floor=completion >= floor)
                if completion >= floor:
                    eligible.append((tpot, -completion, gpu, tag, params, group))
            grid.append(item)
        fallback = not eligible
        if fallback:
            chosen, params, group = default, dict(priority=True, batch=True, hwm=0.9, ratio=0.6), baseline
        else:
            _, _, _, chosen, params, group = min(eligible)
        selection[f"single/{load}"] = dict(
            params=params, candidate=chosen, fallback_default=fallback,
            completion_floor=floor, seed_rule="5 and 6 only",
            evidence={str(seed): dict(source=group[seed][1],
                                      artifact_sha256=group[seed][2]) for seed in (5, 6)},
            grid=grid)
    selection["_audit"] = dict(tuning_manifest_sha256=core.sha(manifest_path),
        tuning_index_sha256=core.sha(index_path), original_failed=sum(errors.values()),
        original_failure_reasons=dict(errors), recovered_by_independent_replay=replay_recovered,
        replay_manifest_sha256=core.sha(replay_path) if replay_path.exists() else None,
        complete_trace_conditions=len(traces), official_solution_sha256=expected_deployment[0],
        official_sim_cluster_sha256=expected_deployment[1],
        selector_sha256=core.sha(Path(__file__)))
    target = HERE / "selection.json"
    if target.exists():
        if core.read(target) != selection:
            raise RuntimeError("Corrected selection already exists and differs")
    else:
        core.write(target, selection)
    print({key: value["candidate"] for key, value in selection.items() if key != "_audit"})


if __name__ == "__main__":
    main()
