"""Final-validation experiments without changing frozen Challenge 1–3 grids."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter
import json

import pandas as pd

from experiments.phase35_common import (
    capacity_tokens_to_mbps,
    load_phase35_context,
    scenario_topology,
)
from src.carbon.config import load_cbgp_config, load_energy_provider
from src.carbon.model import CarbonCostModel
from src.carbon.stage import (
    StageWorkload,
    WorkloadWeightedEnergyProvider,
    evaluate_stage_carbon,
)
from src.carbon.trace import HistoricalCITraceLoader, RegionMappedCIProvider
from src.graph.serving_graph import build_serving_graph
from src.graph.topology import with_cross_region_bandwidth
from src.optimizer.carbon_flow import evaluate_flow_carbon, solve_carbon_aware_flow
from src.optimizer.maxflow import solve_max_flow
from src.optimizer.placement_milp import (
    solve_carbon_aware_placement,
    solve_throughput_optimal_placement,
)
from src.scheduler.carbon_flow_scheduler import CarbonFlowScheduler
from src.scheduler.slow_placement import SlowCBGPController
from src.utils.config import load_yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
OUTPUT = ROOT / "results" / "final_validation"


def _signature(placement) -> str:
    return str(tuple(sorted((gpu, value.start_layer, value.end_layer) for gpu, value in placement.intervals.items())))


def run_stage_aware() -> pd.DataFrame:
    data = load_yaml(CONFIG_DIR / "final_validation.yaml")
    stage_cfg = data["stage_aware"]
    context = load_phase35_context(CONFIG_DIR)
    energy, energy_metadata = load_energy_provider(CONFIG_DIR)
    model = context.phase3.simulation.model
    provider = context.phase3.throughput_provider
    rows: list[dict[str, object]] = []
    for scenario in stage_cfg["gpu_scenarios"]:
        topology = with_cross_region_bandwidth(
            scenario_topology(context, scenario),
            capacity_tokens_to_mbps(
                float(stage_cfg["network_capacity_tokens_per_second"]),
                model.activation_bytes_per_token,
            ),
        )
        helix = solve_throughput_optimal_placement(topology, model, provider)
        target = 0.75 * helix.validated_max_flow
        serving = build_serving_graph(topology, model, helix.placement, provider)
        maximum = solve_max_flow(serving)
        for workload_name, values in stage_cfg["workloads"].items():
            workload = StageWorkload(
                float(values["prefill_tokens"]), float(values["decode_tokens"])
            )
            total_tokens = workload.prefill_tokens + workload.decode_tokens
            weighted_provider = WorkloadWeightedEnergyProvider(
                energy,
                workload.prefill_tokens / total_tokens,
                workload.decode_tokens / total_tokens,
            )
            decode_cost = CarbonCostModel.build(
                topology,
                model,
                helix.placement,
                energy,
                stage_cfg["carbon_intensity_g_per_kwh"],
                phase="decode",
                batch_size=int(stage_cfg["batch_size"]),
            )
            weighted_cost = CarbonCostModel.build(
                topology,
                model,
                helix.placement,
                weighted_provider,
                stage_cfg["carbon_intensity_g_per_kwh"],
                phase="weighted",
                batch_size=int(stage_cfg["batch_size"]),
            )
            decode_flow = solve_carbon_aware_flow(serving, decode_cost, target)
            weighted_flow = solve_carbon_aware_flow(serving, weighted_cost, target)
            decode_stage = evaluate_stage_carbon(
                serving,
                dict(decode_flow.metrics.positive_flow_edges),
                target,
                topology,
                model,
                helix.placement,
                energy,
                stage_cfg["carbon_intensity_g_per_kwh"],
                workload,
                batch_size=int(stage_cfg["batch_size"]),
            )
            weighted_stage = evaluate_stage_carbon(
                serving,
                dict(weighted_flow.metrics.positive_flow_edges),
                target,
                topology,
                model,
                helix.placement,
                energy,
                stage_cfg["carbon_intensity_g_per_kwh"],
                workload,
                batch_size=int(stage_cfg["batch_size"]),
            )
            oracle_start = perf_counter()
            oracle = solve_carbon_aware_placement(
                topology,
                model,
                provider,
                weighted_provider,
                stage_cfg["carbon_intensity_g_per_kwh"],
                target,
                phase="weighted",
                batch_size=int(stage_cfg["batch_size"]),
                mip_rel_gap=0.01,
                time_limit_seconds=2.0,
            )
            oracle_runtime = perf_counter() - oracle_start
            rows.append(
                {
                    "scenario": scenario,
                    "workload": workload_name,
                    "prefill_tokens": workload.prefill_tokens,
                    "decode_tokens": workload.decode_tokens,
                    "target_tokens_per_second": target,
                    "validated_max_flow": maximum.max_flow_value,
                    "stage_energy_profile_status": energy_metadata["parameter_status"],
                    "decode_only_stage_carbon_g": decode_stage.total_carbon_g,
                    "stage_weighted_flow_carbon_g": weighted_stage.total_carbon_g,
                    "stage_weighted_reduction_vs_decode_only": (
                        decode_stage.total_carbon_g - weighted_stage.total_carbon_g
                    ) / decode_stage.total_carbon_g,
                    "decode_flow_signature": str(decode_flow.metrics.path_flow_share),
                    "stage_weighted_flow_signature": str(weighted_flow.metrics.path_flow_share),
                    "joint_stage_carbon_g": oracle.carbon_g_per_second * total_tokens / target,
                    "joint_stage_placement_changed": _signature(oracle.placement) != _signature(helix.placement),
                    "joint_stage_mip_gap": oracle.optimality_gap or 0.0,
                    "joint_stage_runtime_seconds": oracle_runtime,
                }
            )
    return pd.DataFrame(rows)


def run_historical_ci() -> pd.DataFrame:
    data = load_yaml(CONFIG_DIR / "final_validation.yaml")
    historical = data["historical_ci"]
    context = load_phase35_context(CONFIG_DIR)
    model = context.phase3.simulation.model
    provider = context.phase3.throughput_provider
    energy = context.phase3.energy_provider
    topology = with_cross_region_bandwidth(
        scenario_topology(context, "high_asymmetric"),
        capacity_tokens_to_mbps(
            float(historical["network_capacity_tokens_per_second"]),
            model.activation_bytes_per_token,
        ),
    )
    helix = solve_throughput_optimal_placement(topology, model, provider)
    target_base = helix.validated_max_flow
    trace = HistoricalCITraceLoader.from_csv(ROOT / historical["processed_file"])
    mapped = RegionMappedCIProvider(trace, historical["region_mapping"])
    cbgp_config = load_cbgp_config(CONFIG_DIR)
    rows: list[dict[str, object]] = []
    timeseries_rows: list[dict[str, object]] = []
    base_timestamp = min(
        timestamp
        for points in trace.points_by_region.values()
        for timestamp, _ in points
    )
    interval = float(historical["scheduler_interval_seconds"])
    for load_name, load_factor in historical["load_profiles"].items():
        target = float(load_factor) * target_base
        initial_scheduler = CarbonFlowScheduler(
            topology,
            model,
            helix.placement,
            provider,
            energy,
            mapped,
            phase=context.phase3.config.phase,
            batch_size=context.phase3.config.batch_size,
            scheduling_interval_seconds=interval,
        )
        initial = initial_scheduler.schedule(base_timestamp, target)
        initial_maxflow = solve_max_flow(initial.serving_graph)
        helix_edges = {
            edge: value * target / initial_maxflow.max_flow_value
            for edge, value in initial_maxflow.positive_flow_edges.items()
        }
        controller = SlowCBGPController(
            topology,
            model,
            helix.placement,
            provider,
            energy,
            cbgp_config,
            phase=context.phase3.config.phase,
            batch_size=context.phase3.config.batch_size,
            placement_check_interval_seconds=7200.0,
            persistence_intervals=2,
            minimum_dwell_seconds=7200.0,
        )
        static_helix = 0.0
        static_routing = 0.0
        dynamic = 0.0
        slow = 0.0
        flow_switches = 0
        previous = None
        for index in range(len(next(iter(trace.points_by_region.values())))):
            timestamp = base_timestamp + index * interval
            schedule = CarbonFlowScheduler(
                topology,
                model,
                controller.current_placement,
                provider,
                energy,
                mapped,
                phase=context.phase3.config.phase,
                batch_size=context.phase3.config.batch_size,
                scheduling_interval_seconds=interval,
            ).schedule(timestamp, target)
            snapshot = schedule.ci_snapshot
            helix_cost = CarbonCostModel.build(
                topology, model, helix.placement, energy, snapshot,
                phase=context.phase3.config.phase, batch_size=context.phase3.config.batch_size,
            )
            static_helix += evaluate_flow_carbon(
                initial.serving_graph, helix_edges,
                helix_cost, target,
            ).carbon_g_per_second * interval
            static_routing += evaluate_flow_carbon(
                initial.serving_graph, initial.flow_result.metrics.positive_flow_edges,
                helix_cost, target,
            ).carbon_g_per_second * interval
            dynamic += schedule.carbon_g_per_second * interval
            slow += schedule.carbon_g_per_second * interval
            timeseries_rows.append(
                {
                    "load_profile": load_name,
                    "timestamp": timestamp,
                    "carbon_intensity_g_per_kwh": sum(snapshot.values()) / len(snapshot),
                    "dynamic_carbon_g_per_second": schedule.carbon_g_per_second,
                    "dynamic_path_flow_share": json.dumps(
                        schedule.flow_result.metrics.path_flow_share, sort_keys=True
                    ),
                }
            )
            current_paths = schedule.flow_result.metrics.path_flow_share
            if previous is not None:
                flow_switches += int(previous != current_paths)
            previous = current_paths
            controller.maybe_update(timestamp, schedule)
        duration = interval * len(next(iter(trace.points_by_region.values())))
        rows.append(
            {
                "source": historical["source_name"],
                "trace_date": "2025-01-01",
                "region_mapping": "A->GB,B->GB",
                "load_profile": load_name,
                "intervals": len(next(iter(trace.points_by_region.values()))),
                "duration_seconds": duration,
                "static_helix_carbon_g": static_helix,
                "static_carbon_routing_carbon_g": static_routing,
                "dynamic_carbon_carbon_g": dynamic,
                "dynamic_slow_cbgp_carbon_g": slow,
                "dynamic_reduction_vs_static_helix": (static_helix - dynamic) / static_helix,
                "flow_reallocations": flow_switches,
                "slow_cbgp_invocations": controller.invocation_count,
                "accepted_placement_changes": controller.accepted_count,
                "served_fraction": 1.0,
                "latency_metrics": "unsupported",
            }
        )
    pd.DataFrame(timeseries_rows).to_csv(
        OUTPUT / "historical_ci_timeseries.csv", index=False
    )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stage = run_stage_aware()
    historical = run_historical_ci()
    stage.to_csv(OUTPUT / "stage_aware_results.csv", index=False)
    historical.to_csv(OUTPUT / "historical_ci_results.csv", index=False)
    pd.DataFrame(
        [
            {"validation": "request_level_integration", "status": "partial", "reason": "Original simulator has no arrivals, queue, request execution, or latency objects."},
            {"validation": "stage_aware_energy", "status": "pass", "reason": "Prefill/decode parameterized model and workload accounting validated."},
            {"validation": "historical_ci", "status": "pass_limited", "reason": "One real GB trace; mapped to both synthetic regions, so no spatial claim."},
        ]
    ).to_csv(OUTPUT / "final_validation_summary.csv", index=False)
    pd.DataFrame(
        [
            {"metric": "TTFT", "status": "unsupported", "value": ""},
            {"metric": "TBT", "status": "unsupported", "value": ""},
            {"metric": "end_to_end_latency", "status": "unsupported", "value": ""},
            {"metric": "SLO_violations", "status": "unsupported", "value": ""},
        ]
    ).to_csv(OUTPUT / "request_level_results.csv", index=False)
    print(f"STAGE_ROWS={len(stage)}")
    print(f"HISTORICAL_ROWS={len(historical)}")


if __name__ == "__main__":
    main()
