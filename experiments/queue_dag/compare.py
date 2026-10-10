"""Verify paired fixed-window runs and summarize their three target metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


METRICS = {
    "output_throughput_tokens_per_s": 1,
    "ttft_p95_s": -1,
    "tpot_p95_s": -1,
}


def compare(helix_path: Path, candidate_path: Path) -> dict:
    helix = json.loads(helix_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    checks = ("scenario", "duration_s", "warmup_s", "seed",
              "offered_tokens_per_s", "trace_sha256", "evaluation_protocol",
              "python_version", "numpy_version")
    for key in checks:
        if helix[key] != candidate[key]:
            raise ValueError(f"Mismatched {key}: {helix[key]} != {candidate[key]}")
    if helix["method"] != "helix" or candidate["method"] != "queue_dag":
        raise ValueError("Expected Helix baseline and queue_dag candidate")
    for key in ("solution", "sim_cluster"):
        left = hashlib.sha256(Path(helix[key]).read_bytes()).hexdigest()
        right = hashlib.sha256(Path(candidate[key]).read_bytes()).hexdigest()
        if left != right:
            raise ValueError(f"Mismatched {key} content")
    metrics = {}
    for key, direction in METRICS.items():
        baseline, new = helix[key], candidate[key]
        metrics[key] = {"helix": baseline, "queue_dag": new,
                        "improved": direction * (new - baseline) > 0}
    samples = {key: {"helix": helix[key], "queue_dag": candidate[key]}
               for key in ("arrivals", "first_tokens_in_window",
                           "queries_with_tpot_samples", "completion_fraction")}
    return {"scenario": helix["scenario"], "trace_sha256": helix["trace_sha256"],
            "metrics": metrics, "samples": samples,
            "all_three_improved": all(
                entry["improved"] for entry in metrics.values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--helix", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(args.helix, args.candidate)
    report = json.dumps(result, indent=2) + "\n"
    print(report, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    if not result["all_three_improved"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
