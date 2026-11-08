"""Freeze all five 700-token/s keys under the debug-allocator runtime."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TRACE_DIR = ROOT / "experiments/hexgen_e2e/traces"
SELECTIONS = {
    "single": ROOT / "experiments/hexgen_sim/development/slo_v2/single24_r2/SELECTION.json",
}
CONDITIONS = {"single": (700,)}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "manifest.json"
    if output.exists():
        raise FileExistsError(output)
    selected = {}
    for case, source in SELECTIONS.items():
        record = json.loads(source.read_text(encoding="utf-8"))
        if record["status"] != "development_selection" or record["success_count"] < 1:
            raise RuntimeError("Invalid development selection: " + case)
        layout = Path(record["selected_manifest"])
        if not layout.is_absolute():
            layout = ROOT / layout
        if not layout.is_file():
            raise FileNotFoundError(layout)
        selected[case] = {"selection_file": source.relative_to(ROOT).as_posix(),
                          "selection_sha256": sha(source),
                          "layout_manifest": layout.relative_to(ROOT).as_posix(),
                          "layout_manifest_sha256": sha(layout)}
    trace_manifest = json.loads((TRACE_DIR / "manifest_v2.json").read_text(encoding="utf-8"))
    if trace_manifest["duration_s"] != 1800 or trace_manifest["warmup_s"] != 0:
        raise RuntimeError("Frozen trace protocol differs")
    trace_index = {job["key"]: job for job in trace_manifest["jobs"]}
    jobs = {}
    for case, loads in CONDITIONS.items():
        for offered in loads:
            for seed in range(5):
                key = f"{case}_load{offered}_seed{seed}"
                entry = trace_index[key]
                trace_file = TRACE_DIR / entry["file"]
                if sha(trace_file) != entry["file_sha256"]:
                    raise RuntimeError("Frozen trace file differs: " + key)
                jobs[key] = {**selected[case], "scenario": case,
                             "offered": offered, "seed": seed,
                             "trace_file": trace_file.relative_to(ROOT).as_posix(),
                             "trace_file_sha256": entry["file_sha256"],
                             "trace_sha256": entry["trace_sha256"],
                             "requests": entry["requests"]}
    code = [HERE / "run_key.py", HERE / "register.py", HERE / "controller.py",
            ROOT / "experiments/hexgen_sim/evaluate_v2.py",
            ROOT / "experiments/hexgen_sim/admission_scheduler_v2.py",
            ROOT / "experiments/hexgen_sim/evaluate.py",
            ROOT / "experiments/hexgen_sim/hexgen_layout.py",
            ROOT / "experiments/hexgen_sim/slo_search_v2.py",
            ROOT / "benchmarks/fixed_window.py", ROOT / "benchmarks/accumulator.py",
            ROOT / "benchmarks/layout.py", ROOT / "baselines/separate.py"]
    code += [p for p in (ROOT / "simulator").rglob("*.py")
             if "__pycache__" not in p.parts]
    sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(code))}
    record = {"status": "registered", "method": "HexGen simulator adaptation with capacity-safe FIFO admission",
              "paper": "https://proceedings.mlr.press/v235/jiang24f.html",
              "official_source_commit": "949414d1be18e504752508c0559cb966ddf999f4",
              "execution": "CPU discrete-event simulator; full-model PP replicas; round-robin pipeline assignment; capacity-safe FIFO admission",
              "scope": "24-node single-cluster 700 token/s condition, all five seeds; independent formal runtime diagnosis",
              "previous_protocol": "experiments/hexgen_sim/formal_v2/manifest.json",
              "previous_protocol_sha256": sha(ROOT / "experiments/hexgen_sim/formal_v2/manifest.json"),
              "v2_failure_audit_sha256": sha(ROOT / "experiments/hexgen_sim/formal_v2/FINAL_AUDIT.json"),
              "runtime_environment": {"PYTHONMALLOC": "debug", "PYTHONFAULTHANDLER": "1"},
              "duration_s": 1800, "warmup_s": 0,
              "development_seeds": [100, 101], "formal_seeds": [0, 1, 2, 3, 4],
              "conditions": CONDITIONS, "python_version": sys.version.split()[0],
              "numpy_version": np.__version__,
              "known_adaptation": ["GA group search is memory-degenerate on 24 nodes",
                                   "node ordering is greedy and layer allocation uses DP",
                                   "candidate fitness uses fixed-window SLO goodput rather than AlpaServe estimator",
                                   "FIFO admission reserves each admitted query's full input+output KV budget until completion"],
              "trace_manifest_sha256": sha(TRACE_DIR / "manifest_v2.json"),
              "sources_sha256": sources, "jobs": jobs}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(output), "jobs": len(jobs),
                      "sources": len(sources), "sha256": sha(output)}, indent=2))


if __name__ == "__main__":
    main()
