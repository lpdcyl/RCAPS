"""Passive resource accounting around the original external baseline adapters."""
from __future__ import annotations

from baselines import helix, separate, swarm
from benchmarks import fixed_window
from rcaps import v3_method

ADAPTERS = {m.NAME: m for m in (helix, separate, swarm, v3_method)}


def evaluate(scenario, method, offered, duration, seed, root):
    adapter = ADAPTERS[method]
    solution, cluster = adapter.layout(scenario, root)
    original = fixed_window.run
    def profiled(*args, **kwargs):
        kwargs["profile_resources"] = True
        return original(*args, **kwargs)
    # Each window runs in its own process; restore even on error. This changes
    # instrumentation only, including SP's three component simulations.
    fixed_window.run = profiled
    try:
        row = adapter.evaluate(scenario, offered, duration, 0, seed, solution, cluster)
    finally:
        fixed_window.run = original
    if method == "separate":
        row["gpu_busy_fraction"] = {
            f"{group}/{gpu}": fraction
            for group, component in row["sp_components"].items()
            for gpu, fraction in component["gpu_busy_fraction"].items()}
        row["gpu_accounting"] = "all SP physical subclusters; distinct group-prefixed GPU labels"
    row["gpu_seconds_per_output_token"] = (sum(row["gpu_busy_fraction"].values()) /
                                             row["output_throughput_tokens_per_s"])
    return row
