"""Audit the published V3 windows against their paired placement-study sources."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.run import ROOT, output_file
from rcaps.v3_method import NAME, layout

from .verify import MANIFEST, digest


INDEX = ROOT / "experiments/m2_multistage_candidate/formal_index.json"
WINDOWS = ("single", "multi")
LOADS = {"single": 700.0, "multi": 320.0}


def promote() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    evidence = ROOT / manifest["formal_candidate_evidence"]["source"]
    if digest(evidence) != manifest["formal_candidate_evidence"]["sha256"]:
        raise ValueError("Candidate evidence changed since V3 release")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    promoted = []
    for scenario in WINDOWS:
        case = f"C1_{scenario}"
        solution, cluster = layout(scenario, ROOT)
        expected = manifest["layouts"][scenario]
        if digest(solution) != expected["solution_sha256"] or digest(
                cluster) != expected["sim_cluster_sha256"]:
            raise ValueError(f"V3 deployment changed: {scenario}")
        for seed in (0, 1, 2):
            entry = index[case]["multi_any"]["sources"][str(seed)]
            source = ROOT / entry["source"]
            if digest(source) != entry["sha256"]:
                raise ValueError(f"Candidate formal source changed: {source}")
            row = json.loads(source.read_text(encoding="utf-8"))
            required = {
                "case": case, "variant": "multi_any", "scenario": scenario,
                "seed": seed, "duration_s": 1800, "warmup_s": 0,
                "offered_tokens_per_s": LOADS[scenario],
                "evaluation_protocol": "fixed_window_no_tail_drain",
                "query_samples_schema": 1,
                "physical_sha256": expected["physical_sha256"],
                "solution_sha256": expected["solution_sha256"],
                "sim_cluster_sha256": expected["sim_cluster_sha256"],
            }
            for key, value in required.items():
                if row.get(key) != value:
                    raise ValueError(f"Formal source differs at {key}: {source}")
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError(f"Incomplete request samples: {source}")
            helix_file = output_file(ROOT / "benchmarks/runs", scenario, seed, "helix")
            helix = json.loads(helix_file.read_text(encoding="utf-8"))
            if any(row.get(key) != helix.get(key) for key in MATCH_FIELDS):
                raise ValueError(f"Helix trace/protocol mismatch: {source}")
            common_cohort(row, helix)
            target = output_file(ROOT / "benchmarks/runs", scenario, seed, NAME)
            released = json.loads(target.read_text(encoding="utf-8"))
            if released.get("system") != NAME or released.get("reused_sha256") != digest(source):
                raise ValueError(f"V3 source identity differs: {target}")
            for key in ("trace_sha256", "solution_sha256", "sim_cluster_sha256",
                        "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                        "completion_fraction", "backlog_at_window_end", "route_counts",
                        "query_samples"):
                if released.get(key) != row.get(key):
                    raise ValueError(f"V3 released metric differs at {key}: {target}")
            promoted.append({"scenario": scenario, "seed": seed,
                             "source": released["reused_from"],
                             "source_sha256": digest(source),
                             "released": str(target.relative_to(ROOT)).replace("\\", "/"),
                             "released_sha256": digest(target),
                             "trace_sha256": row["trace_sha256"],
                             "helix_physical_hash_status": "absent_in_historical_record"})
    return promoted


def main() -> None:
    rows = promote()
    destination = Path(__file__).with_name("formal_reuse_index.json")
    encoded = json.dumps(rows, indent=2) + "\n"
    destination.write_text(encoded, encoding="utf-8")
    print(f"Verified {len(rows)} formally paired V3 windows")


if __name__ == "__main__":
    main()
