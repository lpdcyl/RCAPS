"""Check that passive profiling preserves the earlier 70B measurements."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from experiments.validation_2026.equivalence import static_single_equals_coarse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FIELDS = ("trace_sha256", "arrivals", "output_throughput_tokens_per_s",
          "completed_request_throughput_per_s", "ttft_p95_s", "tpot_p95_s",
          "completion_fraction", "backlog_at_window_end", "route_counts")


def main() -> None:
    if not static_single_equals_coarse():
        raise AssertionError("Static single layout differs from topology-only")
    checked = 0
    for scenario in ("single", "multi"):
        for seed in (0, 1, 2):
            for method in ("rcaps_coarse", "rcaps"):
                current = HERE / "runs70b" / scenario / f"seed{seed}" / f"{method}.json"
                prior = ROOT / "benchmarks/runs" / scenario / f"seed{seed}" / f"{method}.json"
                if not current.exists():
                    continue
                a = json.loads(current.read_text(encoding="utf-8"))
                b = json.loads(prior.read_text(encoding="utf-8"))
                differences = [key for key in FIELDS if a[key] != b[key]]
                if differences:
                    raise AssertionError(f"Profiling changed {scenario} seed{seed} "
                                         f"{method}: {differences}")
                checked += 1
    seed0 = HERE / "runs70b/single/seed0"
    if (seed0 / "rcaps_static_no_graph.json").exists():
        static = json.loads((seed0 / "rcaps_static_no_graph.json").read_text(
            encoding="utf-8"))
        coarse = json.loads((seed0 / "rcaps_coarse.json").read_text(encoding="utf-8"))
        if any(static[key] != coarse[key] for key in FIELDS):
            raise AssertionError("Single seed0 static/coarse results differ")
    raw = list((HERE / "runs70b").glob("*/seed*/*.json"))
    for path in raw:
        run = json.loads(path.read_text(encoding="utf-8"))
        for name, field in (("solution", "solution_sha256"),
                            ("sim_cluster", "sim_cluster_sha256")):
            actual = hashlib.sha256(Path(run[name]).read_bytes()).hexdigest()
            if actual != run[field]:
                raise AssertionError(f"Layout hash mismatch: {path}, {name}")
    print(f"Protocol checks passed: {checked} historical pairs, "
          f"{len(raw)} saved layout hashes")


if __name__ == "__main__":
    main()
