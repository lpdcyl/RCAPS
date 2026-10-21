"""Minimum-service flow for one fixed V3 placement and workload mix.

The objective has units of seconds per request. It is an idealized routing
lower bound under shared GPU/link/NIC capacities, not a P95 predictor.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

from experiments.v3_joint_routing_candidate.capacity import (
    WorkloadClass, _gpu_work, _link_bytes, _nic_speed, expanded_graph,
)
from rcaps.v3.resource_graph import from_topology


def evaluate(model, template: Path, state: dict,
             classes: tuple[WorkloadClass, ...], arrival_rate: float) -> dict:
    """Route a fixed class mix at ``arrival_rate`` requests/s.

    Source flow is fixed for each class. Every physical GPU, directed link,
    and endpoint NIC has one shared one-second capacity row. Link latency is
    included in the service objective, while bandwidth occupancy is charged
    separately in capacity rows. GPU work uses profiled prompt service and
    decode work divided by the assumed batch size.
    """
    if arrival_rate <= 0 or not classes:
        raise ValueError("A positive arrival rate and workload classes are required")
    if any(item.probability <= 0 or item.input_tokens < 1 or
           item.output_tokens < 1 for item in classes):
        raise ValueError("Invalid workload class")
    if abs(sum(item.probability for item in classes) - 1) > 1e-9:
        raise ValueError("Workload probabilities must sum to one")
    stages, arcs = expanded_graph(model, state)
    resources = from_topology(model)
    n_arcs = len(arcs)
    n_variables = len(classes) * n_arcs
    equalities = lil_matrix((len(classes) * (len(stages) + 1), n_variables))
    right_hand_side = np.zeros(equalities.shape[0])
    coefficients = np.zeros(n_variables)
    resource_rows: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    nic_cache = {}

    def nic(endpoint, outbound):
        key = (endpoint, outbound)
        if key not in nic_cache:
            nic_cache[key] = _nic_speed(template, endpoint, outbound)
        return nic_cache[key]

    for k, workload in enumerate(classes):
        right_hand_side[k * (len(stages) + 1)] = (
            arrival_rate * workload.probability)
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
                work = _gpu_work(model, stage, workload)
                resource_rows[f"gpu:{stage.gpu}"][column] += work
                coefficients[column] += work
            byte_count = _link_bytes(model, arc, workload)
            link = resources.link(left, right)
            bandwidth_work = byte_count / link.bandwidth_bytes_per_s
            resource_rows[f"link:{left}->{right}"][column] += bandwidth_work
            resource_rows[f"nic_out:{left}"][column] += byte_count / nic(left, True)
            resource_rows[f"nic_in:{right}"][column] += byte_count / nic(right, False)
            # One prompt transfer and one transfer for each generated token.
            coefficients[column] += (workload.output_tokens + 1) * link.latency_s
            coefficients[column] += bandwidth_work

    names = sorted(resource_rows)
    upper = lil_matrix((len(names), n_variables))
    for row, name in enumerate(names):
        for column, value in resource_rows[name].items():
            upper[row, column] = value
    result = linprog(coefficients, A_ub=upper.tocsr(),
                     b_ub=np.ones(len(names)), A_eq=equalities.tocsr(),
                     b_eq=right_hand_side, bounds=(0, None), method="highs")
    summary = {"success": bool(result.success), "status": int(result.status),
               "message": result.message, "arrival_rate_requests_per_s": arrival_rate,
               "expanded_states": len(stages), "expanded_arcs": len(arcs),
               "physical_resources": len(names)}
    if result.success:
        utilization = upper @ result.x
        summary.update({
            "minimum_service_seconds_per_request": float(result.fun / arrival_rate),
            "max_resource_utilization": float(max(utilization)),
            "most_utilized_resource": names[int(np.argmax(utilization))],
            "used_arcs": sum(float(value) > 1e-9 for value in result.x),
        })
    return summary
