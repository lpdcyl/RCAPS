"""Experimental controls for the V2 whole-method ablation."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from rcaps.scheduling.routing_dag import QueueDagScheduler
from simulator.event_simulator.coordinator_node import SourceNode
from simulator.event_simulator.network_link import TransmissionType
from simulator.event_simulator.request import PipelineStage, RequestPhase
from simulator.scheduler.base_scheduler import TransmissionSchedule


NAME_CAPACITY = "rcaps_v2_capacity_only"
NAME_STATIC = "rcaps_v2_static_routes"
NAME_BASE = "rcaps_v2_base_safe_static"
NAME_A = "rcaps_v2_fixed_safe_static"
NAME_AB = "rcaps_v2_adaptive_safe_static"


def capacity_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    directory = root / "experiments" / "v2_method_ablation" / "layouts" / scenario
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def static_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    directory = root / "rcaps" / "v2_layouts" / f"{scenario}_adaptive"
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def base_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    directory = root / "experiments" / "v2_method_ablation" / "layouts" / f"{scenario}_fixed_capacity"
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def fixed_static_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    directory = root / "rcaps" / "v2_layouts" / f"{scenario}_fixed"
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def adaptive_safe_static_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    return static_layout(scenario, root)


class StaticLegalPathScheduler(QueueDagScheduler):
    """Deterministic route rotation; no live-state path score or coalescing."""

    def __init__(self, simulator, placement: dict):
        super().__init__(simulator)
        self.placement = placement
        self.paths = []

    def _initialize_paths(self):
        # fixed_window installs the scheduler before loading model layers.
        simulator = self.simulator
        placement = self.placement
        spans = {int(node): tuple(pair) for node, pair in placement["intervals"].items()}
        expected_layers = simulator.model_manager.get_num_layers()
        for branch in placement["branches"]:
            route = [*placement["stem"], *branch]
            stages = []
            previous = simulator.source_node
            boundary = 0
            for node_id in route:
                start, end = spans[node_id]
                if start != boundary or not start < end:
                    raise ValueError("Canonical path does not cover consecutive layers")
                gpu = simulator.compute_nodes[node_id + 2]
                if sorted(gpu.in_vram_model_layers) != list(range(start, end)):
                    raise ValueError("Canonical path disagrees with loaded V2 layout")
                links = [link for link in previous.outbound_links.values()
                         if link.node_out.node_uid == gpu.node_uid]
                if len(links) != 1:
                    raise ValueError("Canonical path has no unique physical link")
                stages.append((links[0].link_uid, gpu.node_uid, start, end))
                previous = gpu
                boundary = end
            if boundary != expected_layers:
                raise ValueError("Canonical path does not complete the model")
            links = [link for link in previous.outbound_links.values()
                     if link.node_out.node_uid == simulator.sink_node.node_uid]
            if len(links) != 1:
                raise ValueError("Canonical path has no unique sink link")
            self.paths.append((stages, links[0].link_uid))
        if len(self.paths) not in (2, 3):
            raise ValueError("Unexpected number of V2 suffix paths")

    def _route(self, request):
        if not self.paths:
            self._initialize_paths()
        stages_spec, final_link = self.paths[self.routes_assigned % len(self.paths)]
        stages = [PipelineStage(link_uid=link_uid, bandwidth_usage=-1,
                                node_uid=node_uid, layers_to_infer=list(range(start, end)))
                  for link_uid, node_uid, start, end in stages_spec]
        stages.append(PipelineStage(link_uid=final_link, bandwidth_usage=-1,
                                    node_uid=self.simulator.sink_node.node_uid,
                                    layers_to_infer=None))
        self.routes_assigned += 1
        return stages


class CapacitySafeStaticPathScheduler(StaticLegalPathScheduler):
    """Keep fixed route rotation executable with a hard KV admission bound.

    The check only delays prompt admission. It never changes the route chosen
    by round-robin, execution priority, or transfer ordering. Each admitted
    query reserves its trace-defined input-plus-target-output KV footprint.
    The simulator exposes the exact target output length to this adapter;
    that is a conservative upper bound for this fixed-trace experiment.
    """

    def __init__(self, simulator, placement: dict):
        super().__init__(simulator, placement)
        self.kv_reservations = {}
        self.capacity_guard_block_events = 0

    def _can_reserve(self, request) -> bool:
        manager = self.simulator.query_manager
        live = manager.queries_on_the_fly
        self.kv_reservations = {uid: demand for uid, demand in self.kv_reservations.items()
                                if uid in live}
        if not self.paths:
            self._initialize_paths()
        path, _ = self.paths[self.routes_assigned % len(self.paths)]
        query = live[request.base_query_uid]
        max_tokens = query.input_seq_length + query.output_seq_length
        demand = {node_uid: (end - start) * max_tokens
                  for _, node_uid, start, end in path}
        reserved = defaultdict(int)
        for existing in self.kv_reservations.values():
            for node_uid, amount in existing.items():
                reserved[node_uid] += amount
        for node_uid, amount in demand.items():
            cache = self.simulator.compute_nodes[node_uid].kv_cache
            if reserved[node_uid] + amount > cache.max_capacity:
                self.capacity_guard_block_events += 1
                return False
        self.kv_reservations[request.base_query_uid] = demand
        return True

    def schedule_transmission(self, node):
        if not isinstance(node, SourceNode):
            return super().schedule_transmission(node)
        schedules = []
        free_send = node.outbound_available_bandwidth
        free_receive = {link.node_out.node_uid: link.node_out.inbound_available_bandwidth
                        for link in node.outbound_links.values()}
        used_links = set()
        requests = sorted(node.outbound_request_dict.values(),
                          key=lambda req: (req.phase != RequestPhase.Increment,
                                           req.location_history[0][1], req.request_uid))
        for request in requests:
            if request.phase == RequestPhase.Initialization and not request.pipeline_set:
                if not self._can_reserve(request):
                    break
                request.set_pipeline(self._route(request))
                self.session_paths[request.base_query_uid] = [
                    stage.node_uid for stage in request.mini_pipeline[:-1]]
            stage = request.get_next_pipeline_stage()
            link = node.outbound_links[stage.link_uid]
            if link.link_uid in used_links:
                continue
            amount = min(free_send, link.get_available_bandwidth(),
                         free_receive[link.node_out.node_uid])
            if amount <= 1:
                continue
            request.march_pipeline_stage()
            schedules.append(TransmissionSchedule(link_uid=link.link_uid,
                                                  bandwidth_usage=amount, requests=[request],
                                                  transmission_type=TransmissionType.NormalExecution))
            free_send -= amount
            free_receive[link.node_out.node_uid] -= amount
            used_links.add(link.link_uid)
            if free_send <= 1:
                break
        return schedules, []


def evaluate_capacity(scenario: str, offered: float, duration: int, warmup: int,
                      seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run
    from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler

    return run(scenario, "queue_dag", offered, duration, warmup, seed,
               solution, sim_cluster, profile_resources=True,
               scheduler_factory=QueueAwareDagScheduler, compact=True,
               record_query_samples=True)


def evaluate_static(scenario: str, offered: float, duration: int, warmup: int,
                    seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run

    placement_file = solution.parent / "placement.json"
    placement = json.loads(placement_file.read_text(encoding="utf-8"))
    return run(scenario, "static_legal_paths", offered, duration, warmup, seed,
               solution, sim_cluster, profile_resources=True,
               scheduler_factory=lambda sim: StaticLegalPathScheduler(sim, placement),
               compact=True, record_query_samples=True)


def evaluate_safe_static(scenario: str, offered: float, duration: int, warmup: int,
                         seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run

    placement = json.loads((solution.parent / "placement.json").read_text(encoding="utf-8"))
    scheduler_holder = {}

    def factory(sim):
        scheduler = CapacitySafeStaticPathScheduler(sim, placement)
        scheduler_holder["scheduler"] = scheduler
        return scheduler

    result = run(scenario, "capacity_safe_static_legal_paths", offered, duration, warmup, seed,
                 solution, sim_cluster, profile_resources=True,
                 scheduler_factory=factory, compact=True, record_query_samples=True)
    result["capacity_guard_block_events"] = scheduler_holder["scheduler"].capacity_guard_block_events
    return result
