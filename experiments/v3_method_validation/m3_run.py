"""Paired M3 state-factor validation on the frozen V3 deployment."""

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
from experiments.v3_release.verify import digest
from rcaps.v3_method import layout as v3_layout

from .crossover import ROOT, HERE, SCENARIOS, SEEDS, _physical, _read, _relative, _write, audit
from .m3_state import VARIANTS


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
LOADS = {"single": 700.0, "multi": 320.0}
ARMS = ("static", "queue_only", "observed_eft", "full_no_session",
        "full_no_link", "full")


def _source(phase: str, scenario: str, seed: int, arm: str) -> Path:
    return HERE / "runs" / f"m3_{phase}" / scenario / f"seed{seed}" / f"{arm}.json"


def _reuse(scenario: str, seed: int, arm: str) -> dict:
    if arm == "full":
        from .crossover import _reuse_rr
        source = _reuse_rr(scenario, seed)
        return {**source, "status": "reused"}
    if arm != "static":
        raise ValueError(arm)
    case = "C1_single" if scenario == "single" else "C1_multi"
    path = ROOT / "experiments/v3_core_ablations/runs/formal" / case / f"seed{seed}" / "B.json"
    row = _read(path)
    index = _read(ROOT / "experiments/v3_core_ablations/formal_index.json")
    item = index["jobs"][f"{case}/B/seed{seed}"]
    solution, cluster = v3_layout(scenario, ROOT)
    expected = {"scenario": scenario, "seed": seed, "offered_tokens_per_s": LOADS[scenario],
                "duration_s": 1800, "warmup_s": 0,
                "solution_sha256": digest(solution), "sim_cluster_sha256": digest(cluster),
                "physical_sha256": digest(_physical(scenario)),
                "evaluation_protocol": "fixed_window_no_tail_drain"}
    if item["sha256"] != digest(path) or any(row.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Static V3 result cannot be reused: {path}")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"Incomplete static request samples: {path}")
    return {"status": "reused", "source": _relative(path), "sha256": digest(path),
            "trace_sha256": row["trace_sha256"]}


def _execute(phase: str, scenario: str, seed: int, arm: str) -> dict:
    output = _source(phase, scenario, seed, arm)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".log")
    failure_path = output.with_suffix(".failure.json")
    solution, cluster = v3_layout(scenario, ROOT)
    expected = {"scenario": scenario, "seed": seed,
                "offered_tokens_per_s": LOADS[scenario],
                "duration_s": 60 if phase == "smoke" else 1800, "warmup_s": 0,
                "solution_sha256": digest(solution), "sim_cluster_sha256": digest(cluster),
                "physical_cluster_sha256": digest(_physical(scenario)),
                "evaluation_protocol": "fixed_window_no_tail_drain",
                "m3_state_variant": arm}
    if output.is_file():
        row = _read(output)
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Existing M3 window has a different identity: {output}")
        return {"status": "passed", "source": _relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "existing": True}
    try:
        with log_path.open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            row = fixed_window_run(
                scenario, "queue_dag", LOADS[scenario], expected["duration_s"], 0,
                seed, solution, cluster, physical_cluster=_physical(scenario),
                scheduler_factory=VARIANTS[arm], compact=True,
                record_query_samples=True, profile_scheduler=phase == "smoke")
            row.update(expected)
            row["adapter_sha256"] = digest(HERE / "m3_state.py")
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
        failure = {"status": "failed", "error_type": type(error).__name__,
                   "error": str(error), "scenario": scenario, "seed": seed,
                   "variant": arm, "last_progress": progress[-1] if progress else None,
                   "log": _relative(log_path), "expected": expected}
        _write(failure_path, failure)
        return {**failure, "failure_source": _relative(failure_path),
                "failure_sha256": digest(failure_path)}


def run_phase(phase: str, workers: int) -> dict:
    audit()
    seeds = (100,) if phase == "smoke" else SEEDS
    index = {"phase": phase, "protocol": {"loads": LOADS, "seeds": list(seeds),
             "duration_s": 60 if phase == "smoke" else 1800,
             "warmup_s": 0, "tail_drain": False},
             "adapter_sha256": digest(HERE / "m3_state.py"), "jobs": {}}
    jobs = []
    for scenario in SCENARIOS:
        for seed in seeds:
            for arm in ARMS:
                key = f"{scenario}/seed{seed}/{arm}"
                if phase == "formal" and arm in ("static", "full"):
                    try:
                        index["jobs"][key] = _reuse(scenario, seed, arm)
                        continue
                    except Exception as error:
                        index["jobs"][key] = {"status": "reuse_rejected", "reason": str(error)}
                if arm == "static":
                    # Smoke parity for static DAG is already in v3_core_ablations.
                    if phase == "smoke":
                        continue
                    raise ValueError("Static formal reuse failed; rerun through v3_core_ablations")
                jobs.append((scenario, seed, arm))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_execute, phase, *item): item for item in jobs}
        for future in as_completed(futures):
            scenario, seed, arm = futures[future]
            key = f"{scenario}/seed{seed}/{arm}"
            try:
                index["jobs"][key] = future.result()
            except Exception as error:
                index["jobs"][key] = {"status": "runner_failed", "error": str(error)}
            _write(HERE / f"m3_{phase}_index.json", index)
            print(f"{key}: {index['jobs'][key]['status']}", flush=True)
    _write(HERE / f"m3_{phase}_index.json", index)
    return index


def report() -> dict:
    index = _read(HERE / "m3_formal_index.json")
    result = {"protocol": index["protocol"], "scenarios": {}}
    lines = ["# V3 M3 实时状态验证", "",
             "全部方法使用冻结 V3 布局、M1 合法 DAG、固定 Decode 路径及相同传输合并。", "",
             "| 拓扑 | 种子 | 方法 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 |",
             "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for scenario in SCENARIOS:
        seeds = {}
        for seed in SEEDS:
            rows = {}
            for arm in ARMS:
                item = index["jobs"].get(f"{scenario}/seed{seed}/{arm}")
                if not item or item["status"] not in ("passed", "reused"):
                    lines.append(f"| {scenario} | {seed} | {arm} | — | — | — | — | — |")
                    continue
                path = ROOT / item["source"]
                if digest(path) != item["sha256"]:
                    raise ValueError(f"M3 raw result hash changed: {path}")
                row = _read(path)
                if row["trace_sha256"] != item["trace_sha256"]:
                    raise ValueError(f"M3 trace hash changed: {path}")
                rows[arm] = row
                lines.append(f"| {scenario} | {seed} | {arm} | "
                             f"{row['output_throughput_tokens_per_s']:.3f} | "
                             f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                             f"{row['completion_fraction']:.3f} | {row['backlog_at_window_end']} |")
            if rows:
                reference = next(iter(rows.values()))
                for arm, row in rows.items():
                    for key in MATCH_FIELDS:
                        left = row.get(key, 1 if key == "query_samples_schema" else None)
                        right = reference.get(key, 1 if key == "query_samples_schema" else None)
                        if left != right:
                            raise ValueError(f"Unpaired M3 run: {scenario}/{seed}/{arm}/{key}")
                    common_cohort(row, reference)
            effects = {}
            for left, right in (("static", "queue_only"), ("queue_only", "observed_eft"),
                                ("observed_eft", "full_no_session"),
                                ("full_no_session", "full"), ("full_no_link", "full")):
                if left in rows and right in rows:
                    effects[f"{left}->{right}"] = {
                        "delta": {key: rows[right][key] - rows[left][key] for key in METRICS},
                        "common_completed": common_completed(rows[left], rows[right])}
            seeds[str(seed)] = {"sources": {arm: index["jobs"][f"{scenario}/seed{seed}/{arm}"]
                                            for arm in rows},
                                "metrics": {arm: {key: row[key] for key in METRICS}
                                            for arm, row in rows.items()},
                                "pending": {arm: pending(row) for arm, row in rows.items()},
                                "effects": effects}
        result["scenarios"][scenario] = {"seeds": seeds}
    lines.extend(["", "## 三种子均值与短窗口选路开销", "",
                  "| 拓扑 | 方法 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 路由 P95 µs |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for scenario in SCENARIOS:
        for arm in ARMS:
            series = [result["scenarios"][scenario]["seeds"][str(seed)]["metrics"].get(arm)
                      for seed in SEEDS]
            if any(row is None for row in series):
                continue
            smoke_path = _source("smoke", scenario, 100, arm)
            route_p95 = None
            if smoke_path.is_file():
                route_p95 = (_read(smoke_path).get("scheduler_call_profile", {})
                             .get("_route", {}).get("p95_us"))
            values = " | ".join(f"{mean(row[key] for row in series):.3f}"
                                for key in METRICS)
            overhead = f"{route_p95:.1f}" if route_p95 is not None else "—"
            lines.append(f"| {scenario} | {arm} | {values} | {overhead} |")
    lines.extend(["", "相邻方法仅改变指定的动态状态项；三个种子只描述波动。",
                  "比较 P95 时同时查看完成率、积压与共同完成请求。", ""])
    _write(HERE / "m3_formal_analysis.json", result)
    (HERE / "m3_formal_report.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("smoke", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "report":
        report()
    else:
        run_phase(args.phase, args.workers)


if __name__ == "__main__":
    main()
