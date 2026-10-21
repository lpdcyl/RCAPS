"""Parameter-free non-preemptive priority M/G/1 interference proxy."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Iterable, Mapping


Edge = tuple[int, int]


@dataclass(frozen=True)
class LinkMoments:
    lambda_prompt: float
    lambda_decode: float
    mean_prompt_s: float
    mean_decode_s: float
    second_prompt_s2: float
    second_decode_s2: float

    @property
    def rho_decode(self) -> float:
        return self.lambda_decode * self.mean_decode_s

    @property
    def wait_decode_s(self) -> float:
        if self.rho_decode >= 1:
            return inf
        return (self.lambda_prompt * self.second_prompt_s2
                + self.lambda_decode * self.second_decode_s2) / (2 * (1 - self.rho_decode))


def effective_bandwidth(link_bytes_per_s: float, sender_nic_bytes_per_s: float,
                        receiver_nic_bytes_per_s: float) -> float:
    """Match routing._transfer_time's min(link, sender NIC, receiver NIC)."""
    result = min(link_bytes_per_s, sender_nic_bytes_per_s,
                 receiver_nic_bytes_per_s)
    if result <= 0:
        raise ValueError("Effective bandwidth must be positive")
    return result


def payload_bytes(token_bytes: float, activation_bytes: float,
                  token_count: int, *, internal: bool = True) -> float:
    """Match routing._transfer_time's payload, without propagation latency."""
    if token_count < 0 or token_bytes < 0 or activation_bytes < 0:
        raise ValueError("Payload inputs must be nonnegative")
    per_token = token_bytes + activation_bytes if internal else token_bytes
    return per_token * token_count


def from_message_sizes(prompt_bytes: Iterable[float], decode_bytes: Iterable[float],
                       duration_s: float, bandwidth_bytes_per_s: float) -> LinkMoments:
    """Use individual message sizes for exact first and second moments."""
    if duration_s <= 0 or bandwidth_bytes_per_s <= 0:
        raise ValueError("Duration and bandwidth must be positive")
    prompt = tuple(prompt_bytes)
    decode = tuple(decode_bytes)
    if any(value < 0 for value in (*prompt, *decode)):
        raise ValueError("Message bytes must be nonnegative")

    def moments(messages: tuple[float, ...]) -> tuple[float, float]:
        if not messages:
            return 0.0, 0.0
        occupied = [value / bandwidth_bytes_per_s for value in messages]
        return (sum(occupied) / len(occupied),
                sum(value * value for value in occupied) / len(occupied))

    mp, sp2 = moments(prompt)
    md, sd2 = moments(decode)
    return LinkMoments(len(prompt) / duration_s, len(decode) / duration_s,
                       mp, md, sp2, sd2)


def from_trace_shares(
        requests: Iterable[tuple[int, int]], duration_s: float,
        edge_shares: Mapping[Edge, float], edge_bandwidths: Mapping[Edge, float],
        token_bytes: float, activation_bytes: float) -> dict[Edge, LinkMoments]:
    """Expected per-edge moments under a fixed, class-independent path share.

    Every request creates one Prompt message and output_length Decode messages
    on each traversed compute-to-compute edge. Each edge's path share multiplies
    both message rates; it does not alter the service-time distributions.
    """
    if duration_s <= 0:
        raise ValueError("Duration must be positive")
    lengths = tuple(requests)
    if any(prompt < 0 or decode < 0 for prompt, decode in lengths):
        raise ValueError("Request lengths must be nonnegative")
    count = len(lengths)
    total_decode = sum(decode for _, decode in lengths)
    result: dict[Edge, LinkMoments] = {}
    for edge, share in edge_shares.items():
        if not 0 <= share <= 1:
            raise ValueError("Path share must be in [0, 1]")
        bandwidth = edge_bandwidths[edge]
        if bandwidth <= 0:
            raise ValueError("Bandwidth must be positive")
        prompt_times = [payload_bytes(token_bytes, activation_bytes, prompt)
                        / bandwidth for prompt, _ in lengths]
        decode_time = payload_bytes(token_bytes, activation_bytes, 1) / bandwidth
        result[edge] = LinkMoments(
            lambda_prompt=share * count / duration_s,
            lambda_decode=share * total_decode / duration_s,
            mean_prompt_s=sum(prompt_times) / count if count else 0.0,
            mean_decode_s=decode_time if total_decode else 0.0,
            second_prompt_s2=(sum(value * value for value in prompt_times) / count
                              if count else 0.0),
            second_decode_s2=decode_time * decode_time if total_decode else 0.0,
        )
    return result


def path_weighted_wait(edge_shares: Mapping[Edge, float],
                       moments: Mapping[Edge, LinkMoments]) -> float:
    """Expected sum of compute-to-compute W along an equally split path."""
    return sum(share * moments[edge].wait_decode_s
               for edge, share in edge_shares.items() if share > 0)
