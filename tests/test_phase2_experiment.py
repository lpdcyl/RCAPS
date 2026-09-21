from pathlib import Path

import pytest

from conftest import CONFIG_DIR
from experiments.exp_ci_sweep import run_ci_sweep
from src.carbon.config import load_energy_provider, load_phase2_experiment


def test_energy_config_is_explicit_simulator_assumption() -> None:
    provider, metadata = load_energy_provider(CONFIG_DIR)
    assert provider.description.startswith("Configured operational-energy proxy")
    assert metadata["parameter_status"] == "simulator_assumption_not_hardware_measurement"
    assert metadata["tdp_used_as_energy_per_token"] is False


def test_phase2_ci_sweep_configuration() -> None:
    config = load_phase2_experiment(CONFIG_DIR)
    assert config.throughput_ratio_rho == pytest.approx(0.95)
    assert config.sweep_values == tuple(float(value) for value in range(50, 801, 50))
    assert config.fixed_carbon_intensity == {"B": 200.0}


def test_phase2_sweep_outputs_and_flow_transition(tmp_path: Path) -> None:
    outputs = run_ci_sweep(CONFIG_DIR, output_dir=tmp_path)
    summary = outputs.summary
    assert len(summary) == 16
    assert all(
        throughput == pytest.approx(104.5)
        for throughput in summary["throughput"]
    )
    assert (summary["carbon_cost_g_per_second"] <= summary["reference_carbon_g_per_second"] + 1e-12).all()
    share_columns = [
        column for column in summary if column.startswith("carbon_path_")
    ]
    assert share_columns
    assert all(
        total == pytest.approx(1.0)
        for total in summary[share_columns].sum(axis=1)
    )
    assert len(summary[share_columns].drop_duplicates()) > 1
    assert outputs.summary_csv.is_file()
    assert outputs.path_csv.is_file()
    assert outputs.flow_share_figure.is_file()
    assert outputs.flow_share_figure.stat().st_size > 0
