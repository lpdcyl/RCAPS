"""Read-only campaign audit; never dispatches or retries simulation windows."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import importlib

from experiments.v4_formal.run import validate as validate_main
from experiments.v4_external.run import validate as validate_external
from .build_report import ROOT, HERE, BATCHES, collect, digest, paired, read, write


def main():
    main_manifest = validate_main()
    external_manifest = validate_external()
    for name in BATCHES:
        if name.startswith("v4_recovery") and (ROOT / "experiments" / name / "index.json").exists():
            importlib.import_module(f"experiments.{name}.run").validate()
    rows, provenance, states = collect()
    campaign = {}
    for name in BATCHES:
        folder = ROOT / "experiments" / name
        if not (folder / "index.json").exists():
            continue
        manifest = read(folder / "manifest.json")
        index = read(folder / "index.json")
        expected = {j["key"]: j for j in manifest["jobs"]}
        assert set(index["jobs"]) <= set(expected)
        counts = Counter()
        for key, item in index["jobs"].items():
            counts[item["status"]] += 1
            output = folder / "runs" / key / "result.json"
            if item["status"] == "failed":
                assert item["exit_code"] != 0 and item["result_sha256"] is None
                assert not output.exists(), "Failed attempt must not have a replacement result"
            if item["status"] != "completed":
                continue
            row = read(output)
            assert row["seed"] == expected[key]["seed"] in (0, 1, 2)
            assert row["duration_s"] == 1800 and row["warmup_s"] == 0
            assert row["evaluation_protocol"] == "fixed_window_no_tail_drain"
            if name.startswith("v4_recovery"):
                assert row["manifest_sha256"] == manifest["core_manifest_sha256"]
                assert row["recovery_manifest_sha256"] == digest(folder / "manifest.json")
            else:
                assert row["manifest_sha256"] == digest(folder / "manifest.json")
            assert row["environment"] == main_manifest["environment"]
            assert row["arrivals"] == len(row["query_samples"])
            gpu = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
            assert abs(gpu - row["gpu_seconds_per_output_token"]) < 1e-10
        campaign[name] = {"counts": dict(counts), "unstarted": sorted(set(expected)-set(index["jobs"])),
                          "manifest_sha256": digest(folder / "manifest.json"),
                          "index_sha256": digest(folder / "index.json")}
    comparisons = []
    for sc, load in sorted({(k[0],k[1]) for k in rows}):
        cells = sorted({k[2] for k in rows if k[:2] == (sc,load)})
        if "v4" in cells:
            for cell in cells:
                if cell != "v4":
                    effect = paired(rows,sc,load,cell,"v4")
                    comparisons.append({"scenario":sc,"load":load,"baseline":cell,
                                        "paired_seeds":[p["seed"] for p in effect["seeds"]],
                                        "complete":effect["complete"]})
    log = ROOT / "experiments/v4_formal/runs/single/load700/static/seed1/worker.log"
    copy = HERE / "diagnostics/static_seed1_worker.txt"
    assert digest(log) == digest(copy)
    write(HERE / "diagnostics/integrity_audit.json", {
        "checked_at":datetime.now(timezone.utc).isoformat(), "status":"passed_for_recorded_checks",
        "scope":"File integrity, protocol fields, accounting and trace pairing; does not certify host stability or numerical correctness",
        "main_source_files":len(main_manifest["sources_sha256"]),
        "external_source_files":len(external_manifest["sources_sha256"]),
        "campaign":campaign,"trace_pairing":comparisons,
        "failure_worker_log_sha256":digest(log),
        "analysis_sha256":digest(HERE / "analysis.json"),
        "figures_visually_checked":["v4_load_curves.png","v4_factorial_320.png","v4_mechanism_320.png"]})
    print(json.dumps({"audit":"passed","completed":sum(s["completed"] for s in states.values()),
                      "pair_groups":len(comparisons),"complete_pair_groups":sum(c["complete"] for c in comparisons)}))


if __name__ == "__main__":
    main()
