"""Compare original Helix with the integrated graph placement and DAG scheduler."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAYOUTS = {
    "single": {
        "helix": (
            "examples/simulation/layouts/ilp/ilp_sol.ini",
            "examples/simulation/layouts/ilp/simulator_cluster.ini",
        ),
        "integrated": (
            "experiments/critical_graph/runs/single_final/solution.ini",
            "experiments/critical_graph/runs/single_final/simulator_cluster.ini",
        ),
    },
    "multi": {
        "helix": (
            "artifact_evaluation/distributed_clusters/layout_llama70b/ilp/ilp_sol.ini",
            "artifact_evaluation/distributed_clusters/layout_llama70b/ilp/simulator_cluster.ini",
        ),
        "integrated": (
            "experiments/critical_graph/runs/multi_final/solution.ini",
            "experiments/critical_graph/runs/multi_final/simulator_cluster.ini",
        ),
    },
}
PAPER_BASELINE = {
    "single": (
        "artifact_evaluation/single_cluster/layout_llama70b/ilp/ilp_sol.ini",
        "artifact_evaluation/single_cluster/layout_llama70b/ilp/simulator_cluster.ini",
    ),
    "multi": LAYOUTS["multi"]["helix"],
}
PAPER_OFFERED = {"single": 700.0, "multi": 320.0}
PAIRED_FIELDS = (
    "scenario", "offered_tokens_per_s", "duration_s", "warmup_s", "seed",
    "evaluation_protocol", "python_version", "numpy_version", "trace_sha256",
    "arrivals",
)


def _layout_hashes(run: dict, expected: tuple[str, str]) -> dict[str, str]:
    hashes = {}
    for key, expected_path in zip(("solution", "sim_cluster"), expected):
        actual = (ROOT / run[key]).resolve()
        wanted = (ROOT / expected_path).resolve()
        if actual != wanted:
            raise ValueError(f"Unexpected {key}: {actual} != {wanted}")
        hashes[key] = hashlib.sha256(actual.read_bytes()).hexdigest()
    return hashes


def compare(helix_path: Path, integrated_path: Path,
            paper_baseline: bool = False) -> dict:
    helix = json.loads(helix_path.read_text(encoding="utf-8"))
    integrated = json.loads(integrated_path.read_text(encoding="utf-8"))
    for key in PAIRED_FIELDS:
        if helix[key] != integrated[key]:
            raise ValueError(f"Mismatched {key}: {helix[key]} != {integrated[key]}")
    if helix["method"] != "helix":
        raise ValueError("Baseline must use the original Helix scheduler")
    if (integrated["method"] != "queue_dag" or
            integrated.get("routing_policy") not in ("final", "coalesced_corrected")):
        raise ValueError("Candidate must use the final queue-DAG scheduler")
    if helix["evaluation_protocol"] != "fixed_window_no_tail_drain":
        raise ValueError("Unexpected evaluation protocol")
    scenario = helix["scenario"]
    if scenario not in LAYOUTS:
        raise ValueError(f"Unsupported scenario: {scenario}")
    if paper_baseline and (helix["offered_tokens_per_s"] != PAPER_OFFERED[scenario]
                           or helix["warmup_s"] != 0
                           or helix["duration_s"] != 1800):
        raise ValueError("Paper baseline requires the published online workload parameters")
    helix_layout = (PAPER_BASELINE[scenario] if paper_baseline
                    else LAYOUTS[scenario]["helix"])
    layout_hashes = {
        "helix": _layout_hashes(helix, helix_layout),
        "integrated": _layout_hashes(integrated, LAYOUTS[scenario]["integrated"]),
    }
    metrics = {}
    for key, higher_is_better in (
        ("output_throughput_tokens_per_s", True),
        ("ttft_p95_s", False),
        ("tpot_p95_s", False),
        ("completed_request_throughput_per_s", True),
        ("e2e_p95_s", False),
        ("completion_fraction", True),
    ):
        before, after = helix[key], integrated[key]
        improvement = ((after / before - 1) if higher_is_better else (1 - after / before)) * 100
        metrics[key] = {
            "helix": before,
            "integrated": after,
            "improvement_percent": improvement,
            "improved": improvement > 0,
        }
    if all(key in helix and key in integrated for key in (
            "paper_prompt_request_p95_s", "paper_decode_request_p95_s")):
        for key in ("paper_prompt_request_p95_s", "paper_decode_request_p95_s"):
            before, after = helix[key], integrated[key]
            improvement = (1 - after / before) * 100
            metrics[key] = {
                "helix": before,
                "integrated": after,
                "improvement_percent": improvement,
                "improved": improvement > 0,
            }
    sample_keys = ["first_tokens_in_window", "queries_with_tpot_samples",
                   "backlog_at_window_start", "backlog_at_window_end"]
    if all(key in helix and key in integrated for key in (
            "paper_prompt_request_count", "paper_decode_request_count")):
        sample_keys.extend(("paper_prompt_request_count", "paper_decode_request_count"))
    return {
        "scenario": scenario,
        "baseline_source": "paper_artifact" if paper_baseline else "example_or_paper_artifact",
        "protocol": {key: helix[key] for key in PAIRED_FIELDS},
        "inputs": {"helix": str(helix_path), "integrated": str(integrated_path)},
        "layout_sha256": layout_hashes,
        "metrics": metrics,
        "sample_counts": {
            key: {"helix": helix[key], "integrated": integrated[key]}
            for key in sample_keys
        },
        "all_three_target_metrics_improved": all(metrics[key]["improved"] for key in (
            "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--helix", type=Path, required=True)
    parser.add_argument("--integrated", type=Path, required=True)
    parser.add_argument("--paper-baseline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(args.helix, args.integrated, args.paper_baseline)
    report = json.dumps(result, indent=2) + "\n"
    print(report, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    if not result["all_three_target_metrics_improved"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
