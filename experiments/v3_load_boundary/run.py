"""Paired fixed-window V3/Helix load scan with strict provenance checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from baselines import helix
from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.fixed_window import run as fixed_window_run
from benchmarks.layout import scenario as benchmark_scenario
from experiments.m2_multistage_candidate.analysis import common_completed, pending
from experiments.v3_release.verify import digest, snapshot
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps import v3_method


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOADS = {"single": (100, 200, 350, 500, 700, 900),
         "multi": (50, 100, 160, 240, 320, 400)}
METHODS = ("rcaps_v3", "helix")
SEEDS = (0, 1, 2)
DURATION = 1800
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    part.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def physical(scenario: str) -> Path:
    return benchmark_scenario(scenario)[0]


def layout(scenario: str, method: str) -> tuple[Path, Path]:
    return (v3_method if method == "rcaps_v3" else helix).layout(scenario, ROOT)


def source(scenario: str, load: int, seed: int, method: str) -> Path:
    return HERE / "runs" / scenario / f"load{load}" / f"seed{seed}" / f"{method}.json"


def identity(scenario: str, load: int, seed: int, method: str) -> dict:
    solution, cluster = layout(scenario, method)
    return {"scenario": scenario, "method_name": method, "seed": seed,
            "offered_tokens_per_s": float(load), "duration_s": DURATION,
            "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
            "query_samples_schema": 1,
            "solution_sha256": digest(solution),
            "sim_cluster_sha256": digest(cluster),
            "physical_sha256": digest(physical(scenario)),
            "benchmark_sha256": digest(ROOT / "benchmarks/fixed_window.py")}


def _historical(scenario: str, load: int, seed: int, method: str) -> Path | None:
    if method == "rcaps_v3" and load == {"single": 700, "multi": 320}[scenario]:
        return ROOT / "benchmarks/runs" / scenario / f"seed{seed}" / "rcaps_v3.json"
    if load == {"single": 350, "multi": 160}[scenario]:
        return (ROOT / "experiments/v3_four_method_comparison/runs" /
                scenario / f"seed{seed}" / f"{method}.json")
    if method == "helix" and load == {"single": 700, "multi": 320}[scenario]:
        return ROOT / "benchmarks/runs" / scenario / f"seed{seed}" / "helix.json"
    return None


def reuse(scenario: str, load: int, seed: int, method: str) -> dict | None:
    path = _historical(scenario, load, seed, method)
    if path is None or not path.is_file():
        return None
    expected = identity(scenario, load, seed, method)
    row = read_json(path)
    checks = ("scenario", "seed", "offered_tokens_per_s", "duration_s",
              "warmup_s", "evaluation_protocol", "query_samples_schema",
              "solution_sha256", "sim_cluster_sha256")
    if any(row.get(key) != expected[key] for key in checks):
        return None
    # Historical Helix and low-load four-method records omit this field.
    # They are rerun rather than silently asserting the physical input.
    if row.get("physical_sha256") != expected["physical_sha256"]:
        return None
    if method == "rcaps_v3":
        if row.get("release_manifest_sha256") != digest(
                ROOT / "experiments/v3_release/manifest.json"):
            return None
    if len(row.get("query_samples", {})) != row.get("arrivals"):
        return None
    return {"status": "reused", "source": relative(path), "sha256": digest(path),
            "trace_sha256": row["trace_sha256"], "identity": expected}


def execute(scenario: str, load: int, seed: int, method: str) -> dict:
    output = source(scenario, load, seed, method)
    output.parent.mkdir(parents=True, exist_ok=True)
    expected = identity(scenario, load, seed, method)
    if output.is_file():
        row = read_json(output)
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Existing result has another identity: {output}")
        return {"status": "passed", "source": relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "identity": expected, "existing": True}
    log_path = output.with_suffix(".log")
    failure_path = output.with_suffix(".failure.json")
    import contextlib
    try:
        solution, cluster = layout(scenario, method)
        with log_path.open("w", encoding="utf-8") as log, \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            row = fixed_window_run(
                scenario, "queue_dag" if method == "rcaps_v3" else "helix",
                float(load), DURATION, 0, seed, solution, cluster,
                physical_cluster=physical(scenario),
                scheduler_factory=(GraphModeledQueueAwareDagScheduler
                                   if method == "rcaps_v3" else None),
                compact=True, record_query_samples=True,
                profile_resources=(method == "rcaps_v3"))
            row.update(expected)
            row["system"] = method
            write_json(output, row)
        failure_path.unlink(missing_ok=True)
        return {"status": "passed", "source": relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "identity": expected, "log": relative(log_path)}
    except Exception as error:
        with log_path.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        failure = {"status": "failed", "identity": expected,
                   "error": repr(error), "log": relative(log_path)}
        write_json(failure_path, failure)
        return {**failure, "failure_source": relative(failure_path),
                "failure_sha256": digest(failure_path)}


def audit() -> dict:
    if snapshot() != read_json(ROOT / "experiments/v3_release/manifest.json"):
        raise ValueError("Frozen V3 release manifest drifted")
    result = {"protocol": {"loads": LOADS, "seeds": SEEDS, "duration_s": DURATION,
                           "warmup_s": 0, "tail_drain": False},
              "physical_sha256": {name: digest(physical(name)) for name in LOADS},
              "layouts": {name: {method: {"solution_sha256": digest(layout(name, method)[0]),
                                            "sim_cluster_sha256": digest(layout(name, method)[1])}
                                 for method in METHODS} for name in LOADS},
              "benchmark_sha256": digest(ROOT / "benchmarks/fixed_window.py")}
    write_json(HERE / "audit.json", result)
    return result


def run(workers: int) -> None:
    audit()
    index = {"audit_sha256": digest(HERE / "audit.json"), "jobs": {}}
    jobs = []
    for scenario, loads in LOADS.items():
        for load in loads:
            for seed in SEEDS:
                for method in METHODS:
                    key = f"{scenario}/{load}/seed{seed}/{method}"
                    reused = reuse(scenario, load, seed, method)
                    if reused:
                        index["jobs"][key] = reused
                    else:
                        jobs.append((scenario, load, seed, method))
    write_json(HERE / "index.json", index)
    print(f"reused={len(index['jobs'])}, to_run={len(jobs)}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(execute, *job): job for job in jobs}
        for future in as_completed(futures):
            scenario, load, seed, method = futures[future]
            key = f"{scenario}/{load}/seed{seed}/{method}"
            try:
                item = future.result()
            except Exception as error:
                item = {"status": "runner_failed", "error": repr(error)}
            index["jobs"][key] = item
            write_json(HERE / "index.json", index)
            print(f"{key}: {item['status']}", flush=True)


def report() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    index = read_json(HERE / "index.json")
    if digest(HERE / "audit.json") != index["audit_sha256"]:
        raise ValueError("Audit file changed after the scan started")
    data = {"loads": {}, "protocol": read_json(HERE / "audit.json")["protocol"]}
    lines = ["# V3–Helix 负载边界", "",
             "offered 为输入加目标输出 token/s；吞吐仅统计窗口内实际输出 token/s。",
             "不同负载点不得把输出吞吐直接相除解释为完成比例。", "",
             "| 拓扑 | 负载 | 方法 | 实际输入到达 | 目标输出到达 | 输出吞吐 | P95 TTFT | P95 TPOT | 完成率 | 末端积压 | 未完成等待 P95 |",
             "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for scenario, loads in LOADS.items():
        data["loads"][scenario] = {}
        for load in loads:
            rows = {}
            for method in METHODS:
                values = []
                for seed in SEEDS:
                    key = f"{scenario}/{load}/seed{seed}/{method}"
                    item = index["jobs"].get(key)
                    if not item or item["status"] not in ("passed", "reused"):
                        continue
                    path = ROOT / item["source"]
                    if digest(path) != item["sha256"]:
                        raise ValueError(f"Result hash changed: {path}")
                    row = read_json(path)
                    expected = identity(scenario, load, seed, method)
                    for field in ("scenario", "seed", "offered_tokens_per_s", "duration_s",
                                  "warmup_s", "evaluation_protocol", "solution_sha256",
                                  "sim_cluster_sha256", "physical_sha256"):
                        if row.get(field) != expected[field]:
                            raise ValueError(f"Record identity differs: {path}, {field}")
                    samples = row.get("query_samples", {})
                    if len(samples) != row["arrivals"]:
                        raise ValueError(f"Incomplete per-request samples: {path}")
                    target = sum(q["output_tokens"] for q in samples.values()) / DURATION
                    offered_input = sum(q["input_tokens"] for q in samples.values()) / DURATION
                    values.append({"seed": seed, "source": relative(path), "sha256": item["sha256"],
                                   "trace_sha256": row["trace_sha256"],
                                   "actual_input_offered": offered_input,
                                   "target_output_offered": target,
                                   "pending": pending(row),
                                   **{metric: row[metric] for metric in METRICS},
                                   "row": row})
                rows[method] = values
                if len(values) == len(SEEDS):
                    means = {metric: float(np.mean([v[metric] for v in values]))
                             for metric in METRICS}
                    input_rate = float(np.mean([v["actual_input_offered"] for v in values]))
                    output_rate = float(np.mean([v["target_output_offered"] for v in values]))
                    waiting = [v["pending"]["p95_s"] for v in values
                               if v["pending"]["p95_s"] is not None]
                    waiting_text = f"{np.mean(waiting):.3f}" if waiting else "—"
                    lines.append(f"| {scenario} | {load} | {method} | "
                                 f"{input_rate:.3f} | {output_rate:.3f} | "
                                 f"{means[METRICS[0]]:.3f} | {means[METRICS[1]]:.3f} | "
                                 f"{means[METRICS[2]]:.3f} | {means[METRICS[3]]:.3f} | "
                                 f"{means[METRICS[4]]:.1f} | {waiting_text} |")
                else:
                    lines.append(f"| {scenario} | {load} | {method} | 不完整 | — | — | — | — | — | — | — |")
            pairs = {}
            for seed in SEEDS:
                left = next((v for v in rows["rcaps_v3"] if v["seed"] == seed), None)
                right = next((v for v in rows["helix"] if v["seed"] == seed), None)
                if left is None or right is None:
                    continue
                a, b = left["row"], right["row"]
                for field in MATCH_FIELDS:
                    if a.get(field, 1 if field == "query_samples_schema" else None) != b.get(
                            field, 1 if field == "query_samples_schema" else None):
                        raise ValueError(f"Unpaired run: {scenario}/{load}/seed{seed}/{field}")
                common_cohort(a, b)
                pairs[str(seed)] = {"delta": {metric: a[metric] - b[metric] for metric in METRICS},
                                    "common_completed": common_completed(a, b)}
            data["loads"][scenario][str(load)] = {
                "methods": {method: [{k: v for k, v in item.items() if k != "row"}
                                     for item in values] for method, values in rows.items()},
                "paired": pairs}
    failures = {key: value for key, value in index["jobs"].items()
                if value["status"] not in ("passed", "reused")}
    data["failures"] = failures
    if failures:
        lines += ["", "## 未完成窗口", "",
                  "失败窗口保留原始异常，不填补 1800 秒性能指标。", "",
                  "| 窗口 | 状态 | 错误 | 日志 |",
                  "| --- | --- | --- | --- |"]
        for label, item in sorted(failures.items()):
            lines.append(f"| {label} | {item['status']} | "
                         f"{item.get('error', '—')} | {item.get('log', '—')} |")
    write_json(HERE / "analysis.json", data)
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7), sharex="row")
    labels = {"rcaps_v3": "RCAPS V3", "helix": "Helix ILP"}
    keys = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")
    titles = ("Output throughput (token/s)", "P95 TTFT (s)", "P95 TPOT (s)")
    for row_idx, (scenario, loads) in enumerate(LOADS.items()):
        for col_idx, (key, title) in enumerate(zip(keys, titles)):
            ax = axes[row_idx, col_idx]
            for method in METHODS:
                xs, ys, errs = [], [], []
                for load in loads:
                    values = data["loads"][scenario][str(load)]["methods"][method]
                    if len(values) != len(SEEDS):
                        continue
                    xs.append(load)
                    measurements = [value[key] for value in values]
                    ys.append(float(np.mean(measurements)))
                    errs.append(float(np.std(measurements, ddof=1)))
                ax.errorbar(xs, ys, yerr=errs, marker="o", capsize=3, label=labels[method])
            ax.set_title(f"{scenario}: {title}")
            ax.set_xlabel("Offered input + target-output token/s")
            ax.grid(alpha=.25)
            if row_idx == 0 and col_idx == 0:
                ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / "load_curve.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for scenario, axis in zip(LOADS, axes):
        axis2 = axis.twinx()
        for method in METHODS:
            xs, completion, backlog = [], [], []
            for load in LOADS[scenario]:
                values = data["loads"][scenario][str(load)]["methods"][method]
                if len(values) != len(SEEDS):
                    continue
                xs.append(load)
                completion.append(float(np.mean([v["completion_fraction"] for v in values])))
                backlog.append(float(np.mean([v["backlog_at_window_end"] for v in values])))
            axis.plot(xs, completion, marker="o", label=labels[method])
            axis.set_title(f"{scenario}: completion fraction")
            axis.set_xlabel("Offered input + target-output token/s")
            axis.set_ylim(0, 1.02)
            axis.grid(alpha=.25)
            if scenario == "single":
                axis.legend()
            axis2.plot(xs, backlog, linestyle="--", alpha=.5,
                       color=("C0" if method == "rcaps_v3" else "C1"))
            axis2.set_ylabel("Window-end backlog (dashed)")
    fig.tight_layout()
    fig.savefig(HERE / "completion_backlog.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("audit", "run", "report"))
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.phase == "audit":
        audit()
    elif args.phase == "run":
        run(args.workers)
    else:
        report()


if __name__ == "__main__":
    main()
