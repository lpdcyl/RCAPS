"""Resolve and validate reusable V2/static-M1 fixed-window records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.compare import MATCH_FIELDS, common_cohort
from experiments.v2_core_ablations.audit_layouts import audit as audit_layout


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOADS = {"single": 700.0, "multi": 320.0}
SEEDS = (0, 1, 2)
SYSTEMS = ("m1_static_candidate", "v2_reference")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def layout(scenario: str, system: str) -> tuple[Path, Path]:
    if system == "m1_static_candidate":
        directory = HERE / "layouts" / scenario
    elif system == "v2_reference":
        directory = ROOT / "rcaps/v2_layouts" / f"{scenario}_adaptive"
    else:
        raise ValueError(system)
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def sources(scenario: str, seed: int, system: str) -> list[tuple[Path, str]]:
    if system == "m1_static_candidate":
        historical = (ROOT / "experiments/v2_method_comparisons/runs" / scenario /
                      f"seed{seed}/rcaps_v2_static_resource_model.json")
    elif system == "v2_reference":
        historical = (ROOT / "experiments/v2_method_ablation/runs" / scenario /
                      f"seed{seed}/rcaps_v2.json")
    else:
        raise ValueError(system)
    local = HERE / "runs" / scenario / f"seed{seed}" / f"{system}.json"
    return [(local, "local_rerun"), (historical, "historical_reuse")]


def expected_record(scenario: str, seed: int, system: str,
                    record_source: str) -> dict:
    solution, cluster = layout(scenario, system)
    method_name = ({"m1_static_candidate": "rcaps_v2_static_resource_model",
                    "v2_reference": "rcaps_v2"}[system]
                   if record_source == "historical_reuse" else system)
    return {"system": method_name, "method": "queue_dag",
            "scenario": scenario, "seed": seed,
            "offered_tokens_per_s": LOADS[scenario], "duration_s": 1800,
            "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
            "query_samples_schema": 1,
            "solution_sha256": digest(solution),
            "sim_cluster_sha256": digest(cluster)}


def valid_record(path: Path, scenario: str, seed: int, system: str,
                 record_source: str) -> dict:
    row = json.loads(path.read_text(encoding="utf-8"))
    for key, value in expected_record(scenario, seed, system, record_source).items():
        if row.get(key) != value:
            raise ValueError(f"{path}: {key} mismatch")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"{path}: incomplete query samples")
    for key in ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                "completion_fraction", "backlog_at_window_end"):
        if row.get(key) is None:
            raise ValueError(f"{path}: missing {key}")
    return row


def choose(scenario: str, seed: int, system: str) -> tuple[dict | None, dict]:
    if scenario not in LOADS or seed not in SEEDS:
        raise ValueError((scenario, seed))
    solution, cluster = layout(scenario, system)
    audit = audit_layout(solution, cluster, scenario)
    rejected = []
    for path, source_kind in sources(scenario, seed, system):
        if not path.is_file():
            rejected.append({"path": str(path.relative_to(ROOT)),
                             "reason": "missing"})
            continue
        try:
            row = valid_record(path, scenario, seed, system, source_kind)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            rejected.append({"path": str(path.relative_to(ROOT)),
                             "reason": str(error)})
            continue
        return row, {"source": str(path.relative_to(ROOT)).replace("\\", "/"),
                     "source_kind": source_kind, "source_sha256": digest(path),
                     "layout_audit": audit, "rejected_prior_sources": rejected}
    return None, {"source": None, "source_kind": "missing",
                  "layout_audit": audit, "rejected_prior_sources": rejected}


def paired(candidate: dict, reference: dict) -> dict:
    for field in MATCH_FIELDS:
        if candidate.get(field) != reference.get(field):
            raise ValueError(f"Unpaired {field}: {candidate['scenario']}/{candidate['seed']}")
    return common_cohort(candidate, reference)
