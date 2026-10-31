"""Independent execution toggles over the existing Helix MaxFlow scheduler."""
from __future__ import annotations

from simulator.event_simulator.network_link import TransmissionType
from simulator.event_simulator.coordinator_node import SourceNode
from simulator.event_simulator.request import RequestPhase
from simulator.scheduler.base_scheduler import TransmissionSchedule
from simulator.scheduler.global_maxflow.global_maxflow_scheduler import GlobalFlowScheduler
from simulator.scheduler.global_maxflow.kv_expectation import KVParameters
from simulator.scheduler.global_maxflow.network_flow import FlowParameters
from simulator.scheduler.global_maxflow.scheduler_core import SchedulingMode

from experiments.v5_core_supplement.adapters import HelixPlus
from rcaps.v3.online_scheduler import DecodeTransferBatchingScheduler
from rcaps.v3.routing import QueueDagScheduler


class TunableHelix(HelixPlus):
    """Keep MaxFlow route assignment; change only independently chosen toggles."""

    prompt_link_priority = False

    def __init__(self, simulator, priority: bool, batch: bool,
                 expected_kv_hwm: float, expected_output_length_ratio: float):
        GlobalFlowScheduler.__init__(
            self,
            FlowParameters(token_size=simulator.model_manager.get_model_token_size(),
                           token_activation_size=simulator.model_manager.get_model_activation_size()),
            simulator,
            KVParameters(expected_kv_hwm=expected_kv_hwm,
                         expected_output_length_ratio=expected_output_length_ratio),
            SchedulingMode.Online)
        self.simulator = simulator
        self.omitted_idle_nodes = []
        self.priority = bool(priority)
        self.batch = bool(batch)

    def schedule_execution(self, node, executable_requests):
        method = (QueueDagScheduler.schedule_execution if self.priority
                  else GlobalFlowScheduler.schedule_execution)
        return method(self, node, executable_requests)

    def schedule_transmission(self, node):
        if self.priority and self.batch:
            return DecodeTransferBatchingScheduler.schedule_transmission(self, node)
        if self.priority:
            return QueueDagScheduler.schedule_transmission(self, node)
        if not self.batch:
            return GlobalFlowScheduler.schedule_transmission(self, node)
        return self._fifo_decode_batch(node)

    def _fifo_decode_batch(self, node):
        """Batch only a contiguous ready decode prefix on one FIFO hop."""
        if isinstance(node, SourceNode):
            # A source can have prompts queued before MaxFlow installs their route.
            return GlobalFlowScheduler.schedule_transmission(self, node)
        free_send = node.outbound_available_bandwidth
        free_receive = {link.node_out.node_uid: link.node_out.inbound_available_bandwidth
                        for link in node.outbound_links.values()}
        ready = list(node.outbound_request_dict.values())
        schedules = []
        used = set()
        selected_ids = set()
        for request in ready:
            if request.request_uid in selected_ids:
                continue
            if not request.pipeline_set:
                raise RuntimeError("MaxFlow must assign the route before sending")
            stage = request.get_next_pipeline_stage()
            if stage.link_uid not in node.outbound_links:
                raise RuntimeError(
                    f"MaxFlow queued request {request.request_uid} for hop "
                    f"{stage.link_uid} outside node {node.node_uid}; FIFO batching unavailable")
            if stage.link_uid in used:
                continue
            link = node.outbound_links[stage.link_uid]
            amount = min(free_send, link.get_available_bandwidth(),
                         free_receive[link.node_out.node_uid])
            if amount <= 1:
                continue
            selected = [request]
            if request.phase == RequestPhase.Increment:
                # Preserve order: a prompt at the head of this hop stops coalescing.
                later = False
                for other in ready:
                    if other is request:
                        later = True
                        continue
                    if (not later or other.request_uid in selected_ids or
                            other.get_next_pipeline_stage().link_uid != stage.link_uid):
                        continue
                    if other.phase != RequestPhase.Increment:
                        break
                    selected.append(other)
            for item in selected:
                selected_ids.add(item.request_uid)
                item.march_pipeline_stage()
            schedules.append(TransmissionSchedule(
                link_uid=stage.link_uid, bandwidth_usage=amount,
                requests=selected, transmission_type=TransmissionType.NormalExecution))
            used.add(stage.link_uid)
            free_send -= amount
            free_receive[link.node_out.node_uid] -= amount
            if free_send <= 1:
                break
        return schedules, []


def factory(priority, batch, hwm, ratio):
    return lambda simulator: TunableHelix(simulator, priority, batch, hwm, ratio)
