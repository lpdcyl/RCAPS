"""Carbon-aware routing on an automatically optimized Helix placement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from experiments.phase3_common import (
    carbon_intensities,
    json_edge_mapping,
    json_float_mapping,
    load_phase3_context,
    solve_helix_baseline,
)
from src.analysis.breakpoint import placement_signature, serialize_placement_signature
from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import build_serving_graph
from src.optimizer.carbon_flow import solve_carbon_aware_flow


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"


@dataclass(frozen=True, slots=True)
class HelixRoutingOutputs:
    summary: pd.DataFrame
    summary_csv: Path


def run_helix_carbon_routing(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path | None = None,
) -> HelixRoutingOutputs:
    """Solve one carbon-independent Helix placement, then sweep routing."""

    context = load_phase3_context(config_dir)
    config = context.config
    helix = solve_helix_baseline(context)
    placement = helix.placement
    signature = placement_signature(placement)
    serving = build_serving_graph(
        context.topology,
        context.simulation.model,
        placement,
        context.throughput_provider,
    )
    target = config.throughput_ratio_rho * helix.validated_max_flow
    rows: list[dict[str, object]] = []
    for sweep_value in config.sweep_values:
        intensities = carbon_intensities(config, sweep_value)
        carbon_model = CarbonCostModel.build(
            context.topology,
            context.simulation.model,
            placement,
            context.energy_provider,
            intensities,
            phase=config.phase,
            batch_size=config.batch_size,
        )
        routing = solve_carbon_aware_flow(serving, carbon_model, target)
        ci_a = float(intensities["A"])
        ci_b = float(intensities["B"])
        rows.append(
            {
                "ci_a": ci_a,
                "ci_b": ci_b,
                "ci_ratio": ci_a / ci_b,
                "helix_placement_id": placement.name,
                "helix_placement_signature": serialize_placement_signature(signature),
                "helix_layer_ranges": serialize_placement_signature(signature),
                "F_H": helix.validated_max_flow,
                "rho": config.throughput_ratio_rho,
                "F_target": target,
                "throughput": routing.metrics.throughput,
                "routing_carbon_g_per_second": routing.metrics.carbon_g_per_second,
                "routing_carbon_g_per_1000_tokens": routing.metrics.carbon_g_per_1000_tokens,
                "flow_share": json_float_mapping(routing.metrics.path_flow_share),
                "active_edges": json_edge_mapping(routing.metrics.positive_flow_edges),
                "routing_solver_time_seconds": routing.solver_time_seconds,
                "helix_solver_time_seconds": helix.solver_time_seconds,
            }
        )
    summary = pd.DataFrame(rows)
    destination = (
        PROJECT_ROOT / config.helix_routing_csv
        if output_dir is None
        else Path(output_dir) / Path(config.helix_routing_csv).name
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(destination, index=False)
    return HelixRoutingOutputs(summary, destination)


def main() -> None:
    outputs = run_helix_carbon_routing()
    summary = outputs.summary
    print("=== Helix Placement + Carbon-Aware Routing ===")
    print(f"Helix placement: {summary.iloc[0]['helix_placement_id']}")
    print(f"F_H: {summary.iloc[0]['F_H']:.3f} token/s")
    print(f"CI points: {len(summary)}")
    print(f"CSV: {outputs.summary_csv}")


if __name__ == "__main__":
    main()
