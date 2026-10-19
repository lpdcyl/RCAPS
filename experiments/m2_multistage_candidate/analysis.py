"""Integrity checks and path-use evidence for multistage M2 windows."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

import numpy as np

from rcaps.v3.topology import TopologyModel

from .placement import HERE, ROOT, digest, validate
from .prepare import files


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def p95(values: list[float]) -> float | None:
    return float(np.percentile(values, 95)) if values else None


def pending(row: dict) -> dict:
    ages = [max(0.0, row["duration_s"] - sample["arrival_s"])
            for sample in row["query_samples"].values() if not sample["completed"]]
    if len(ages) != row["backlog_at_window_end"]:
        raise ValueError("Request-level backlog does not match aggregate backlog")
    return {"count": len(ages), "p50_s": float(np.percentile(ages, 50)) if ages else None,
            "p95_s": p95(ages), "max_s": max(ages) if ages else None}


def common_completed(left: dict, right: dict) -> dict:
    if left["trace_sha256"] != right["trace_sha256"]:
        raise ValueError("Paired runs use different arrival traces")
    a, b = left["query_samples"], right["query_samples"]
    if set(a) != set(b):
        raise ValueError("Paired runs have different request identities")
    shared = [key for key in a if a[key]["completed"] and b[key]["completed"]]
    result = {"count": len(shared)}
    for name in ("ttft_s", "tpot_s"):
        eligible = [key for key in shared if a[key][name] is not None and
                    b[key][name] is not None]
        result[name] = {"count": len(eligible),
                        "left_p95_s": p95([a[key][name] for key in eligible]),
                        "right_p95_s": p95([b[key][name] for key in eligible])}
    return result


def path_use(case: str, variant: str, row: dict) -> dict:
    physical, _, _ = files(case)
    model = TopologyModel(physical)
    placement_file = HERE / "layouts" / case / variant / "placement.json"
    placement = json.loads(placement_file.read_text(encoding="utf-8"))
    checked = validate(model, placement["state"])
    dag = checked["dag"]
    memberships = {}
    for level, segment in enumerate(placement["state"]["segments"]):
        for branch, replica in enumerate(segment["replicas"]):
            for node in replica:
                memberships[node] = (level, branch)
    distinct = set()
    total = noncanonical = 0
    gpu_request_counts = {str(node): 0 for node in checked["spans"]}
    for encoded, count in row["route_counts"].items():
        nodes = tuple(int(token) - 2 for token in encoded.split("-"))
        route = list(zip(("source", *nodes), (*nodes, "sink")))
        if any(edge not in dag.edge_set for edge in route):
            raise ValueError(f"Executed route is absent from M1 DAG: {encoded}")
        if not nodes or checked["spans"][nodes[0]][0] != 0 or \
                checked["spans"][nodes[-1]][1] != model.layers:
            raise ValueError(f"Incomplete executed model route: {encoded}")
        distinct.add(nodes)
        total += count
        for node in set(nodes):
            gpu_request_counts[str(node)] += count
        seen = {}
        for node in nodes:
            level, branch = memberships[node]
            seen.setdefault(level, set()).add(branch)
        if any(len(branches) > 1 for branches in seen.values()):
            noncanonical += count
    return {"compatible_dag_paths": dag.path_count(),
            "compatible_dag_edges": len(dag.edges),
            "actual_distinct_paths": len(distinct),
            "routed_requests": total,
            "cross_replica_requests": noncanonical,
            "cross_replica_fraction": noncanonical / total if total else None,
            "gpu_request_counts": gpu_request_counts}


def source(phase: str, case: str, variant: str, seed: int) -> tuple[dict, dict] | None:
    index_file = HERE / f"{phase}_index.json"
    if not index_file.exists():
        return None
    index = json.loads(index_file.read_text(encoding="utf-8"))
    item = index.get(case, {}).get(variant, {})
    if item.get("status") != "passed" or str(seed) not in item.get("sources", {}):
        return None
    entry = item["sources"][str(seed)]
    path = ROOT / entry["source"]
    if digest(path) != entry["sha256"]:
        raise ValueError(f"Raw run hash changed: {path}")
    row = json.loads(path.read_text(encoding="utf-8"))
    if row["trace_sha256"] != entry["trace_sha256"]:
        raise ValueError(f"Trace hash changed: {path}")
    return row, entry


def summarize(case: str, variant: str, seed: int) -> dict | None:
    selected = source("formal", case, variant, seed)
    if selected is None:
        return None
    row, entry = selected
    return {"source": entry, "metrics": {key: row[key] for key in METRICS},
            "pending": pending(row), "paths": path_use(case, variant, row),
            "gpu_busy_fraction": row.get("gpu_busy_fraction", {}),
            "gpu_queued_at_end": row.get("gpu_queued_at_end"),
            "link_occupied_fraction": row.get("link_occupied_fraction", {})}


def means(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row[key] is not None]
    return mean(values) if values else None
