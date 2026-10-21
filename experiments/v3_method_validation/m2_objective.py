"""Objective-factor ablation of the frozen V3 M2 search.

The frozen search module is imported unchanged. Each worker substitutes only
its objective callable in its own process, then exports into this experiment.
"""

from __future__ import annotations

import argparse
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from statistics import mean

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.analysis import common_completed, pending
from experiments.m2_multistage_candidate.prepare import (files, initial_state,
                                                           reference_state)
from experiments.v3_release.verify import digest
from rcaps.v3 import search as frozen_search
from rcaps.v3.placement import (measure as frozen_measure, normalize, objective as full_objective,
                                save, signature, validate)
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel
from rcaps.v3_method import layout as frozen_layout

from .crossover import ROOT, HERE, SEEDS, _read, _relative, _write, audit


CASES = ("C1_single", "C1_multi", "C2", "C3")
ONLINE = ("C1_single", "C1_multi")
OBJECTIVES = {
    "full": (0.40, 0.35, 0.25),
    "prompt_only": (1.0, 0.0, 0.0),
    "decode_only": (0.0, 1.0, 0.0),
    "prompt_decode": (0.40 / 0.75, 0.35 / 0.75, 0.0),
}
KEYS = ("ttft_s", "tpot_s", "bottleneck_s")
LOADS = {"C1_single": 700.0, "C1_multi": 320.0}
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def score(metrics: dict, reference: dict, variant: str) -> float:
    return sum(weight * metrics[key] / reference[key]
               for weight, key in zip(OBJECTIVES[variant], KEYS))


def _plan_one(case: str, variant: str) -> dict:
    physical, template, topology = files(case)
    model = TopologyModel(physical)
    seed = initial_state(case, model)
    reference = reference_state(case, model, seed)
    reference_metrics = frozen_measure(model, reference)
    candidates = {}
    original_measure, original_objective = frozen_search.measure, frozen_search.objective

    def tracked_measure(physical_model, state):
        metrics = original_measure(physical_model, state)
        candidates[signature(state)] = {"state": normalize(state), "metrics": metrics}
        return metrics

    def ablated_objective(metrics, reference_metrics):
        return score(metrics, reference_metrics, variant)

    try:
        frozen_search.measure = tracked_measure
        frozen_search.objective = ablated_objective
        outcome = frozen_search.search(model, reference, a100_prefix=False,
                                       seed_state=seed)
        result = outcome["multi"]
    finally:
        frozen_search.measure = original_measure
        frozen_search.objective = original_objective
    if result["status"] != "feasible":
        raise ValueError(f"No feasible M2 layout: {case}/{variant}")
    state = result["state"]
    checked = validate(model, state)
    destination = HERE / "m2_layouts" / case / variant
    record = save(model, template, state, destination,
                  {"objective_variant": variant,
                   "reference": reference_metrics,
                   "candidate_evaluations": result["candidate_evaluations"],
                   "search_wall_s": outcome["search_wall_s"],
                   "score": result["score"]})
    selected = frozen_measure(model, state)
    item = {"case": case, "variant": variant,
            "physical_sha256": digest(physical), "template_sha256": digest(template),
            "reference": reference_metrics, "selected_metrics": selected,
            "score_under_own_objective": score(selected, reference_metrics, variant),
            "score_under_frozen_full_objective": full_objective(selected, reference_metrics),
            "candidate_evaluations": result["candidate_evaluations"],
            "common_evaluations": result["common_evaluations"],
            "additional_evaluations": result["additional_evaluations"],
            "search_wall_s": record.get("search_wall_s"),
            "solution_sha256": digest(destination / "solution.ini"),
            "sim_cluster_sha256": digest(destination / "simulator_cluster.ini"),
            "state_sha256": digest(destination / "placement.json"),
            "widths": record["widths"], "boundaries": [x["end"] for x in state["segments"][:-1]],
            "active_gpus": record["active_gpus"], "layer_copies": record["layer_copies"],
            "compatible_paths": checked["dag"].path_count(),
            "candidate_bank_size": len(candidates)}
    _write(HERE / "m2_candidates" / case / f"{variant}.json",
           {"case": case, "variant": variant, "reference": reference_metrics,
            "candidates": candidates})
    _write(HERE / "m2_plans" / case / f"{variant}.json", item)
    if variant == "full" and case in ONLINE:
        scenario = "single" if case == "C1_single" else "multi"
        frozen_solution, frozen_cluster = frozen_layout(scenario, ROOT)
        if (item["solution_sha256"] != digest(frozen_solution) or
                item["sim_cluster_sha256"] != digest(frozen_cluster)):
            raise ValueError(f"Full M2 objective did not reproduce frozen V3: {case}")
    return item


def plan(workers: int) -> dict:
    audit()
    jobs = [(case, variant) for case in CASES for variant in OBJECTIVES]
    result = {"objectives": OBJECTIVES, "cases": {case: {} for case in CASES}}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_plan_one, *item): item for item in jobs}
        for future in as_completed(futures):
            case, variant = futures[future]
            try:
                item = future.result()
                result["cases"][case][variant] = item
                print(f"{case}/{variant}: score={item['score_under_own_objective']:.4f}",
                      flush=True)
            except Exception as error:
                result["cases"][case][variant] = {"status": "failed",
                                                     "error": repr(error)}
                print(f"{case}/{variant}: failed: {error}", flush=True)
            _write(HERE / "m2_offline_index.json", result)
    for case in CASES:
        if any(result["cases"][case][variant].get("status") == "failed"
               for variant in OBJECTIVES):
            continue
        bank = {}
        reference = result["cases"][case]["full"]["reference"]
        for variant in OBJECTIVES:
            source = _read(HERE / "m2_candidates" / case / f"{variant}.json")
            if source["reference"] != reference:
                raise ValueError(f"Different M2 reference metrics: {case}/{variant}")
            bank.update(source["candidates"])
        analysis = {"case": case, "union_legal_candidates": len(bank),
                    "reference": reference, "selected": {}}
        for variant in OBJECTIVES:
            values = sorted((score(item["metrics"], reference, variant), key)
                            for key, item in bank.items())
            selected = _read(HERE / "m2_layouts" / case / variant / "placement.json")
            state_key = signature(selected["state"])
            selected_score = score(bank[state_key]["metrics"], reference, variant)
            rank = 1 + sum(value < selected_score - 1e-9 for value, _ in values)
            analysis["selected"][variant] = {
                "own_score_rank_in_union": rank,
                "best_union_score": values[0][0],
                "selected_score": selected_score}
        _write(HERE / "m2_candidates" / case / "union_analysis.json", analysis)
        result["cases"][case]["union_analysis"] = analysis
    _write(HERE / "m2_offline_index.json", result)
    return result


def _source(phase: str, case: str, seed: int, variant: str) -> Path:
    return HERE / "runs" / f"m2_{phase}" / case / f"seed{seed}" / f"{variant}.json"


def _execute(phase: str, case: str, seed: int, variant: str) -> dict:
    output = _source(phase, case, seed, variant)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".log")
    failure_path = output.with_suffix(".failure.json")
    physical, _, scenario = files(case)
    deployment = HERE / "m2_layouts" / case / variant
    solution, cluster = deployment / "solution.ini", deployment / "simulator_cluster.ini"
    expected = {"case": case, "m2_objective_variant": variant,
                "scenario": scenario, "seed": seed,
                "offered_tokens_per_s": LOADS[case],
                "duration_s": 60 if phase == "smoke" else 1800,
                "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
                "physical_cluster_sha256": digest(physical),
                "solution_sha256": digest(solution), "sim_cluster_sha256": digest(cluster)}
    if output.is_file():
        row = _read(output)
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Existing M2 result has a different identity: {output}")
        return {"status": "passed", "source": _relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"], "existing": True}
    try:
        with log_path.open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            row = fixed_window_run(
                scenario, "queue_dag", LOADS[case], expected["duration_s"], 0,
                seed, solution, cluster, physical_cluster=physical,
                scheduler_factory=GraphModeledQueueAwareDagScheduler,
                compact=True, record_query_samples=True)
            row.update(expected)
            _write(output, row)
        failure_path.unlink(missing_ok=True)
        return {"status": "passed", "source": _relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "log": _relative(log_path), "existing": False}
    except Exception as error:
        with log_path.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        progress = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("progress:")]
        failure = {"status": "failed", "case": case, "seed": seed, "variant": variant,
                   "error_type": type(error).__name__, "error": str(error),
                   "last_progress": progress[-1] if progress else None,
                   "log": _relative(log_path), "expected": expected}
        _write(failure_path, failure)
        return {**failure, "failure_source": _relative(failure_path),
                "failure_sha256": digest(failure_path)}


def run_phase(phase: str, workers: int) -> dict:
    offline = _read(HERE / "m2_offline_index.json")
    seeds = (100,) if phase == "smoke" else SEEDS
    jobs = [(case, seed, variant) for case in ONLINE for seed in seeds
            for variant in OBJECTIVES]
    index = {"phase": phase, "loads": LOADS, "seeds": list(seeds),
             "duration_s": 60 if phase == "smoke" else 1800,
             "jobs": {}, "offline_index_sha256": digest(HERE / "m2_offline_index.json")}
    pending_jobs = []
    scheduled_by_deployment = {}
    for case, seed, variant in jobs:
        key = f"{case}/seed{seed}/{variant}"
        plan_item = offline["cases"][case][variant]
        if plan_item.get("status") == "failed":
            index["jobs"][key] = {"status": "offline_failed"}
            continue
        deployment_key = (case, seed, plan_item["solution_sha256"],
                          plan_item["sim_cluster_sha256"])
        if deployment_key in scheduled_by_deployment:
            index["jobs"][key] = {"status": "duplicate_layout",
                                   "same_as": scheduled_by_deployment[deployment_key]}
            continue
        scheduled_by_deployment[deployment_key] = key
        if variant == "full" and phase == "formal":
            scenario = "single" if case == "C1_single" else "multi"
            path = ROOT / "benchmarks/runs" / scenario / f"seed{seed}" / "rcaps_v3.json"
            row = _read(path)
            if (row.get("solution_sha256") != plan_item["solution_sha256"] or
                    row.get("sim_cluster_sha256") != plan_item["sim_cluster_sha256"] or
                    row.get("physical_sha256") != plan_item["physical_sha256"] or
                    row.get("duration_s") != 1800 or row.get("seed") != seed or
                    row.get("offered_tokens_per_s") != LOADS[case]):
                raise ValueError(f"Cannot reuse frozen V3 window: {path}")
            index["jobs"][key] = {"status": "reused", "source": _relative(path),
                                   "sha256": digest(path), "trace_sha256": row["trace_sha256"],
                                   "same_execution_semantics": True}
            continue
        pending_jobs.append((case, seed, variant))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_execute, phase, *item): item for item in pending_jobs}
        for future in as_completed(futures):
            case, seed, variant = futures[future]
            key = f"{case}/seed{seed}/{variant}"
            try:
                index["jobs"][key] = future.result()
            except Exception as error:
                index["jobs"][key] = {"status": "runner_failed", "error": repr(error)}
            _write(HERE / f"m2_{phase}_index.json", index)
            print(f"{key}: {index['jobs'][key]['status']}", flush=True)
    _write(HERE / f"m2_{phase}_index.json", index)
    return index


def report() -> dict:
    index = _read(HERE / "m2_formal_index.json")
    offline = _read(HERE / "m2_offline_index.json")
    result = {"offline_index_sha256": index["offline_index_sha256"], "cases": {}}
    lines = ["# V3 M2 静态目标验证", "",
             "搜索空间、初始化、邻域和评分上限相同；仅改变归一化目标权重。",
             "原完整目标与 V3 冻结布局逐字节核对。", "",
             "## 离线结构与规划开销", "",
             "| 资源池 | 目标 | 副本宽度 | 边界 | 评价数 | 规划秒 | 原完整目标分数 |",
             "| --- | --- | --- | --- | ---: | ---: | ---: |"]
    for case in CASES:
        for variant in OBJECTIVES:
            item = offline["cases"][case][variant]
            if item.get("status") == "failed":
                lines.append(f"| {case} | {variant} | 失败 | — | — | — | — |")
                continue
            lines.append(f"| {case} | {variant} | {'→'.join(map(str, item['widths']))} | "
                         f"{','.join(map(str, item['boundaries']))} | "
                         f"{item['candidate_evaluations']} | {item['search_wall_s']:.2f} | "
                         f"{item['score_under_frozen_full_objective']:.4f} |")
    lines.extend(["", "## 同轨迹在线结果", "",
             "| 资源池 | 种子 | 目标 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 |",
             "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for case in ONLINE:
        result["cases"][case] = {}
        for seed in SEEDS:
            rows = {}
            for variant in OBJECTIVES:
                item = index["jobs"].get(f"{case}/seed{seed}/{variant}")
                if item and item["status"] == "duplicate_layout":
                    item = index["jobs"][item["same_as"]]
                if not item or item["status"] not in ("passed", "reused"):
                    lines.append(f"| {case} | {seed} | {variant} | — | — | — | — | — |")
                    continue
                source = ROOT / item["source"]
                if digest(source) != item["sha256"]:
                    raise ValueError(f"M2 raw result hash changed: {source}")
                row = _read(source)
                expected = offline["cases"][case][variant]
                if (row.get("solution_sha256") != expected["solution_sha256"] or
                        row.get("sim_cluster_sha256") != expected["sim_cluster_sha256"]):
                    raise ValueError(f"M2 reused deployment differs: {source}")
                rows[variant] = row
                lines.append(f"| {case} | {seed} | {variant} | "
                             f"{row['output_throughput_tokens_per_s']:.3f} | "
                             f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                             f"{row['completion_fraction']:.3f} | {row['backlog_at_window_end']} |")
            reference = rows.get("full")
            if reference:
                for variant, row in rows.items():
                    for key in MATCH_FIELDS:
                        left = row.get(key, 1 if key == "query_samples_schema" else None)
                        right = reference.get(key, 1 if key == "query_samples_schema" else None)
                        if left != right:
                            raise ValueError(f"Unpaired M2 window: {case}/{seed}/{variant}/{key}")
                    common_cohort(row, reference)
            result["cases"][case][str(seed)] = {
                "metrics": {variant: {key: row[key] for key in METRICS}
                            for variant, row in rows.items()},
                "pending": {variant: pending(row) for variant, row in rows.items()},
                "full_vs_variant": {variant: {
                    "delta": {key: rows["full"][key] - row[key] for key in METRICS},
                    "common_completed": common_completed(row, rows["full"])}
                    for variant, row in rows.items() if variant != "full" and "full" in rows}}
    lines.extend(["", "## 三种子均值", "",
                  "| 资源池 | 目标 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for case in ONLINE:
        for variant in OBJECTIVES:
            series = [result["cases"][case][str(seed)]["metrics"].get(variant)
                      for seed in SEEDS]
            if any(row is None for row in series):
                continue
            lines.append(f"| {case} | {variant} | " + " | ".join(
                f"{mean(row[key] for row in series):.3f}" for key in METRICS) + " |")
    lines.extend(["", "原目标分数只与同一原目标下的布局分数比较；不同消融目标的数值不直接比较。",
                  "三个种子只描述波动；结合完成率、积压和共同完成请求解释 P95。", ""])
    _write(HERE / "m2_formal_analysis.json", result)
    (HERE / "m2_formal_report.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("plan", "smoke", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "plan":
        plan(args.workers)
    elif args.phase == "report":
        report()
    else:
        run_phase(args.phase, args.workers)


if __name__ == "__main__":
    main()
