"""Full-cycle session pricing for V3 M3 (candidate, not the frozen method).

Frozen V3 prices a GPU on a prompt route by the live KV sessions times the
decode work of only the layer slice this request would run there. A decode
token, however, waits for the GPU's whole cyclic layer round
(``ComputeNode.march_to_next_layer`` visits every resident layer), and the
decode route is locked to the prompt route. A cross-replica path that enters
a GPU mid-segment therefore pays that GPU's full round on every token while
the frozen price charges only the slice.

The candidate charges the full resident-layer round instead of the slice.
On a canonical path every GPU runs its full segment, so the price is
unchanged; only partial-segment hops become more expensive. There is no
new coefficient.
"""

from __future__ import annotations

from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler


class RouteRecorder:
    """Record compute hops of every admitted prompt route without changing it."""

    def _route(self, request):
        stages = super()._route(request)
        partial = 0
        for stage in stages[:-1]:
            resident = self.simulator.compute_nodes[stage.node_uid].in_vram_model_layers
            if len(stage.layers_to_infer) != len(resident):
                partial += 1
        if not hasattr(self, "route_records"):
            self.route_records = {}
        self.route_records[request.base_query_uid] = (len(stages) - 1, partial)
        return stages


class RecordedV3Scheduler(RouteRecorder, GraphModeledQueueAwareDagScheduler):
    """Frozen V3 M3 with passive route recording."""


class FullCycleSessionScheduler(RouteRecorder, GraphModeledQueueAwareDagScheduler):
    """V3 M3 that prices every visited GPU by its full decode round."""

    def _decode_token_service(self, node, first, end, active_sessions):
        layers = sorted(node.in_vram_model_layers)
        return super()._decode_token_service(node, layers[0], layers[-1] + 1,
                                             active_sessions)
