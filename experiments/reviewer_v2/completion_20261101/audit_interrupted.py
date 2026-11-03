"""Verify the isolated replay of the three reboot-interrupted windows."""
from __future__ import annotations

import math
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha, write

from .replay_interrupted import BASE, check_manifest
from .report import expected_deployment
from .run import HERE


def same_condition(campaign, left, right):
    if left["seed"] != right["seed"]:
        return False
    if campaign == "e5a":
        return left["load"] == right["load"]
    return (left["scenario"], left["load"]) == (right["scenario"], right["load"])


def main():
    manifest_path, index_path = BASE / "manifest.json", BASE / "index.json"
    manifest, index = read(manifest_path), read(index_path)
    check_manifest(manifest)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Interrupted replay is not terminal")
    expected = {f"{item['campaign']}/{item['key']}" for item in manifest["jobs"]}
    if len(expected) != 3 or set(index["jobs"]) != expected:
        raise RuntimeError("Replay key population mismatch")
    rows = []
    for item in manifest["jobs"]:
        campaign, job = item["campaign"], item["job"]
        identity = f"{campaign}/{item['key']}"
        state = index["jobs"][identity]
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal replay: " + identity)
        source = ROOT / state["source"]
        if sha(source) != state["artifact_sha256"]:
            raise RuntimeError("Replay artifact SHA mismatch: " + identity)
        row = read(source)
        if (row.get("job") != job or row.get("campaign") != campaign
                or row.get("original_failure_sha256") != item["original_failure_sha256"]):
            raise RuntimeError("Replay lineage mismatch: " + identity)
        result = {"key": identity, "status": state["status"],
                  "source": state["source"], "artifact_sha256": state["artifact_sha256"],
                  "original_failure_sha256": item["original_failure_sha256"],
                  "error": row.get("error", row.get("classification"))}
        if state["status"] == "completed":
            if (row.get("status") != "completed"
                    or row.get("manifest_sha256") != sha(manifest_path)
                    or row.get("duration_s") != job["duration_s"]
                    or row.get("seed") != job["seed"]
                    or row.get("warmup_s") != 0
                    or row.get("evaluation_protocol") != "fixed_window_no_tail_drain"
                    or len(row.get("query_samples", {})) != row.get("arrivals")):
                raise RuntimeError("Replay protocol mismatch: " + identity)
            deployment = expected_deployment(campaign, job)
            actual = (row["solution_sha256"], row["sim_cluster_sha256"],
                      row.get("physical_sha256", row.get("physical_cluster_sha256")))
            if deployment != actual:
                raise RuntimeError("Replay deployment mismatch: " + identity)
            throughput = row["output_throughput_tokens_per_s"]
            if throughput <= 0 or not math.isclose(
                    row["gpu_seconds_per_output_token"],
                    sum(row["gpu_busy_fraction"].values()) / throughput,
                    rel_tol=1e-12):
                raise RuntimeError("Replay GPU accounting mismatch: " + identity)
            formal = HERE / campaign / "formal"
            formal_manifest = read(formal / "manifest.json")
            formal_index = read(formal / "index.json")
            paired_traces = []
            for old in formal_manifest["jobs"]:
                if not same_condition(campaign, job, old):
                    continue
                previous = formal_index["jobs"][old["key"]]
                if previous["status"] == "completed":
                    paired_traces.append(read(ROOT / previous["source"])["trace_sha256"])
            if paired_traces and any(value != row["trace_sha256"]
                                     for value in paired_traces):
                raise RuntimeError("Replay trace differs from formal peers: " + identity)
            result.update(trace_sha256=row["trace_sha256"],
                          paired_formal_sources=len(paired_traces))
        rows.append(result)
    audit = {"passed": True, "registered": 3,
             "completed": sum(row["status"] == "completed" for row in rows),
             "failed": sum(row["status"] == "failed" for row in rows),
             "manifest_sha256": sha(manifest_path), "index_sha256": sha(index_path),
             "script_sha256": sha(Path(__file__)), "rows": rows,
             "interpretation": "Independent replay only; formal failures unchanged"}
    write(BASE / "FINAL_AUDIT.json", audit)
    print(audit)


if __name__ == "__main__":
    main()
