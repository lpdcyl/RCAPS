"""Enumerate only the audited completion bundle and its local provenance."""
from __future__ import annotations

import subprocess
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha, write

from .run import HERE


INCLUDE = {".py", ".ps1", ".md", ".json", ".csv", ".log"}


def reviewer_extras():
    """Collect missing, SHA-verified terminal experiment evidence without broad git add."""
    tracked = {name.decode().replace("\\", "/") for name in
               subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0") if name}
    experiment_root = ROOT / "experiments"
    reviewer = experiment_root / "reviewer_v2"
    extras: set[Path] = set()

    def add_untracked(path):
        if not path.is_file():
            raise RuntimeError("Missing indexed artifact: " + str(path))
        if path.relative_to(ROOT).as_posix() not in tracked:
            extras.add(path)

    for index_path in experiment_root.rglob("index.json"):
        if (index_path.is_relative_to(HERE)
                or index_path == ROOT / "experiments/v5_kv_admission/smoke_attempt1/index.json"):
            continue
        try:
            index = read(index_path)
        except (OSError, ValueError):
            continue
        if index.get("status") != "terminal" or not isinstance(index.get("jobs"), dict):
            continue
        manifest_path = index_path.with_name("manifest.json")
        if index.get("manifest_sha256"):
            if not manifest_path.is_file() or sha(manifest_path) != index["manifest_sha256"]:
                raise RuntimeError("Experiment manifest changed: " + str(index_path))
            add_untracked(manifest_path)
        add_untracked(index_path)
        for key, state in index["jobs"].items():
            if (not isinstance(state, dict) or state.get("status") not in
                    ("completed", "failed", "reused", "reused_success", "reused_failure",
                     "cancelled_baseline_adaptation")
                    or not state.get("source")):
                continue
            artifact = ROOT / state["source"]
            expected = state.get("artifact_sha256", state.get("sha256"))
            if not expected or sha(artifact) != expected:
                raise RuntimeError("Experiment indexed artifact changed: " + str(index_path) + "/" + key)
            add_untracked(artifact)
            for name in ("lineage.json", "index.json", "capacities.json"):
                sidecar = artifact.parent / name
                if sidecar.is_file():
                    add_untracked(sidecar)
            if state.get("status") == "failed":
                log = artifact.parent / "worker.log"
                if log.is_file():
                    add_untracked(log)

    retry_base = reviewer / "remaining_failure_retry_20261031"
    retry_audit = read(retry_base / "FINAL_AUDIT.json")
    if not retry_audit["passed"] or retry_audit["registered"] != 254:
        raise RuntimeError("Historical reviewer retry audit changed")
    retry_index = read(retry_base / "index.json")
    for row in retry_audit["rows"]:
        artifact = ROOT / row["artifact"]
        if sha(artifact) != row["artifact_sha256"]:
            raise RuntimeError("Historical reviewer retry artifact changed: " + row["key"])
        add_untracked(artifact)
        key = row["group"] + "::" + row["key"]
        child_index = artifact.parent / "index.json"
        if sha(child_index) != retry_index["jobs"][key]["child_index_sha256"]:
            raise RuntimeError("Historical reviewer child index changed: " + key)
        add_untracked(child_index)
        lineage = artifact.parent / "lineage.json"
        if lineage.is_file():
            add_untracked(lineage)

    e4 = reviewer / "E4_tcp_wsl/interrupted_replay_20261101/runs/12p5MBps/priority/repeat0"
    e4_result = read(e4 / "result.json")
    for name, field in (("raw_latency.json.gz", "raw_latency_sha256"),
                        ("receiver.json", "receiver_sha256")):
        path = e4 / name
        if sha(path) != e4_result[field]:
            raise RuntimeError("E4 replay raw artifact changed: " + name)
        add_untracked(path)
    add_untracked(e4 / "started.json")
    return extras


def main():
    reconciliation_path = HERE / "FINAL_RECONCILIATION.json"
    reconciliation = read(reconciliation_path)
    if not reconciliation["passed"]:
        raise RuntimeError("Completion reconciliation has not passed")
    paper = ROOT / "paper/RCAPS_V4_EVIDENCE_STATUS_CN.md"
    if sha(paper) != reconciliation["paper_sha256"]:
        raise RuntimeError("Paper changed after final reconciliation")
    files = sorted((path for path in HERE.rglob("*") if path.is_file()
                    and path.suffix.lower() in INCLUDE
                    and path.name not in {"UPLOAD_MANIFEST.json", "watchdog.log", "finalize_once.log"}
                    and "__pycache__" not in path.parts), key=lambda path: path.as_posix())
    files.extend(sorted(reviewer_extras(), key=lambda path: path.as_posix()))
    files.append(paper)
    if len(files) != len(set(files)):
        raise RuntimeError("Duplicate file in upload scope")
    rels = {path.relative_to(ROOT).as_posix() for path in files}
    for campaign in reconciliation["campaigns"]:
        relative = {"e5a_formal": "e5a/formal", "e6_formal": "e6/formal",
                    "milp_formal": "milp/formal", "e5a_replay": "e5a_failure_replay",
                    "e6_replay": "e6_failure_replay", "failed_retry_v2": "failed_replay_retry_v2",
                    "milp_replay": "milp_failure_replay"}[campaign]
        index = read(HERE / relative / "index.json")
        for key, state in index["jobs"].items():
            if state["source"] not in rels:
                raise RuntimeError("Indexed artifact omitted from upload: " + campaign + "/" + key)
            if sha(ROOT / state["source"]) != state["artifact_sha256"]:
                raise RuntimeError("Indexed artifact changed: " + campaign + "/" + key)
    entries = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                "sha256": sha(path)} for path in files]
    output = HERE / "UPLOAD_MANIFEST.json"
    if output.exists():
        previous = read(output)
        if previous["files"] != entries:
            raise RuntimeError("Upload scope changed; inspect before rebuilding")
    else:
        write(output, {"scope": "Audited 2026-11-01 completion bundle; SHA-verified terminal experiment outcomes and historical retry sidecars; E4 raw replay; one paper evidence table",
                       "excluded_index": "experiments/v5_kv_admission/smoke_attempt1/index.json (cancelled engineering attempt with changed artifact)",
                       "final_reconciliation_sha256": sha(reconciliation_path),
                       "file_count": len(entries), "total_bytes": sum(row["bytes"] for row in entries),
                       "files": entries})
    print({"file_count": len(entries), "total_bytes": sum(row["bytes"] for row in entries),
           "manifest": str(output)})


if __name__ == "__main__":
    main()
