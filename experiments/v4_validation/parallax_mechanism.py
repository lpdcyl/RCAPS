"""Parallax-inspired P2 layer-DAG latency routing on the common RCAPS stack.

Not a reproduction of the complete Parallax system. The paper P2 recurrence
is constrained to the common simulator's resident-span exit boundaries;
the live latency map is explicitly operationalized using the
simulator's present unfinished GPU work plus profiled Prompt layer service.
No future arrivals, future completion times, or observed outcome tuning.
"""
from __future__ import annotations

from simulator.event_simulator.request import RequestPhase, PipelineStage
from .diagnostics import ProfileScheduler


class ParallaxInspiredScheduler(ProfileScheduler):
    def _route(self, request):
        sim = self.simulator
        if self.allowed_edges is None:
            self._initialize_graph()
        source, sink = sim.source_node, sim.sink_node
        nodes = {uid:n for uid,n in sim.compute_nodes.items() if n.in_vram_model_layers}
        links = {(l.node_in.node_uid,l.node_out.node_uid):l for l in sim.links.values()}
        release,_ = self._release_snapshot()
        queue = {uid:max(0.,release.get(uid,sim.current_time)-sim.current_time)
                 /len(n.in_vram_model_layers) for uid,n in nodes.items()}
        # Each state is (cumulative latency, tuple of chosen GPU for each layer).
        states = {}
        for layer in range(sim.model_manager.get_num_layers()):
            following = {}
            for uid,node in sorted(nodes.items()):
                if layer not in node.in_vram_model_layers:
                    continue
                tau = self._layer_service(node,layer,RequestPhase.Initialization,
                                          request.token_seq_length)+queue[uid]
                if layer == 0:
                    link=links.get((source.node_uid,uid))
                    if link is not None and self._allow_placement_edge(source.node_uid,uid):
                        following[uid]=(link.latency+tau,(uid,))
                    continue
                best = None
                for previous,(cost,path) in sorted(states.items()):
                    if previous == uid:
                        candidate=(cost+tau,path+(uid,))
                    else:
                        # The common executor always finishes the resident
                        # layer span before forwarding. RCAPS obeys the same
                        # restriction. An early exit produces extra execution
                        # and a discontinuous next stage, even if the abstract
                        # per-layer chain itself covers every layer once.
                        if max(nodes[previous].in_vram_model_layers) != layer-1:
                            continue
                        link=links.get((previous,uid))
                        if link is None or not self._allow_placement_edge(previous,uid):
                            continue
                        candidate=(cost+link.latency+tau,path+(uid,))
                    if best is None or candidate < best:
                        best=candidate
                if best is not None:
                    following[uid]=best
            states=following
        candidates=[]
        for uid,(cost,path) in states.items():
            link=links.get((uid,sink.node_uid))
            if link is not None and self._allow_placement_edge(uid,sink.node_uid):
                candidates.append((cost+link.latency,path,link.link_uid))
        if not candidates:
            raise RuntimeError('No complete admissible Parallax-inspired layer chain')
        _,path,final_link=min(candidates)
        stages=[]
        start,previous=0,source.node_uid
        while start<len(path):
            uid=path[start]; end=start+1
            while end<len(path) and path[end]==uid:
                end+=1
            stages.append(PipelineStage(link_uid=links[previous,uid].link_uid,
                bandwidth_usage=-1,node_uid=uid,layers_to_infer=list(range(start,end))))
            previous,start=uid,end
        assert [layer for stage in stages for layer in stage.layers_to_infer]==list(range(len(path)))
        assert all(stage.layers_to_infer[-1] == max(nodes[stage.node_uid].in_vram_model_layers)
                   for stage in stages)
        stages.append(PipelineStage(link_uid=final_link,bandwidth_usage=-1,
                                    node_uid=sink.node_uid,layers_to_infer=None))
        self.routes_assigned+=1
        return stages


def evaluate(job,duration=1800):
    from . import diagnostics
    original=diagnostics.ProfileScheduler
    diagnostics.ProfileScheduler=ParallaxInspiredScheduler
    try:
        row=diagnostics.evaluate(dict(job,condition='reference',cell='v4'),duration,duration)
    finally:
        diagnostics.ProfileScheduler=original
    row['comparison_identity']={
        'display_name':'Boundary-constrained Parallax-inspired DAG latency routing + common RCAPS placement/S/T',
        'kind':'mechanism_control_not_full_system',
        'source':'arXiv:2509.26182v1, section 3.3, P2 recurrence',
        'fixed':'RCAPS M2 layout, legal/admitted links, Prompt/Decode execution, S/T and batch profiles',
        'changed':'M3 replaced by per-layer min-sum DP with live GPU latency and physical one-way latency',
        'tau_definition':'Profiled Prompt layer service plus current unfinished GPU wait divided by loaded layer count',
        'rho_definition':'Physical one-way propagation latency; no payload serialization or link queue price in route objective',
        'deviations':['No Parallax phase-1 allocation or water-filling',
                      'No distributed DHT, periodic telemetry, membership changes, or original inference engine',
                      'Live latency definition is an explicit simulator adaptation, not verified original code',
                      'GPU handoff is restricted to resident-span ends, as required by the common executor and RCAPS routes; arbitrary early per-layer handoffs are not evaluated',
                      'Common S admissibility constrains candidate links; this is not unrestricted Parallax routing'],
        'allowed_claim':'Difference between these routing mechanisms under common simulated execution; not RCAPS versus full Parallax'}
    return row
