"""Recheck paired metrics and record the preserved seed-2 execution failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from work3_chunk_012.report import report
from work3_chunk_012.run import AUDIT, HERE, PROTOCOL, digest, freeze, write


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    freeze()
    report()
    analysis = read(HERE / "analysis.json")
    failure_path = HERE / "runs" / "chunk_4MiB_seed2.failure.json"
    if not failure_path.exists():
        raise AssertionError("Preserved seed-2 failure artifact is missing")
    failure = read(failure_path)
    if failure["seed"] != 2 or "coroutine" not in failure["error"]:
        raise AssertionError("Preserved failure identity differs")
    diagnostic = read(HERE / "diagnostic_seed2.json")
    result = read(HERE / "runs" / "chunk_4MiB_seed2.json")
    parity = {key: diagnostic[key] == result[key] for key in
              ("trace_sha256", "arrivals", "tpot_p95_s", "output_throughput_tokens_per_s")}
    if not all(parity.values()):
        raise AssertionError("Isolated completed seed-2 diagnostic differs")
    if not analysis["known_seed_joint_gate_passed"]:
        raise AssertionError("Successful windows failed the frozen numeric gate")
    rows = analysis["rows"]
    if [row["seed"] for row in rows] != PROTOCOL["seeds"]:
        raise AssertionError("Seed list differs")
    means = {name: sum(row["versus_gate"][name] for row in rows) / len(rows)
             for name in ("tpot_relative", "common_tpot_relative", "ttft_relative",
                          "throughput_relative", "gpu_work_relative")}
    outcome = {"protocol_sha256": digest(HERE / "protocol.json"),
               "audit_sha256": digest(AUDIT),
               "successful_window_numeric_gate_passed": True,
               "first_attempt_execution_clean": False,
               "unexplained_seed2_failures": 2,
               "preserved_latest_failure_sha256": hashlib.sha256(failure_path.read_bytes()).hexdigest(),
               "seed2_completed_diagnostic_parity": parity,
               "mean_relative_to_gate": means,
               "status": "numeric_pass_with_execution_instability_disclosed"}
    write(HERE / "verification.json", outcome)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
