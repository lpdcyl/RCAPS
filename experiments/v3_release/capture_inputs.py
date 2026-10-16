"""Capture the audited M2 seed and reference states for the V3 release."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.m2_multistage_candidate.prepare import files, legacy_state, reference_state
from rcaps.placement.topology import TopologyModel

from .verify import CASES, ROOT, digest


def main() -> None:
    captured = {}
    for case, scenario in CASES.items():
        physical, template, _ = files(case)
        model = TopologyModel(physical)
        seed = legacy_state(case, model)
        reference = reference_state(case, model, seed)
        captured[case] = {
            "scenario": scenario,
            "physical": str(physical.relative_to(ROOT)).replace("\\", "/"),
            "physical_sha256": digest(physical),
            "template": str(template.relative_to(ROOT)).replace("\\", "/"),
            "template_sha256": digest(template),
            "seed_state": seed,
            "reference_state": reference,
        }
    destination = ROOT / "rcaps/v3/planning_inputs.json"
    encoded = json.dumps(captured, indent=2) + "\n"
    if destination.exists() and destination.read_text(encoding="utf-8") != encoded:
        raise ValueError("Frozen V3 planning inputs differ from captured candidate")
    destination.write_text(encoded, encoding="utf-8")
    print(f"Captured {len(captured)} V3 planning cases")


if __name__ == "__main__":
    main()
