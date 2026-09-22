from pathlib import Path

import pytest

from src.carbon.config import load_energy_provider
from src.carbon.model import (
    CarbonCostModel,
    ConfiguredLinearEnergyProvider,
)
from src.carbon.stage import StageWorkload, evaluate_stage_carbon
from src.carbon.trace import HistoricalCITraceLoader, RegionMappedCIProvider
from src.graph.serving_graph import ProfiledThroughputProvider, build_serving_graph
from src.optimizer.carbon_flow import solve_carbon_aware_flow


def _provider() -> ConfiguredLinearEnergyProvider:
    return ConfiguredLinearEnergyProvider(
        {
            "A100": {"prefill": {1: 0.20}, "decode": {1: 0.10}},
            "L4": {"prefill": {1: 0.10}, "decode": {1: 0.05}},
            "T4": {"prefill": {1: 0.16}, "decode": {1: 0.08}},
        }
    )


def _flow(phase1_topology, phase1_model, placement_a):
    throughput = ProfiledThroughputProvider(
        {gpu.gpu_type: {8: 220.0, 16: 120.0, 24: 82.0} for gpu in phase1_topology.gpus.values()}
    )
    serving = build_serving_graph(
        phase1_topology, phase1_model, placement_a, throughput
    )
    result = solve_carbon_aware_flow(
        serving,
        CarbonCostModel.build(
            phase1_topology,
            phase1_model,
            placement_a,
            _provider(),
            {"A": 100.0, "B": 200.0},
            phase="decode",
            batch_size=1,
        ),
        100.0,
    )
    return serving, result


def test_prefill_and_decode_can_have_different_energy(phase1_gpus, phase1_model) -> None:
    provider = _provider()
    assert provider.energy_joules_per_token(
        phase1_gpus[0], 0, 8, phase1_model, phase="prefill", batch_size=1
    ) == pytest.approx(1.6)
    assert provider.energy_joules_per_token(
        phase1_gpus[0], 0, 8, phase1_model, phase="decode", batch_size=1
    ) == pytest.approx(0.8)


def test_legacy_single_value_loader_maps_to_both_phases(tmp_path: Path) -> None:
    (tmp_path / "energy_profiles.yaml").write_text(
        "metadata:\n  tdp_used_as_energy_per_token: false\n"
        "provider: configured_linear\n"
        "gpu_types:\n  legacy:\n    joules_per_token: 0.25\n",
        encoding="utf-8",
    )
    provider, _ = load_energy_provider(tmp_path)
    assert provider.profiles["legacy"]["prefill"][1] == pytest.approx(0.25)
    assert provider.profiles["legacy"]["decode"][1] == pytest.approx(0.25)


def test_stage_carbon_is_linear_in_prefill_tokens(
    phase1_topology, phase1_model, placement_a
) -> None:
    serving, flow = _flow(phase1_topology, phase1_model, placement_a)
    first = evaluate_stage_carbon(
        serving,
        dict(flow.metrics.positive_flow_edges),
        flow.metrics.throughput,
        phase1_topology,
        phase1_model,
        placement_a,
        _provider(),
        {"A": 100.0, "B": 200.0},
        StageWorkload(2.0, 4.0),
        batch_size=1,
    )
    second = evaluate_stage_carbon(
        serving,
        dict(flow.metrics.positive_flow_edges),
        flow.metrics.throughput,
        phase1_topology,
        phase1_model,
        placement_a,
        _provider(),
        {"A": 100.0, "B": 200.0},
        StageWorkload(4.0, 4.0),
        batch_size=1,
    )
    assert second.prefill_carbon_g == pytest.approx(2.0 * first.prefill_carbon_g)
    assert second.decode_carbon_g == pytest.approx(first.decode_carbon_g)


def test_stage_carbon_is_linear_in_decode_tokens(
    phase1_topology, phase1_model, placement_a
) -> None:
    serving, flow = _flow(phase1_topology, phase1_model, placement_a)
    result = evaluate_stage_carbon(
        serving,
        dict(flow.metrics.positive_flow_edges),
        flow.metrics.throughput,
        phase1_topology,
        phase1_model,
        placement_a,
        _provider(),
        {"A": 100.0, "B": 200.0},
        StageWorkload(1.0, 8.0),
        batch_size=1,
    )
    doubled = evaluate_stage_carbon(
        serving,
        dict(flow.metrics.positive_flow_edges),
        flow.metrics.throughput,
        phase1_topology,
        phase1_model,
        placement_a,
        _provider(),
        {"A": 100.0, "B": 200.0},
        StageWorkload(1.0, 16.0),
        batch_size=1,
    )
    assert doubled.decode_carbon_g == pytest.approx(2.0 * result.decode_carbon_g)


def test_same_stage_values_match_decode_legacy_carbon(
    phase1_topology, phase1_model, placement_a
) -> None:
    provider = ConfiguredLinearEnergyProvider(
        {
            "A100": {"prefill": {1: 0.10}, "decode": {1: 0.10}},
            "L4": {"prefill": {1: 0.05}, "decode": {1: 0.05}},
            "T4": {"prefill": {1: 0.08}, "decode": {1: 0.08}},
        }
    )
    serving, flow = _flow(phase1_topology, phase1_model, placement_a)
    stage = evaluate_stage_carbon(
        serving,
        dict(flow.metrics.positive_flow_edges),
        flow.metrics.throughput,
        phase1_topology,
        phase1_model,
        placement_a,
        provider,
        {"A": 100.0, "B": 200.0},
        StageWorkload(0.0, 10.0),
        batch_size=1,
    )
    legacy = flow.metrics.carbon_g_per_1000_tokens / 1000.0 * 10.0
    assert stage.total_carbon_g == pytest.approx(legacy)


def test_historical_loader_standard_format_and_mapping(tmp_path: Path) -> None:
    path = tmp_path / "historical.csv"
    path.write_text(
        "timestamp,region,carbon_intensity_g_per_kwh\n"
        "2025-01-01T00:00:00Z,GB,50\n"
        "2025-01-01T00:30:00Z,GB,100\n",
        encoding="utf-8",
    )
    provider = HistoricalCITraceLoader.from_csv(path)
    mapped = RegionMappedCIProvider(provider, {"A": "GB", "B": "GB"})
    assert mapped.get_ci("A", 1735689600.0) == pytest.approx(50.0)
    assert mapped.get_ci("B", 1735691400.0) == pytest.approx(100.0)
