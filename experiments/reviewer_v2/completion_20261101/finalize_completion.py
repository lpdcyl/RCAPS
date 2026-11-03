"""Reconcile all new completion campaigns and publish their local evidence table."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, now, read, sha, write

from .build_manual_failed_key_commands import main as build_commands
from .build_upload_manifest import main as build_upload_manifest
from .replay_e5a_failed import check_manifest as check_e5a_replay
from .replay_e6_failed import check_manifest as check_e6_replay
from .retry_failed_replays import check_manifest as check_retry
from .replay_milp_failed import check_manifest as check_milp_replay
from .run import HERE, check as check_formal


CAMPAIGNS = (
    ("e5a_formal", "e5a/formal", "e5a/FINAL_AUDIT.json", 60, "e5a"),
    ("e6_formal", "e6/formal", "e6/FINAL_AUDIT.json", 60, "e6"),
    ("milp_formal", "milp/formal", "milp/FINAL_AUDIT.json", 50, "milp"),
    ("e5a_replay", "e5a_failure_replay", "e5a_failure_replay/FINAL_AUDIT.json", 45, "e5a_replay"),
    ("e6_replay", "e6_failure_replay", "e6_failure_replay/FINAL_AUDIT.json", 29, "e6_replay"),
    ("failed_retry_v2", "failed_replay_retry_v2", "failed_replay_retry_v2/FINAL_AUDIT.json", 24, "retry"),
    ("milp_replay", "milp_failure_replay", "milp_failure_replay/FINAL_AUDIT.json", 38, "milp_replay"),
)


def check_campaign(name, relative, audit_relative, expected, kind):
    base = HERE / relative
    manifest_path, index_path, audit_path = base / "manifest.json", base / "index.json", HERE / audit_relative
    manifest, index, audit = read(manifest_path), read(index_path), read(audit_path)
    if kind in ("e5a", "e6", "milp"):
        check_formal(kind, manifest)
    else:
        {"e5a_replay": check_e5a_replay, "e6_replay": check_e6_replay,
         "retry": check_retry, "milp_replay": check_milp_replay}[kind](manifest)
    jobs = {item["key"] for item in manifest["jobs"]}
    if (len(jobs) != expected or len(manifest["jobs"]) != expected
            or index["status"] != "terminal" or set(index["jobs"]) != jobs
            or not audit["passed"] or audit["registered"] != expected
            or index["manifest_sha256"] != sha(manifest_path)
            or audit["manifest_sha256"] != sha(manifest_path)
            or audit["index_sha256"] != sha(index_path)):
        raise RuntimeError("Campaign registration or audit mismatch: " + name)
    counts = Counter()
    for key, state in index["jobs"].items():
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal key: " + name + "/" + key)
        artifact = ROOT / state["source"]
        if not artifact.is_file() or sha(artifact) != state["artifact_sha256"]:
            raise RuntimeError("Artifact SHA mismatch: " + name + "/" + key)
        counts[state["status"]] += 1
    if (audit["completed"] != counts["completed"] or audit["failed"] != counts["failed"]):
        raise RuntimeError("Audited counts mismatch: " + name)
    if kind in ("e5a", "e6", "milp") and audit["complete_five_seed_groups"] != 0:
        raise RuntimeError("Unexpected formal five-seed group: " + name)
    return {"registered": expected, "completed": counts["completed"],
            "failed": counts["failed"], "manifest_sha256": sha(manifest_path),
            "index_sha256": sha(index_path), "audit_sha256": sha(audit_path)}


def main():
    target = HERE / "FINAL_RECONCILIATION.json"
    results = {name: check_campaign(name, rel, audit, expected, kind)
               for name, rel, audit, expected, kind in CAMPAIGNS}
    retry_audit = read(HERE / "failed_replay_retry_v2/FINAL_AUDIT.json")
    retry_by_campaign = Counter(row["campaign"] for row in retry_audit["rows"] if row["status"] == "failed")
    milp = results["milp_replay"]
    paper = ROOT / "paper/RCAPS_V4_EVIDENCE_STATUS_CN.md"
    old = "E5a/E6 的第二轮有界独立重跑已审计：24 键中 4 成功、20 失败（E5a 3/22 成功，E6 1/2 成功）；MILP 38 个正式失败键的独立重放正在运行，尚未审计。"
    new = ("E5a/E6 的 24 个第一轮重放失败键在第二轮有界独立重跑中 "
           f"{results['failed_retry_v2']['completed']} 成功、{results['failed_retry_v2']['failed']} 失败，"
           f"其中仍失败 E5a {retry_by_campaign['e5a']} 键、E6 {retry_by_campaign['e6']} 键；"
           f"MILP 的 38 个正式失败键独立重放 {milp['completed']} 成功、{milp['failed']} 失败。"
           "两轮审计及原正式批互不合并，正式完整五种子组仍均为零。"
           "详见 [E5a/E6 第二轮审计](../experiments/reviewer_v2/completion_20261101/failed_replay_retry_v2/FINAL_AUDIT.json)"
           "与 [MILP 独立重放审计](../experiments/reviewer_v2/completion_20261101/milp_failure_replay/FINAL_AUDIT.json)。")
    content = paper.read_text(encoding="utf-8")
    if old in content:
        paper.write_text(content.replace(old, new, 1), encoding="utf-8")
    elif new not in content:
        raise RuntimeError("Paper completion paragraph changed; update manually")
    build_commands()
    manual = HERE / "MANUAL_FAILED_KEY_COMMANDS_CN.md"
    summary = {"passed": True, "checked_at": now(), "campaigns": results,
               "remaining_failed_keys": {"e5a": retry_by_campaign["e5a"],
                                          "e6": retry_by_campaign["e6"],
                                          "milp": milp["failed"]},
               "paper_sha256": sha(paper), "manual_commands_sha256": sha(manual),
               "scope": "New 2026-11-01 E5a/E6/MILP formal and independent replay campaigns; no formal backfill"}
    if target.exists():
        previous = read(target)
        if (previous["campaigns"] != results or previous["paper_sha256"] != sha(paper)
                or previous["manual_commands_sha256"] != sha(manual)):
            raise RuntimeError("Final reconciliation exists but sources changed")
    else:
        write(target, summary)
    build_upload_manifest()
    print({"passed": True, "campaigns": {key: (value["completed"], value["failed"])
          for key, value in results.items()}, "remaining": summary["remaining_failed_keys"]})


if __name__ == "__main__":
    main()
