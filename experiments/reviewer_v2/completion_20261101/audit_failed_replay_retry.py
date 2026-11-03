"""Audit the bounded second retry without changing formal or first replay results."""
from __future__ import annotations

from collections import Counter

from experiments.v5_core_supplement.run import ROOT, read, sha, write

from .report import expected_deployment
from .retry_failed_replays import BASE, PARENTS, check_manifest


def main():
    manifest_path, index_path = BASE / "manifest.json", BASE / "index.json"
    manifest, index = read(manifest_path), read(index_path)
    check_manifest(manifest)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Retry is not terminal")
    items = {item["key"]: item for item in manifest["jobs"]}
    if len(items) != len(manifest["jobs"]) or set(items) != set(index["jobs"]):
        raise RuntimeError("Retry key population mismatch")
    counts = Counter()
    rows = []
    for key, item in items.items():
        state = index["jobs"][key]
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal retry key: " + key)
        parent_index = read(PARENTS[item["campaign"]] / "index.json")
        if parent_index["jobs"][key]["status"] != "failed":
            raise RuntimeError("Parent retry source is not failed: " + key)
        source = ROOT / state["source"]
        if sha(source) != state["artifact_sha256"]:
            raise RuntimeError("Retry artifact SHA mismatch: " + key)
        artifact = read(source)
        if (artifact.get("job") != item["job"]
                or artifact.get("campaign") != item["campaign"]
                or artifact.get("retry_campaign") != "failed_replay_retry_v2"
                or artifact.get("parent_failure_sha256") != item["parent_failure_sha256"]
                or artifact.get("formal_failure_sha256") != item["formal_failure_sha256"]):
            raise RuntimeError("Retry lineage mismatch: " + key)
        if state["status"] == "completed":
            if (artifact.get("status") != "completed"
                    or artifact.get("manifest_sha256") != sha(manifest_path)
                    or artifact.get("duration_s") != item["job"]["duration_s"]
                    or artifact.get("seed") != item["job"]["seed"]
                    or artifact.get("warmup_s") != 0
                    or artifact.get("evaluation_protocol") != "fixed_window_no_tail_drain"
                    or len(artifact.get("query_samples", {})) != artifact.get("arrivals")):
                raise RuntimeError("Retry protocol mismatch: " + key)
            expected = expected_deployment(item["campaign"], item["job"])
            actual = (artifact["solution_sha256"], artifact["sim_cluster_sha256"],
                      artifact.get("physical_sha256", artifact.get("physical_cluster_sha256")))
            if actual != expected:
                raise RuntimeError("Retry deployment mismatch: " + key)
            if artifact["output_throughput_tokens_per_s"] <= 0:
                raise RuntimeError("Retry throughput invalid: " + key)
        counts[state["status"]] += 1
        rows.append({"key": key, "campaign": item["campaign"], "status": state["status"],
                     "source": state["source"], "artifact_sha256": state["artifact_sha256"],
                     "parent_failure_sha256": item["parent_failure_sha256"],
                     "formal_failure_sha256": item["formal_failure_sha256"],
                     "error": artifact.get("error", artifact.get("classification"))})
    result = {"passed": True, "registered": len(items), "completed": counts["completed"],
              "failed": counts["failed"], "manifest_sha256": sha(manifest_path),
              "index_sha256": sha(index_path), "rows": rows,
              "interpretation": "Diagnostic retry only; formal and first replay results unchanged"}
    target = BASE / "FINAL_AUDIT.json"
    if target.exists():
        raise RuntimeError("Audit already exists; inspect before rerunning")
    write(target, result)
    print({key: result[key] for key in ("passed", "registered", "completed", "failed")})


if __name__ == "__main__":
    main()
