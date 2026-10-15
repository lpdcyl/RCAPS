"""Benchmark adapters for complete V2 method alternatives."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.v2_method_ablation.adapters import StaticLegalPathScheduler
from simulator.event_simulator.request import PipelineStage


STATIC_RESOURCE = "rcaps_v2_static_resource_model"
BEAM_SEARCH = "rcaps_v2_beam_placement"
LIVE_PIPELINE = "rcaps_v2_live_pipeline"


def generated_layout(variant: str, scenario: str, root: Path) -> tuple[Path, Path]:
    if scenario not in ("single", "multi"):
        raise ValueError(scenario)
    directory = root / "experiments" / "v2_method_comparisons" / "layouts" / variant / scenario
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def static_resource_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    return generated_layout("static_resource", scenario, root)


def beam_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    return generated_layout("beam_search", scenario, root)


def v2_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    directory = root / "rcaps" / "v2_layouts" / f"{scenario}_adaptive"
    return directory / "solution.ini", directory / "simulator_cluster.ini"


class LiveCanonicalPipelineScheduler(StaticLegalPathScheduler):
    """Select a complete legal pipeline by its current projected prefill finish.

    Decode remains on that path; transmissions are per request. This replaces
    the online scheduling method rather than changing one V2 route-cost term.
    """

    def _route(self, request):
        if not self.paths:
            self._initialize_paths()
        now = self.simulator.current_time
        gpu_release, link_release = self._release_snapshot()
        options = []
        for index, (stages, final_link) in enumerate(self.paths):
            finish = now
            for link_uid, node_uid, first, end in stages:
                link = self.simulator.links[link_uid]
                node = self.simulator.compute_nodes[node_uid]
                arrival = max(finish, link_release.get(link_uid, now))
                arrival += self._transfer_time(link, request)
                finish = max(arrival, gpu_release.get(node_uid, now))
                finish += self._request_work(node, request, first, end)
            sink_link = self.simulator.links[final_link]
            finish = max(finish, link_release.get(final_link, now))
            finish += self._transfer_time(sink_link, request)
            options.append((finish, index, stages, final_link))
        _, _, stages_spec, final_link = min(options)
        stages = [PipelineStage(link_uid=link_uid, bandwidth_usage=-1,
                                node_uid=node_uid, layers_to_infer=list(range(first, end)))
                  for link_uid, node_uid, first, end in stages_spec]
        stages.append(PipelineStage(link_uid=final_link, bandwidth_usage=-1,
                                    node_uid=self.simulator.sink_node.node_uid,
                                    layers_to_infer=None))
        self.routes_assigned += 1
        return stages


def evaluate_placement(scenario: str, offered: float, duration: int,
                       warmup: int, seed: int, solution: Path,
                       sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run
    from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler

    return run(scenario, "queue_dag", offered, duration, warmup, seed,
               solution, sim_cluster, profile_resources=True,
               scheduler_factory=QueueAwareDagScheduler, compact=True,
               record_query_samples=True)


def evaluate_pipeline(scenario: str, offered: float, duration: int,
                      warmup: int, seed: int, solution: Path,
                      sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run

    placement = json.loads((solution.parent / "placement.json").read_text(
        encoding="utf-8"))
    return run(scenario, "live_canonical_pipeline", offered, duration,
               warmup, seed, solution, sim_cluster, profile_resources=True,
               scheduler_factory=lambda sim: LiveCanonicalPipelineScheduler(sim, placement),
               compact=True, record_query_samples=True)
