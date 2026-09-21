from pathlib import Path

import pytest

from src.graph.serving_graph import LayerInterval, LayerPlacement, ModelProfile
from src.graph.topology import (
    COORDINATOR_SINK,
    COORDINATOR_SOURCE,
    ClusterTopology,
    GPUNode,
    NetworkLink,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"


@pytest.fixture
def phase1_model() -> ModelProfile:
    return ModelProfile(
        name="phase1_transformer",
        num_layers=48,
        token_bytes=4,
        activation_bytes_per_token=16_000,
        layer_compute_units_per_token=(1.0,) * 48,
        layer_memory_gb=(0.25,) * 48,
    )


@pytest.fixture
def phase1_gpus() -> list[GPUNode]:
    return [
        GPUNode("c1", "A", "A100", 80, 1920),
        GPUNode("c2", "A", "L4", 24, 1280),
        GPUNode("c3", "A", "T4", 16, 800),
        GPUNode("c4", "B", "A100", 80, 1920),
        GPUNode("c5", "B", "L4", 24, 1280),
        GPUNode("c6", "B", "T4", 16, 800),
    ]


def make_topology(gpus: list[GPUNode], cross_capacity: float = 30) -> ClusterTopology:
    activation_bytes = 16_000
    intra_mbps = 100 * 8 * activation_bytes / 1_000_000
    cross_mbps = cross_capacity * 8 * activation_bytes / 1_000_000
    links: list[NetworkLink] = []
    for gpu in gpus:
        links.append(NetworkLink(COORDINATOR_SOURCE, gpu.gpu_id, 1.0))
        links.append(NetworkLink(gpu.gpu_id, COORDINATOR_SINK, 1.0))
    for source in gpus:
        for target in gpus:
            if source.gpu_id == target.gpu_id:
                continue
            bandwidth = intra_mbps if source.region == target.region else cross_mbps
            links.append(NetworkLink(source.gpu_id, target.gpu_id, bandwidth))
    return ClusterTopology.from_iterables(gpus, links)


@pytest.fixture
def phase1_topology(phase1_gpus: list[GPUNode]) -> ClusterTopology:
    return make_topology(phase1_gpus, cross_capacity=30)


@pytest.fixture
def placement_a() -> LayerPlacement:
    return LayerPlacement(
        "placement_a",
        {
            "c1": LayerInterval(0, 16),
            "c2": LayerInterval(0, 16),
            "c3": LayerInterval(16, 32),
            "c4": LayerInterval(16, 32),
            "c5": LayerInterval(32, 48),
            "c6": LayerInterval(32, 48),
        },
    )


@pytest.fixture
def placement_b() -> LayerPlacement:
    return LayerPlacement(
        "placement_b",
        {
            "c1": LayerInterval(0, 16),
            "c2": LayerInterval(16, 32),
            "c3": LayerInterval(32, 48),
            "c4": LayerInterval(0, 16),
            "c5": LayerInterval(16, 32),
            "c6": LayerInterval(32, 48),
        },
    )
