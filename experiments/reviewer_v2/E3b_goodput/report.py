"""Audit E3b original results and independent failure replay; build cautious summaries."""
from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from .probe import SLO
from .run import HERE, LOADS, METHODS, ROOT, check, read, sha, write

T4 = 2.7764451051977987
FORMAL = HERE / "formal"
REPLAY = HERE / "failure_replay"
TIERS = ("strict", "medium", "loose")


def almost(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-8)


def interval(values):
    if len(values) != 5:
        raise ValueError("Five paired seeds required")
    center = mean(values)
    half = T4 * stdev(values) / math.sqrt(5)
    return dict(mean=center, low=center-half, high=center+half)


def verified(path, digest):
    if not path.is_file() or sha(path) != digest:
        raise RuntimeError(f"Missing or changed artifact: {path}")
    return read(path)


def check_result(key, job, row, manifest_sha):
    if (row.get("status") != "completed" or row.get("job") != job or
            row.get("manifest_sha256") != manifest_sha or
            row.get("evaluation_protocol") != "warmup300_measure1800_drain_cap3600_v1" or
            row.get("warmup_s") != 300 or row.get("duration_s") != 2100):
        raise RuntimeError(f"Protocol or identity mismatch: {key}")
    good, drain = row["goodput"], row["drain"]
    samples = drain["query_samples"]
    arrivals = len(samples)
    if (good["measurement_s"] != 1800 or drain["measurement_s"] != 1800 or
            drain["tail_cap_s"] != 3600 or arrivals != drain["arrivals"] or
            arrivals != good["measurement_arrivals"] or
            drain["completed"] != good["completed_by_tail"] or
            drain["right_censored"] != good["right_censored"] or
            arrivals != drain["completed"] + drain["right_censored"] or
            good["deployed_gpu_count"] <= 0 or
            good["gpu_busy_seconds_measurement_and_tail"] < 0 or
            not almost(sum(good["gpu_busy_seconds_by_uid"].values()),
                       good["gpu_busy_seconds_measurement_and_tail"])):
        raise RuntimeError(f"Cohort or GPU accounting mismatch: {key}")
    # The simulator starts after model loading, so its absolute clock has a
    # positive layout offset relative to the 2100 s arrival horizon.
    layout_offset = good["tail_stop_s"] - drain["tail_elapsed_s"] - row["duration_s"]
    if (not 0 <= layout_offset <= 600 or
            not 0 <= drain["tail_elapsed_s"] <= 3600 or
            good["tail_stop_s"] > layout_offset + 5700 + 1e-8):
        raise RuntimeError(f"Drain stopping mismatch: {key}")
    if not row.get("trace_sha256") or not row.get("solution_sha256"):
        raise RuntimeError(f"Missing source hashes: {key}")
    for tier in TIERS:
        bound1, bound2 = SLO[job["scenario"]][tier]
        item = good["tiers"][tier]
        eligible = [x for x in samples if x["completed"] and x["output_tokens"] >= 2
                    and x["ttft_s"] is not None and x["tpot_s"] is not None
                    and x["ttft_s"] <= bound1 and x["tpot_s"] <= bound2]
        tokens = sum(x["output_tokens"] for x in eligible)
        rate = tokens / 1800
        busy = good["gpu_busy_seconds_measurement_and_tail"]
        expected_busy_rate = tokens / busy if busy else None
        if (item["qualified_requests"] != len(eligible) or
                item["qualified_output_tokens"] != tokens or
                not almost(item["goodput_tokens_per_s"], rate) or
                not almost(item["goodput_tokens_per_s_per_gpu"],
                           rate/good["deployed_gpu_count"]) or
                (expected_busy_rate is None) != (item["qualified_tokens_per_gpu_busy_s"] is None) or
                (expected_busy_rate is not None and not almost(
                    item["qualified_tokens_per_gpu_busy_s"], expected_busy_rate))):
            raise RuntimeError(f"SLO calculation mismatch: {key}/{tier}")
    if [good["tiers"][tier]["qualified_requests"] for tier in TIERS] != sorted(
            good["tiers"][tier]["qualified_requests"] for tier in TIERS):
        raise RuntimeError(f"Non-monotone thresholds: {key}")


def main():
    manifest_path, index_path = FORMAL / "manifest.json", FORMAL / "index.json"
    manifest, index = read(manifest_path), read(index_path)
    check(manifest)
    mhash = sha(manifest_path)
    jobs = {j["key"]: j for j in manifest["jobs"]}
    if (index["status"] != "terminal" or index["manifest_sha256"] != mhash or
            set(index["jobs"]) != set(jobs) or len(jobs) != 200):
        raise RuntimeError("Formal batch is not an intact 200-key terminal batch")
    replay_manifest_path, replay_index_path = REPLAY / "manifest.json", REPLAY / "index.json"
    replay_manifest, replay_index = read(replay_manifest_path), read(replay_index_path)
    if (replay_index["status"] != "terminal" or
            replay_index["manifest_sha256"] != sha(replay_manifest_path) or
            replay_manifest["original_manifest_sha256"] != mhash or
            replay_manifest["original_index_sha256"] != sha(index_path)):
        raise RuntimeError("Replay registration or terminal state mismatch")
    failed = {key for key, state in index["jobs"].items() if state["status"] == "failed"}
    if set(replay_index["jobs"]) != failed or set(replay_manifest["original_failures"]) != failed:
        raise RuntimeError("Replay keys differ from original failures")
    records, results, errors, replay_errors = [], {}, Counter(), Counter()
    traces = defaultdict(set)
    deployments = defaultdict(set)
    for key, job in jobs.items():
        state = index["jobs"][key]
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError(f"Nonterminal key: {key}")
        artifact = verified(ROOT / state["source"], state["artifact_sha256"])
        if artifact.get("job") != job:
            raise RuntimeError(f"Artifact job mismatch: {key}")
        case, load, method, seed = job["scenario"], job["load"], job["method"], job["seed"]
        out = dict(scenario=case, load=load, cell=method, seed=seed, status=state["status"],
                   source=state["source"], artifact_sha256=state["artifact_sha256"], error="")
        if state["status"] == "completed":
            check_result(key, job, artifact, mhash)
            results[(case, load, method, seed)] = artifact
            traces[(case, load, seed)].add(artifact["trace_sha256"])
            deployments[(case, method)].add((artifact["solution_sha256"],
                                               artifact["sim_cluster_sha256"],
                                               artifact["physical_cluster_sha256"]))
            good = artifact["goodput"]
            out.update(trace_sha256=artifact["trace_sha256"],
                solution_sha256=artifact["solution_sha256"],
                sim_cluster_sha256=artifact["sim_cluster_sha256"],
                deployed_gpu_count=good["deployed_gpu_count"],
                gpu_busy_seconds=good["gpu_busy_seconds_measurement_and_tail"],
                measurement_arrivals=good["measurement_arrivals"],
                completed_by_tail=good["completed_by_tail"], right_censored=good["right_censored"],
                completion_fraction=good["completed_by_tail"]/good["measurement_arrivals"]
                    if good["measurement_arrivals"] else 0,
                **{f"{tier}_goodput_tokens_per_s":good["tiers"][tier]["goodput_tokens_per_s"]
                   for tier in TIERS},
                **{f"{tier}_goodput_per_gpu":good["tiers"][tier]["goodput_tokens_per_s_per_gpu"]
                   for tier in TIERS},
                **{f"{tier}_tokens_per_gpu_busy_s":good["tiers"][tier]["qualified_tokens_per_gpu_busy_s"]
                   for tier in TIERS})
        else:
            error = artifact.get("error", artifact.get("classification", "unknown"))
            errors[error] += 1
            out["error"] = error
            replay_state = replay_index["jobs"][key]
            original = replay_manifest["original_failures"][key]
            if (original["job"] != job or original["source"] != state["source"] or
                    original["artifact_sha256"] != state["artifact_sha256"] or
                    replay_state["status"] not in ("completed", "failed")):
                raise RuntimeError(f"Replay origin mismatch: {key}")
            replay = verified(ROOT / replay_state["source"], replay_state["artifact_sha256"])
            if replay.get("job") != job:
                raise RuntimeError(f"Replay job mismatch: {key}")
            replay_error = replay.get("error", replay.get("classification", "none"))
            replay_errors[replay_error] += 1
            out.update(replay_status=replay_state["status"], replay_source=replay_state["source"],
                       replay_artifact_sha256=replay_state["artifact_sha256"], replay_error=replay_error)
        records.append(out)
    if any(len(v) != 1 for v in traces.values()) or any(len(v) != 1 for v in deployments.values()):
        raise RuntimeError("Matched trace or fixed deployment mismatch")
    if len(results) != 188 or len(failed) != 12:
        raise RuntimeError("Unexpected original success and failure counts")
    columns = ("scenario", "load", "cell", "seed", "status", "source",
        "artifact_sha256", "error", "replay_status", "replay_source",
        "replay_artifact_sha256", "replay_error", "trace_sha256",
        "solution_sha256", "sim_cluster_sha256", "deployed_gpu_count",
        "gpu_busy_seconds", "measurement_arrivals", "completed_by_tail",
        "right_censored", "completion_fraction",
        *(f"{tier}_goodput_tokens_per_s" for tier in TIERS),
        *(f"{tier}_goodput_per_gpu" for tier in TIERS),
        *(f"{tier}_tokens_per_gpu_busy_s" for tier in TIERS))
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
    groups, comparisons = {}, {}
    for case, loads in LOADS.items():
        for load in loads:
            for method in METHODS:
                members = [results.get((case, load, method, seed)) for seed in range(5)]
                if any(x is None for x in members):
                    groups[f"{case}/{load}/{method}"] = dict(success=sum(x is not None for x in members), expected=5)
                    continue
                groups[f"{case}/{load}/{method}"] = dict(success=5, expected=5,
                    means={tier: mean(x["goodput"]["tiers"][tier]["goodput_tokens_per_s"] for x in members)
                           for tier in TIERS},
                    deployed_gpu_count=mean(x["goodput"]["deployed_gpu_count"] for x in members),
                    completion_fraction=mean(x["goodput"]["completed_by_tail"] /
                        x["goodput"]["measurement_arrivals"] for x in members),
                    gpu_busy_seconds=mean(x["goodput"]["gpu_busy_seconds_measurement_and_tail"] for x in members))
                if method != "RCAPS":
                    base = [results.get((case, load, "RCAPS", seed)) for seed in range(5)]
                    if all(base):
                        comparisons[f"{case}/{load}/RCAPS_minus_{method}"] = {tier: interval([
                            base[s]["goodput"]["tiers"][tier]["goodput_tokens_per_s"]-
                            members[s]["goodput"]["tiers"][tier]["goodput_tokens_per_s"]
                            for s in range(5)]) for tier in TIERS}
    write(HERE / "groups.json", groups)
    write(HERE / "paired_comparisons.json", comparisons)
    lines = ["# E3b：逐请求 SLO goodput 负载扫描", "",
        "70B 画像驱动 CPU 仿真；预热 300 s、测量到达 1800 s、尾部最多排空 3600 s。",
        "goodput 只计测量期到达、在排空前完成且同时满足逐请求 TTFT/TPOT 阈值的输出 token。",
        "下表为中等 SLO；严格/宽松逐种子数据在 individual.csv，完整组均值在 groups.json。", "",
        "| 拓扑/负载 | 方法 | 原批成功 | 中等 SLO goodput token/s | 部署 GPU 均数 | 排空完成率 | GPU 忙碌秒均值 |",
        "|---|---|---:|---:|---:|---:|---:|"]
    for case, loads in LOADS.items():
        for load in loads:
            for method in METHODS:
                group = groups[f"{case}/{load}/{method}"]
                if group["success"] == 5:
                    lines.append(f"| {case}/{load} | {method} | 5/5 | {group['means']['medium']:.3f} | "
                        f"{group['deployed_gpu_count']:.1f} | {group['completion_fraction']*100:.2f}% | "
                        f"{group['gpu_busy_seconds']:.1f} |")
                else:
                    lines.append(f"| {case}/{load} | {method} | {group['success']}/5 | — | — | — | — |")
    lines += ["", "## 配对比较", "",
        "paired_comparisons.json 含 RCAPS 减各方法 goodput 的五种子绝对差及 df=4 双侧 t 95% CI。",
        "缺种子组不计算均值或配对 CI；严格/中等/宽松三档分别报告。", "",
        "## 失败和独立重放", "",
        f"原批 188/200 成功、12/200 失败；独立重放 {sum(s['status']=='completed' for s in replay_index['jobs'].values())}/12 成功。",
        "12 个原失败集中在 multi/400 的 Helix 三方法；失败原件与重放在不同目录留存。",
        "失败由原版 GlobalFlowScheduler 在 compute 15/19/23 报告无可接纳下游节点，",
        "这是本高负载部署的调度可行性边界；不能把失败记为 goodput=0，也不能将独立重放当作原批成功。",
        "原错误部署的 E2a 单集群结果未用于本实验；Helix-tuned 只继承已纠错的独立选择。", "",
        "## 论文可用表述", "",
        "在 70B 画像驱动仿真中，我们以预先固定的三档逐请求 TTFT 与 TPOT SLO 比较了八个负载点。",
        "测量请求的合格输出 token 以固定 1800 s 归一化，另列部署 GPU 数与 GPU 忙碌秒。",
        "同一拓扑、负载和种子的成功运行使用相同请求轨迹。",
        "在三集群 400 token/s，Helix 系列发生可复现的下游不可接纳断言，故其缺种子组仅报告成功数与原因。",
        "这些结果来自模拟器，并非真实 GPU 集群测量。", ""]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    audit = dict(passed=True, formal_status=index["status"], registered=200, completed=len(results),
        original_failed=len(failed), replay_status=replay_index["status"],
        replay_completed=sum(v["status"] == "completed" for v in replay_index["jobs"].values()),
        replay_failed=sum(v["status"] == "failed" for v in replay_index["jobs"].values()),
        original_failure_reasons=dict(errors), replay_failure_reasons=dict(replay_errors),
        complete_five_seed_groups=sum(x["success"] == 5 for x in groups.values()),
        incomplete_groups={k:v["success"] for k,v in groups.items() if v["success"] != 5},
        matched_trace_groups=len(traces), audited_deployments=len(deployments),
        paired_comparison_groups=len(comparisons),
        sources=dict(formal_manifest_sha256=mhash, formal_index_sha256=sha(index_path),
                     replay_manifest_sha256=sha(replay_manifest_path),
                     replay_index_sha256=sha(replay_index_path)),
        outputs={name:sha(HERE / name) for name in ("individual.csv","groups.json",
                "paired_comparisons.json","RESULTS_CN.md")},
        report_script_sha256=sha(Path(__file__)))
    write(HERE / "FINAL_AUDIT.json", audit)
    print(f"E3b audit passed: {len(results)}/200 original, {len(failed)} failures, "
          f"{audit['complete_five_seed_groups']}/40 full groups, "
          f"{audit['replay_failed']}/12 replay failures", flush=True)


if __name__ == "__main__":
    main()
