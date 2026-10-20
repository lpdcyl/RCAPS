"""Align completed formal600 result metadata after a non-executed profile-path edit."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> None:
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    for path in (HERE / "runs/formal600").rglob("*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("phase") != "formal600":
            raise ValueError(f"Unexpected result file: {path}")
        # The changed code only removed an aborted profile600 execution path;
        # formal600 always passed profile_resources=False.
        row["runtime_sha256"] = plan["runtime_sha256"]
        row["metadata_migration"] = {
            "reason": "Removed unused profile600 execution path after formal600 completed.",
            "formal600_execution_changed": False,
        }
        path.write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


if __name__ == "__main__":
    main()
