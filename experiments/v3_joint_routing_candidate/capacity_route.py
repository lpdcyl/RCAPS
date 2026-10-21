"""Bounded Pareto routing with live M3 work and offline capacity prices.

The LP prices only break choices within a fixed 10% live-cost slack.  This
keeps prompt latency as the primary online objective while allowing a route
with spare physical capacity to preserve contested GPUs, links and NICs.
Decode follows the chosen prompt route through the unchanged V3 scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.event_simulator.request import PipelineStage, RequestPhase

from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.resource_graph import from_simulator


LABEL_WIDTH = 4
LIVE_COST_SLACK = 0.10


@dataclass(frozen=True)
class Label:
    live_cost: float
    pressure: float
    path: tuple


def pareto_insert(current: list[Label], candidate: Label,
                  width: int = LABEL_WIDTH) -> list[Label]:
    """Keep bounded, deterministic nondominated labels per DAG state."""
    if any(row.live_cost <= candidate.live_cost and
           row.pressure <= candidate.pressure for row in current):
        return current
    remaining = [row for row in current
                 if not (candidate.live_cost <= row.live_cost and
                         candidate.pressure <= row.pressure)]
    remaining.append(candidate)
    remaining.sort(key=lambda row: (row.live_cost, row.pressure, row.path))
    if len(remaining) <= width:
        return remaining
    cheapest = min(remaining, key=lambda row: (row.pressure, row.live_cost,
                                               row.path))
    kept = remaining[:width - 1]
    if cheapest not in kept:
        kept.append(cheapest)
    return sorted(kept, key=lambda row: (row.live_cost, row.pressure, row.path))


def resource_weights(lp: dict) -> dict[str, float]:
    """Nonnegative pressure from LP marginal value and near saturation."""
    rate = lp["requests_per_s"]
    if rate <= 0:
        raise ValueError("Capacity rate must be positive")
    return {row["resource"]:
            row["shadow_price"] / rate +
            max(0.0, row["utilization"] - 0.8) / 0.2
            for row in lp["resource_utilization"]}


class CapacityGuidedM3(GraphModeledQueueAwareDagScheduler):
    """Read the deployed M1 DAG and choose a live, capacity-aware prompt path."""

    def __init__(self, simulator, *, lp: dict, typical_output_tokens: int):
        super().__init__(simulator)
        self.weights = resource_weights(lp)
        self.typical_output_tokens = max(1, typical_output_tokens)

    def _allow_placement_edge(self, left_uid: int, right_uid: int) -> bool:
        if self.execution_dag is None:
            self.execution_dag = from_simulator(self.simulator)
        left = "source" if left_uid == self.simulator.source_node.node_uid else left_uid
        right = "sink" if right_uid == self.simulator.sink_node.node_uid else right_uid
        return (left, right) in self.execution_dag.edge_set

    def _pressure(self, previous, node, link, request, first: int,
                  end: int) -> float:
        """Approximate LP-normalized per-request use; no output length oracle."""
        prompt = sum(self._layer_service(node, layer,
                                        RequestPhase.Initialization,
                                        request.token_seq_length)
                     for layer in range(first, end)) if node is not None else 0.0
        gpu = 0.0
        if node is not None:
            decode_batch = sum(self._layer_service(node, layer,
                                                   RequestPhase.Increment, 8)
                               for layer in range(first, end)) / 8
            gpu = self.weights.get(f"gpu:{node.node_uid - 2}", 0.0) * (
                prompt + self.typical_output_tokens * decode_batch)
        payload = request.token_size if node is None or previous is self.simulator.source_node \
            else request.token_size + request.activation_size
        bytes_sent = payload * (request.token_seq_length + self.typical_output_tokens)
        left = "source" if previous is self.simulator.source_node else previous.node_uid - 2
        right = "sink" if node is None else node.node_uid - 2
        network = (
            self.weights.get(f"link:{left}->{right}", 0.0) * bytes_sent / link.bandwidth +
            self.weights.get(f"nic_out:{left}", 0.0) * bytes_sent /
            previous.outbound_nic_speed +
            self.weights.get(f"nic_in:{right}", 0.0) * bytes_sent /
            link.node_out.inbound_nic_speed)
        return gpu + network

    def _route(self, request):
        sim = self.simulator
        source, sink = sim.source_node, sim.sink_node
        gpu_release, link_release = self._release_snapshot()
        sessions = self._active_session_counts()
        nodes = []
        for node in sim.compute_nodes.values():
            if node.in_vram_model_layers:
                layers = sorted(node.in_vram_model_layers)
                nodes.append((node, layers[0], layers[-1] + 1))
        nodes.sort(key=lambda row: (row[2], row[1], row[0].node_uid))
        labels = {(0, source.node_uid): [Label(0.0, 0.0, ())]}
        for node, start, end in nodes:
            key = (end, node.node_uid)
            for (boundary, last_uid), incoming in tuple(labels.items()):
                if not start <= boundary < end or last_uid == node.node_uid:
                    continue
                if not self._allow_placement_edge(last_uid, node.node_uid):
                    continue
                previous = source if last_uid == source.node_uid else sim.compute_nodes[last_uid]
                prompt = sum(self._layer_service(node, layer,
                                                 RequestPhase.Initialization,
                                                 request.token_seq_length)
                             for layer in range(boundary, end))
                decode = self._decode_token_service(
                    node, boundary, end, sessions[node.node_uid])
                gpu_wait = max(0.0, gpu_release.get(node.node_uid,
                                                    sim.current_time) - sim.current_time)
                for link in previous.outbound_links.values():
                    if link.node_out.node_uid != node.node_uid:
                        continue
                    link_wait = max(0.0, link_release[link.link_uid] - sim.current_time)
                    work = prompt + gpu_wait + sessions[node.node_uid] * decode + \
                        link_wait + self._transfer_time(link, request)
                    pressure = self._pressure(previous, node, link, request,
                                              boundary, end)
                    for label in incoming:
                        item = Label(label.live_cost + work,
                                     label.pressure + pressure,
                                     label.path + ((link.link_uid, node.node_uid,
                                                    boundary, end),))
                        labels[key] = pareto_insert(labels.get(key, []), item)
        endings = []
        for (boundary, last_uid), incoming in labels.items():
            if boundary != sim.model_manager.get_num_layers():
                continue
            if not self._allow_placement_edge(last_uid, sink.node_uid):
                continue
            previous = sim.compute_nodes[last_uid]
            for link in previous.outbound_links.values():
                if link.node_out.node_uid != sink.node_uid:
                    continue
                link_wait = max(0.0, link_release[link.link_uid] - sim.current_time)
                work = link_wait + self._transfer_time(link, request)
                pressure = self._pressure(previous, None, link, request, 0, 0)
                endings.extend((label.live_cost + work,
                                label.pressure + pressure, label.path,
                                link.link_uid) for label in incoming)
        if not endings:
            raise RuntimeError("Placement has no source-to-sink layer route")
        earliest = min(row[0] for row in endings)
        allowed = [row for row in endings
                   if row[0] <= earliest + LIVE_COST_SLACK * max(1.0, earliest)]
        _, _, path, last_link = min(allowed, key=lambda row: (row[1], row[0],
                                                              row[2], row[3]))
        stages = [PipelineStage(link_uid=link_uid, bandwidth_usage=-1,
                                node_uid=node_uid,
                                layers_to_infer=list(range(first, end)))
                  for link_uid, node_uid, first, end in path]
        stages.append(PipelineStage(link_uid=last_link, bandwidth_usage=-1,
                                    node_uid=sink.node_uid, layers_to_infer=None))
        self.routes_assigned += 1
        return stages
