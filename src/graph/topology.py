"""Physical GPU and network topology data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


COORDINATOR_SOURCE = "coordinator_source"
COORDINATOR_SINK = "coordinator_sink"


@dataclass(frozen=True, slots=True)
class GPUNode:
    """A single simulated GPU with configuration-derived capabilities."""

    gpu_id: str
    region: str
    gpu_type: str
    memory_gb: float
    effective_compute_units_per_second: float

    def __post_init__(self) -> None:
        if not self.gpu_id:
            raise ValueError("GPU id must be non-empty")
        if self.memory_gb <= 0:
            raise ValueError(f"GPU {self.gpu_id} memory_gb must be positive")
        if self.effective_compute_units_per_second <= 0:
            raise ValueError(
                f"GPU {self.gpu_id} effective compute capacity must be positive"
            )


@dataclass(frozen=True, slots=True)
class NetworkLink:
    """One explicit directed physical connection."""

    source: str
    target: str
    bandwidth_mbps: float

    def __post_init__(self) -> None:
        if not self.source or not self.target:
            raise ValueError("Network link endpoints must be non-empty")
        if self.source == self.target:
            raise ValueError("Network links must connect distinct endpoints")
        if self.bandwidth_mbps <= 0:
            raise ValueError(
                f"Bandwidth for {self.source}->{self.target} must be positive"
            )


@dataclass(slots=True)
class ClusterTopology:
    """A cluster whose connectivity is defined only by explicit directed links."""

    gpus: dict[str, GPUNode]
    links: tuple[NetworkLink, ...]
    _link_index: dict[tuple[str, str], NetworkLink] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not self.gpus:
            raise ValueError("Cluster topology must contain at least one GPU")
        valid_endpoints = set(self.gpus) | {COORDINATOR_SOURCE, COORDINATOR_SINK}
        index: dict[tuple[str, str], NetworkLink] = {}
        for link in self.links:
            if link.source not in valid_endpoints:
                raise ValueError(f"Unknown link source: {link.source}")
            if link.target not in valid_endpoints:
                raise ValueError(f"Unknown link target: {link.target}")
            key = (link.source, link.target)
            if key in index:
                raise ValueError(f"Duplicate directed link: {link.source}->{link.target}")
            index[key] = link
        self._link_index = index

    @classmethod
    def from_iterables(
        cls, gpus: Iterable[GPUNode], links: Iterable[NetworkLink]
    ) -> "ClusterTopology":
        """Create a topology while rejecting duplicate GPU identifiers."""

        gpu_index: dict[str, GPUNode] = {}
        for gpu in gpus:
            if gpu.gpu_id in gpu_index:
                raise ValueError(f"Duplicate GPU id: {gpu.gpu_id}")
            gpu_index[gpu.gpu_id] = gpu
        return cls(gpus=gpu_index, links=tuple(links))

    def get_link(self, source: str, target: str) -> NetworkLink | None:
        """Return an explicit directed link, or ``None`` when absent."""

        return self._link_index.get((source, target))


def with_cross_region_bandwidth(
    topology: ClusterTopology, bandwidth_mbps: float
) -> ClusterTopology:
    """Return a copy with GPU-to-GPU cross-region links set to one bandwidth.

    Coordinator links and same-region GPU links are preserved exactly.
    """

    if bandwidth_mbps <= 0:
        raise ValueError("bandwidth_mbps must be positive")
    links: list[NetworkLink] = []
    for link in topology.links:
        source_gpu = topology.gpus.get(link.source)
        target_gpu = topology.gpus.get(link.target)
        is_cross_region = (
            source_gpu is not None
            and target_gpu is not None
            and source_gpu.region != target_gpu.region
        )
        links.append(
            NetworkLink(
                link.source,
                link.target,
                bandwidth_mbps if is_cross_region else link.bandwidth_mbps,
            )
        )
    return ClusterTopology(dict(topology.gpus), tuple(links))
