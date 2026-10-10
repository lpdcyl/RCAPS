"""A max-plus event graph for explaining pipeline latency and resource contention.

Each event is a compute operation, a transfer, or an explicitly measured wait.
Dependency edges encode layer order and token causality. Resource edges encode
the order in which a GPU or a link serves operations. The longest path is the
completion time of the represented execution, not a network-flow estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import isclose


@dataclass(frozen=True)
class Event:
    name: str
    duration_s: float
    dependencies: tuple[str, ...]
    kind: str
    resource: str | None = None


@dataclass(frozen=True)
class CriticalPath:
    completion_s: float
    events: tuple[str, ...]
    resource_time_s: dict[str, float]


class EventGraph:
    def __init__(self) -> None:
        self.events: dict[str, Event] = {}
        self._last_on_resource: dict[str, str] = {}

    def add(self, name: str, duration_s: float, dependencies=(), *,
            kind: str, resource: str | None = None,
            serialize_resource: bool = False) -> str:
        if name in self.events:
            raise ValueError(f"Duplicate event: {name}")
        if duration_s < 0:
            raise ValueError(f"Negative duration for {name}")
        parents = list(dict.fromkeys(dependencies))
        for parent in parents:
            if parent not in self.events:
                raise ValueError(f"Unknown predecessor {parent} for {name}")
        if serialize_resource:
            if resource is None:
                raise ValueError("Resource serialization needs a resource name")
            previous = self._last_on_resource.get(resource)
            if previous is not None and previous not in parents:
                parents.append(previous)
            self._last_on_resource[resource] = name
        self.events[name] = Event(name, float(duration_s), tuple(parents), kind, resource)
        return name

    def critical_path(self, finish: str) -> CriticalPath:
        if finish not in self.events:
            raise ValueError(f"Unknown finish event: {finish}")
        # Edges always point to events already inserted, but use a topological
        # pass so callers can inspect the graph independently of insertion order.
        indegree = {name: len(event.dependencies) for name, event in self.events.items()}
        children: dict[str, list[str]] = {name: [] for name in self.events}
        for name, event in self.events.items():
            for parent in event.dependencies:
                children[parent].append(name)
        ready: list[str] = []
        for name, degree in indegree.items():
            if degree == 0:
                heappush(ready, name)
        finish_times: dict[str, float] = {}
        predecessor: dict[str, str | None] = {}
        while ready:
            name = heappop(ready)
            event = self.events[name]
            parent = max(event.dependencies, key=lambda p: (finish_times[p], p), default=None)
            start_s = finish_times[parent] if parent is not None else 0.0
            finish_times[name] = start_s + event.duration_s
            predecessor[name] = parent
            for child in children[name]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    heappush(ready, child)
        if len(finish_times) != len(self.events):
            raise ValueError("Event dependencies contain a cycle")
        path: list[str] = []
        cursor: str | None = finish
        resource_time: dict[str, float] = {}
        while cursor is not None:
            path.append(cursor)
            event = self.events[cursor]
            if event.resource is not None:
                resource_time[event.resource] = (
                    resource_time.get(event.resource, 0.0) + event.duration_s
                )
            cursor = predecessor[cursor]
        path.reverse()
        assert isclose(sum(self.events[name].duration_s for name in path),
                       finish_times[finish], rel_tol=1e-9, abs_tol=1e-9)
        return CriticalPath(finish_times[finish], tuple(path), resource_time)


def pipeline_graph(stages: list[dict], *, prompt_tokens: int,
                   generated_tokens: int, queue_wait_s: dict[str, float] | None = None,
                   serialize_resources: bool = True) -> tuple[EventGraph, str]:
    """Build a request's prefill and decode DAG from profiled stage/link costs.

    A stage supplies ``device``, ``prefill_s``, ``decode_s``, ``incoming_link``,
    ``incoming_latency_s``, ``incoming_bytes_per_s`` and ``payload_bytes``.
    The link's prefill payload scales with prompt length; decode carries one
    token plus activation on compute-to-compute links. In the Helix simulator,
    sending occupies bandwidth for payload/bandwidth and propagation then adds
    one RTT before the receiver sees the request. A stage's queue wait can be
    supplied from observed workload.
    ``generated_tokens`` includes the first token emitted by prefill.
    """
    if prompt_tokens < 1 or generated_tokens < 1:
        raise ValueError("Both token counts must be positive")
    if not stages:
        raise ValueError("A pipeline needs at least one stage")
    graph = EventGraph()
    waits = queue_wait_s or {}
    last_token_finish: str | None = None
    for token in range(generated_tokens):
        previous: str | None = last_token_finish if token > 0 else None
        for index, stage in enumerate(stages):
            device = str(stage["device"])
            link = str(stage["incoming_link"])
            items = (int(stage.get("prefill_items", prompt_tokens)) if token == 0
                     else int(stage.get("decode_items", 1)))
            payload = float(stage["payload_bytes"]) * items
            bandwidth = float(stage["incoming_bytes_per_s"])
            if bandwidth <= 0:
                raise ValueError(f"Nonpositive bandwidth on {link}")
            transfer = graph.add(
                f"token{token}:transfer{index}", payload / bandwidth,
                () if previous is None else (previous,), kind="transfer",
                resource=f"link:{link}", serialize_resource=serialize_resources,
            )
            transfer = graph.add(
                f"token{token}:propagation{index}",
                float(stage["incoming_latency_s"]), (transfer,), kind="propagation")
            wait = float(waits.get(device, 0.0)) if token == 0 else 0.0
            if wait:
                transfer = graph.add(f"token{token}:wait{index}", wait,
                                     (transfer,), kind="queue", resource=f"gpu:{device}")
            previous = graph.add(
                f"token{token}:compute{index}",
                float(stage["prefill_s"] if token == 0 else stage["decode_s"]),
                (transfer,), kind="compute", resource=f"gpu:{device}",
                serialize_resource=serialize_resources,
            )
        assert previous is not None
        last_token_finish = previous
    assert last_token_finish is not None
    return graph, last_token_finish


def interleaved_workload_graph(pipelines: list[list[dict]], *, prompt_tokens: int,
                               generated_tokens: int, arrivals_s: list[float]
                               ) -> tuple[EventGraph, list[str], list[str]]:
    """Replay concurrent requests over shared GPU and link resources.

    Operations are offered in token-round order. Resource edges serialize uses
    of a GPU or link; dependency edges preserve each request's layer and token
    order. The returned first/last event IDs permit per-request latency analysis.
    """
    if not pipelines or len(pipelines) != len(arrivals_s):
        raise ValueError("Each request needs a pipeline and arrival time")
    if generated_tokens < 1 or prompt_tokens < 1:
        raise ValueError("Token counts must be positive")
    graph = EventGraph()
    previous: list[str | None] = []
    first_token: list[str] = [""] * len(pipelines)
    for request, arrival_s in enumerate(arrivals_s):
        if arrival_s < 0:
            raise ValueError("Arrival times must be nonnegative")
        previous.append(graph.add(f"request{request}:arrival", arrival_s,
                                  kind="arrival"))
    for token in range(generated_tokens):
        for request, stages in enumerate(pipelines):
            if not stages:
                raise ValueError("A request needs at least one stage")
            parent = previous[request]
            for index, stage in enumerate(stages):
                items = (int(stage.get("prefill_items", prompt_tokens)) if token == 0
                         else int(stage.get("decode_items", 1)))
                bandwidth = float(stage["incoming_bytes_per_s"])
                if bandwidth <= 0:
                    raise ValueError("Link bandwidth must be positive")
                transfer_s = items * float(stage["payload_bytes"]) / bandwidth
                parent = graph.add(
                    f"request{request}:token{token}:transfer{index}", transfer_s,
                    (parent,), kind="transfer", resource=f"link:{stage['incoming_link']}",
                    serialize_resource=True,
                )
                parent = graph.add(
                    f"request{request}:token{token}:propagation{index}",
                    float(stage["incoming_latency_s"]), (parent,), kind="propagation")
                parent = graph.add(
                    f"request{request}:token{token}:compute{index}",
                    float(stage["prefill_s"] if token == 0 else stage["decode_s"]),
                    (parent,), kind="compute", resource=f"gpu:{stage['device']}",
                    serialize_resource=True,
                )
            assert parent is not None
            previous[request] = parent
            if token == 0:
                first_token[request] = parent
    return graph, first_token, [event for event in previous if event is not None]
