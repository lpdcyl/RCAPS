"""Audit each E6 independent replay against the preserved formal failure."""
from collections import Counter

from experiments.v5_core_supplement.run import ROOT, read, sha, write
from . import replay_failures as replay


def main():
    manifest = read(replay.MANIFEST)
    index = read(replay.INDEX)
    formal_manifest = read(replay.FORMAL / "manifest.json")
    formal_index = read(replay.FORMAL / "index.json")
    if (index["status"] != "terminal" or index["manifest_sha256"] != sha(replay.MANIFEST)
            or manifest["formal_manifest_sha256"] != sha(replay.FORMAL / "manifest.json")
            or manifest["formal_index_sha256"] != sha(replay.FORMAL / "index.json")
            or manifest["formal_source_sha256"] != sha(replay.HERE / "run.py")):
        raise RuntimeError("Replay or formal lineage changed")
    if len(manifest["jobs"]) != 13 or len(index["jobs"]) != 13:
        raise RuntimeError("Expected 13 replay keys")
    rows = []
    for item in manifest["jobs"]:
        key = item["key"]
        state = index["jobs"][key]
        original = formal_index["jobs"][key]
        if (original["status"] != "failed" or original["source"] != item["original_source"]
                or original["artifact_sha256"] != item["original_sha256"]
                or sha(ROOT / item["original_source"]) != item["original_sha256"]
                or read(ROOT / item["original_source"])["job"] != item["job"]):
            raise RuntimeError("Original failure lineage mismatch: " + key)
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal replay key: " + key)
        artifact = ROOT / state["source"]
        if sha(artifact) != state["artifact_sha256"]:
            raise RuntimeError("Replay artifact changed: " + key)
        observed = read(artifact)
        if observed["job"] != item["job"] or observed["status"] != state["status"]:
            raise RuntimeError("Replay job/status mismatch: " + key)
        if state["status"] == "completed":
            old_reference = formal_manifest["old_rows"][f"{item['job']['scenario']}/load{item['job']['load']}/V4/seed{item['job']['seed']}"]
            if (artifact.name != "result.json" or observed["origin"] != "E6_independent_failure_replay"
                    or observed["original_failure_sha256"] != item["original_sha256"]
                    or observed["replay_manifest_sha256"] != sha(replay.MANIFEST)
                    or observed["trace_sha256"] != old_reference["trace_sha256"]
                    or observed["solution_sha256"] != old_reference["solution_sha256"]
                    or observed["sim_cluster_sha256"] != old_reference["sim_cluster_sha256"]
                    or len(observed["query_samples"]) != observed["arrivals"]):
                raise RuntimeError("Replay result provenance/metric mismatch: " + key)
        elif artifact.name != "failure.json":
            raise RuntimeError("Failure artifact mismatch: " + key)
        elif observed.get("original_failure_sha256", item["original_sha256"]) != item["original_sha256"]:
            raise RuntimeError("Failure original hash mismatch: " + key)
        rows.append({"key": key, "original_status": "failed", "replay_status": state["status"],
                     "original_sha256": item["original_sha256"],
                     "replay_source": state["source"], "replay_sha256": state["artifact_sha256"],
                     "error": observed.get("error", observed.get("classification"))})
    summary = Counter(x["replay_status"] for x in rows)
    result = {"passed": True, "formal_registered": len(formal_index["jobs"]),
              "formal_completed": sum(x["status"] == "completed" for x in formal_index["jobs"].values()),
              "formal_failed": sum(x["status"] == "failed" for x in formal_index["jobs"].values()),
              "replay_registered": len(rows), "replay_completed": summary["completed"],
              "replay_failed": summary["failed"],
              "formal_index_sha256": sha(replay.FORMAL / "index.json"),
              "replay_manifest_sha256": sha(replay.MANIFEST),
              "replay_index_sha256": sha(replay.INDEX), "rows": rows,
              "interpretation": "Independent replay is separate; formal failure rate remains unchanged"}
    write(replay.BATCH / "FINAL_AUDIT.json", result)
    print({k: v for k, v in result.items() if k != "rows"})


if __name__ == "__main__":
    main()
