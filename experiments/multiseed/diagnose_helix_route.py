"""Replay one failed hybrid run and record Helix's route-filter decisions.

This wrapper does not change Helix scheduling. It inspects the original
schedule_initialization traceback frame only after the assertion fires.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.critical_graph.fixed_window import run
from experiments.multiseed.run import GUROBI_VERSION, ROOT
from simulator.event_simulator.compute_node import ComputeNode


SCENARIO = "single"
SEED = 1
LAYOUT = ROOT / "experiments/critical_graph/runs/single_final"
OUTPUT = ROOT / "experiments/multiseed/runs/seed1/single/paper_scheduler_helix_diagnostic.json"


def main() -> None:
    try:
        run(name=SCENARIO, method="helix", offered=700, duration=1800,
            warmup=0, seed=SEED, solution=LAYOUT / "solution.ini",
            sim_cluster=LAYOUT / "simulator_cluster.ini", compact=True)
    except AssertionError as error:
        frame = None
        traceback = error.__traceback__
        while traceback is not None:
            if traceback.tb_frame.f_code.co_name == "schedule_initialization":
                frame = traceback.tb_frame
            traceback = traceback.tb_next
        if frame is None or "reason" not in frame.f_locals:
            raise
        values = frame.f_locals
        scheduler_node = values["self"]
        request = values["reqeust"]
        core = scheduler_node.scheduler_core
        cluster = core.cluster
        candidates = []
        for index, node in enumerate(scheduler_node.outbound_simulator_nodes):
            candidate = {
                "node_uid": node.node_uid,
                "filter_reason": values["reason"][index],
                "flow_tokens_per_s": scheduler_node.outbound_links_used_token_throughput[index],
                "flow_share": (scheduler_node.outbound_links_used_token_throughput[index] /
                               values["sum_of_used_token_throughput"]
                               if values["sum_of_used_token_throughput"] else None),
            }
            setting = scheduler_node.outbound_node_inference_settings[index]
            candidate["prompt_max_tokens"] = (setting.prompt_max_tokens
                                               if setting is not None else None)
            if isinstance(node, ComputeNode):
                status = core.kv_expectation.node_uid_to_status[node.node_uid]
                candidate.update({
                    "kv_expected_available": status.avail_kv_capacity,
                    "kv_total_capacity": status.total_kv_capacity,
                    "kv_can_add": core.kv_expectation.check_can_add(
                        node_uid=node.node_uid,
                        input_seq_length=request.token_seq_length),
                })
            candidates.append(candidate)
        details = {
            "scenario": SCENARIO,
            "seed": SEED,
            "sim_time_s": cluster.current_time,
            "request_uid": request.request_uid,
            "query_uid": request.base_query_uid,
            "prompt_tokens": request.token_seq_length,
            "current_node_uid": scheduler_node.node_uid,
            "mask": values["mask"],
            "reason": values["reason"],
            "active_queries": len(cluster.query_manager.queries_on_the_fly),
            "expected_kv_bottleneck_usage": core.kv_expectation.bottleneck_usage(),
            "candidates": candidates,
            "assertion": str(error),
            "gurobi_version": GUROBI_VERSION,
            "solution": str(LAYOUT / "solution.ini"),
        }
        OUTPUT.write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(details, indent=2), flush=True)


if __name__ == "__main__":
    main()
