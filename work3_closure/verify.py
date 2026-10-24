"""Recompute the four-pool summary directly from paired raw windows."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def gpu_work(run):
    return sum(run["gpu_busy_fraction"].values()) / run["output_throughput_tokens_per_s"]


def metric_pair(base, gated):
    assert base["trace_sha256"] == gated["trace_sha256"]
    assert base["arrivals"] == gated["arrivals"]
    return {
        "gpu_work_relative": gpu_work(gated) / gpu_work(base) - 1,
        "tpot_relative": gated["tpot_p95_s"] / base["tpot_p95_s"] - 1,
        "throughput_relative": gated["output_throughput_tokens_per_s"] /
                               base["output_throughput_tokens_per_s"] - 1,
    }


def verify():
    sources = {
        "C1_single": (
            "benchmarks/runs/single/seed{seed}/rcaps_v3.json",
            "work3_sparse_replication/runs/C1_single/gated_seed{seed}.json"),
        "C1_multi": (
            "benchmarks/runs/multi/seed{seed}/rcaps_v3.json",
            "work3_sparse_replication/runs/C1_multi/gated_seed{seed}.json"),
        "C2": (
            "work3_control_replay/runs/C2/v3_seed{seed}.json",
            "work3_efficiency_formal/runs/C2/gated_seed{seed}.json"),
        "C3": (
            "work3_control_replay/runs/C3/v3_seed{seed}.json",
            "work3_efficiency_formal/runs/C3/gated_seed{seed}.json"),
    }
    means = {}
    for case, (base_pattern, gate_pattern) in sources.items():
        rows = [metric_pair(read(base_pattern.format(seed=seed)),
                            read(gate_pattern.format(seed=seed)))
                for seed in (0, 1, 2)]
        means[case] = {name: statistics.mean(row[name] for row in rows)
                       for name in rows[0]}
    expected = {
        "C1_single": (-0.45869039855052585, -0.09460350447343809, 0.006729504982222838),
        "C1_multi": (-0.297333238219976, 0.018129614688823903, -0.00026144375856314756),
        "C2": (-0.7315083345934821, -0.004075233077853846, 0.0033501105792429118),
        "C3": (-0.32743341509492463, 0.003291466585031433, 0.0001291600995071788),
    }
    for case, values in expected.items():
        for field, target in zip(("gpu_work_relative", "tpot_relative",
                                  "throughput_relative"), values):
            assert abs(means[case][field] - target) < 1e-12, (case, field)
    archived_parity = 0
    parity_fields = ("trace_sha256", "output_throughput_tokens_per_s",
                     "ttft_p95_s", "tpot_p95_s", "completion_fraction",
                     "backlog_at_window_end", "route_counts",
                     "gpu_busy_fraction", "query_samples")
    for case in ("C2", "C3"):
        for seed in (0, 1, 2):
            archived = read(f"experiments/m2_multistage_candidate/runs/formal/{case}/seed{seed}/single_a100.json")
            replay = read(f"work3_control_replay/runs/{case}/v3_seed{seed}.json")
            assert all(archived[field] == replay[field] for field in parity_fields)
            archived_parity += 1
    outcome = {
        "status": "passed", "paired_windows": 12,
        "archived_v3_parity": f"{archived_parity}/6",
        "four_pool_means": means,
        "link_price_development_passed":
            read("work3_link_price/runs/v1/development_analysis.json")["development_passed"],
        "transfer_development_passed":
            read("work3_transfer/analysis.json")["development_passed"],
        "efficiency_formal_passed":
            read("work3_control_replay/analysis.json")["same_runtime_gate_passed"],
    }
    assert outcome["link_price_development_passed"] is False
    assert outcome["transfer_development_passed"] is False
    assert outcome["efficiency_formal_passed"] is True
    output = ROOT / "work3_closure" / "verification.json"
    output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return output


if __name__ == "__main__":
    print(verify())
