"""Check that only a reproducible line-ending difference preserves identity."""

import hashlib

from experiments.v3_cluster42.capacity_report import pair
from experiments.v3_cluster42.run import PHYSICAL


def test_cluster_encoding_identity():
    physical = PHYSICAL.read_bytes().replace(b"\r\n", b"\n")
    row = dict(trace_sha256="trace", offered_tokens_per_s=2150, duration_s=1800,
               warmup_s=0, arrivals=100, evaluation_protocol="fixed_window_no_tail_drain",
               seed=0, output_throughput_tokens_per_s=10, ttft_p95_s=1, tpot_p95_s=1,
               physical_cluster_sha256=hashlib.sha256(physical).hexdigest())
    other = {**row, "physical_cluster_sha256": hashlib.sha256(
        physical.replace(b"\n", b"\r\n")).hexdigest()}
    assert pair(row, other, 53)["pass"]
    assert not pair(row, {**other, "physical_cluster_sha256": "different"}, 53)["pass"]
    assert not pair(row, {**other, "trace_sha256": "different"}, 53)["pass"]
    assert not pair(row, other, 64)["pass"]
    assert not pair({**row, "ttft_p95_s": 1.001}, other, 53)["pass"]


if __name__ == "__main__":
    test_cluster_encoding_identity()
