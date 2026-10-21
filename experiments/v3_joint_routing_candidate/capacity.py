"""Class-aware flow capacity for a fixed layered deployment.

The LP is a resource-capacity proxy, not a prediction of online P95 latency.
It expands every (GPU, entry-layer) execution state, so an overlapping GPU
interval is charged only for the layers actually executed on that route.
All states of a physical GPU share one compute-capacity constraint.
"""

from __future__ import annotations

from collections import defaultdict
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

from rcaps.v3.placement import validate
from rcaps.v3.resource_graph import from_topology
from rcaps.v3.topology import TopologyModel, UNITS, profile_at


@dataclass(frozen=True)
class WorkloadClass:
    name: str
    input_tokens: int
    output_tokens: int
    probability: float
    decode_batch: int = 8


@dataclass(frozen=True)
class Stage:
    gpu: int
    first: int
    end: int


@dataclass(frozen=True)
class Arc:
    source: int | None
    target: int | None
    link: tuple[int | str, int | str]


def workload_classes(trace: list[tuple[float, int, int]]) -> tuple[WorkloadClass, ...]:
    """Four input/output length bins, with frequencies from planning only."""
    if not trace:
        raise ValueError("A planning trace is required")
    input_cut = median(row[1] for row in trace)
    output_cut = median(row[2] for row in trace)
    bins = defaultdict(list)
    for _, inputs, outputs in trace:
        bins[(int(inputs > input_cut), int(outputs > output_cut))].append((inputs, outputs))
    result = []
    for (a, b), values in sorted(bins.items()):
        result.append(WorkloadClass(
            f"input_{'long' if a else 'short'}_output_{'long' if b else 'short'}",
            max(1, round(median(value[0] for value in values))),
            max(1, round(median(value[1] for value in values))),
            len(values) / len(trace)))
    if abs(sum(row.probability for row in result) - 1.0) > 1e-12:
        raise AssertionError("Workload frequencies do not sum to one")
    return tuple(result)


def expanded_graph(model: TopologyModel, state: dict,
                   allowed_edges: frozenset | None = None) -> tuple[tuple[Stage, ...], tuple[Arc, ...]]:
    checked = validate(model, state)
    dag = checked["dag"]
    allowed = dag.edge_set if allowed_edges is None else allowed_edges
    if not allowed <= dag.edge_set:
        raise ValueError("Capacity graph includes a nonphysical or layer-incompatible edge")
    spans = checked["spans"]
    outgoing = defaultdict(list)
    for left, right in sorted(allowed, key=str):
        outgoing[left].append(right)
    stages: list[Stage] = []
    indices: dict[Stage, int] = {}
    arcs: list[Arc] = []

    def add(stage: Stage) -> int:
        if stage not in indices:
            indices[stage] = len(stages)
            stages.append(stage)
        return indices[stage]

    for gpu in outgoing["source"]:
        if not isinstance(gpu, int) or spans[gpu][0] != 0:
            raise ValueError("Invalid source transition")
        target = add(Stage(gpu, 0, spans[gpu][1]))
        arcs.append(Arc(None, target, ("source", gpu)))
    cursor = 0
    while cursor < len(stages):
        stage = stages[cursor]
        if stage.end == model.layers and "sink" in outgoing[stage.gpu]:
            arcs.append(Arc(cursor, None, (stage.gpu, "sink")))
        for gpu in outgoing[stage.gpu]:
            if gpu == "sink":
                continue
            start, end = spans[gpu]
            if not start <= stage.end < end:
                continue
            target = add(Stage(gpu, stage.end, end))
            arcs.append(Arc(cursor, target, (stage.gpu, gpu)))
        cursor += 1
    if not any(arc.target is None for arc in arcs):
        raise ValueError("No complete capacity path")
    return tuple(stages), tuple(arcs)


def _nic_speed(template: Path, endpoint: int | str, outbound: bool) -> float:
    config = ConfigParser()
    if not config.read(template):
        raise FileNotFoundError(template)
    section = ("Coordinator" if isinstance(endpoint, str)
               else f"compute_node_{endpoint + 2}")
    key = "outbound_nic_speed" if outbound else "inbound_nic_speed"
    value = float(eval(config[section][key], {"__builtins__": {}}, UNITS))
    if value <= 0:
        raise ValueError(f"Invalid NIC speed for {endpoint}")
    return value


def _gpu_work(model: TopologyModel, stage: Stage,
              workload: WorkloadClass) -> float:
    profile = model.profiles[model.types[stage.gpu]]
    layers = stage.end - stage.first
    prompt = profile_at(profile.prompt_bs2time, workload.input_tokens)
    decode_batch_time = profile_at(profile.decode_bs2time, workload.decode_batch)
    return layers * (prompt + workload.output_tokens * decode_batch_time /
                     workload.decode_batch)


def _link_bytes(model: TopologyModel, arc: Arc,
                workload: WorkloadClass) -> float:
    token = model.manager.get_model_token_size()
    activation = model.manager.get_model_activation_size()
    payload = token if isinstance(arc.link[0], str) or isinstance(arc.link[1], str) \
        else token + activation
    return payload * (workload.input_tokens + workload.output_tokens)


def solve(model: TopologyModel, template: Path, state: dict,
          classes: tuple[WorkloadClass, ...],
          allowed_edges: frozenset | None = None) -> dict:
    """Maximize request/s with shared GPU, link and aggregate NIC capacities."""
    if not classes or abs(sum(item.probability for item in classes) - 1) > 1e-9:
        raise ValueError("Workload probabilities must sum to one")
    if any(item.probability <= 0 or item.input_tokens < 1 or
           item.output_tokens < 1 for item in classes):
        raise ValueError("Invalid workload class")
    stages, arcs = expanded_graph(model, state, allowed_edges)
    resources = from_topology(model)
    n_arcs = len(arcs)
    n_classes = len(classes)
    n_variables = n_classes * n_arcs + 1
    lambda_index = n_variables - 1
    # Every resource row is normalized to a capacity of 1 per second.
    resource_rows: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    equalities = lil_matrix((n_classes * (len(stages) + 1), n_variables))
    for k, workload in enumerate(classes):
        for e, arc in enumerate(arcs):
            column = k * n_arcs + e
            left, right = arc.link
            if arc.source is None:
                equalities[k * (len(stages) + 1), column] += 1
            else:
                equalities[k * (len(stages) + 1) + arc.source + 1, column] -= 1
            if arc.target is not None:
                equalities[k * (len(stages) + 1) + arc.target + 1, column] += 1
                stage = stages[arc.target]
                resource_rows[f"gpu:{stage.gpu}"][column] += _gpu_work(
                    model, stage, workload)
            byte_count = _link_bytes(model, arc, workload)
            link_bandwidth = resources.link(left, right).bandwidth_bytes_per_s
            resource_rows[f"link:{left}->{right}"][column] += byte_count / link_bandwidth
            resource_rows[f"nic_out:{left}"][column] += byte_count / _nic_speed(
                template, left, True)
            resource_rows[f"nic_in:{right}"][column] += byte_count / _nic_speed(
                template, right, False)
        equalities[k * (len(stages) + 1), lambda_index] = -workload.probability
    names = sorted(resource_rows)
    upper = lil_matrix((len(names), n_variables))
    for row, name in enumerate(names):
        for column, value in resource_rows[name].items():
            upper[row, column] = value
    objective = np.zeros(n_variables)
    objective[lambda_index] = -1
    result = linprog(objective, A_ub=upper.tocsr(), b_ub=np.ones(len(names)),
                     A_eq=equalities.tocsr(), b_eq=np.zeros(equalities.shape[0]),
                     bounds=(0, None), method="highs")
    summary = {"status": int(result.status), "message": result.message,
               "success": bool(result.success), "workload_classes": [
                   vars(item) for item in classes], "expanded_states": len(stages),
               "expanded_arcs": len(arcs), "physical_resources": len(names)}
    if not result.success:
        return summary
    utilization = upper @ result.x
    price = {name: max(0.0, -float(result.ineqlin.marginals[row]))
             for row, name in enumerate(names)}
    bottlenecks = sorted(({"resource": name,
                           "utilization": float(utilization[row]),
                           "shadow_price": price[name]} for row, name in enumerate(names)),
                         key=lambda row: (-row["shadow_price"],
                                          -row["utilization"], row["resource"]))
    flow_edges = defaultdict(float)
    for k, workload in enumerate(classes):
        for e, arc in enumerate(arcs):
            value = result.x[k * n_arcs + e]
            if value > 1e-9:
                flow_edges[f"{arc.link[0]}->{arc.link[1]}"] += float(value)
    summary.update({"requests_per_s": float(result.x[lambda_index]),
                    "shadow_prices": price,
                    "resource_utilization": [{"resource": name,
                        "utilization": float(utilization[row]),
                        "shadow_price": price[name]}
                        for row, name in enumerate(names)],
                    "bottlenecks": bottlenecks[:12],
                    "physical_edge_flow_per_s": dict(flow_edges)})
    return summary
