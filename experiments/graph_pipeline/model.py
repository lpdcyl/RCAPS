"""Explainable event-DAG cost model for pipeline inference.

Vertices represent a request's compute stages; directed edges represent token or
activation transfers. We add profiled service time and observed occupancy along a
path, while taking the largest per-stage demand as a capacity warning. This is a
critical-path and resource-demand model, not a token-flow network.
"""

from __future__ import annotations


def interpolate_profile(points: dict[int, float], tokens: int) -> float:
    """Linear interpolation of raw measured batch-size/time samples."""
    sizes = sorted(points)
    if not sizes[0] <= tokens <= sizes[-1]:
        raise ValueError(f"Batch size {tokens} is outside profiled range")
    if tokens in points:
        return points[tokens]
    left = max(size for size in sizes if size < tokens)
    right = min(size for size in sizes if size > tokens)
    return points[left] + (points[right] - points[left]) * (tokens - left) / (right - left)


class EventDagModel:
    def __init__(self, queue_weight: float = 0.03, session_weight: float = 0.012):
        self.queue_weight = queue_weight
        self.session_weight = session_weight

    def compute_cost(self, node, first_layer: int, last_layer: int,
                     prompt_tokens: int, active_sessions: int) -> dict:
        service = sum(interpolate_profile(node.in_vram_model_layers[k].prompt_bs2time,
                                          prompt_tokens)
                      for k in range(first_layer, last_layer))
        queues = len(node.inbound_request_queue) + sum(len(q) for q in node.between_layer_queues.values())
        contention = self.queue_weight * queues + self.session_weight * active_sessions
        return {"service_s": service, "queue_s": contention,
                "total_s": service + contention, "queued_requests": queues,
                "active_sessions": active_sessions}

    @staticmethod
    def transfer_cost(link, prompt_tokens: int, bytes_per_token: float) -> float:
        return link.latency + prompt_tokens * bytes_per_token / link.bandwidth

    @staticmethod
    def describe_path(stages: list[dict]) -> dict:
        critical_path_s = sum(stage["compute_s"] + stage["transfer_s"] + stage["queue_s"]
                              for stage in stages)
        bottleneck_s = max((stage["compute_s"] + stage["transfer_s"] for stage in stages),
                           default=0.0)
        return {"critical_path_s": critical_path_s, "bottleneck_stage_s": bottleneck_s,
                "stages": stages}
