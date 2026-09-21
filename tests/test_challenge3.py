from pathlib import Path

import pytest

from src.carbon.model import CarbonCostModel, ConfiguredLinearEnergyProvider
from src.carbon.trace import TraceCIProvider
from src.graph.serving_graph import build_serving_graph
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.scheduler.carbon_flow_scheduler import CarbonFlowScheduler
from src.scheduler.request_dispatcher import (
    DeterministicQuotaDispatcher,
    Request,
)


def energy_provider() -> ConfiguredLinearEnergyProvider:
    return ConfiguredLinearEnergyProvider(
        {
            "A100": {"decode": {1: 0.100}},
            "L4": {"decode": {1: 0.055}},
            "T4": {"decode": {1: 0.085}},
        }
    )


def test_trace_provider_piecewise_boundaries_and_late_hold(tmp_path: Path) -> None:
    path = tmp_path / "trace.csv"
    path.write_text(
        "timestamp,region,carbon_intensity\n"
        "0,A,100\n0,B,200\n60,A,300\n60,B,50\n",
        encoding="utf-8",
    )
    provider = TraceCIProvider.from_csv(path)
    assert provider.get_ci("A", 0.0) == 100.0
    assert provider.get_ci("A", 59.9) == 100.0
    assert provider.get_ci("A", 60.0) == 300.0
    assert provider.get_ci("A", 600.0) == 300.0
    with pytest.raises(ValueError, match="precedes first"):
        provider.get_ci("A", -1.0)
    with pytest.raises(ValueError, match="Unknown"):
        provider.get_ci("C", 0.0)


def test_trace_provider_requires_timestamp() -> None:
    provider = TraceCIProvider.from_rows([(0.0, "A", 100.0)])
    with pytest.raises(ValueError, match="explicit timestamp"):
        provider.get_ci("A")


def test_constant_trace_scheduler_matches_static_flow(
    phase1_topology, phase1_model, placement_a
) -> None:
    provider = TraceCIProvider.from_rows([(0.0, "A", 100.0), (0.0, "B", 200.0)])
    energy = energy_provider()
    scheduler = CarbonFlowScheduler(
        phase1_topology,
        phase1_model,
        placement_a,
        _throughput_provider(phase1_topology),
        energy,
        provider,
        phase="decode",
        batch_size=1,
        scheduling_interval_seconds=60.0,
    )
    dynamic = scheduler.schedule(0.0, 100.0)
    serving = build_serving_graph(
        phase1_topology,
        phase1_model,
        placement_a,
        _throughput_provider(phase1_topology),
    )
    static_cost = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy,
        {"A": 100.0, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    static = solve_carbon_aware_flow(serving, static_cost, 100.0)
    assert dynamic.carbon_g_per_second == pytest.approx(
        static.metrics.carbon_g_per_second
    )
    assert dynamic.served_throughput == pytest.approx(100.0)


def _throughput_provider(topology):
    from src.graph.serving_graph import ProfiledThroughputProvider

    return ProfiledThroughputProvider(
        {
            gpu.gpu_type: {8: 220.0, 16: 120.0, 24: 82.0}
            for gpu in topology.gpus.values()
        }
    )


def test_step_trace_switches_flow_allocation(
    phase1_topology, phase1_model, placement_a
) -> None:
    provider = TraceCIProvider.from_rows(
        [
            (0.0, "A", 50.0),
            (0.0, "B", 800.0),
            (60.0, "A", 800.0),
            (60.0, "B", 50.0),
        ]
    )
    scheduler = CarbonFlowScheduler(
        phase1_topology,
        phase1_model,
        placement_a,
        _throughput_provider(phase1_topology),
        energy_provider(),
        provider,
        phase="decode",
        batch_size=1,
        scheduling_interval_seconds=60.0,
    )
    first = scheduler.schedule(0.0, 100.0)
    second = scheduler.schedule(60.0, 100.0)
    assert first.flow_result.metrics.path_flow_share != second.flow_result.metrics.path_flow_share
    assert first.flow_result.metrics.throughput == pytest.approx(100.0)
    assert second.flow_result.metrics.throughput == pytest.approx(100.0)


def test_scheduler_capacity_invariants_and_determinism(
    phase1_topology, phase1_model, placement_a
) -> None:
    provider = TraceCIProvider.from_rows([(0.0, "A", 200.0), (0.0, "B", 200.0)])
    kwargs = dict(
        topology=phase1_topology,
        model=phase1_model,
        placement=placement_a,
        throughput_provider=_throughput_provider(phase1_topology),
        energy_provider=energy_provider(),
        ci_source=provider,
        phase="decode",
        batch_size=1,
        scheduling_interval_seconds=60.0,
    )
    first = CarbonFlowScheduler(**kwargs).schedule(0.0, 100.0)
    second = CarbonFlowScheduler(**kwargs).schedule(0.0, 100.0)
    assert first.flow_result.metrics.path_flow_share == second.flow_result.metrics.path_flow_share
    for edge, flow in first.flow_result.metrics.positive_flow_edges.items():
        assert flow <= first.flow_result.edge_capacities[edge] + 1e-8


def test_dispatch_respects_quota_and_is_deterministic() -> None:
    requests = tuple(Request(f"r{index}") for index in range(10))
    first = DeterministicQuotaDispatcher(
        {"p1": 0.6, "p2": 0.4}, duration_seconds=10.0
    ).dispatch_batch(requests)
    second = DeterministicQuotaDispatcher(
        {"p1": 0.6, "p2": 0.4}, duration_seconds=10.0
    ).dispatch_batch(requests)
    assert first.decisions == second.decisions
    assert first.accepted_tokens == pytest.approx(10.0)
    assert first.rejected_tokens == pytest.approx(0.0)
    assert all(value >= -1e-9 for value in first.remaining_quota_tokens.values())


def test_dispatch_rejects_when_aggregate_quota_is_exhausted() -> None:
    result = DeterministicQuotaDispatcher(
        {"p1": 1.0}, duration_seconds=1.0
    ).dispatch_batch((Request("r1", 1.0), Request("r2", 1.0)))
    assert result.accepted_tokens == pytest.approx(1.0)
    assert result.rejected_tokens == pytest.approx(1.0)
    assert result.decisions[1].path is None
