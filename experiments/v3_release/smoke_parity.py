"""Check that the V3 adapter reproduces candidate seed-100 execution."""

from __future__ import annotations

import json
from pathlib import Path

from .verify import ROOT, digest


FIELDS = (
    "trace_sha256", "solution_sha256", "sim_cluster_sha256",
    "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
    "completion_fraction", "backlog_at_window_end", "route_counts",
    "query_samples",
)


def main() -> None:
    records = []
    for scenario in ("single", "multi"):
        source = (ROOT / "experiments/m2_multistage_candidate/runs/smoke" /
                  f"C1_{scenario}/seed100/multi_any.json")
        target = (ROOT / "experiments/v3_release/smoke" /
                  scenario / "seed100/rcaps_v3.json")
        original = json.loads(source.read_text(encoding="utf-8"))
        released = json.loads(target.read_text(encoding="utf-8"))
        for field in FIELDS:
            if original[field] != released[field]:
                raise ValueError(f"V3 smoke differs from candidate: {scenario}/{field}")
        records.append({"scenario": scenario,
                        "source": str(source.relative_to(ROOT)).replace("\\", "/"),
                        "source_sha256": digest(source),
                        "v3": str(target.relative_to(ROOT)).replace("\\", "/"),
                        "v3_sha256": digest(target),
                        "checked_fields": list(FIELDS), "status": "identical"})
    destination = Path(__file__).with_name("smoke_parity.json")
    encoded = json.dumps(records, indent=2) + "\n"
    if destination.exists() and destination.read_text(encoding="utf-8") != encoded:
        raise ValueError("Saved V3 smoke parity record differs")
    destination.write_text(encoded, encoding="utf-8")
    print("V3 candidate smoke parity: single and multi passed")


if __name__ == "__main__":
    main()
