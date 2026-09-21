"""Configuration loading for the synthetic Challenge 3 scheduler study."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from src.utils.config import load_yaml


@dataclass(frozen=True, slots=True)
class Challenge3Config:
    scheduling_interval_seconds: float
    placement_check_interval_seconds: float
    placement_persistence_intervals: int
    minimum_placement_dwell_seconds: float
    solver_tolerance: float
    joint_oracle_mip_rel_gap: float
    joint_oracle_time_limit_seconds: float | None
    request_tokens: float
    random_seed: int
    trace_duration_intervals: int
    trace_files: Mapping[str, str]
    load_profiles: Mapping[str, float]
    gpu_scenarios: tuple[str, ...]
    network_capacities_tokens_per_second: Mapping[str, float]
    dispatch_policy: str
    scheduler_mode: str

    def __post_init__(self) -> None:
        if self.scheduling_interval_seconds <= 0.0:
            raise ValueError("scheduling_interval_seconds must be positive")
        if self.placement_check_interval_seconds < self.scheduling_interval_seconds:
            raise ValueError("placement check interval must not be faster than scheduling")
        if self.placement_persistence_intervals <= 0:
            raise ValueError("placement_persistence_intervals must be positive")
        if self.minimum_placement_dwell_seconds < 0.0:
            raise ValueError("minimum_placement_dwell_seconds cannot be negative")
        if self.solver_tolerance <= 0.0 or self.request_tokens <= 0.0:
            raise ValueError("solver tolerance and request tokens must be positive")
        if not 0.0 <= self.joint_oracle_mip_rel_gap <= 1.0:
            raise ValueError("joint oracle mip relative gap must be in [0, 1]")
        if self.joint_oracle_time_limit_seconds is not None and self.joint_oracle_time_limit_seconds <= 0.0:
            raise ValueError("joint oracle time limit must be positive when supplied")
        if self.trace_duration_intervals <= 0:
            raise ValueError("trace_duration_intervals must be positive")
        if not self.trace_files or not self.load_profiles:
            raise ValueError("Challenge 3 requires traces and load profiles")
        if any(value <= 0.0 or value > 1.0 for value in self.load_profiles.values()):
            raise ValueError("load profiles must be factors in (0, 1]")
        if any(value <= 0.0 for value in self.network_capacities_tokens_per_second.values()):
            raise ValueError("network capacities must be positive")
        if self.dispatch_policy != "deterministic_quota":
            raise ValueError("Only deterministic_quota dispatch is implemented")
        if self.scheduler_mode != "dynamic_carbon_flow":
            raise ValueError("Only dynamic_carbon_flow scheduler mode is implemented")


def load_challenge3_config(config_dir: str | Path) -> Challenge3Config:
    root = Path(config_dir)
    data = load_yaml(root / "challenge3_scheduler.yaml")
    return Challenge3Config(
        scheduling_interval_seconds=float(data["scheduling_interval_seconds"]),
        placement_check_interval_seconds=float(
            data["placement_check_interval_seconds"]
        ),
        placement_persistence_intervals=int(data["placement_persistence_intervals"]),
        minimum_placement_dwell_seconds=float(data["minimum_placement_dwell_seconds"]),
        solver_tolerance=float(data["solver_tolerance"]),
        joint_oracle_mip_rel_gap=float(data.get("joint_oracle_mip_rel_gap", 0.0)),
        joint_oracle_time_limit_seconds=(
            None
            if data.get("joint_oracle_time_limit_seconds") is None
            else float(data["joint_oracle_time_limit_seconds"])
        ),
        request_tokens=float(data["request_tokens"]),
        random_seed=int(data["random_seed"]),
        trace_duration_intervals=int(data["trace_duration_intervals"]),
        trace_files={
            str(name): str(path) for name, path in data["trace_files"].items()
        },
        load_profiles={
            str(name): float(value) for name, value in data["load_profiles"].items()
        },
        gpu_scenarios=tuple(str(value) for value in data["gpu_scenarios"]),
        network_capacities_tokens_per_second={
            str(name): float(value)
            for name, value in data["network_capacities_tokens_per_second"].items()
        },
        dispatch_policy=str(data["dispatch_policy"]),
        scheduler_mode=str(data["scheduler_mode"]),
    )
