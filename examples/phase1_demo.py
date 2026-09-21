"""Run the three accepted Phase 1 numerical validation cases."""

from __future__ import annotations

from pathlib import Path

from src.simulator.simulator import SimulationRun, run_all_validation_cases


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"


def _pass_fail(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _print_run(run: SimulationRun) -> None:
    result = run.result
    print(f"\nValidation case: {run.case.name}")
    print(f"Placement: {run.case.placement_name}")
    print(f"Network topology: {run.case.network_topology_file}")
    print(f"Throughput model: {run.serving_graph.throughput_model}")
    print(f"\nMax flow: {result.max_flow_value:.3f} token/s")
    print(f"Min cut: {result.min_cut_value:.3f} token/s")

    print("\nPositive flow edges:")
    for edge, flow in result.positive_flow_edges.items():
        capacity = result.edge_capacities[edge]
        utilization = result.edge_utilization[edge]
        edge_type = result.edge_types[edge]
        print(
            f"  {edge[0]:>12} -> {edge[1]:<12} "
            f"flow={flow:8.3f} capacity={capacity:9.3f} "
            f"utilization={utilization:6.1%} type={edge_type}"
        )

    print("\nMin-cut edges:")
    for edge, capacity in result.cut_edges.items():
        edge_type = result.edge_types[edge]
        print(
            f"  {edge[0]:>12} -> {edge[1]:<12} "
            f"capacity={capacity:8.3f} type={edge_type}"
        )

    print(f"\nFlow conservation: {_pass_fail(result.conservation_check)}")
    print(
        "Capacity constraints: "
        f"{_pass_fail(result.capacity_constraints_check)}"
    )
    print(f"Max-flow == Min-cut: {_pass_fail(result.max_flow_min_cut_check)}")


def main() -> None:
    """Execute and print every YAML-defined validation case."""

    print("=== Phase 1: Helix-style Max-Flow Simulator ===")
    for run in run_all_validation_cases(CONFIG_DIR):
        _print_run(run)


if __name__ == "__main__":
    main()
