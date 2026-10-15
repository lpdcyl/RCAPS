"""Audit same-trace resource-pool windows and aggregate paired statistics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

from .prepare import HERE, ROOT, COUNTS


PROTOCOL = {"C1": (700.0, ("adaptive", "fixed_branches", "fixed_structure", "helix")),
            "C2": (160.0, ("adaptive", "fixed_branches", "helix")),
            "C3": (400.0, ("adaptive", "fixed_branches", "fixed_structure", "helix_petals")),
            "C4": (120.0, ("adaptive", "fixed_branches", "helix_petals")),
            "C5": (500.0, ("adaptive", "fixed_branches", "fixed_structure", "helix_petals"))}
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(case: str, method: str, seed: int, offered: float) -> tuple[Path, Path, Path, bool]:
    if case == "C1":
        scenario = "single"
        if method == "helix":
            path = ROOT / "benchmarks/runs" / scenario / f"seed{seed}/helix.json"
            layout = ROOT / "artifact_evaluation/single_cluster/layout_llama70b/ilp"
            return path, layout / "ilp_sol.ini", layout / "simulator_cluster.ini", False
        if method == "fixed_branches":
            path = ROOT / "experiments/v2_core_ablations/runs" / scenario / f"seed{seed}/rcaps_v2_fixed_branches.json"
            layout = ROOT / "experiments/v2_core_ablations/layouts/fixed_branches/single"
        else:
            suffix = "adaptive" if method == "adaptive" else "fixed"
            name = "rcaps_v2" if method == "adaptive" else "rcaps_v2_fixed_structure"
            path = ROOT / "experiments/v2_method_ablation/runs" / scenario / f"seed{seed}/{name}.json"
            layout = ROOT / "rcaps/v2_layouts" / f"single_{suffix}"
        return path, layout / "solution.ini", layout / "simulator_cluster.ini", False
    aliased = case in ("C2", "C4") and method == "fixed_branches"
    actual = "adaptive" if aliased else method
    path = HERE / "runs" / case / "1800s" / f"load{offered:g}" / f"seed{seed}" / f"{actual}.json"
    directory = HERE / "layouts" / case / (
        "helix_numeric" if method == "helix" else
        "petals" if method == "helix_petals" else method)
    solution = directory / ("ilp_sol.ini" if method == "helix" else
                            "petals_sol.ini" if method == "helix_petals" else "solution.ini")
    return path, solution, directory / "simulator_cluster.ini", aliased


def aggregate() -> dict:
    summary = {"protocol": "LLaMA-70B, complete single-cluster 1 ms/1000 mbps network, 1800 s, zero warmup, seeds 0/1/2",
               "cases": {}}
    for case, (offered, methods) in PROTOCOL.items():
        rows = []
        plan = json.loads((HERE / "pools" / case / "plan.json").read_text(encoding="utf-8"))
        physical = HERE / "pools" / case / "physical.ini"
        for seed in range(3):
            by_method = {}
            for method in methods:
                path, solution, cluster, aliased = source(case, method, seed, offered)
                record = json.loads(path.read_text(encoding="utf-8"))
                if (record["seed"] != seed or record["duration_s"] != 1800 or
                        record["warmup_s"] != 0 or
                        record["offered_tokens_per_s"] != offered):
                    raise ValueError(f"Protocol mismatch: {path}")
                for key, file in (("solution_sha256", solution),
                                  ("sim_cluster_sha256", cluster)):
                    if record.get(key) != digest(file):
                        raise ValueError(f"Layout mismatch: {path} {key}")
                if case != "C1" and record.get("physical_sha256") != digest(physical):
                    raise ValueError(f"Physical topology mismatch: {path}")
                if aliased:
                    adaptive_dir = HERE / "layouts" / case / "adaptive"
                    if (digest(solution), digest(cluster)) != (
                            digest(adaptive_dir / "solution.ini"),
                            digest(adaptive_dir / "simulator_cluster.ini")):
                        raise ValueError(f"Aliased layout differs: {case}")
                by_method[method] = {"path": str(path.relative_to(ROOT)),
                                     "aliased_same_layout": aliased,
                                     "trace_sha256": record["trace_sha256"],
                                     "metrics": {key: record[key] for key in METRICS}}
            if len({item["trace_sha256"] for item in by_method.values()}) != 1:
                raise ValueError(f"Trace mismatch: {case}, seed {seed}")
            rows.append({"seed": seed, "methods": by_method})
        statistics = {method: {key: {"mean": mean(row["methods"][method]["metrics"][key]
                                               for row in rows),
                                    "sample_sd": stdev(row["methods"][method]["metrics"][key]
                                                       for row in rows)}
                               for key in METRICS} for method in methods}
        paired = {}
        for method in methods:
            if method == "adaptive":
                continue
            paired[method] = {}
            for key in METRICS:
                differences = [row["methods"]["adaptive"]["metrics"][key] -
                               row["methods"][method]["metrics"][key]
                               for row in rows]
                paired[method][key] = {"mean": mean(differences),
                                       "sample_sd": stdev(differences)}
        summary["cases"][case] = {"counts": COUNTS[case], "offered": offered,
                                  "structure": {method: plan[method] for method in
                                                ("adaptive", "fixed_branches", "fixed_structure")},
                                  "rows": rows, "statistics": statistics,
                                  "paired_adaptive_minus_control": paired}
    low_rows = []
    for seed in range(3):
        pair = {}
        for method in ("adaptive", "helix"):
            path, solution, cluster, _ = source("C2", method, seed, 80.0)
            record = json.loads(path.read_text(encoding="utf-8"))
            if (record["seed"] != seed or record["duration_s"] != 1800 or
                    record["warmup_s"] != 0 or record["offered_tokens_per_s"] != 80.0):
                raise ValueError(f"C2 low-load protocol mismatch: {path}")
            for key, file in (("solution_sha256", solution),
                              ("sim_cluster_sha256", cluster),
                              ("physical_sha256", HERE / "pools/C2/physical.ini")):
                if record.get(key) != digest(file):
                    raise ValueError(f"C2 low-load input mismatch: {path} {key}")
            pair[method] = {"path": str(path.relative_to(ROOT)),
                            "trace_sha256": record["trace_sha256"],
                            "metrics": {key: record[key] for key in METRICS}}
        if pair["adaptive"]["trace_sha256"] != pair["helix"]["trace_sha256"]:
            raise ValueError(f"C2 low-load trace mismatch: seed {seed}")
        low_rows.append({"seed": seed, "methods": pair})
    summary["supplemental_c2_80"] = {
        "offered": 80.0, "rows": low_rows,
        "statistics": {method: {key: {"mean": mean(row["methods"][method]["metrics"][key]
                                                for row in low_rows),
                                      "sample_sd": stdev(row["methods"][method]["metrics"][key]
                                                         for row in low_rows)}
                                for key in METRICS}
                       for method in ("adaptive", "helix")}}
    return summary


if __name__ == "__main__":
    output = aggregate()
    target = HERE / "summary.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(target)
