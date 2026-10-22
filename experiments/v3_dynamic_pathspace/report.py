"""Audit paired traces and write a compact, reproducible mechanism index."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean

from experiments.v3_cycle_pricing.run import ROOT, write

HERE = Path(__file__).resolve().parent


def load(path: Path) -> dict:
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["arrivals"] == len(row["query_samples"]), path
    assert row["kv_admission"]["deferred_checks"] == 0, path
    return row


def source(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def measure(row: dict) -> dict:
    throughput = row["output_throughput_tokens_per_s"]
    assert abs(row["gpu_seconds_per_output_token"] -
               sum(row["gpu_busy_fraction"].values()) / throughput) < 1e-10
    return {
        "python": row["python_version"], "numpy": row["numpy_version"],
        "trace_sha256": row["trace_sha256"], "arrivals": row["arrivals"],
        "throughput": throughput, "ttft_p95_s": row["ttft_p95_s"],
        "tpot_p95_s": row["tpot_p95_s"],
        "completion_fraction": row["completion_fraction"],
        "backlog": row["backlog_at_window_end"],
        "mean_decode_batch": row["decode_batches"]["mean_batch"],
        "single_decode_share": row["decode_batches"]["single_share"],
        "gpu_seconds_per_output_token": row["gpu_seconds_per_output_token"],
        "link_service_seconds_per_output_token":
            sum(row["link_service_request_s"].values()) /
            (throughput * row["duration_s"]),
        "dispatch_wait_seconds_per_arrival":
            sum(row["link_dispatch_wait_request_s"].values()) / row["arrivals"],
        "routes_used": len(row["route_counts"]),
        "selected_extra_edges": row["gate_counts"].get("dynamic_selected", 0),
        "peak_kv_reserved_fraction": row["kv_peak_fraction"],
    }


def pair(phase: str, condition: str, cells: tuple[str, ...]) -> dict:
    values = {}
    identities = []
    for cell in cells:
        path = HERE / "runs" / phase / condition / f"{cell}_seed100.json"
        row = load(path)
        assert row["condition"] == condition and row["cell"] == cell
        assert row["seed"] == 100 and row["duration_s"] == 300
        identities.append(tuple(row[key] for key in (
            "solution_sha256", "sim_cluster_sha256", "physical_sha256")))
        values[cell] = {"source": source(path), **measure(row)}
    assert len(set(identities)) == 1
    assert len({v["trace_sha256"] for v in values.values()}) == 1
    assert len({(v["python"], v["numpy"]) for v in values.values()}) == 1
    return values


def formal_resource(case: str) -> dict:
    records = []
    for seed in (0, 1, 2):
        paths = {
            "v3": ROOT / "experiments/v3_cycle_pricing/runs/formal" / case / f"v3_seed{seed}.json",
            "static": ROOT / "experiments/v3_gated_pathspace/runs/formal" / case / f"gated_seed{seed}.json",
        }
        rows = {cell: json.loads(path.read_text(encoding="utf-8"))
                for cell, path in paths.items()}
        assert rows["v3"]["trace_sha256"] == rows["static"]["trace_sha256"]
        assert rows["v3"]["solution_sha256"] == rows["static"]["solution_sha256"]
        assert rows["v3"]["sim_cluster_sha256"] == rows["static"]["sim_cluster_sha256"]
        assert len({(row["python_version"], row["numpy_version"])
                    for row in rows.values()}) == 1
        record = {"seed": seed, "trace_sha256": rows["v3"]["trace_sha256"]}
        for cell, row in rows.items():
            throughput = row["output_throughput_tokens_per_s"]
            record[cell] = {
                "source": source(paths[cell]),
                "throughput": throughput, "tpot_p95_s": row["tpot_p95_s"],
                "gpu_seconds_per_output_token":
                    sum(row["gpu_busy_fraction"].values()) / throughput,
                "link_service_seconds_per_output_token":
                    sum(row["link_service_request_s"].values()) / (throughput * 1800),
                "dispatch_wait_seconds_per_arrival":
                    sum(row["link_dispatch_wait_request_s"].values()) / row["arrivals"],
            }
        records.append(record)
    averages = {}
    for metric in ("throughput", "tpot_p95_s", "gpu_seconds_per_output_token",
                   "link_service_seconds_per_output_token"):
        averages[metric + "_relative_static_vs_v3"] = mean(
            record["static"][metric] / record["v3"][metric] - 1
            for record in records)
    return {"seeds": records, "mean_paired_relative": averages}


def cross_environment_repeat() -> dict:
    first = HERE / "runs/dev_link_gllm/C1_multi/dynamic_link_no_batch_seed100.json"
    clean = HERE / "runs/dev_link_py312/C1_multi/dynamic_link_no_batch_seed100.json"
    a, b = load(first), load(clean)
    for key in ("trace_sha256", "output_throughput_tokens_per_s",
                "ttft_p95_s", "tpot_p95_s", "completion_fraction",
                "backlog_at_window_end", "route_counts", "gate_counts",
                "query_samples", "decode_batches", "gpu_busy_fraction"):
        assert a[key] == b[key], key
    return {"status": "exact_match_for_all_checked_fields",
            "first": source(first), "clean_exit_repeat": source(clean),
            "environments": [[a["python_version"], a["numpy_version"]],
                             [b["python_version"], b["numpy_version"]]]}


def main() -> None:
    report = {
        "development_only": {
            "gpu_plus_link_v2": {case: pair("dev", case, ("static", "dynamic"))
                                 for case in ("C1_single", "C1_multi")},
            "link_only_v3": {case: pair("dev_link_gllm", case,
                                         ("static", "dynamic_link", "dynamic_link_no_batch"))
                             for case in ("C1_single", "C1_multi")},
            "mechanism": {
                "C1_single": pair("mechanism_dev", "C1_single", ("full",)),
                "C1_multi": pair("mechanism_dev", "C1_multi", ("canonical", "full")),
                "C1_single_low_350": pair("mechanism_dev", "C1_single_low", ("full", "static")),
                "C1_single_sparse_100": pair("idle_dev", "C1_single_idle", ("full", "static")),
            },
        },
        "existing_formal_three_seed_resource": {
            case: formal_resource(case) for case in ("C1_single", "C1_multi")},
        "cross_environment_repeat": cross_environment_repeat(),
        "formal_decision": "Neither new dynamic candidate passed its pre-registered development go rule; no new formal windows were run.",
    }
    write(HERE / "analysis.json", report)
    print(HERE / "analysis.json")


if __name__ == "__main__":
    main()
