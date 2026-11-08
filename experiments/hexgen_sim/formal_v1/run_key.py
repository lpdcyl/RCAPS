"""Run one pre-registered HexGen simulator comparison key in its own process."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path

from experiments.hexgen_sim.evaluate import evaluate

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_key(key: str) -> dict:
    protocol = HERE / "manifest.json"
    frozen = json.loads(protocol.read_text(encoding="utf-8"))
    if key not in frozen["jobs"]:
        raise KeyError(key)
    for name, digest in frozen["sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen source changed: " + name)
    item = frozen["jobs"][key]
    layout = ROOT / item["layout_manifest"]
    trace_file = ROOT / item["trace_file"]
    if sha(layout) != item["layout_manifest_sha256"] or sha(trace_file) != item["trace_file_sha256"]:
        raise RuntimeError("Frozen layout or trace changed")
    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    if trace["trace_sha256"] != item["trace_sha256"]:
        raise RuntimeError("Trace hash metadata changed")
    destination = HERE / "runs" / key
    if (destination / "result.json").exists() or (destination / "failure.json").exists():
        raise FileExistsError(f"Existing formal artifact: {destination}")
    try:
        result = evaluate(layout, item["offered"], frozen["duration_s"],
                          frozen["warmup_s"], item["seed"],
                          trace_override=[tuple(row) for row in trace["entries"]])
        if result["trace_sha256"] != item["trace_sha256"]:
            raise AssertionError("Paired trace SHA mismatch")
        if result["arrivals"] != len(trace["entries"]):
            raise AssertionError("Arrival count mismatch")
        record = {"status": "success", "key": key,
                  "protocol_sha256": sha(protocol),
                  "layout_manifest_sha256": sha(layout),
                  "trace_file_sha256": sha(trace_file),
                  "result": result}
        write_once(destination / "result.json", record)
        return {"status": "success", "key": key,
                "result_sha256": sha(destination / "result.json"),
                "completion_fraction": result["completion_fraction"]}
    except BaseException as error:
        failure = {"status": "failure", "key": key,
                   "protocol_sha256": sha(protocol),
                   "exception": type(error).__name__, "message": str(error),
                   "traceback": traceback.format_exc()}
        write_once(destination / "failure.json", failure)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("key")
    args = parser.parse_args()
    print(json.dumps(run_key(args.key), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
