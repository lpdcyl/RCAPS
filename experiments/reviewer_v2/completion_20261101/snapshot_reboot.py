"""Save immutable controller state before resuming after a host reboot."""
from __future__ import annotations

import argparse
from pathlib import Path

from experiments.v5_core_supplement.run import now, read, sha, write

from .run import HERE, activated


def snapshot(campaign: str, incident: str) -> None:
    activated()
    base = HERE / campaign / "formal"
    index_path = base / "index.json"
    index = read(index_path)
    if index["status"] != "running":
        raise RuntimeError("Only a running index can be snapshotted")
    original = index_path.read_bytes()
    recovery = base / f"recovery_{incident}"
    recovery.mkdir(exist_ok=False)
    with (recovery / "original_index.json").open("xb") as stream:
        stream.write(original)
    interrupted = []
    for key, state in index["jobs"].items():
        if state["status"] != "running":
            continue
        folder = base / "runs" / key
        artifacts = {}
        for name in ("worker.log", "result.json", "failure.json"):
            path = folder / name
            if path.exists():
                artifacts[name] = sha(path)
        interrupted.append({"key": key, "pid": state.get("pid"),
                            "started_at": state.get("started_at"),
                            "artifacts_sha256": artifacts})
    write(recovery / "amendment.json", {
        "recorded_at": now(), "incident": incident,
        "original_index_sha256": sha(recovery / "original_index.json"),
        "manifest_sha256": index["manifest_sha256"],
        "original_controller_pid": index.get("controller_pid"),
        "interrupted": interrupted,
        "policy": "Original running attempt retained; resume only pending keys",
    })
    print(campaign, len(interrupted), recovery)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", choices=("e5a", "e6", "milp"))
    parser.add_argument("--incident", required=True)
    args = parser.parse_args()
    snapshot(args.campaign, args.incident)


if __name__ == "__main__":
    main()
