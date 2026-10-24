"""Independent consistency checks for the new Work3 development artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from work3_edge_admission.report import report as edge_report
from work3_joint_diagnostic.report import report as joint_report

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PARITY_KEYS = (
    "trace_sha256", "arrivals", "output_throughput_tokens_per_s", "ttft_p95_s",
    "tpot_p95_s", "completion_fraction", "backlog_at_window_end",
    "route_counts", "query_samples", "gpu_busy_fraction",
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    joint_report()
    edge_report()
    gate = read(ROOT / "work3_joint_diagnostic/runs/smoke/gate_seed170.json")
    mask = read(HERE / "runs/smoke/mask15_seed170.json")
    parity = {key: gate[key] == mask[key] for key in PARITY_KEYS}
    if not all(parity.values()):
        raise AssertionError(f"Static gate smoke parity failed: {parity}")
    failures = [str(path.relative_to(ROOT)) for root in
                (ROOT / "work3_joint_diagnostic", HERE)
                for path in root.rglob("*.failure.json")]
    if failures:
        raise AssertionError(f"Failure artifacts exist: {failures}")
    lp = {case: read(HERE / f"lp_probe_{case}.json")
          for case in ("C1_single", "C1_multi")}
    for case, row in lp.items():
        if abs(row["full_requests_per_s"] - row["canonical_requests_per_s"]) > 1e-9:
            raise AssertionError(f"LP graph capacity differs: {case}")
        if any(abs(item["increment_requests_per_s"]) > 1e-9 for item in row["candidates"]):
            raise AssertionError(f"LP single-edge marginal differs: {case}")
    selected = read(HERE / "analysis.json")["selected_mask"]
    if selected != 15:
        raise AssertionError(f"Unexpected frozen development decision: {selected}")
    outcome = {"static_gate_smoke_parity": parity, "selected_development_mask": selected,
               "lp_zero_marginals": {case: len(row["candidates"]) for case, row in lp.items()},
               "failure_files": failures, "status": "passed"}
    (HERE / "verification.json").write_text(
        json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(outcome, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
