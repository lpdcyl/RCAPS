"""Deterministic request-level dispatch over an aggregate path quota."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Request:
    request_id: str
    tokens: float = 1.0

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if self.tokens <= 0.0:
            raise ValueError("request tokens must be positive")


@dataclass(frozen=True, slots=True)
class DispatchDecision:
    request_id: str
    path: str | None
    tokens: float
    accepted: bool
    reason: str


@dataclass(frozen=True, slots=True)
class DispatchBatchResult:
    decisions: tuple[DispatchDecision, ...]
    remaining_quota_tokens: Mapping[str, float]
    accepted_tokens: float
    rejected_tokens: float


class DeterministicQuotaDispatcher:
    """Use largest normalized remaining quota, then path name as tie-break."""

    def __init__(
        self,
        path_quota_tokens_per_second: Mapping[str, float],
        *,
        duration_seconds: float,
        tolerance: float = 1e-9,
    ) -> None:
        if duration_seconds <= 0.0:
            raise ValueError("duration_seconds must be positive")
        if any(value < 0.0 for value in path_quota_tokens_per_second.values()):
            raise ValueError("Path quotas cannot be negative")
        self._remaining = {
            path: float(rate) * duration_seconds
            for path, rate in sorted(path_quota_tokens_per_second.items())
        }
        self.tolerance = tolerance

    def dispatch(self, request: Request) -> DispatchDecision:
        feasible = [
            path
            for path, remaining in self._remaining.items()
            if remaining + self.tolerance >= request.tokens
        ]
        if not feasible:
            return DispatchDecision(
                request.request_id,
                None,
                request.tokens,
                False,
                "quota_exhausted_or_no_feasible_path",
            )
        path = min(
            feasible,
            key=lambda candidate: (
                -self._remaining[candidate],
                candidate,
            ),
        )
        self._remaining[path] -= request.tokens
        return DispatchDecision(
            request.request_id,
            path,
            request.tokens,
            True,
            "accepted",
        )

    def dispatch_batch(self, requests: Sequence[Request]) -> DispatchBatchResult:
        decisions = tuple(self.dispatch(request) for request in requests)
        accepted = sum(decision.tokens for decision in decisions if decision.accepted)
        rejected = sum(decision.tokens for decision in decisions if not decision.accepted)
        if any(value < -self.tolerance for value in self._remaining.values()):
            raise RuntimeError("Dispatch exceeded aggregate path quota")
        return DispatchBatchResult(
            decisions,
            dict(sorted(self._remaining.items())),
            accepted,
            rejected,
        )
