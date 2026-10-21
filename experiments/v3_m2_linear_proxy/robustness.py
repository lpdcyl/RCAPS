"""Check whether the linear-proxy ranking survives decode-batch assumptions."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from experiments.v3_joint_routing_candidate.capacity import workload_classes
from experiments.v3_joint_routing_candidate.joint import case_inputs

from .diagnose import HERE, LABELS, SOURCE
from .model import evaluate


def run() -> dict:
    case, offered = "C1_multi", 320
    model, _, template = case_inputs(case)
    trace = OnlineRequestFeeder(cluster_token_throughput=offered,
                                start_time=0, duration=300, seed=100).trace
    classes = workload_classes(trace)
    output = {"case": case, "offered_tokens_per_s": offered,
              "development_seed": 100, "decode_batches": {}}
    for batch in (4, 8, 16):
        varied = tuple(replace(item, decode_batch=batch) for item in classes)
        scores = []
        for label in LABELS:
            placement = json.loads((SOURCE / "layouts" / case / label /
                                    "placement.json").read_text(encoding="utf-8"))
            result = evaluate(model, template, placement["state"], varied,
                              len(trace) / 300)
            if not result["success"]:
                raise ValueError(f"Proxy infeasible at batch {batch}: {label}")
            scores.append({"layout": label, "service_seconds_per_request":
                           result["minimum_service_seconds_per_request"]})
        scores.sort(key=lambda row: (row["service_seconds_per_request"], row["layout"]))
        output["decode_batches"][str(batch)] = scores
    path = HERE / "batch_robustness.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return output


if __name__ == "__main__":
    result = run()
    for batch, scores in result["decode_batches"].items():
        print(batch, [(row["layout"], round(row["service_seconds_per_request"], 5))
                      for row in scores])
