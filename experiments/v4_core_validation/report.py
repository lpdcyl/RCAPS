"""One terminal-only reconciliation of the core supplement; never rerun jobs."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from experiments.v4_formal.run import ROOT, read, write, digest, stamp
from experiments.v4_validation.summarize import check, mechanism
from .run import validate, MANIFEST

HERE = Path(__file__).resolve().parent
INDEX = HERE / "execution/index.json"
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "backlog_at_window_end", "gpu_seconds_per_output_token",
           "total_gpu_busy_s", "last_completion_s", "paths", "token_weighted_decode_batch",
           "singleton_execution_fraction", "decode_gpu_busy_s", "prompt_network_wait_s",
           "decode_network_wait_s", "boundary_cost_hold_s")


def identity(row):
    return [(round(q["arrival_s"], 9), q["input_tokens"], q["output_tokens"])
            for q in sorted(row["query_samples"].values(), key=lambda q: q["arrival_s"])]


def metrics(row):
    result = {k: row.get(k) for k in METRICS}
    profile = mechanism(row)
    result.update({k: profile[k] for k in METRICS if k in profile})
    result.update(total_gpu_busy_s=row["cohort"]["total_gpu_busy_s"],
                  last_completion_s=row["cohort"]["last_completion_s"],
                  boundary_cost_hold_s=row["phase_link_profile"].get(
                      "boundary_cost_accounting", {}).get("hold_s", 0))
    return result


def summary(values):
    if len(values) != 3 or any(v is None or not math.isfinite(v) for v in values):
        return None
    return dict(n=3, mean=mean(values), sample_std=stdev(values), values=values)


def fmt(value, digits=3):
    return "缺失" if value is None else f"{value:.{digits}f}"


def main():
    if (HERE / "results.json").exists():
        raise RuntimeError("Final synthesis already exists; read it instead of repeating automatically")
    registration = read(HERE / "report_registration.json")
    if registration["report_sha256"] != digest(Path(__file__)):
        raise RuntimeError("Report source differs from its registered reconciliation hash")
    index = read(INDEX)
    if index["status"] != "completed" or any(
            e["status"] in {"pending", "running", "starting"} for e in index["jobs"].values()):
        raise RuntimeError("Queue is not terminal; no partial-data synthesis")
    checks, problems = [], []

    def verify(condition, name, detail=None):
        record = dict(check=name, passed=bool(condition), detail=detail)
        checks.append(record)
        if not condition:
            problems.append(record)
        return bool(condition)

    frozen = validate()
    verify(index["manifest_sha256"] == digest(MANIFEST), "index_manifest_identity")
    for name in ("launch_amendment.json", "execution_amendment.json"):
        amendment = read(HERE / name)
        verify(amendment["manifest_sha256"] == digest(MANIFEST), "amendment_manifest", name)
        for path, expected in amendment["sources_sha256"].items():
            verify((ROOT / path).exists() and digest(ROOT / path) == expected, "amendment_source_hash", path)

    def inspect(row, label):
        start = len(problems)
        verify(not check(row), "metric_and_resource_checks", dict(source=label, errors=check(row)))
        traces = identity(row)
        computed = hashlib.sha256(json.dumps(traces, separators=(",", ":")).encode()).hexdigest()
        verify(computed == row["trace_sha256"], "reconstruct_arrival_trace", label)
        verify(len(traces) == row["arrivals"], "all_request_identities_retained", label)
        verify(sum(x[2] for x in traces) == row["cohort"]["target_output_tokens"],
               "requested_output_tokens", label)
        for name in ("ttft", "tpot"):
            samples = [q[name + "_s"] for q in row["query_samples"].values()
                       if q.get(name + "_s") is not None]
            verify(bool(samples) and math.isclose(float(np.percentile(samples, 95)),
                row[name + "_p95_s"], rel_tol=1e-9, abs_tol=1e-8), "request_percentile", [label, name])
        complete = sum(q["completed"] for q in row["query_samples"].values())
        verify(math.isclose(complete / row["arrivals"], row["completion_fraction"], abs_tol=1e-10),
               "request_completion_fraction", label)
        verify(row["arrivals"] - complete == row["backlog_at_window_end"], "request_backlog", label)
        cohort = row["cohort"]
        verify(cohort["completed"] == (cohort["right_censored_queries"] == 0), "censoring_identity", label)
        if cohort["completed"]:
            verify(cohort["produced_output_tokens"] == cohort["target_output_tokens"],
                   "complete_cohort_output_conservation", label)
        verify(math.isclose(sum(row["gpu_busy_fraction"].values()) * row["duration_s"],
            cohort["total_gpu_busy_s"], rel_tol=1e-9), "total_gpu_work", label)
        verify(math.isclose(sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"],
            row["gpu_seconds_per_output_token"], rel_tol=1e-9), "work_per_output_token", label)
        return len(problems) == start

    refs, accepted, windows, failures, missing, rejected, intervals = {}, {}, [], [], [], [], []
    for ref in frozen["references"]:
        path = ROOT / ref["path"]
        if not verify(digest(path) == ref["sha256"], "reference_hash", ref["path"]):
            continue
        row = read(path)
        if not inspect(row, ref["path"]):
            rejected.append(ref["path"])
            continue
        key = (ref["scenario"], ref["load"], ref["cell"], ref["seed"])
        refs[key] = row
        windows.append(dict(kind="reused_reference", experiment="reference", scenario=ref["scenario"],
            load=ref["load"], cell=ref["cell"], seed=ref["seed"], source=ref["path"], sha256=ref["sha256"],
            metrics=metrics(row), cohort=row["cohort"], mechanism=mechanism(row),
            trace_sha256=row["trace_sha256"], audit_passed=True))

    for job in frozen["jobs"]:
        key = job["key"]
        entry = index["jobs"].get(key)
        directory = HERE / "execution/runs" / key
        if entry is None:
            missing.append(key)
            continue
        if entry.get("pid") and entry.get("started_at") and entry.get("finished_at"):
            intervals += [(datetime.fromisoformat(entry["started_at"]), 1),
                          (datetime.fromisoformat(entry["finished_at"]), -1)]
        if entry["status"] != "completed":
            record = dict(job=job, index_entry=entry, files={})
            for name in ("worker.log", "failure.json", "dispatch_failure.json", "worker_started.json"):
                path = directory / name
                if path.exists():
                    record["files"][path.relative_to(ROOT).as_posix()] = digest(path)
            failure = directory / "failure.json"
            dispatch = directory / "dispatch_failure.json"
            verify(failure.exists() or dispatch.exists(), "retained_failure_record", key)
            started_file = directory / "worker_started.json"
            if entry.get("pid") is not None:
                verify(started_file.exists(), "failed_worker_lifecycle_record", key)
                if started_file.exists():
                    started_record = read(started_file)
                    verify(started_record.get("pid") == entry["pid"] and math.isclose(
                        started_record.get("create_time", -1), entry.get("create_time", -2),
                        rel_tol=0, abs_tol=1e-6), "failed_worker_pid_creation_identity", key)
            if failure.exists():
                verify(digest(failure) == entry.get("failure_sha256"), "failure_hash", key)
                record["failure"] = read(failure)
                worker_log = directory / "worker.log"
                if worker_log.exists():
                    log_text = worker_log.read_text(encoding="utf-8", errors="replace")
                    record["failure"]["native_crash_signature"] = (
                        "Windows access violation" if "Windows fatal exception: access violation" in log_text
                        else "not identified as access violation")
            elif dispatch.exists():
                verify(digest(dispatch) == entry.get("dispatch_failure_sha256"), "dispatch_hash", key)
                record["failure"] = read(dispatch)
            failures.append(record)
            continue
        path = directory / "result.json"
        if not path.exists():
            missing.append(key)
            verify(False, "completed_record_missing_result", key)
            continue
        row, before = read(path), len(problems)
        started_file, done_file = directory / "worker_started.json", directory / "worker_done.json"
        verify(started_file.exists() and done_file.exists(), "worker_lifecycle_records", key)
        if started_file.exists():
            started_record = read(started_file)
            verify(started_record.get("pid") == entry.get("pid") and math.isclose(
                started_record.get("create_time", -1), entry.get("create_time", -2),
                rel_tol=0, abs_tol=1e-6), "worker_pid_creation_identity", key)
        if done_file.exists():
            done_record = read(done_file)
            verify(done_record.get("status") == "completed" and
                   done_record.get("result_sha256") == digest(path), "worker_completion_marker", key)
        verify(digest(path) == entry["result_sha256"], "result_hash", key)
        verify(row["manifest_sha256"] == digest(MANIFEST), "result_manifest", key)
        verify(row["environment"] == frozen["environment"], "result_environment", key)
        verify(row["job"] == job, "registered_job_identity", key)
        inspect(row, key)
        full = refs.get((job["scenario"], job["load"], "v4", job["seed"]))
        if full is None:
            verify(False, "matching_complete_reference", key)
        else:
            for field in ("scenario", "solution", "sim_cluster", "physical_cluster_sha256", "seed",
                          "duration_s", "warmup_s", "offered_tokens_per_s", "arrivals", "trace_sha256",
                          "validation_protocol"):
                verify(row[field] == full[field], "paired_common_configuration", [key, field])
            verify(identity(row) == identity(full), "paired_request_identity", key)
            for field in ("mode", "threshold_Bps", "allowed_edges", "allowed_edge_count"):
                verify(row["admission"][field] == full["admission"][field], "fixed_admission_graph", [key, field])
        requested_routing = "no_session" if job["experiment"] == "session" else "live"
        verify(row["admission"]["routing_state"] == requested_routing, "routing_control_applied", key)
        chunk = row["phase_link_profile"]["chunking"]
        cost = chunk["boundary_cost"]
        verify(cost["seconds_per_intermediate_boundary"] == job["boundary_cost_s"], "registered_boundary_cost", key)
        verify(chunk["chunk_bytes"] == 4_194_304 and chunk["scope"] == "slow"
               and chunk["threshold_Bps"] == 50_000_000, "fixed_chunk_configuration", key)
        if job["boundary_cost_s"] > 0:
            verify(cost["boundaries_charged"] > 0 and cost["boundaries_charged"] ==
                cost["boundaries_released"] + cost["holding_at_end"], "cost_event_conservation", key)
            verify(cost["boundaries_released"] == chunk["paused_chunks"], "one_cost_per_intermediate_release", key)
            if row["cohort"]["completed"]:
                verify(math.isclose(cost["nominal_total_added_hold_s"],
                    row["phase_link_profile"]["boundary_cost_accounting"]["hold_s"],
                    rel_tol=1e-7, abs_tol=1e-6), "completed_no_byte_hold_accounting", key)
        good = len(problems) == before
        if not good:
            rejected.append(key)
        else:
            accepted[key] = row
        windows.append(dict(kind="new_execution", experiment=job["experiment"], scenario=job["scenario"],
            load=job["load"], cell=job["cell"], seed=job["seed"], key=key,
            source=path.relative_to(ROOT).as_posix(), sha256=digest(path), metrics=metrics(row),
            cohort=row["cohort"], mechanism=mechanism(row), audit_passed=good,
            trace_sha256=row["trace_sha256"], cost=cost))

    count, peak = 0, 0
    for _, change in sorted(intervals, key=lambda x: (x[0], x[1])):
        count += change
        peak = max(peak, count)
    verify(peak <= 2 and count == 0, "maximum_two_registered_simulation_workers", peak)
    verify(set(index["jobs"]) == {j["key"] for j in frozen["jobs"]}, "unique_registered_attempts")

    groups = defaultdict(list)
    for job in frozen["jobs"]:
        groups[job["experiment"], job["scenario"], job["load"], job["cell"]].append(job)
    paired = []
    for (experiment, scenario, load, cell), js in groups.items():
        comparators = ["v4"] if experiment == "session" else ["v4", "spatial"]
        for comparator in comparators:
            records = []
            for job in sorted(js, key=lambda x: x["seed"]):
                tested = accepted.get(job["key"])
                ref = refs.get((scenario, load, comparator, job["seed"]))
                if tested is None or ref is None:
                    continue
                if not verify(identity(tested) == identity(ref), "comparison_pair_identity",
                              [job["key"], comparator]):
                    continue
                numerator, denominator = (ref, tested) if experiment == "session" else (tested, ref)
                a, b = metrics(numerator), metrics(denominator)
                relative, absolute = {}, {}
                for m in METRICS:
                    absolute[m] = a[m] - b[m] if a[m] is not None and b[m] is not None else None
                    relative[m] = 100 * (a[m] / b[m] - 1) if a[m] is not None and b[m] not in (None, 0) else None
                records.append(dict(seed=job["seed"], numerator=a, denominator=b,
                    relative_change_percent=relative, absolute_change=absolute,
                    both_cohorts_complete=tested["cohort"]["completed"] and ref["cohort"]["completed"]))
            complete = len(records) == 3
            paired.append(dict(experiment=experiment, scenario=scenario, load=load, cell=cell,
                comparator=comparator, direction="RCAPS/no_session-1" if experiment == "session" else f"{cell}/{comparator}-1",
                seeds=records, complete_three_seed=complete,
                same_completed_work=complete and all(r["both_cohorts_complete"] for r in records),
                aggregate={m: summary([r["relative_change_percent"][m] for r in records]) for m in METRICS}))

    coverage = dict(Counter(e["status"] for e in index["jobs"].values()))
    prior = read(HERE / "index.json")
    final_status = ("audit_issues" if problems or missing else
                    "verified_with_failed_windows" if failures else "verified")
    result = dict(finished_at=stamp(), status=final_status,
        manifest_sha256=digest(MANIFEST), execution_index_sha256=digest(INDEX),
        report_source_sha256=digest(Path(__file__)), registered_windows=len(frozen["jobs"]),
        execution_status=coverage, accepted_windows=len(accepted), missing=missing, rejected=rejected,
        failures=failures, right_censored=[w["source"] for w in windows
            if w["kind"] == "new_execution" and not w["cohort"]["completed"]],
        prior_engineering_dispatch_failures=dict(count=len(prior["jobs"]),
            started_workers=0, index_sha256=digest(HERE / "index.json"),
            note="Retained pre-simulation dispatch failures; separate from new execution outcomes"),
        engineering=read(HERE / "preflight.json"), hardware_calibration_completed=False,
        windows=windows, paired=paired, checks=checks, problems=problems,
        limits=["Profile-driven CPU simulation, not real distributed engine",
            "Boundary costs are hypotheses, not measured software/communication overhead",
            "5400-second denominator; do not mix throughput with 1800-second main table",
            "Three seeds do not establish statistical significance",
            "Full-method novelty and cross-load superiority to all external systems are unproven"])
    write(HERE / "results.json", result)
    columns = ["kind", "experiment", "scenario", "load", "cell", "seed", "source", "sha256", "audit_passed"]
    with (HERE / "individual.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns + list(METRICS) + ["cohort_complete", "right_censored_queries"])
        writer.writeheader()
        for w in windows:
            writer.writerow(dict({k: w.get(k) for k in columns}, **w["metrics"],
                cohort_complete=w["cohort"]["completed"], right_censored_queries=w["cohort"]["right_censored_queries"]))
    lines = ["# RCAPS 收紧主线后的核心补证结果", "",
        f"核验时间：{result['finished_at']}。本报告只包含已登记的会话项独立对照和分块额外占用成本敏感性。", "",
        "## 1. 执行与证据身份", "",
        f"登记 {len(frozen['jobs'])} 个窗口；执行状态 {json.dumps(coverage, ensure_ascii=False)}；"
        f"原始核验接受 {len(accepted)} 个；缺失 {len(missing)} 个；核验排除 {len(rejected)} 个；"
        f"成功记录中仍有请求右删失的窗口 {len(result['right_censored'])} 个。", "",
        "此外，15 次进入仿真之前的派发失败单独留档；修正的是启动适配器，不改变实验条件。原失败 index 与日志未覆盖。", "",
        f"综合核验 {len(checks)} 项，其中未通过 {len(problems)} 项；已登记 worker 记录的峰值并发为 {peak}。", "",
        "同一 1800 秒到达前缀，观察至 5400 秒。只有请求与输出目标一致且双方全部完成时，才标作相同完成工作量比较。", "",
        "## 2. 逐种子配对结果", "",
        "表中均为三个种子分别计算相对变化后的均值 ± 样本标准差（%）。负数表示该数值下降，不自动代表所有指标改善；没有完整三种子时不填组均值。", "",
        "|实验与场景|比值方向|完整种子|TPOT P95|TTFT P95|GPU 工作/token|同完成工作量|",
        "|---|---|---:|---:|---:|---:|---|"]
    for p in paired:
        cells = []
        for m in ("tpot_p95_s", "ttft_p95_s", "gpu_seconds_per_output_token"):
            a = p["aggregate"][m]
            cells.append("不完整" if a is None else f"{a['mean']:+.2f} ± {a['sample_std']:.2f}")
        lines.append(f"|{p['scenario']} {p['load']} / {p['cell']}|{p['direction']}|{len(p['seeds'])}/3|"
                     + "|".join(cells) + f"|{'是' if p['same_completed_work'] else '否'}|")
    lines += ["", "`v4` 在原始参照中表示完整 RCAPS；`spatial` 表示保留空间准入、关闭传输分块。正式正文使用机制名称。", "",
        "全部单值、完成率、积压、吞吐、最后完成时刻和机制统计见 individual.csv 与 results.json；不能仅摘取改善的指标。", "",
        "## 3. 主线解释与边界", "",
        "会话对照仅移除活跃会话的持续 Decode 服务代价，保留实时等待、放置、路径空间、KV 缓存与会话绑定。其结果只能解释这一项在完整系统中的条件作用。", "",
        "分块成本按每个实际发生的中间块边界计费：在载荷字节发送结束后继续持有原链路及收发 NIC 额度，分别持续 1、10 或 100 ms，再让出资源。该区间不计作新增字节。它不代表全局 CPU 排队成本，也不等于实测通信开销。", ""]
    crossings = []
    for p in paired:
        if p["experiment"] == "boundary_cost" and p["comparator"] == "spatial" and p["complete_three_seed"]:
            a = p["aggregate"]["tpot_p95_s"]
            if a is not None:
                ms = int(p["cell"].split("_")[1][:-2])
                signs = [fmt(r["relative_change_percent"]["tpot_p95_s"], 2) for r in p["seeds"]]
                crossings.append((ms, a["mean"]))
                lines.append(f"- {ms} ms/中间边界：相对不分块，TPOT P95 的逐种子变化为 {'、'.join(signs)}%；三种子均值 {a['mean']:+.2f}%。")
    if len(crossings) == 3 and all(v < 0 for _, v in crossings):
        lines += ["", "三个已测试正成本点的均值仍低于不分块条件；只能说该离散测试范围未观察到均值交叉，不能外推更高成本阈值或保证区间内单调。"]
    elif crossings:
        lines += ["", "仅报告上列离散成本点的观测；不把单点或三种子均值差异解释为显著阈值，也不假设成本—性能关系单调。"]
    else:
        lines += ["尚无可完整配对的三种子成本组，不能判断成本边界。"]
    lines += ["", "机制统计报告实际路径数、Decode batch、GPU 忙碌时间与已结算网络等待；窗口边界未结算量单独保留。上述共同变化不构成可加的独立因果分解。", "",
        "预检完成零干预公共指标精确等价、会话模式切换及正成本短运行的边界事件计数检查。短窗口未满足同路径且全完成的配对条件，因此本轮不声称完成了同路径下的全载荷对照；额外占用区间与有效载荷字节分开记账。", "",
        "真实异构集群校准与分布式引擎验证仍未完成。本文结论仍限于已测画像驱动仿真；不新增跨负载战胜所有外部方法或完整新颖性已证的结论。", "",
        "## 4. 失败、缺失与核验问题", ""]
    for fail in failures:
        lines.append(f"- {fail['job']['key']}：{fail.get('failure', {}).get('error', fail.get('failure', {}).get('kind', '见原始记录'))}")
    for key in missing:
        lines.append(f"- 缺失：{key}")
    for problem in problems:
        lines.append(f"- 核验未通过：{problem['check']} / {problem['detail']}")
    if not failures and not missing and not problems:
        lines.append("本轮实际执行无失败、无缺失，综合核验未发现问题。此前派发工程失败仍独立保留。")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=result["status"], execution_status=coverage,
        accepted=len(accepted), problems=len(problems), missing=len(missing)), ensure_ascii=False))


if __name__ == "__main__":
    main()
