"""Queue-aware DAG routing with immediate decode-transfer coalescing."""

from __future__ import annotations

from simulator.event_simulator.coordinator_node import SourceNode
from simulator.event_simulator.network_link import TransmissionType
from simulator.event_simulator.request import RequestPhase
from simulator.scheduler.base_scheduler import TransmissionSchedule

from .scheduler_queue_cost import SingleTokenQueueCostScheduler


class DecodeTransferBatchingScheduler(SingleTokenQueueCostScheduler):
    """Pay the link propagation delay once for ready decodes sharing a hop.

    The batch contains only requests already queued for the same link at this
    scheduling event. Prompts remain individually transferable, so a large
    prompt cannot extend a decode transfer batch. No holdback timer or future
    arrival estimate is used.
    """

    def schedule_transmission(self, node):
        free_send = node.outbound_available_bandwidth
        free_receive = {link.node_out.node_uid: link.node_out.inbound_available_bandwidth
                        for link in node.outbound_links.values()}
        grouped = {}
        requests = sorted(node.outbound_request_dict.values(),
                          key=lambda req: (req.phase != RequestPhase.Increment,
                                           req.location_history[0][1], req.request_uid))
        for request in requests:
            if request.phase == RequestPhase.Initialization and not request.pipeline_set:
                if not isinstance(node, SourceNode):
                    raise RuntimeError("Only source may assign a prompt route")
                request.set_pipeline(self._route(request))
                self.session_paths[request.base_query_uid] = [
                    stage.node_uid for stage in request.mini_pipeline[:-1]]
            stage = request.get_next_pipeline_stage()
            grouped.setdefault(stage.link_uid, []).append(request)

        schedules = []
        for link_uid, ready in grouped.items():
            link = node.outbound_links[link_uid]
            amount = min(free_send, link.get_available_bandwidth(),
                         free_receive[link.node_out.node_uid])
            if amount <= 1:
                continue
            decodes = [req for req in ready if req.phase == RequestPhase.Increment]
            selected = decodes if decodes else ready[:1]
            for request in selected:
                request.march_pipeline_stage()
            schedules.append(TransmissionSchedule(
                link_uid=link_uid, bandwidth_usage=amount, requests=selected,
                transmission_type=TransmissionType.NormalExecution))
            free_send -= amount
            free_receive[link.node_out.node_uid] -= amount
            if free_send <= 1:
                break
        return schedules, []


# Historical ablation name for the transfer-only variant.
CoalescedQueueDagScheduler = DecodeTransferBatchingScheduler


class QueueAwareDagScheduler(DecodeTransferBatchingScheduler):
    """Final scheduler: queue-aware routing and grouped decode transfers.

    Correct the service cost for a one-request decode batch to match the
    simulator's execution profile.
    """

    def _decode_token_service(self, node, first, end, active_sessions):
        return 2 * super()._decode_token_service(node, first, end, active_sessions)


# Historical experiment records use the old class and policy name.
CorrectedCoalescedQueueDagScheduler = QueueAwareDagScheduler
