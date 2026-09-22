"""Run the smallest existing vanilla Helix request-level baseline.

The experiment intentionally uses the original ``ClusterSimulator``,
``GlobalFlowScheduler`` in Online mode, and ``OnlineRequestFeeder``.  Carbon
code is only used after the run to map already-recorded placement/pipeline
objects; no scheduler or simulator behavior is changed.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simulator.event_simulator.cluster_simulator import (  # noqa: E402
    ClusterSimulator,
    ModelName,
    SchedulingMethod,
)
from simulator.initial_layout.layout_synthesizer import LayoutMethod, LayoutSynthesizer  # noqa: E402
from simulator.scheduler.global_maxflow.global_maxflow_scheduler import (  # noqa: E402
    KVParameters,
    SchedulingMode,
)
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder  # noqa: E402
from src.integration.helix_adapter import route_from_helix_pipeline  # noqa: E402
from src.integration.helix_request_metrics import (  # noqa: E402
    extract_query_metrics,
    metrics_row,
    summarize_metrics,
)


DEFAULT_DURATION = 60
DEFAULT_THROUGHPUT = 600.0
DEFAULT_SEED = 0


def run_baseline(
    *,
    output_dir: Path,
    duration: int = DEFAULT_DURATION,
    cluster_token_throughput: float = DEFAULT_THROUGHPUT,
    seed: int = DEFAULT_SEED,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one deterministic A100/ILP/Online Helix artifact case."""

    if duration <= 0 or duration % 3:
        raise ValueError("duration must be a positive multiple of 3")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = REPO_ROOT / "artifact_evaluation" / "single_cluster"
    layout_dir = artifact_dir / "layout_llama30b" / "ilp" / "a100"
    machine_num_dict = {"A100": 4}

    layout = LayoutSynthesizer(
        complete_cluster_file_name=str(artifact_dir / "config" / "a100.ini"),
        machine_profile_name=str(artifact_dir / "config" / "machine_profiles.ini"),
        model_name=ModelName.LLaMa30B,
        workspace_path=str(output_dir / "helix_layout_workspace"),
        layout_method=LayoutMethod.LoadExisting,
        machine_num_dict=machine_num_dict,
    )
    cluster_path = layout.synthesize(
        {
            "solution_file_name": str(layout_dir / "ilp_sol.ini"),
            "simulator_cluster_file_name": str(layout_dir / "simulator_cluster.ini"),
        }
    )

    simulator = ClusterSimulator(model_name=ModelName.LLaMa30B, machine_num_dict=machine_num_dict)
    simulator.from_ini_file(config_file_name=cluster_path)
    simulator.init_scheduler(
        scheduling_method=SchedulingMethod.MaxFlow,
        args={
            "kv_param": KVParameters(expected_kv_hwm=0.9, expected_output_length_ratio=0.6),
            "scheduling_mode": SchedulingMode.Online,
        },
    )
    simulator.init_query_manager()
    simulator.mark_as_ready()
    finish_model_loading_time = layout.set_layout(simulator=simulator)
    simulator.update_scheduler()

    feeder = OnlineRequestFeeder(
        cluster_token_throughput=cluster_token_throughput,
        start_time=finish_model_loading_time,
        duration=duration,
        seed=seed,
    )
    feeder.auto_simulate(simulator=simulator)

    query_metrics = [
        extract_query_metrics(query, completion_time=completion_time)
        for _, (completion_time, query) in sorted(simulator.query_manager.finished_queries.items())
    ]
    rows: list[dict[str, Any]] = []
    for metric in query_metrics:
        row = metrics_row(metric)
        query = simulator.query_manager.finished_queries[metric.query_uid][1]
        first_path = query.inference_history[0].path if query.inference_history else []
        route = route_from_helix_pipeline(first_path) if first_path else None
        row.update(
            {
                "baseline_case": "llama30b_single_cluster_a100_ilp_online",
                "model": "LLaMa-30B",
                "placement": "existing_ilp",
                "scheduler": "GlobalFlowScheduler/Online",
                "feeder": "OnlineRequestFeeder/AzureConv",
                "seed": seed,
                "duration_seconds": duration,
                "cluster_token_throughput": cluster_token_throughput,
                "finish_model_loading_time": finish_model_loading_time,
                "route_node_uids": "" if route is None else json.dumps(route.node_uids),
                "route_link_uids": "" if route is None else json.dumps(route.link_uids),
            }
        )
        rows.append(row)

    summary = dict(summarize_metrics(query_metrics))
    summary.update(
        {
            "baseline_case": "llama30b_single_cluster_a100_ilp_online",
            "model": "LLaMa-30B",
            "placement": "existing_ilp",
            "scheduler": "GlobalFlowScheduler/Online",
            "feeder": "OnlineRequestFeeder/AzureConv",
            "seed": seed,
            "duration_seconds": duration,
            "cluster_token_throughput": cluster_token_throughput,
            "finish_model_loading_time": finish_model_loading_time,
            "trace_query_count": len(feeder.trace),
            "finished_request_count": len(simulator.finished_requests),
        }
    )

    request_file = output_dir / "baseline_requests.csv"
    if rows:
        with request_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        request_file.write_text("\n", encoding="utf-8")
    summary_file = output_dir / "baseline_summary.csv"
    with summary_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary))
        writer.writeheader()
        writer.writerow(summary)
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "results" / "request_level_integration")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION)
    parser.add_argument("--throughput", type=float, default=DEFAULT_THROUGHPUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    _, summary = run_baseline(
        output_dir=args.output_dir,
        duration=args.duration,
        cluster_token_throughput=args.throughput,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
