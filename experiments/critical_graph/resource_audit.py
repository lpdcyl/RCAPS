"""Check whether analytic route demand explains measured GPU busy ranks."""

from __future__ import annotations

import json
from pathlib import Path

from scipy.stats import spearmanr

from .model_audit import state_from_placement
from .partition import scenario
from .path_ensemble import measure as path_ensemble_measure
from .topology import TopologyModel


RUNS = Path(__file__).resolve().parent / "runs"


def rank_correlation(left: dict[int, float], right: dict[int, float]) -> float:
    keys = sorted(left)
    if keys != sorted(right):
        raise ValueError("GPU sets differ")
    return float(spearmanr([left[key] for key in keys],
                           [right[key] for key in keys]).statistic)


def top_keys(values: dict[int, float], count: int = 5) -> list[int]:
    return [key for key, _ in sorted(values.items(),
                                    key=lambda item: (-item[1], item[0]))[:count]]


def audit(name: str) -> dict:
    model = TopologyModel(scenario(name)[0])
    state = state_from_placement(RUNS / name / "placement.json")
    observed = json.loads((RUNS / name / "pilot_profile_seed1_240.json").read_text(
        encoding="utf-8"))
    if (observed["seed"], observed["duration_s"], observed["warmup_s"]) != (1, 300, 60):
        raise ValueError("Unexpected resource profile protocol")
    actual = {int(label.split("-")[1]) - 2: value
              for label, value in observed["gpu_busy_fraction"].items()}
    canonical = {node: 0.0 for node in model.types}
    for path in state["paths"]:
        for stage in model._stages(state, path):
            if stage["device"] == "sink":
                continue
            node = int(stage["device"])
            canonical[node] += 0.5 * max(
                stage["prefill_s"] / model.prompt_tokens,
                stage["decode_s"] / model.decode_batch)
    ensemble = path_ensemble_measure(model, state)
    expected = ensemble.gpu_demand_s
    return {
        "scenario": name, "seed": 1, "measurement_s": 240,
        "actual_top5": top_keys(actual),
        "canonical_top5": top_keys(canonical),
        "path_ensemble_top5": top_keys(expected),
        "canonical_rank_correlation": rank_correlation(canonical, actual),
        "path_ensemble_rank_correlation": rank_correlation(expected, actual),
        "canonical_top5_overlap": len(set(top_keys(canonical)) & set(top_keys(actual))),
        "path_ensemble_top5_overlap": len(set(top_keys(expected)) & set(top_keys(actual))),
        "path_ensemble_total_sink_probability": sum(
            value for edge, value in ensemble.edge_probability.items()
            if edge.endswith("->sink")),
    }


def main() -> None:
    report = {name: audit(name) for name in ("single", "multi")}
    output = RUNS / "resource_audit_seed1_240.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
