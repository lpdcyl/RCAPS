"""Helix/V3 placement-by-scheduler crossover on paired fixed windows.

Usage: python -m experiments.v3_method_validation.crossover --phase audit|smoke|formal|low
       python -m experiments.v3_method_validation.crossover --phase report
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from configparser import ConfigParser
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from statistics import mean

from baselines.helix import layout as helix_layout
from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.fixed_window import run as fixed_window_run
from benchmarks.layout import scenario as benchmark_scenario
from experiments.m2_multistage_candidate.analysis import common_completed, pending
from experiments.v3_release.verify import digest
from rcaps.v3.resource_graph import GpuResource, PhysicalLink, ResourceGraph, layer_dag
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel, UNITS
from rcaps.v3_method import layout as v3_layout
from simulator.event_simulator.utils import MB, GB


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCENARIOS = ("single", "multi")
CELLS = {"HH": ("helix", "helix"), "HR": ("helix", "m3"),
         "RH": ("v3", "helix"), "RR": ("v3", "m3")}
LOADS = {"formal": {"single": 700.0, "multi": 320.0},
         "low": {"single": 350.0, "multi": 160.0}}
SEEDS = (0, 1, 2)
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
PAIRS = (("HH", "HR"), ("HH", "RH"), ("HR", "RR"), ("RH", "RR"))


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _layout(scenario: str, cell: str) -> tuple[Path, Path]:
    placement, _ = CELLS[cell]
    return (helix_layout if placement == "helix" else v3_layout)(scenario, ROOT)


def _physical(scenario: str) -> Path:
    return benchmark_scenario(scenario)[0]


def _runtime_hash() -> dict[str, str]:
    names = ("benchmarks/fixed_window.py", "rcaps/v3/resource_graph.py",
             "rcaps/v3/scheduler.py", "rcaps/v3/routing.py",
             "rcaps/v3/queue_cost.py", "rcaps/v3/online_scheduler.py",
             "simulator/scheduler/global_maxflow/global_maxflow_scheduler.py",
             "simulator/scheduler/global_maxflow/scheduler_core.py")
    return {name: digest(ROOT / name) for name in names}


def _number(expression: str) -> float:
    return float(eval(expression, {"__builtins__": {}}, {**UNITS, "MB": MB, "GB": GB}))


def _node_id(name: str) -> str | int:
    return name if name in ("source", "sink") else int(name.removeprefix("compute_node_")) - 2


def _audit_layout(scenario: str, placement: str) -> dict:
    physical = _physical(scenario)
    model = TopologyModel(physical)
    solution, cluster = _layout(scenario, "HH" if placement == "helix" else "RR")
    sol, sim = ConfigParser(), ConfigParser()
    if not sol.read(solution) or not sim.read(cluster):
        raise FileNotFoundError(f"Missing deployment: {solution}, {cluster}")
    names = ast.literal_eval(sim["ComputeNodes"]["names"])
    if len(names) != len(model.types):
        raise ValueError(f"Different physical GPU count: {scenario}/{placement}")
    for name in names:
        node = _node_id(name)
        kind = ast.literal_eval(sim[name]["machine_type"])
        if kind != model.types[node]:
            raise ValueError(f"GPU type mismatch: {scenario}/{placement}/{name}")
        if _number(sim[name]["kv_cache_capacity"]) <= 0:
            raise ValueError(f"Nonpositive KV capacity: {scenario}/{placement}/{name}")
    spans = {}
    for name, encoded in sol["Solution"].items():
        layers = ast.literal_eval(encoded)
        if not layers:
            continue
        if layers != list(range(layers[0], layers[-1] + 1)):
            raise ValueError(f"Noncontiguous layers: {scenario}/{placement}/{name}")
        node = _node_id(name)
        if len(layers) > model.capacity[node]:
            raise ValueError(f"VRAM layer capacity exceeded: {scenario}/{placement}/{name}")
        spans[node] = (layers[0], layers[-1] + 1)
    edges = {}
    for name in ast.literal_eval(sim["Links"]["names"]):
        values = sim[name]
        left, right = _node_id(values["in"]), _node_id(values["out"])
        expected_latency, expected_bandwidth = model.link(left, right)
        actual_latency = _number(values["latency"])
        actual_bandwidth = _number(values["bandwidth"])
        if not (math.isclose(actual_latency, expected_latency, rel_tol=1e-8, abs_tol=1e-9)
                and math.isclose(actual_bandwidth, expected_bandwidth, rel_tol=1e-8)):
            raise ValueError(f"Physical link differs: {scenario}/{placement}/{name}")
        edges[left, right] = PhysicalLink(actual_latency, actual_bandwidth)
    resources = ResourceGraph({node: GpuResource(model.types[node], model.capacity[node])
                               for node in model.types}, edges, model.layers)
    entries = tuple(node for node, (start, _) in spans.items()
                    if start == 0 and ("source", node) in edges)
    dag = layer_dag(resources, spans, entries)
    if dag.edge_set != frozenset(edges):
        raise ValueError(f"Deployment contains an edge outside the layer-compatible DAG: {scenario}/{placement}")
    forward, backward = {"source"}, {"sink"}
    for _ in range(len(spans) + 1):
        forward.update(right for left, right in dag.edges if left in forward)
        backward.update(left for left, right in dag.edges if right in backward)
    stranded = sorted(node for node in spans if node not in forward.intersection(backward))
    hardware = {name: {field: _number(sim[name][field]) for field in (
                    "vram_size", "inbound_nic_speed", "outbound_nic_speed", "disk_speed",
                    "activation_backup_capacity")}
                for name in names}
    return {"solution": _relative(solution), "solution_sha256": digest(solution),
            "sim_cluster": _relative(cluster), "sim_cluster_sha256": digest(cluster),
            "physical": _relative(physical), "physical_sha256": digest(physical),
            "loaded_gpus": len(spans), "disconnected_loaded_gpus": stranded,
            "logical_edges": len(edges),
            "complete_paths": dag.path_count(), "gpu_types": dict(Counter(model.types.values())),
            "hardware": hardware}


def audit() -> dict:
    manifest = _read(ROOT / "experiments/v3_release/manifest.json")
    for name, expected in manifest["code_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Frozen V3 code drifted: {name}")
    result = {"runtime_sha256": _runtime_hash(), "scenarios": {}}
    for scenario in SCENARIOS:
        layouts = {placement: _audit_layout(scenario, placement)
                   for placement in ("helix", "v3")}
        expected = manifest["layouts"][scenario]
        for key in ("solution_sha256", "sim_cluster_sha256", "physical_sha256"):
            if layouts["v3"][key] != expected[key]:
                raise ValueError(f"V3 deployment drifted: {scenario}/{key}")
        if layouts["helix"]["physical_sha256"] != layouts["v3"]["physical_sha256"]:
            raise ValueError("Crossover placements use different physical pools")
        if layouts["helix"]["hardware"] != layouts["v3"]["hardware"]:
            raise ValueError(f"Crossover GPU/NIC hardware differs: {scenario}")
        result["scenarios"][scenario] = layouts
    _write(HERE / "crossover_audit.json", result)
    return result


def _source(phase: str, scenario: str, seed: int, cell: str) -> Path:
    return HERE / "runs" / phase / scenario / f"seed{seed}" / f"{cell}.json"


def _audit_routes(row: dict, scenario: str, cell: str) -> dict:
    solution, cluster = _layout(scenario, cell)
    sol, sim = ConfigParser(), ConfigParser()
    sol.read(solution)
    sim.read(cluster)
    spans = {}
    for name, encoded in sol["Solution"].items():
        layers = ast.literal_eval(encoded)
        if layers:
            spans[_node_id(name)] = (layers[0], layers[-1] + 1)
    edges = {(_node_id(sim[name]["in"]), _node_id(sim[name]["out"]))
             for name in ast.literal_eval(sim["Links"]["names"])}
    layer_count = TopologyModel(_physical(scenario)).layers
    total = 0
    for encoded, count in row.get("route_counts", {}).items():
        route = [int(part) - 2 for part in encoded.split("-")]
        boundary, previous = 0, "source"
        for node in route:
            if (previous, node) not in edges or node not in spans:
                raise ValueError(f"Executed edge is absent from deployment: {encoded}")
            start, end = spans[node]
            if not start <= boundary < end:
                raise ValueError(f"Executed route does not advance layers: {encoded}")
            boundary, previous = end, node
        if boundary != layer_count or (previous, "sink") not in edges:
            raise ValueError(f"Executed route lacks full layer coverage: {encoded}")
        total += count
    return {"actual_distinct_paths": len(row.get("route_counts", {})),
            "routed_requests": total, "checked": True}


def _expected(phase: str, scenario: str, seed: int, cell: str) -> dict:
    solution, cluster = _layout(scenario, cell)
    return {"scenario": scenario, "seed": seed,
            "offered_tokens_per_s": LOADS["formal" if phase == "smoke" else phase][scenario],
            "duration_s": 60 if phase == "smoke" else 1800, "warmup_s": 0,
            "evaluation_protocol": "fixed_window_no_tail_drain",
            "solution_sha256": digest(solution), "sim_cluster_sha256": digest(cluster),
            "physical_cluster_sha256": digest(_physical(scenario)),
            "placement": CELLS[cell][0], "scheduler": CELLS[cell][1], "cell": cell}


def _reuse_rr(scenario: str, seed: int) -> dict:
    source = ROOT / "benchmarks/runs" / scenario / f"seed{seed}" / "rcaps_v3.json"
    row = _read(source)
    solution, cluster = _layout(scenario, "RR")
    expected = _expected("formal", scenario, seed, "RR")
    for key in ("scenario", "seed", "offered_tokens_per_s", "duration_s",
                "warmup_s", "evaluation_protocol", "solution_sha256",
                "sim_cluster_sha256"):
        if row.get(key) != expected[key]:
            raise ValueError(f"RR reuse differs on {key}: {source}")
    if row.get("physical_sha256") != expected["physical_cluster_sha256"]:
        raise ValueError(f"RR physical hash differs: {source}")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"RR request sample set incomplete: {source}")
    # Existing release audit checks the deployed graph and route semantics.
    from experiments.v3_core_ablations.run import _audit_reuse
    _audit_reuse("C1_single" if scenario == "single" else "C1_multi",
                 "D", seed, "formal")
    return {"status": "reused", "source": _relative(source),
            "sha256": digest(source), "trace_sha256": row["trace_sha256"],
            "runtime_sha256": _runtime_hash()}


def _execute(phase: str, scenario: str, seed: int, cell: str) -> dict:
    output = _source(phase, scenario, seed, cell)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".log")
    failure_path = output.with_suffix(".failure.json")
    expected = _expected(phase, scenario, seed, cell)
    if output.is_file():
        previous = _read(output)
        if any(previous.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Existing window has different identity: {output}")
        return {"status": "passed", "source": _relative(output), "sha256": digest(output),
                "trace_sha256": previous["trace_sha256"], "existing": True}
    placement, scheduler = CELLS[cell]
    solution, cluster = _layout(scenario, cell)
    try:
        with log_path.open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            print(json.dumps({"phase": phase, "scenario": scenario, "seed": seed,
                              "cell": cell, "expected": expected}, ensure_ascii=False), flush=True)
            row = fixed_window_run(
                scenario, "helix" if scheduler == "helix" else "queue_dag",
                expected["offered_tokens_per_s"], expected["duration_s"], 0,
                seed, solution, cluster,
                physical_cluster=_physical(scenario),
                scheduler_factory=(GraphModeledQueueAwareDagScheduler
                                   if scheduler == "m3" else None),
                compact=True, record_query_samples=True)
            row["route_audit"] = _audit_routes(row, scenario, cell)
            row.update(expected)
            row["runtime_sha256"] = _runtime_hash()
            _write(output, row)
            print(f"completed {scenario}/{cell}/seed{seed}", flush=True)
        failure_path.unlink(missing_ok=True)
        return {"status": "passed", "source": _relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "log": _relative(log_path), "existing": False}
    except Exception as error:
        with log_path.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        progress = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("progress:")]
        failure = {"status": "failed", "phase": phase, "scenario": scenario,
                   "seed": seed, "cell": cell, "error_type": type(error).__name__,
                   "error": str(error), "last_progress": progress[-1] if progress else None,
                   "log": _relative(log_path), "expected": expected}
        _write(failure_path, failure)
        return {**failure, "failure_source": _relative(failure_path),
                "failure_sha256": digest(failure_path)}


def run_phase(phase: str, workers: int, scenarios: tuple[str, ...]) -> dict:
    audit_result = audit()
    if phase == "low":
        high = _read(HERE / "formal_index.json")
        scenarios = tuple(scenario for scenario in scenarios
                          if any(high["jobs"].get(f"{scenario}/seed{seed}/{cell}", {}).get("status")
                                 == "failed" for seed in SEEDS for cell in CELLS))
        if not scenarios:
            raise ValueError("Low-load fallback requires a formal high-load failure")
    seeds = (100,) if phase == "smoke" else SEEDS
    jobs = [(scenario, seed, cell) for scenario in scenarios
            for seed in seeds for cell in CELLS]
    index = {"phase": phase, "protocol": {"loads": LOADS["formal" if phase == "smoke" else phase],
             "seeds": list(seeds), "duration_s": 60 if phase == "smoke" else 1800,
             "warmup_s": 0, "tail_drain": False},
             "audit_sha256": digest(HERE / "crossover_audit.json"), "jobs": {}}
    pending_jobs = []
    for scenario, seed, cell in jobs:
        key = f"{scenario}/seed{seed}/{cell}"
        if phase == "formal" and cell == "RR":
            try:
                index["jobs"][key] = _reuse_rr(scenario, seed)
                continue
            except Exception as error:
                index["jobs"][key] = {"status": "reuse_rejected", "reason": str(error)}
        pending_jobs.append((scenario, seed, cell))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_execute, phase, *item): item for item in pending_jobs}
        for future in as_completed(futures):
            scenario, seed, cell = futures[future]
            key = f"{scenario}/seed{seed}/{cell}"
            try:
                index["jobs"][key] = future.result()
            except Exception as error:
                index["jobs"][key] = {"status": "runner_failed", "error": str(error)}
            _write(HERE / f"{phase}_index.json", index)
            print(f"{key}: {index['jobs'][key]['status']}", flush=True)
    _write(HERE / f"{phase}_index.json", index)
    return index


def _record(phase: str, scenario: str, seed: int, cell: str, index: dict) -> tuple[dict, dict] | None:
    item = index["jobs"].get(f"{scenario}/seed{seed}/{cell}")
    if not item or item["status"] not in ("passed", "reused"):
        return None
    source = ROOT / item["source"]
    if digest(source) != item["sha256"]:
        raise ValueError(f"Raw result hash changed: {source}")
    row = _read(source)
    expected = _expected(phase, scenario, seed, cell)
    for key in ("scenario", "seed", "offered_tokens_per_s", "duration_s",
                "warmup_s", "evaluation_protocol", "solution_sha256", "sim_cluster_sha256"):
        if row.get(key) != expected[key]:
            raise ValueError(f"Record identity differs on {key}: {source}")
    if item["status"] == "passed" and row.get("physical_cluster_sha256") != expected["physical_cluster_sha256"]:
        raise ValueError(f"Physical hash differs: {source}")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"Incomplete request samples: {source}")
    return row, item


def report(phase: str) -> dict:
    index = _read(HERE / f"{phase}_index.json")
    result = {"phase": phase, "protocol": index["protocol"],
              "audit_sha256": index["audit_sha256"], "scenarios": {}}
    lines = ["# V3 × Helix 放置与调度交叉实验", "",
             "HH=Helix ILP+Helix Online MaxFlow；HR=Helix ILP+V3 M3；"
             "RH=V3 M2+Helix Online MaxFlow；RR=完整 V3。",
             "相同拓扑、负载、种子、请求轨迹和固定窗口；失败不填补指标。", ""]
    for scenario in SCENARIOS:
        if scenario not in ("single", "multi") or not any(
                key.startswith(f"{scenario}/") for key in index["jobs"]):
            continue
        lines.extend([f"## {scenario}", "",
                      "| 种子 | 格 | 状态 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 未完成驻留 P95 s |",
                      "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        entries = {}
        complete = {}
        for seed in SEEDS:
            rows, sources = {}, {}
            for cell in CELLS:
                entry = _record(phase, scenario, seed, cell, index)
                if entry is None:
                    status = index["jobs"].get(f"{scenario}/seed{seed}/{cell}", {}).get("status", "missing")
                    lines.append(f"| {seed} | {cell} | {status} | — | — | — | — | — | — |")
                    continue
                row, source = entry
                rows[cell], sources[cell] = row, source
                wait = pending(row)
                pending_p95 = (f"{wait['p95_s']:.3f}"
                               if wait['p95_s'] is not None else "—")
                lines.append(f"| {seed} | {cell} | {source['status']} | "
                             f"{row['output_throughput_tokens_per_s']:.3f} | "
                             f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                             f"{row['completion_fraction']:.3f} | {row['backlog_at_window_end']} | "
                             f"{pending_p95} |")
            if len(rows) >= 2:
                reference = next(iter(rows.values()))
                for cell, row in rows.items():
                    for key in MATCH_FIELDS:
                        left = row.get(key, 1 if key == "query_samples_schema" else None)
                        right = reference.get(key, 1 if key == "query_samples_schema" else None)
                        if left != right:
                            raise ValueError(f"Unpaired {scenario}/seed{seed}/{cell} on {key}")
                    common_cohort(row, reference)
            effects = {}
            for left, right in PAIRS:
                if left in rows and right in rows:
                    effects[f"{left}->{right}"] = {
                        "deltas": {metric: rows[right][metric] - rows[left][metric]
                                   for metric in METRICS},
                        "common_completed": common_completed(rows[left], rows[right])}
            interaction = ({metric: rows["RR"][metric] - rows["RH"][metric]
                            - rows["HR"][metric] + rows["HH"][metric]
                            for metric in METRICS} if len(rows) == 4 else None)
            entries[str(seed)] = {"sources": sources,
                                  "metrics": {cell: {metric: row[metric] for metric in METRICS}
                                              for cell, row in rows.items()},
                                  "pending": {cell: pending(row) for cell, row in rows.items()},
                                  "route_audit": {cell: _audit_routes(row, scenario, cell)
                                                  for cell, row in rows.items()},
                                  "effects": effects, "interaction": interaction,
                                  "trace_sha256": reference["trace_sha256"] if rows else None}
            if len(rows) == 4:
                complete[str(seed)] = entries[str(seed)]
        lines.append("")
        lines.extend(["| 种子 | 配对 | 共同完成数 | TTFT P95 左/右 s | TPOT P95 左/右 s |",
                      "| ---: | --- | ---: | ---: | ---: |"])
        for seed, entry in entries.items():
            for pair, comparison in entry["effects"].items():
                shared = comparison["common_completed"]
                ttft = shared["ttft_s"]
                tpot = shared["tpot_s"]
                lines.append(f"| {seed} | {pair} | {shared['count']} | "
                             f"{ttft['left_p95_s']:.3f}/{ttft['right_p95_s']:.3f} | "
                             f"{tpot['left_p95_s']:.3f}/{tpot['right_p95_s']:.3f} |")
        lines.extend(["", "| 种子 | 格 | 未完成数 | 驻留 P50/P95/最大 s |",
                      "| ---: | --- | ---: | ---: |"])
        for seed, entry in entries.items():
            for cell, distribution in entry["pending"].items():
                ages = (f"{distribution['p50_s']:.3f}/{distribution['p95_s']:.3f}/"
                        f"{distribution['max_s']:.3f}"
                        if distribution["count"] else "—")
                lines.append(f"| {seed} | {cell} | {distribution['count']} | {ages} |")
        lines.append("")
        lines.extend(["| 对照 | 指标 | 配对差均值 |", "| --- | --- | ---: |"])
        for left, right in PAIRS:
            for metric in METRICS:
                values = [entry["effects"][f"{left}->{right}"]["deltas"][metric]
                          for entry in entries.values()
                          if f"{left}->{right}" in entry["effects"]]
                if len(values) == len(SEEDS):
                    lines.append(f"| {left}→{right} | {metric} | {mean(values):.4f} |")
        if len(complete) == len(SEEDS):
            for metric in METRICS:
                values = [entry["interaction"][metric] for entry in complete.values()]
                lines.append(f"| 四格交互 | {metric} | {mean(values):.4f} |")
        else:
            lines.append("| 四格交互 | — | 不计算：四格未在全部种子齐全 |")
        lines.append("")
        result["scenarios"][scenario] = {"seeds": entries,
                                          "complete_four_cell_seeds": sorted(complete)}
    lines.extend(["三个种子仅描述波动，不作显著性声明。条件收益不能解释为脱离另一组件的固定贡献。", ""])
    _write(HERE / f"{phase}_analysis.json", result)
    (HERE / f"{phase}_report.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("audit", "smoke", "formal", "low", "report"),
                        required=True)
    parser.add_argument("--report-phase", choices=("formal", "low"), default="formal")
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS,
                        default=list(SCENARIOS))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.phase == "audit":
        result = audit()
        print(f"Audited {len(result['scenarios'])} topologies")
    elif args.phase == "report":
        result = report(args.report_phase)
        print(f"Reported {len(result['scenarios'])} topologies")
    else:
        run_phase(args.phase, args.workers, tuple(args.scenarios))


if __name__ == "__main__":
    main()
