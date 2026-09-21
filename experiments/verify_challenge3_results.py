"""Independent integrity checks for the frozen Challenge 3 output tables."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "challenge3_scheduler.yaml"
OUTPUT = ROOT / "results" / "challenge3"


def verify() -> None:
    points = pd.read_csv(OUTPUT / "challenge3_point_results.csv")
    if len(points) != 135:
        raise AssertionError(f"expected 135 points, got {len(points)}")
    if set(points.trace) != {"constant", "step", "periodic", "slow_drift", "noisy_boundary"}:
        raise AssertionError("trace grid mismatch")
    if not np.allclose(points.mean_demand_satisfaction_dynamic, 1.0, atol=1e-12):
        raise AssertionError("dynamic throughput demand was not fully served")
    if points.performance_violation.sum() or points.capacity_violation_count.sum():
        raise AssertionError("capacity or performance violation present")
    digest = sha256(CONFIG.read_bytes()).hexdigest()
    recorded = (OUTPUT / "challenge3_config_hash.txt").read_text(encoding="utf-8").split()[0]
    if digest != recorded:
        raise AssertionError("configuration hash mismatch")
    print("CHALLENGE3_VERIFY=PASS")
    print(f"POINTS={len(points)}")
    print(f"IMPROVED_VS_HELIX={int((points.dynamic_reduction_vs_helix > 0).sum())}")
    print(f"MEAN_REDUCTION={points.dynamic_reduction_vs_helix.mean():.12g}")
    print(f"MAX_REDUCTION={points.dynamic_reduction_vs_helix.max():.12g}")


if __name__ == "__main__":
    verify()
