"""Explain modeled first-token critical paths under WAN-RTT perturbations.

This is an analytic event-DAG decomposition of four representative requests,
not a measurement of simulator queueing delay. Work from *other* requests on
the target's critical path is labeled resource contention.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.critical_graph.event_graph import interleaved_workload_graph
from experiments.critical_graph.model_audit import state_from_placement
from experiments.critical_graph.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ARRIVALS = [0.0, 0.05, 0.10, 0.15]


def analyze(cluster: Path, placement: Path) -> dict:
    model = TopologyModel(cluster)
    state = state_from_placement(placement)
    paths = [model._stages(state, path) for path in state["paths"]]
    graph, first_events, _ = interleaved_workload_graph(
        [paths[0], paths[1], paths[0], paths[1]],
        prompt_tokens=model.prompt_tokens, generated_tokens=8,
        arrivals_s=ARRIVALS)
    requests = []
    for request, finish in enumerate(first_events):
        critical = graph.critical_path(finish)
        own = {"compute": 0.0, "transfer": 0.0, "propagation": 0.0}
        interference = arrival_time = 0.0
        for name in critical.events:
            event = graph.events[name]
            if event.kind == "arrival":
                arrival_time += event.duration_s
            elif name.startswith(f"request{request}:"):
                own[event.kind] += event.duration_s
            else:
                interference += event.duration_s
        resource_time = sum(own.values()) + interference
        assert abs(resource_time + arrival_time - critical.completion_s) < 1e-8
        requests.append({"request_index": request,
                         "first_token_completion_s": critical.completion_s,
                         "own_compute_s": own["compute"],
                         "own_transfer_s": own["transfer"],
                         "own_propagation_s": own["propagation"],
                         "other_request_service_s": interference,
                         "critical_path_resource_time_s": resource_time,
                         "shares": {
                             "compute": own["compute"] / resource_time,
                             "transfer": own["transfer"] / resource_time,
                             "propagation": own["propagation"] / resource_time,
                             "resource_contention": interference / resource_time,
                         }})
    return {"physical_cluster": str(cluster), "placement": str(placement),
            "representative_prompt_tokens": model.prompt_tokens,
            "representative_decode_batch": model.decode_batch,
            "arrival_offsets_s": ARRIVALS,
            "requests": requests,
            "mean_critical_path_share": {
                key: sum(item["shares"][key] for item in requests) / len(requests)
                for key in ("compute", "transfer", "propagation",
                            "resource_contention")}}


def main() -> None:
    variants = {
        "rtt_0p5x": HERE / "network_layouts/rtt_0p5x",
        "official": None,
        "rtt_2x": HERE / "network_layouts/rtt_2x",
    }
    result = {}
    for name, base in variants.items():
        if base is None:
            cluster = ROOT / "artifact_evaluation/distributed_clusters/config/3cluster24.ini"
            placement = ROOT / "experiments/critical_graph/runs/multi_final/placement.json"
        else:
            cluster = base / "physical_cluster.ini"
            placement = base / "green/placement.json"
        result[name] = analyze(cluster, placement)
    output = HERE / "runs/network_mechanism.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: data["mean_critical_path_share"]
                      for name, data in result.items()}, indent=2))


if __name__ == "__main__":
    main()
