"""Check whether longer representative queues change event-DAG move rankings."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .event_graph import interleaved_workload_graph
from .model_audit import state_from_placement
from .partition import scenario
from .topology import TopologyModel


RUNS = Path(__file__).resolve().parent / "runs"


def evaluate(model: TopologyModel, state: dict, *, requests: int,
             arrival_spacing_s: float) -> dict:
    paths = [model._stages(state, path) for path in state["paths"]]
    pipelines = [paths[index % 2] for index in range(requests)]
    arrivals = [index * arrival_spacing_s for index in range(requests)]
    graph, first, last = interleaved_workload_graph(
        pipelines, prompt_tokens=model.prompt_tokens, generated_tokens=8,
        arrivals_s=arrivals)
    first_times = [graph.critical_path(event).completion_s for event in first]
    last_times = [graph.critical_path(event).completion_s for event in last]
    ttfts = [time - arrival for time, arrival in zip(first_times, arrivals)]
    tpots = [(end - start) / 7 for start, end in zip(first_times, last_times)]
    return {"ttft_p95_s": float(np.percentile(ttfts, 95)),
            "tpot_p95_s": float(np.percentile(tpots, 95)),
            "ttft_last_s": ttfts[-1], "tpot_last_s": tpots[-1]}


def main() -> None:
    model = TopologyModel(scenario("single")[0])
    old = state_from_placement(RUNS / "single/placement.json")
    new = state_from_placement(RUNS / "single_sharedpush/placement.json")
    rows = []
    for requests in (4, 8, 16, 32):
        for spacing in (0.1, 1.0, 2.5):
            baseline = evaluate(model, old, requests=requests,
                                arrival_spacing_s=spacing)
            moved = evaluate(model, new, requests=requests,
                             arrival_spacing_s=spacing)
            rows.append({"requests": requests, "arrival_spacing_s": spacing,
                         "before": baseline, "after": moved,
                         "ttft_p95_change_percent": 100 * (
                             moved["ttft_p95_s"] / baseline["ttft_p95_s"] - 1),
                         "tpot_p95_change_percent": 100 * (
                             moved["tpot_p95_s"] / baseline["tpot_p95_s"] - 1)})
    output = RUNS / "workload_dag_audit.json"
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([{"requests": row["requests"],
                       "arrival_spacing_s": row["arrival_spacing_s"],
                       "ttft_p95_change_percent": row["ttft_p95_change_percent"],
                       "tpot_p95_change_percent": row["tpot_p95_change_percent"]}
                      for row in rows], indent=2))


if __name__ == "__main__":
    main()
