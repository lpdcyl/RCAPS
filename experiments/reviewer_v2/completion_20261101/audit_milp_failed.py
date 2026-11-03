"""Audit independent MILP-online failure replay without merging formal outcomes."""
from __future__ import annotations

from collections import Counter

from experiments.v5_core_supplement.run import ROOT, read, sha, write

from .report import expected_deployment
from .replay_milp_failed import BASE, FORMAL, check_manifest


def main():
    manifest_path, index_path = BASE / "manifest.json", BASE / "index.json"
    manifest, index = read(manifest_path), read(index_path)
    check_manifest(manifest)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("MILP failure replay is not terminal")
    items = {item["key"]: item for item in manifest["jobs"]}
    if len(items) != 38 or set(items) != set(index["jobs"]):
        raise RuntimeError("MILP replay population mismatch")
    formal_index = read(FORMAL / "index.json")
    counts = Counter()
    rows = []
    for key, item in items.items():
        state = index["jobs"][key]
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal MILP replay key: " + key)
        if formal_index["jobs"][key]["status"] != "failed":
            raise RuntimeError("Original MILP formal status changed: " + key)
        source = ROOT / state["source"]
        if sha(source) != state["artifact_sha256"]:
            raise RuntimeError("MILP replay artifact SHA mismatch: " + key)
        artifact = read(source)
        job = item["job"]
        if (artifact.get("job") != job or artifact.get("campaign") != "milp"
                or artifact.get("formal_failure_sha256") != item["formal_failure_sha256"]):
            raise RuntimeError("MILP replay lineage mismatch: " + key)
        if state["status"] == "completed":
            if (artifact.get("status") != "completed"
                    or artifact.get("manifest_sha256") != sha(manifest_path)
                    or artifact.get("duration_s") != job["duration_s"]
                    or artifact.get("seed") != job["seed"]
                    or artifact.get("warmup_s") != 0
                    or artifact.get("evaluation_protocol") != "fixed_window_no_tail_drain"
                    or len(artifact.get("query_samples", {})) != artifact.get("arrivals")
                    or artifact.get("output_throughput_tokens_per_s", 0) <= 0):
                raise RuntimeError("MILP replay protocol mismatch: " + key)
            expected = expected_deployment("milp", job)
            actual = (artifact["solution_sha256"], artifact["sim_cluster_sha256"],
                      artifact.get("physical_sha256", artifact.get("physical_cluster_sha256")))
            if actual != expected:
                raise RuntimeError("MILP replay deployment mismatch: " + key)
        counts[state["status"]] += 1
        rows.append({"key": key, "status": state["status"], "source": state["source"],
                     "artifact_sha256": state["artifact_sha256"],
                     "formal_failure_sha256": item["formal_failure_sha256"],
                     "error": artifact.get("error", artifact.get("classification"))})
    result = {"passed": True, "registered": len(items),
              "completed": counts["completed"], "failed": counts["failed"],
              "formal_completed": 12, "formal_failed": 38,
              "manifest_sha256": sha(manifest_path), "index_sha256": sha(index_path),
              "rows": rows,
              "interpretation": "Independent diagnostic replay; formal results and five-seed groups unchanged"}
    target = BASE / "FINAL_AUDIT.json"
    if target.exists():
        raise RuntimeError("MILP replay audit already exists")
    write(target, result)
    print({key: result[key] for key in ("passed", "registered", "completed", "failed")})


if __name__ == "__main__":
    main()
