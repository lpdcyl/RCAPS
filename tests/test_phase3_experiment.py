import json
from pathlib import Path
import shutil

import pytest
import yaml
import numpy as np

from conftest import CONFIG_DIR
from experiments.exp_routing_placement_sweep import run_routing_placement_sweep
from src.carbon.config import load_phase3_experiment


def _small_phase3_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    for source in CONFIG_DIR.glob("*.yaml"):
        shutil.copy2(source, config_dir / source.name)
    phase3_path = config_dir / "phase3_experiment.yaml"
    data = yaml.safe_load(phase3_path.read_text(encoding="utf-8"))
    data["carbon"]["sweep"] = {
        "region": "A",
        "start": 50.0,
        "stop": 100.0,
        "step": 50.0,
    }
    phase3_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return config_dir


def test_phase3_default_configuration() -> None:
    config = load_phase3_experiment(CONFIG_DIR)
    assert config.throughput_provider == "profiled"
    assert config.throughput_ratio_rho == pytest.approx(0.95)
    assert config.sweep_values == tuple(float(value) for value in range(50, 801, 25))
    assert config.routing_gap_epsilon == pytest.approx(0.03)


def test_small_strategy_sweep_outputs_and_invariants(tmp_path: Path) -> None:
    config_dir = _small_phase3_config(tmp_path)
    output_dir = tmp_path / "results"
    outputs = run_routing_placement_sweep(config_dir, output_dir=output_dir)
    summary = outputs.summary
    assert len(summary) == 2
    assert summary["F_target"].nunique() == 1
    assert np.allclose(summary["routing_throughput"], summary["F_target"])
    assert np.allclose(summary["joint_throughput"], summary["F_target"])
    assert (summary["joint_carbon"] <= summary["routing_carbon"] + 1e-10).all()
    assert (summary["routing_gap"] >= -1e-10).all()
    for value in summary["carbon_placement_signature"]:
        parsed = json.loads(value)
        assert parsed and len(parsed[0]) == 3
    for path in (
        outputs.summary_csv,
        outputs.routing_breakpoints_csv,
        outputs.placement_breakpoints_csv,
        outputs.transition_figure,
    ):
        assert path.is_file()
        assert path.stat().st_size > 0
