"""Replay a frozen V3 M2 search without touching adopted layouts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .topology import TopologyModel

from .placement import normalize, save, validate
from .search import search


ROOT = Path(__file__).resolve().parents[2]
INPUTS = Path(__file__).with_name("planning_inputs.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(case: str, destination: Path) -> dict:
    cases = json.loads(INPUTS.read_text(encoding="utf-8"))
    if case not in cases:
        raise ValueError(f"Unknown V3 planning case: {case}")
    item = cases[case]
    physical, template = ROOT / item["physical"], ROOT / item["template"]
    if digest(physical) != item["physical_sha256"] or digest(
            template) != item["template_sha256"]:
        raise ValueError("Frozen V3 planning resource inputs changed")
    model = TopologyModel(physical)
    seed, reference = normalize(item["seed_state"]), normalize(item["reference_state"])
    validate(model, seed)
    validate(model, reference)
    result = search(model, reference, a100_prefix=False, seed_state=seed)["multi"]
    if result["status"] != "feasible":
        raise ValueError(f"V3 search found no feasible layout for {case}")
    metadata = {key: value for key, value in result.items()
                if key not in ("state", "status")}
    metadata.update({"version": "RCAPS V3", "candidate_variant": "multi_any",
                     "case": case})
    return save(model, template, result["state"], destination, metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=json.loads(INPUTS.read_text(encoding="utf-8")))
    parser.add_argument("--output", type=Path, required=True,
                        help="A separate output directory; adopted layouts are never overwritten")
    args = parser.parse_args()
    if args.output.resolve().is_relative_to((ROOT / "rcaps/v3_layouts").resolve()):
        parser.error("Do not overwrite the adopted V3 layouts")
    result = replay(args.case, args.output)
    print(args.case, result["widths"], result["solution_sha256"],
          result["sim_cluster_sha256"])


if __name__ == "__main__":
    main()
