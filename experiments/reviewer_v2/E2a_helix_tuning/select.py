"""Strict held-out selection from E2a tuning seeds 5 and 6 only."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from .run import HERE, LOADS, candidates, check, label, read, sha, write


def main():
    manifest_path = HERE / "tuning/manifest.json"
    manifest = read(manifest_path)
    check(manifest)
    index_path = HERE / "tuning/index.json"
    index = read(index_path)
    if index["status"] != "terminal":
        raise RuntimeError("Tuning is not terminal")
    if index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Tuning manifest hash mismatch")
    jobs = {job["key"]: job for job in manifest["jobs"]}
    if set(index["jobs"]) != set(jobs) or len(jobs) != 96:
        raise RuntimeError("Tuning key set mismatch")
    outcomes = defaultdict(dict)
    failure_reasons = Counter()
    trace_by_condition = {}
    deployment_by_case = {}
    for key, job in jobs.items():
        entry = index["jobs"][key]
        if entry["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal job: " + key)
        source = HERE.parents[2] / entry["source"]
        if not source.exists() or sha(source) != entry["artifact_sha256"]:
            raise RuntimeError("Source missing or hash mismatch: " + key)
        result = read(source)
        if result["job"] != job:
            raise RuntimeError("Job identity mismatch: " + key)
        if entry["status"] == "failed":
            failure_reasons[result.get("error", result.get("classification", "unknown"))] += 1
            continue
        if result["status"] != "completed" or result["manifest_sha256"] != sha(manifest_path):
            raise RuntimeError("Result provenance mismatch: " + key)
        cond = (job["scenario"], job["load"], job["seed"])
        digest = result["trace_sha256"]
        if cond in trace_by_condition and trace_by_condition[cond] != digest:
            raise RuntimeError("Different traces for same condition: " + key)
        trace_by_condition[cond] = digest
        case = job["scenario"]
        deployment = (result["solution_sha256"], result["sim_cluster_sha256"])
        if case in deployment_by_case and deployment_by_case[case] != deployment:
            raise RuntimeError("Different deployments for case: " + key)
        deployment_by_case[case] = deployment
        outcomes[(case, job["load"], label(job["params"]))][job["seed"]] = (
            result, entry["source"], entry["artifact_sha256"])
    replay_path = HERE / "failure_replay/manifest.json"
    replay_count = 0
    if replay_path.exists():
        replay_manifest = read(replay_path)
        check(replay_manifest)
        replay_index_path = HERE / "failure_replay/index.json"
        replay_index = read(replay_index_path)
        if (replay_index["status"] != "terminal" or
                replay_index["manifest_sha256"] != sha(replay_path) or
                replay_manifest["original_manifest_sha256"] != sha(manifest_path) or
                replay_manifest["original_index_sha256"] != sha(index_path)):
            raise RuntimeError("Replay provenance mismatch")
        if set(replay_index["jobs"]) != {job["key"] for job in replay_manifest["jobs"]}:
            raise RuntimeError("Replay key set mismatch")
        for job in replay_manifest["jobs"]:
            key = job["key"]
            original = index["jobs"][key]
            if original["status"] != "failed":
                raise RuntimeError("Replay key was not originally failed: " + key)
            failure = replay_manifest["original_failures"][key]
            if (failure["source"] != original["source"] or
                    failure["artifact_sha256"] != original["artifact_sha256"] or
                    sha(HERE.parents[2] / failure["source"]) != failure["artifact_sha256"]):
                raise RuntimeError("Original failure has changed: " + key)
            entry = replay_index["jobs"][key]
            if entry["status"] != "completed":
                continue
            source = HERE.parents[2] / entry["source"]
            if sha(source) != entry["artifact_sha256"]:
                raise RuntimeError("Replay result hash mismatch: " + key)
            result = read(source)
            if (result["job"] != job or result["status"] != "completed" or
                    result["manifest_sha256"] != sha(replay_path)):
                raise RuntimeError("Replay result identity mismatch: " + key)
            cond = (job["scenario"], job["load"], job["seed"])
            if cond in trace_by_condition and trace_by_condition[cond] != result["trace_sha256"]:
                raise RuntimeError("Replay trace mismatch: " + key)
            trace_by_condition[cond] = result["trace_sha256"]
            case = job["scenario"]
            deployment = (result["solution_sha256"], result["sim_cluster_sha256"])
            if case in deployment_by_case and deployment_by_case[case] != deployment:
                raise RuntimeError("Replay deployment mismatch: " + key)
            outcomes[(case, job["load"], label(job["params"]))][job["seed"]] = (
                result, entry["source"], entry["artifact_sha256"])
            replay_count += 1
    selection = {}
    for case, load in LOADS:
        baseline_label = label(dict(priority=True, batch=True, hwm=0.9, ratio=0.6))
        baseline = outcomes[(case, load, baseline_label)]
        if set(baseline) != {5, 6}:
            raise RuntimeError(f"Default Helix+ tuning baseline incomplete: {case}/{load}")
        floor = mean(baseline[s][0]["completion_fraction"] for s in (5, 6))
        eligible = []
        audit_grid = []
        for params in candidates():
            tag = label(params)
            group = outcomes[(case, load, tag)]
            record = dict(candidate=tag, params=params, success_seeds=sorted(group),
                          success_count=len(group))
            if set(group) == {5, 6}:
                completion = mean(group[s][0]["completion_fraction"] for s in (5, 6))
                tpot = mean(group[s][0]["tpot_p95_s"] for s in (5, 6))
                gpu = mean(group[s][0]["gpu_seconds_per_output_token"] for s in (5, 6))
                record.update(mean_completion_fraction=completion, mean_tpot_p95_s=tpot,
                              mean_gpu_seconds_per_output_token=gpu,
                              meets_completion_floor=completion >= floor)
                if completion >= floor:
                    eligible.append((tpot, -completion, gpu, tag, params, group))
            audit_grid.append(record)
        fallback = not eligible
        if fallback:
            params = dict(priority=True, batch=True, hwm=0.9, ratio=0.6)
            group, chosen = baseline, baseline_label
        else:
            _, _, _, chosen, params, group = min(eligible)
        selection[f"{case}/{load}"] = dict(
            params=params, candidate=chosen, fallback_default=fallback,
            completion_floor=floor,
            seed_rule="5 and 6 only",
            evidence={str(seed): dict(source=group[seed][1],
                                      artifact_sha256=group[seed][2]) for seed in (5, 6)},
            grid=audit_grid)
    selection["_audit"] = dict(tuning_manifest_sha256=sha(manifest_path),
                               tuning_index_sha256=sha(index_path),
                               failed_jobs=sum(failure_reasons.values()),
                               recovered_by_independent_replay=replay_count,
                               replay_manifest_sha256=sha(replay_path) if replay_path.exists() else None,
                               failure_reasons=dict(failure_reasons),
                               complete_trace_conditions=len(trace_by_condition),
                               selection_script_sha256=sha(Path(__file__)))
    target = HERE / "selection.json"
    if target.exists():
        if read(target) != selection:
            raise RuntimeError("Existing frozen selection differs")
    else:
        write(target, selection)
    print(json.dumps({key: value["candidate"] for key, value in selection.items()
                      if key != "_audit"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
