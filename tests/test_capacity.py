import pytest

from src.graph.serving_graph import (
    AnalyticalThroughputProvider,
    MissingThroughputProfileError,
    ModelProfile,
    ProfiledThroughputProvider,
)
from src.graph.topology import GPUNode
from src.utils.config import (
    bandwidth_mbps_to_activation_tokens_per_second,
    bandwidth_mbps_to_tokens_per_second,
)


@pytest.fixture
def model() -> ModelProfile:
    return ModelProfile(
        name="test",
        num_layers=48,
        token_bytes=4,
        activation_bytes_per_token=16_000,
        layer_compute_units_per_token=(1.0,) * 48,
        layer_memory_gb=(0.25,) * 48,
    )


@pytest.fixture
def a100() -> GPUNode:
    return GPUNode("c1", "A", "A100", 80, 1920)


def test_bandwidth_to_activation_capacity() -> None:
    assert bandwidth_mbps_to_activation_tokens_per_second(12.8, 16_000) == 100
    assert bandwidth_mbps_to_activation_tokens_per_second(3.84, 16_000) == 30


def test_bandwidth_to_token_capacity() -> None:
    assert bandwidth_mbps_to_tokens_per_second(1.0, 4) == 31_250


def test_analytical_throughput(model: ModelProfile, a100: GPUNode) -> None:
    provider = AnalyticalThroughputProvider()
    assert provider.throughput(a100, 0, 16, model) == 120
    assert provider.description == "Simulator analytical approximation"


def test_profiled_throughput(model: ModelProfile, a100: GPUNode) -> None:
    provider = ProfiledThroughputProvider({"A100": {16: 123.5}})
    assert provider.throughput(a100, 0, 16, model) == 123.5


def test_missing_profile_raises(model: ModelProfile, a100: GPUNode) -> None:
    provider = ProfiledThroughputProvider({"A100": {8: 220}})
    with pytest.raises(MissingThroughputProfileError, match="A100.*16 layers"):
        provider.throughput(a100, 0, 16, model)
