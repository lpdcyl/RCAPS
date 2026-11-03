"""Audit the independent E5a failed-key replay without merging formal outcomes."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from experiments.v5_core_supplement.run import ROOT, read, sha, write

from .replay_e5a_failed import BASE, FORMAL, check_manifest
from .report import expected_deployment


def main():
    manifest_path, index_path = BASE / "manifest.json", BASE / "index.json"
    manifest, index = read(manifest_path), read(index_path)
    check_manifest(manifest)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("E5a replay is not terminal")
    items = {item["key"]: item for item in manifest["jobs"]}
    if len(items) != 45 or set(items) != set(index["jobs"]):
        raise RuntimeError("Replay key population mismatch")
    formal_manifest = read(FORMAL / "manifest.json")
    formal_index = read(FORMAL / "index.json")
    formal_jobs = {job["key"]: job for job in formal_manifest["jobs"]}
    counts = Counter()
    rows = []
    replay_traces = defaultdict(set)
    for key, item in items.items():
        state = index["jobs"][key]
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal replay key: " + key)
        if formal_index["jobs"][key]["status"] != "failed":
            raise RuntimeError("Original formal status changed: " + key)
        source = ROOT / state["source"]
        if sha(source) != state["artifact_sha256"]:
            raise RuntimeError("Replay artifact SHA mismatch: " + key)
        artifact = read(source)
        job = item["job"]
        if (artifact.get("job") != job or artifact.get("campaign") != "e5a"
                or artifact.get("original_failure_sha256") != item["original_failure_sha256"]):
            raise RuntimeError("Replay lineage mismatch: " + key)
        counts[state["status"]] += 1
        row = {"key": key, "status": state["status"], "source": state["source"],
               "artifact_sha256": state["artifact_sha256"],
               "original_failure_sha256": item["original_failure_sha256"],
               "error": artifact.get("error", artifact.get("classification"))}
        if state["status"] == "completed":
            if (artifact.get("status") != "completed"
                    or artifact.get("manifest_sha256") != sha(manifest_path)
                    or artifact.get("duration_s") != job["duration_s"]
                    or artifact.get("seed") != job["seed"]
                    or artifact.get("warmup_s") != 0
                    or artifact.get("evaluation_protocol") != "fixed_window_no_tail_drain"
                    or len(artifact.get("query_samples", {})) != artifact.get("arrivals")):
                raise RuntimeError("Replay protocol mismatch: " + key)
            expected = expected_deployment("e5a", job)
            actual = (artifact["solution_sha256"], artifact["sim_cluster_sha256"],
                      artifact.get("physical_sha256", artifact.get("physical_cluster_sha256")))
            if actual != expected:
                raise RuntimeError("Replay deployment mismatch: " + key)
            throughput = artifact["output_throughput_tokens_per_s"]
            if throughput <= 0 or not math.isclose(
                    artifact["gpu_seconds_per_output_token"],
                    sum(artifact["gpu_busy_fraction"].values()) / throughput, rel_tol=1e-12):
                raise RuntimeError("Replay GPU accounting mismatch: " + key)
            matched = 0
            for formal_key, peer in formal_jobs.items():
                if (peer["load"], peer["seed"]) != (
                        job["load"], job["seed"]):
                    continue
                previous = formal_index["jobs"][formal_key]
                if previous["status"] != "completed":
                    continue
                if read(ROOT / previous["source"])["trace_sha256"] != artifact["trace_sha256"]:
                    raise RuntimeError("Replay trace differs from formal peer: " + key)
                matched += 1
            replay_traces[(job["load"], job["seed"])].add(
                artifact["trace_sha256"])
            row.update(trace_sha256=artifact["trace_sha256"],
                       matched_formal_peers=matched)
        rows.append(row)
    if any(len(values) > 1 for values in replay_traces.values()):
        raise RuntimeError("Same-seed replay request traces differ")
    result = {"passed": True, "registered": len(items),
              "completed": counts["completed"], "failed": counts["failed"],
              "formal_completed": 15, "formal_failed": 45,
              "manifest_sha256": sha(manifest_path), "index_sha256": sha(index_path),
              "rows": rows, "interpretation":
              "Independent replay only; original formal results and five-seed groups unchanged"}
    target = BASE / "FINAL_AUDIT.json"
    if target.exists():
        raise RuntimeError("Audit already exists; inspect before rerunning")
    write(target, result)
    print({key: result[key] for key in ("passed", "registered", "completed", "failed")})


if __name__ == "__main__":
    main()
