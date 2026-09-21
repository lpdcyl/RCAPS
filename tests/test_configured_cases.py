import pytest

from conftest import CONFIG_DIR
from src.simulator.simulator import load_simulation_inputs, run_all_validation_cases


def test_yaml_defaults_to_analytical_provider() -> None:
    inputs = load_simulation_inputs(CONFIG_DIR)
    assert inputs.throughput_provider.description == "Simulator analytical approximation"
    assert inputs.allow_partial_inference is False
    assert inputs.random_seed == 0


def test_all_configured_validation_cases() -> None:
    runs = run_all_validation_cases(CONFIG_DIR)
    values = {
        run.case.name: (run.result.max_flow_value, run.result.min_cut_value)
        for run in runs
    }
    assert values == {
        "placement_a_cross_30": pytest.approx((110, 110)),
        "placement_b_cross_30": pytest.approx((100, 100)),
        "placement_a_cross_20": pytest.approx((80, 80)),
    }
