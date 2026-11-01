"""One-key independent WSL2 replay; leaves the frozen E4 batch untouched."""
import json
from pathlib import Path

import bench
import traffic


HERE = Path(__file__).resolve().parent
DEST = HERE / "interrupted_replay_20261101"
KEY = "12p5MBps/priority/repeat0"
ORIGINAL = HERE / "runs" / KEY / "failure.json"


def main():
    if DEST.exists():
        raise RuntimeError(f"Independent replay already exists: {DEST}")
    if not ORIGINAL.exists() or traffic.read(ORIGINAL).get("classification") != "interrupted":
        raise RuntimeError("Original interrupted failure is missing or changed")
    frozen = traffic.read(traffic.MANIFEST)
    if traffic.sha(HERE / "bench.py") != frozen["scripts_sha256"]["bench.py"]:
        raise RuntimeError("Frozen benchmark script changed")
    if traffic.sha(HERE / "traffic.py") != frozen["scripts_sha256"]["traffic.py"]:
        raise RuntimeError("Frozen traffic script changed")
    if traffic.sha(traffic.TRAFFIC) != frozen["traffic_sha256"]:
        raise RuntimeError("Frozen traffic changed")
    all_traffic = traffic.read(traffic.TRAFFIC)
    repetition = next(x for x in all_traffic["repetitions"] if x["repeat"] == 0)
    DEST.mkdir()
    traffic.write(DEST / "manifest.json", {
        "key": KEY,
        "original_failure_sha256": traffic.sha(ORIGINAL),
        "original_manifest_sha256": traffic.sha(traffic.MANIFEST),
        "traffic_sha256": traffic.sha(traffic.TRAFFIC),
        "frozen_bench_sha256": traffic.sha(HERE / "bench.py"),
        "policy": "single independent retry; original batch remains unchanged",
    })
    bench.RUNS = DEST / "runs"
    namespace, device = bench.setup()
    try:
        bench.command(["tc", "qdisc", "replace", "dev", device, "root", "netem",
                       "delay", "25ms", "rate", "100mbit"])
        bench.qdisc_bytes(device)
        bench.command(["tc", "qdisc", "replace", "dev", device, "root", "netem",
                       "delay", "25ms", "rate", "100mbit"])
        outcome = bench.run_one(12.5, "priority", repetition, namespace, device,
                                all_traffic, frozen)
    finally:
        bench.teardown(namespace, device)
    folder = DEST / "runs" / KEY
    artifact = folder / ("result.json" if outcome == "completed" else "failure.json")
    traffic.write(DEST / "index.json", {
        "status": outcome,
        "key": KEY,
        "manifest_sha256": traffic.sha(DEST / "manifest.json"),
        "artifact": artifact.relative_to(DEST).as_posix(),
        "artifact_sha256": traffic.sha(artifact),
        "original_failure_sha256": traffic.sha(ORIGINAL),
    })
    print(json.dumps(traffic.read(DEST / "index.json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
