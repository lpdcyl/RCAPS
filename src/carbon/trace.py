"""Local piecewise-constant carbon-intensity traces."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import csv
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from src.carbon.model import validate_carbon_intensity_g_per_kwh


@dataclass(frozen=True, slots=True)
class TraceCIProvider:
    """Piecewise-constant regional CI provider backed by local trace points.

    Query semantics are explicit: timestamps before a region's first point
    raise ``ValueError``; timestamps at or after the last point use the latest
    point at or before the query (including holding the final value forever).
    """

    points_by_region: Mapping[str, tuple[tuple[float, float], ...]]

    def __post_init__(self) -> None:
        normalized: dict[str, tuple[tuple[float, float], ...]] = {}
        for region, points in self.points_by_region.items():
            if not isinstance(region, str) or not region:
                raise ValueError("Trace regions must be non-empty strings")
            ordered = tuple(sorted((float(t), float(v)) for t, v in points))
            if not ordered:
                raise ValueError(f"Trace region {region!r} has no points")
            if len({timestamp for timestamp, _ in ordered}) != len(ordered):
                raise ValueError(f"Trace region {region!r} has duplicate timestamps")
            if any(
                validate_carbon_intensity_g_per_kwh(region, value) != value
                for _, value in ordered
            ):
                raise ValueError("Invalid trace carbon intensity")
            normalized[region] = ordered
        if not normalized:
            raise ValueError("Trace must contain at least one region")
        object.__setattr__(self, "points_by_region", MappingProxyType(normalized))

    @classmethod
    def from_rows(
        cls, rows: Iterable[tuple[float, str, float]]
    ) -> "TraceCIProvider":
        grouped: dict[str, list[tuple[float, float]]] = {}
        for timestamp, region, value in rows:
            grouped.setdefault(str(region), []).append((float(timestamp), float(value)))
        return cls(grouped)

    @classmethod
    def from_csv(cls, path: str | Path) -> "TraceCIProvider":
        """Load ``timestamp,region,carbon_intensity`` rows from a local CSV."""

        grouped: dict[str, list[tuple[float, float]]] = {}
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"timestamp", "region", "carbon_intensity"}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise ValueError(
                    "CI trace CSV must contain timestamp, region, carbon_intensity"
                )
            for row in reader:
                grouped.setdefault(str(row["region"]), []).append(
                    (float(row["timestamp"]), float(row["carbon_intensity"]))
                )
        return cls(grouped)

    @property
    def regions(self) -> tuple[str, ...]:
        return tuple(sorted(self.points_by_region))

    def get_ci(self, region: str, timestamp: float | None = None) -> float:
        if region not in self.points_by_region:
            raise ValueError(f"Unknown CI trace region {region!r}")
        if timestamp is None:
            raise ValueError("TraceCIProvider requires an explicit timestamp")
        query = float(timestamp)
        points = self.points_by_region[region]
        if query < points[0][0]:
            raise ValueError(
                f"Timestamp {query} precedes first CI point for region {region!r}"
            )
        index = bisect_right([point[0] for point in points], query) - 1
        return points[index][1]
