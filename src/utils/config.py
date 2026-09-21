"""YAML loading, schema checks, and capacity unit conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


def bandwidth_mbps_to_bytes_per_second(bandwidth_mbps: float) -> float:
    """Convert decimal megabits/second to bytes/second."""

    if bandwidth_mbps <= 0:
        raise ValueError("bandwidth_mbps must be positive")
    return bandwidth_mbps * 1_000_000.0 / 8.0


def bandwidth_mbps_to_tokens_per_second(
    bandwidth_mbps: float, token_bytes: float
) -> float:
    """Convert bandwidth to token/s for coordinator traffic."""

    if token_bytes <= 0:
        raise ValueError("token_bytes must be positive")
    return bandwidth_mbps_to_bytes_per_second(bandwidth_mbps) / token_bytes


def bandwidth_mbps_to_activation_tokens_per_second(
    bandwidth_mbps: float, activation_bytes_per_token: float
) -> float:
    """Convert bandwidth to token/s for inter-GPU activation traffic."""

    if activation_bytes_per_token <= 0:
        raise ValueError("activation_bytes_per_token must be positive")
    return (
        bandwidth_mbps_to_bytes_per_second(bandwidth_mbps)
        / activation_bytes_per_token
    )


def load_yaml(path: str | Path) -> Mapping[str, Any]:
    """Load one YAML mapping with a clear error for malformed top-level data."""

    source = Path(path)
    with source.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a top-level mapping: {source}")
    return data
