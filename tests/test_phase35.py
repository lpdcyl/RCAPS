from pathlib import Path
import shutil

import numpy as np
import pytest
import yaml

from conftest import CONFIG_DIR
from experiments.exp_placement_cost_curves import run_placement_cost_curves
from experiments.exp_rho_sensitivity import run_rho_sensitivity
from experiments.phase35_common import (
    load_phase35_context,
    run_ci_sweep,
    scenario_topology,
)
from src.analysis.breakpoint import PlacementBreakpoint
from src.analysis.placement_boundary import validate_placement_boundary
from src.carbon.model import CarbonCostModel, ConfiguredLinearEnergyProvider
from src.graph.serving_graph import (
    LayerInterval,
    LayerPlacement,
    build_serving_graph,
    gpu_in_node,
    gpu_out_node,
)
from src.optimizer.carbon_flow import evaluate_flow_carbon


def _small_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    for source in CONFIG_DIR.glob("*.yaml"):
        shutil.copy2(source, config_dir / source.name)
    phase3_path = config_dir / "phase3_experiment.yaml"
    phase3 = yaml.safe_load(phase3_path.read_text(encoding="utf-8"))
    phase3["carbon"]["sweep"] = {
        "region": "A",
        "start": 100.0,
        "stop": 200.0,
        "step": 100.0,
    }
    phase3_path.write_text(yaml.safe_dump(phase3, sort_keys=False), encoding="utf-8")
    phase35_path = config_dir / "phase35_sensitivity.yaml"
    phase35 = yaml.safe_load(phase35_path.read_text(encoding="utf-8"))
    phase35["rho_values"] = [0.90, 0.95]
    phase35_path.write_text(yaml.safe_dump(phase35, sort_keys=False), encoding="utf-8")
    return config_dir


def _transition() -> PlacementBreakpoint:
    old = (("c1", 0, 1),)
    new = (("c1", 1, 2),)
    return PlacementBreakpoint(0.5, 1.5, old, new, 2, 0.5)


def test_validated_boundary_crossing() -> None:
    result = validate_placement_boundary(
        _transition(),
        lambda placement, ratio: ratio if placement.name == "old" else 2.0 - ratio,
    )
    assert result.cost_crossing
    assert not result.degenerate
    assert result.validated
    assert result.delta_mid == pytest.approx(0.0)


def test_equal_cost_switch_is_degenerate_not_material() -> None:
    result = validate_placement_boundary(
        _transition(),
        lambda placement, ratio: (
            1.0 if placement.name == "old" else 1.0 + 1e-6 * (ratio - 1.0)
        ),
    )
    assert result.cost_crossing
    assert result.degenerate
    assert not result.validated


def test_gpu_scenario_loader_changes_composition_not_regions() -> None:
    context = load_phase35_context(CONFIG_DIR)
    topology = scenario_topology(context, "moderate_asymmetric")
    assert [topology.gpus[f"c{i}"].gpu_type for i in range(1, 7)] == [
        "A100",
        "L4",
        "T4",
        "L4",
        "T4",
        "T4",
    ]
    assert [topology.gpus[f"c{i}"].region for i in range(1, 7)] == [
        "A",
        "A",
        "A",
        "B",
        "B",
        "B",
    ]


def test_rho_sweep_uses_scenario_fh_and_joint_is_no_worse(tmp_path: Path) -> None:
    outputs = run_rho_sensitivity(
        _small_config(tmp_path), output_dir=tmp_path / "results"
    )
    assert len(outputs.runs) == 2
    for run in outputs.runs:
        assert np.allclose(run.summary["F_target"], run.rho * run.summary["F_H"])
        assert (run.summary["joint_carbon"] <= run.summary["routing_carbon"] + 1e-10).all()


def test_candidate_cost_curve_envelope_is_pointwise_minimum(tmp_path: Path) -> None:
    outputs = run_placement_cost_curves(
        _small_config(tmp_path), output_dir=tmp_path / "results"
    )
    grouped = outputs.summary.groupby("ci_ratio")
    for _, group in grouped:
        assert group["global_optimum_envelope"].nunique() == 1
        assert group["global_optimum_envelope"].iloc[0] == pytest.approx(
            group["carbon_objective"].min()
        )
    assert outputs.summary["is_helix_placement"].any()


def test_region_shares_and_cross_region_fraction(
    phase1_topology, phase1_model
) -> None:
    placement = LayerPlacement(
        "crossing",
        {
            "c1": LayerInterval(0, 16),
            "c2": LayerInterval(0, 16),
            "c3": LayerInterval(32, 48),
            "c4": LayerInterval(0, 16),
            "c5": LayerInterval(16, 32),
            "c6": LayerInterval(32, 48),
        },
    )
    from src.graph.serving_graph import AnalyticalThroughputProvider, SOURCE, SINK

    serving = build_serving_graph(
        phase1_topology, phase1_model, placement, AnalyticalThroughputProvider()
    )
    energy = ConfiguredLinearEnergyProvider(
        {
            gpu_type: {"decode": {1: value}}
            for gpu_type, value in {"A100": 0.1, "L4": 0.055, "T4": 0.085}.items()
        }
    )
    carbon = CarbonCostModel.build(
        phase1_topology,
        phase1_model,
        placement,
        energy,
        {"A": 100.0, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    flow = 10.0
    edges = {
        (SOURCE, gpu_in_node("c1")): flow,
        (gpu_in_node("c1"), gpu_out_node("c1")): flow,
        (gpu_out_node("c1"), gpu_in_node("c5")): flow,
        (gpu_in_node("c5"), gpu_out_node("c5")): flow,
        (gpu_out_node("c5"), gpu_in_node("c3")): flow,
        (gpu_in_node("c3"), gpu_out_node("c3")): flow,
        (gpu_out_node("c3"), SINK): flow,
    }
    metrics = evaluate_flow_carbon(serving, edges, carbon, flow)
    assert sum(metrics.region_flow_share.values()) == pytest.approx(1.0)
    assert metrics.region_flow_share["A"] == pytest.approx(2.0 / 3.0)
    assert metrics.region_flow_share["B"] == pytest.approx(1.0 / 3.0)
    assert metrics.cross_region_flow_fraction == pytest.approx(2.0)


def test_asymmetric_run_has_scenario_specific_target(tmp_path: Path) -> None:
    context = load_phase35_context(_small_config(tmp_path))
    rho = 0.95
    symmetric = run_ci_sweep(
        context,
        study="test",
        scenario="symmetric",
        rho=rho,
        topology=scenario_topology(context, "symmetric"),
    )
    asymmetric = run_ci_sweep(
        context,
        study="test",
        scenario="moderate_asymmetric",
        rho=rho,
        topology=scenario_topology(context, "moderate_asymmetric"),
    )
    assert symmetric.helix.validated_max_flow != asymmetric.helix.validated_max_flow
    assert asymmetric.summary["F_target"].iloc[0] == pytest.approx(
        rho * asymmetric.helix.validated_max_flow
    )
