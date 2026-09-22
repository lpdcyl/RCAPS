"""Local piecewise-constant carbon-intensity traces."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import csv
from datetime import datetime, timezone
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
        """Load standard or legacy ``timestamp,region,carbon_intensity`` CSV rows."""

        grouped: dict[str, list[tuple[float, float]]] = {}
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(
                    "CI trace CSV must contain a header"
                )
            if "carbon_intensity_g_per_kwh" in reader.fieldnames:
                value_column = "carbon_intensity_g_per_kwh"
            elif "carbon_intensity" in reader.fieldnames:
                value_column = "carbon_intensity"
            else:
                raise ValueError(
                    "CI trace CSV must contain carbon_intensity_g_per_kwh"
                )
            required = {"timestamp", "region", value_column}
            if not required.issubset(reader.fieldnames):
                raise ValueError(
                    "CI trace CSV must contain timestamp, region, and carbon intensity"
                )
            for row in reader:
                grouped.setdefault(str(row["region"]), []).append(
                    (float(row["timestamp"]), float(row[value_column]))
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


def _parse_historical_timestamp(value: str) -> float:
    """Parse UNIX seconds or an ISO-8601 UTC timestamp."""

    try:
        return float(value)
    except ValueError:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()


@dataclass(frozen=True, slots=True)
class HistoricalCITraceLoader:
    """Importer for standard historical CI CSV traces.

    The loader performs no interpolation. If ``interval_seconds`` is supplied,
    samples are assigned to fixed windows and the last observation in each
    region/window is retained (piecewise-constant resampling).
    """

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        interval_seconds: float | None = None,
    ) -> TraceCIProvider:
        source = Path(path)
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("Historical CI CSV must contain a header")
            required = {"timestamp", "region", "carbon_intensity_g_per_kwh"}
            if not required.issubset(reader.fieldnames):
                raise ValueError(
                    "Historical CI CSV must contain timestamp, region, "
                    "carbon_intensity_g_per_kwh"
                )
            rows = [
                (
                    _parse_historical_timestamp(str(row["timestamp"])),
                    str(row["region"]),
                    float(row["carbon_intensity_g_per_kwh"]),
                )
                for row in reader
            ]
        if interval_seconds is not None:
            if interval_seconds <= 0.0:
                raise ValueError("interval_seconds must be positive")
            latest: dict[tuple[str, float], tuple[float, str, float]] = {}
            for timestamp, region, intensity in rows:
                bucket = (timestamp // interval_seconds) * interval_seconds
                latest[(region, bucket)] = (bucket, region, intensity)
            rows = list(latest.values())
        return TraceCIProvider.from_rows(rows)


@dataclass(frozen=True, slots=True)
class RegionMappedCIProvider:
    """Map simulator regions to source-trace regions without changing values."""

    source: object
    region_map: Mapping[str, str]

    def get_ci(self, region: str, timestamp: float | None = None) -> float:
        try:
            source_region = self.region_map[region]
        except KeyError as exc:
            raise ValueError(f"No historical trace mapping for region {region!r}") from exc
        return float(self.source.get_ci(source_region, timestamp))
