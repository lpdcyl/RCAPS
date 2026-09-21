import pytest

from src.carbon.model import (
    JOULES_PER_KWH,
    CarbonCostModel,
    ConfiguredLinearEnergyProvider,
    ConstantCIProvider,
    MissingEnergyProfileError,
    MultipliedEnergyProvider,
    operational_carbon_g,
)


@pytest.fixture
def energy_provider() -> ConfiguredLinearEnergyProvider:
    return ConfiguredLinearEnergyProvider(
        {
            "A100": {"decode": {1: 0.100}},
            "L4": {"decode": {1: 0.055}},
            "T4": {"decode": {1: 0.085}},
        }
    )


def test_configured_energy_scales_with_layer_count(
    energy_provider, phase1_gpus, phase1_model
) -> None:
    a100 = phase1_gpus[0]
    assert energy_provider.energy_joules_per_token(
        a100, 0, 16, phase1_model, phase="decode", batch_size=1
    ) == pytest.approx(1.6)
    assert energy_provider.energy_joules_per_token(
        a100, 0, 8, phase1_model, phase="decode", batch_size=1
    ) == pytest.approx(0.8)
    assert energy_provider.energy_joules_per_token_for_layer_count(
        a100, 16, phase="decode", batch_size=1
    ) == pytest.approx(1.6)


def test_missing_energy_profile_raises(
    energy_provider, phase1_gpus, phase1_model
) -> None:
    with pytest.raises(MissingEnergyProfileError, match="batch_size=4"):
        energy_provider.energy_joules_per_token(
            phase1_gpus[0],
            0,
            16,
            phase1_model,
            phase="decode",
            batch_size=4,
        )


def test_carbon_cost_uses_physical_unit_conversion(
    energy_provider, phase1_topology, phase1_model, placement_a
) -> None:
    model = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        {"A": 100.0, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    expected = 100.0 * 1.6 / JOULES_PER_KWH
    assert model.carbon_g_per_token("c1") == pytest.approx(expected)
    assert model.accounting_scope == "operational GPU-compute carbon proxy"


def test_exact_joules_to_kwh_carbon_conversion() -> None:
    assert operational_carbon_g(3_600_000.0, 1.0) == pytest.approx(1.0)


def test_doubling_ci_doubles_carbon_cost(
    energy_provider, phase1_topology, phase1_model, placement_a
) -> None:
    low = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        {"A": 100.0, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    high = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        {"A": 200.0, "B": 400.0},
        phase="decode",
        batch_size=1,
    )
    for gpu_id in phase1_topology.gpus:
        assert high.carbon_g_per_token(gpu_id) == pytest.approx(
            2.0 * low.carbon_g_per_token(gpu_id)
        )


def test_doubling_energy_doubles_carbon_cost(
    energy_provider, phase1_topology, phase1_model, placement_a
) -> None:
    base = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        {"A": 100.0, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    doubled_energy = MultipliedEnergyProvider(
        energy_provider,
        {"A100": 2.0, "L4": 2.0, "T4": 2.0},
    )
    doubled = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        doubled_energy,
        {"A": 100.0, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    for gpu_id in phase1_topology.gpus:
        assert doubled.carbon_g_per_token(gpu_id) == pytest.approx(
            2.0 * base.carbon_g_per_token(gpu_id)
        )


def test_equal_energy_region_cost_ratio_matches_ci_ratio(
    energy_provider, phase1_topology, phase1_model, placement_a
) -> None:
    model = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        {"A": 100.0, "B": 250.0},
        phase="decode",
        batch_size=1,
    )
    assert model.gpu_costs["c1"].energy_joules_per_token == pytest.approx(
        model.gpu_costs["c4"].energy_joules_per_token
    )
    assert model.carbon_g_per_token("c4") / model.carbon_g_per_token(
        "c1"
    ) == pytest.approx(2.5)


def test_constant_ci_provider_rejects_unknown_region() -> None:
    provider = ConstantCIProvider({"A": 100.0})
    assert provider.get_ci("A") == provider.get_ci("A", timestamp=999.0) == 100.0
    with pytest.raises(ValueError, match="Missing carbon intensity.*'B'"):
        provider.get_ci("B")


def test_mapping_and_constant_provider_are_numerically_identical(
    energy_provider, phase1_topology, phase1_model, placement_a
) -> None:
    intensities = {"A": 100.0, "B": 200.0}
    mapping_model = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        intensities,
        phase="decode",
        batch_size=1,
    )
    provider_model = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        ConstantCIProvider(intensities),
        phase="decode",
        batch_size=1,
    )
    for gpu_id in phase1_topology.gpus:
        assert abs(
            mapping_model.carbon_g_per_token(gpu_id)
            - provider_model.carbon_g_per_token(gpu_id)
        ) <= 1e-12


def test_provider_is_resolved_once_per_region_per_model_build(
    energy_provider, phase1_topology, phase1_model, placement_a
) -> None:
    class CountingProvider:
        def __init__(self) -> None:
            self.calls: list[tuple[str, float | None]] = []

        def get_ci(self, region: str, timestamp: float | None = None) -> float:
            self.calls.append((region, timestamp))
            return {"A": 100.0, "B": 200.0}[region]

    provider = CountingProvider()
    CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        provider,
        phase="decode",
        batch_size=1,
        timestamp=123.0,
    )
    assert provider.calls == [("A", 123.0), ("B", 123.0)]


def test_low_ci_inefficient_gpu_is_not_automatically_cheapest(
    energy_provider, phase1_topology, phase1_model, placement_a
) -> None:
    model = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement_a,
        energy_provider,
        {"A": 100.0, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    # T4 in lower-carbon Region A: 1.36 J/token * 100 g/kWh.
    # L4 in higher-carbon Region B: 0.88 J/token * 200 g/kWh.
    assert model.carbon_g_per_token("c3") < model.carbon_g_per_token("c5")
    # The comparison is driven by CI * energy, not CI alone.
    assert model.gpu_costs["c3"].energy_joules_per_token > model.gpu_costs["c5"].energy_joules_per_token
