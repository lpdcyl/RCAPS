"""Replan all frozen resource pools and compare byte-identical deployments."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from rcaps.v3.plan import replay

from .verify import CASES, MANIFEST


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = []
    with TemporaryDirectory(prefix="rcaps-v3-replay-") as temporary:
        for case, scenario in CASES.items():
            destination = Path(temporary) / case
            replanned = replay(case, destination)
            frozen = manifest["layouts"][scenario]
            status = (replanned["solution_sha256"] == frozen["solution_sha256"]
                      and replanned["sim_cluster_sha256"] ==
                      frozen["sim_cluster_sha256"])
            if not status:
                raise ValueError(f"V3 search replay differs from frozen layout: {case}")
            rows.append({"case": case, "scenario": scenario,
                         "status": "byte_identical",
                         "solution_sha256": replanned["solution_sha256"],
                         "sim_cluster_sha256": replanned["sim_cluster_sha256"],
                         "candidate_evaluations": replanned["candidate_evaluations"]})
            print(case, "byte-identical", flush=True)
    destination = Path(__file__).with_name("replay_audit.json")
    encoded = json.dumps(rows, indent=2) + "\n"
    if destination.exists() and destination.read_text(encoding="utf-8") != encoded:
        raise ValueError("Saved V3 replay audit differs")
    destination.write_text(encoded, encoding="utf-8")
    print(f"V3 M2 replay passed for {len(rows)} resource pools")


if __name__ == "__main__":
    main()
