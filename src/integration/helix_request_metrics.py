"""Request-level metrics extracted from the unmodified Helix simulator.

The adapter deliberately consumes the simulator's public state objects instead of
changing the event loop or scheduler.  A completed query is represented by the
``(completion_time, Query)`` tuple stored in ``QueryManager.finished_queries``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean
from typing import Any, Iterable, Mapping


def percentile(values: Iterable[float], q: float) -> float | None:
    """Return a deterministic linearly interpolated percentile.

    ``q`` is in ``[0, 1]``.  ``None`` is returned for an empty sample rather
    than manufacturing a latency for a missing observation.
    """

    sample = sorted(float(value) for value in values)
    if not sample:
        return None
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    if len(sample) == 1:
        return sample[0]
    position = q * (len(sample) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sample[lower]
    fraction = position - lower
    return sample[lower] + fraction * (sample[upper] - sample[lower])


def _phase_name(value: Any) -> str:
    """Normalize ``RequestPhase`` values without importing Helix eagerly."""

    name = getattr(value, "name", None)
    if name in {"Initialization", "Increment"}:
        return str(name)
    text = str(getattr(value, "value", value))
    if text.endswith("Initialization"):
        return "Initialization"
    if text.endswith("Increment"):
        return "Increment"
    return text


def _finite_time(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class QueryMetrics:
    """Metrics for one Helix query.

    ``helix_prompt_latency`` and ``helix_decode_iteration_latency`` preserve
    the simulator's original request-level metrics.  TTFT uses the completion
    of the initialization request as the first-token-ready boundary; see the
    audit report for the semantic limitation of this approximation.
    """

    query_uid: int
    creation_time: float
    completion_time: float | None
    complete: bool
    input_tokens: int
    output_tokens: int
    ttft: float | None
    tbt_mean: float | None
    tbt_p50: float | None
    tbt_p95: float | None
    tbt_p99: float | None
    tbt_intervals: tuple[float, ...]
    e2e: float | None
    helix_prompt_latency: float | None
    helix_decode_iteration_latency: tuple[float, ...]

    @property
    def helix_decode_iteration_latency_mean(self) -> float | None:
        """Mean of the per-iteration decode request latencies."""

        if not self.helix_decode_iteration_latency:
            return None
        return mean(self.helix_decode_iteration_latency)


def extract_query_metrics(query: Any, completion_time: float | None = None) -> QueryMetrics:
    """Extract TTFT/TBT/E2E and preserved Helix metrics from a ``Query``.

    The function accepts a duck-typed query so unit tests and downstream tools
    do not need to construct a complete simulator.  Histories must be in the
    order in which Helix appended them and have monotonic start/end times.
    An unfinished query never receives an invented E2E value.
    """

    creation = _finite_time(query.creation_time, "query.creation_time")
    histories = list(getattr(query, "inference_history", ()))
    previous_end = creation
    for index, history in enumerate(histories):
        start = _finite_time(history.start_time, f"history[{index}].start_time")
        end = _finite_time(history.end_time, f"history[{index}].end_time")
        if end < start:
            raise ValueError(f"history[{index}] ends before it starts")
        if start < previous_end:
            raise ValueError("query inference timestamps are not monotonic")
        previous_end = end

    initialization = [h for h in histories if _phase_name(h.request_phase) == "Initialization"]
    decode = [h for h in histories if _phase_name(h.request_phase) == "Increment"]
    prompt = initialization[0] if initialization else None
    ttft = None if prompt is None else _finite_time(prompt.end_time, "initialization.end_time") - creation
    prompt_latency = None if prompt is None else float(prompt.end_time) - float(prompt.start_time)
    decode_latencies = tuple(float(h.end_time) - float(h.start_time) for h in decode)
    decode_completion_times = [float(h.end_time) for h in decode]
    tbt = [right - left for left, right in zip(decode_completion_times, decode_completion_times[1:])]
    if any(delta < 0 for delta in tbt):
        raise ValueError("decode completion timestamps are not monotonic")

    inferred = int(getattr(query, "inferred_token_count", 0))
    expected = int(getattr(query, "input_seq_length", 0)) + int(getattr(query, "output_seq_length", 0))
    complete = inferred >= expected and expected > 0 and len(initialization) == 1
    finished_at = None if completion_time is None else _finite_time(completion_time, "completion_time")
    if complete and finished_at is None and histories:
        finished_at = float(histories[-1].end_time)
    e2e = None if not complete or finished_at is None else finished_at - creation
    return QueryMetrics(
        query_uid=int(query.query_uid),
        creation_time=creation,
        completion_time=finished_at,
        complete=complete,
        input_tokens=int(getattr(query, "input_seq_length", 0)),
        output_tokens=int(getattr(query, "output_seq_length", 0)),
        ttft=ttft,
        tbt_mean=None if not tbt else mean(tbt),
        tbt_p50=percentile(tbt, 0.50),
        tbt_p95=percentile(tbt, 0.95),
        tbt_p99=percentile(tbt, 0.99),
        tbt_intervals=tuple(tbt),
        e2e=e2e,
        helix_prompt_latency=prompt_latency,
        helix_decode_iteration_latency=decode_latencies,
    )


def _csv_value(value: Any) -> Any:
    return "" if value is None else value


def metrics_row(metrics: QueryMetrics) -> dict[str, Any]:
    """Convert one metrics object to a stable CSV-ready mapping."""

    return {
        "query_uid": metrics.query_uid,
        "creation_time": metrics.creation_time,
        "completion_time": _csv_value(metrics.completion_time),
        "complete": int(metrics.complete),
        "input_tokens": metrics.input_tokens,
        "output_tokens": metrics.output_tokens,
        "ttft": _csv_value(metrics.ttft),
        "tbt_mean": _csv_value(metrics.tbt_mean),
        "tbt_p50": _csv_value(metrics.tbt_p50),
        "tbt_p95": _csv_value(metrics.tbt_p95),
        "tbt_p99": _csv_value(metrics.tbt_p99),
        "e2e": _csv_value(metrics.e2e),
        "helix_prompt_latency": _csv_value(metrics.helix_prompt_latency),
        "helix_decode_iteration_latency_mean": _csv_value(
            metrics.helix_decode_iteration_latency_mean
        ),
        "decode_iteration_count": len(metrics.helix_decode_iteration_latency),
    }


def summarize_metrics(metrics: Iterable[QueryMetrics]) -> Mapping[str, float | int | None]:
    """Aggregate completed query metrics for the baseline summary CSV."""

    completed = [item for item in metrics if item.complete]
    all_tbt = [interval for item in completed for interval in item.tbt_intervals]
    def avg(name: str) -> float | None:
        values = [getattr(item, name) for item in completed]
        values = [float(value) for value in values if value is not None]
        return None if not values else mean(values)

    def pct(name: str, q: float) -> float | None:
        values = [getattr(item, name) for item in completed]
        return percentile((float(value) for value in values if value is not None), q)

    return {
        "query_count": len(completed),
        "ttft_mean": avg("ttft"),
        "ttft_p50": pct("ttft", 0.50),
        "ttft_p95": pct("ttft", 0.95),
        "ttft_p99": pct("ttft", 0.99),
        "tbt_mean": None if not all_tbt else mean(all_tbt),
        "tbt_p50": percentile(all_tbt, 0.50),
        "tbt_p95": percentile(all_tbt, 0.95),
        "tbt_p99": percentile(all_tbt, 0.99),
        "e2e_mean": avg("e2e"),
        "e2e_p50": pct("e2e", 0.50),
        "e2e_p95": pct("e2e", 0.95),
        "e2e_p99": pct("e2e", 0.99),
        "helix_prompt_latency_mean": avg("helix_prompt_latency"),
        "helix_decode_iteration_latency_mean": avg(
            "helix_decode_iteration_latency_mean"
        ),
    }
