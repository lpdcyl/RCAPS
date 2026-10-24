"""Measure one-edge capacity marginals before proposing an admission algorithm.

This is an exploratory model diagnostic. The capacity LP omits batch
fragmentation and online latency; no edge is selected from this file alone.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.v3_joint_routing_candidate.capacity import solve, workload_classes
from experiments.v3_joint_routing_candidate.joint import ROOT, case_inputs, read
from experiments.v3_joint_routing_candidate.joint_capacity import train_trace
from experiments.v3_pathspace_ablation.run import canonical_edges
from rcaps.v3.placement import validate

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(case: str) -> dict:
    model, physical, template = case_inputs(case)
    scenario = "single" if case == "C1_single" else "multi"
    layout = ROOT / "rcaps" / "v3_layouts" / scenario
    state = read(layout / "placement.json")["state"]
    dag = validate(model, state)["dag"]
    canonical = frozenset(canonical_edges(state, dag))
    full = dag.edge_set
    classes = workload_classes(train_trace(case, "uniform"))
    base = solve(model, template, state, classes, canonical)
    complete = solve(model, template, state, classes, full)
    if not base["success"] or not complete["success"]:
        raise ValueError("Capacity LP failed")
    candidates = []
    for edge in sorted(full - canonical, key=str):
        lp = solve(model, template, state, classes, canonical | {edge})
        if not lp["success"]:
            raise ValueError(f"One-edge LP failed: {edge}")
        candidates.append({"edge": list(edge), "requests_per_s": lp["requests_per_s"],
                           "increment_requests_per_s": lp["requests_per_s"] - base["requests_per_s"],
                           "flow_on_edge_per_s": lp["physical_edge_flow_per_s"].get(
                               f"{edge[0]}->{edge[1]}", 0.0)})
    out = {"case": case,
           "warning": "Exploratory capacity model only; no online batch fragmentation or tail latency.",
           "model_inputs": {"physical_sha256": digest(physical), "template_sha256": digest(template),
                            "placement_sha256": digest(layout / "placement.json"),
                            "source_sha256": digest(Path(__file__)),
                            "capacity_model_sha256": digest(ROOT / "experiments/v3_joint_routing_candidate/capacity.py")},
           "workload_classes": [vars(item) for item in classes],
           "edge_counts": {"canonical": len(canonical), "full": len(full)},
           "canonical_requests_per_s": base["requests_per_s"],
           "full_requests_per_s": complete["requests_per_s"],
           "candidates": candidates}
    output = HERE / f"lp_probe_{case}.json"
    output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    for name in ("C1_single", "C1_multi"):
        result = probe(name)
        positive = [item for item in result["candidates"]
                    if item["increment_requests_per_s"] > 1e-9]
        print(name, result["canonical_requests_per_s"],
              result["full_requests_per_s"], len(positive), "positive single-edge marginals")
        for item in sorted(positive, key=lambda row: -row["increment_requests_per_s"]):
            print(" ", item["edge"], item["increment_requests_per_s"])
