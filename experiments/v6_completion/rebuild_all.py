"""Rebuild every paper-facing table, figure and audit from frozen raw outputs."""
from __future__ import annotations

import importlib
import zipfile
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, check, now, read, sha, write

HERE = Path(__file__).resolve().parent
CAMPAIGNS = ("robustness", "generalization", "session_cost", "session_capacity",
             "weight_online", "bandwidth_threshold", "scalability", "failure_replay")


def audit_inputs():
    records = []
    for name in CAMPAIGNS:
        folder = HERE / name / "formal"
        manifest, index = read(folder / "manifest.json"), read(folder / "index.json")
        assert index["status"] == "terminal", name
        assert index["manifest_sha256"] == sha(folder / "manifest.json"), name
        check(manifest)
        archive = read(folder / "frozen_runtime_archive.json")
        archive_path = folder / "frozen_runtime_inputs.zip"
        assert archive["sha256"] == sha(archive_path), name
        assert archive["manifest_sha256"] == sha(folder / "manifest.json"), name
        with zipfile.ZipFile(archive_path) as z:
            assert set(z.namelist()) == set(manifest["sources_sha256"]), name
        for job in manifest["jobs"]:
            entry = index["jobs"][job["key"]]
            assert entry["status"] in ("completed", "failed"), (name, job["key"])
            assert sha(ROOT / entry["source"]) == entry["artifact_sha256"]
        records.append(dict(campaign=name, jobs=len(manifest["jobs"]),
                            manifest_sha256=sha(folder / "manifest.json"),
                            index_sha256=sha(folder / "index.json"),
                            archive_sha256=sha(archive_path)))
    return records


def main():
    inputs = audit_inputs()
    from experiments.v5_core_supplement.rebuild_supplements import main as old_rebuild
    print("REBUILD v5_supplements", flush=True)
    old_rebuild()
    from experiments.v5_failure_replay.run import report as replay_report
    from experiments.v5_failure_replay.analyze import main as replay_causes
    replay_report()
    replay_causes()
    from experiments.v6_completion.weight_search import report as weight_search_report
    weight_search_report()
    outputs = []
    for name in CAMPAIGNS:
        module = importlib.import_module("experiments.v6_completion." + name)
        print("REBUILD", name, flush=True)
        module.report()
        result = HERE / name / "FINAL_AUDIT.json"
        assert read(result)["passed"], name
        outputs.append(dict(name=name, audit_sha256=sha(result),
                            result_sha256=sha(HERE / name / "RESULTS_CN.md")))
    from experiments.v6_completion.session_batch_report import main as batch_report
    batch_report()
    assert read(HERE / "session_cost/BATCH_AUDIT.json")["passed"]
    assert read(HERE / "failure_replay/FINAL_AUDIT.json")["passed"]
    from experiments.v6_completion.figures import main as figures
    figures()
    write(HERE / "REBUILD_AUDIT.json", dict(passed=True, rebuilt_at=now(),
          scope="CPU simulator evidence only; real-machine P1-2 and P2-3 excluded",
          inputs=inputs, outputs=outputs,
          failure_replay_audit_sha256=sha(ROOT / "experiments/v5_failure_replay/FINAL_AUDIT.json"),
          figure_audit_sha256=sha(HERE / "figures/FINAL_AUDIT.json")))
    print("ALL_REGISTERED_SIMULATION_EVIDENCE_REBUILT", flush=True)


if __name__ == "__main__":
    main()
