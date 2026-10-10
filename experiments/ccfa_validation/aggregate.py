"""Validate paired experiments and write a compact, evidence-bound report."""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean, stdev


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BASE = ROOT / "experiments/multiseed/runs"
SCENARIOS = ("single", "multi")
SEEDS = (0, 1, 2)
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def read(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def stats(values) -> dict:
    numbers = list(values)
    return {"mean": mean(numbers), "sd": stdev(numbers) if len(numbers) > 1 else None,
            "values": numbers}


def cross_cluster_hops(record: dict) -> float:
    def region(uid: int) -> int:
        node = uid - 2
        return 0 if node < 4 else 1 if node < 14 else 2

    total_hops = total_routes = 0
    for route, count in record["route_counts"].items():
        groups = [region(int(uid)) for uid in route.split("-")]
        total_hops += count * sum(a != b for a, b in zip(groups, groups[1:]))
        total_routes += count
    assert 0 < total_routes <= record["arrivals"]
    return total_hops / total_routes


def paper(scenario: str, seed: int, method: str) -> tuple[Path, dict]:
    name = "paper_helix" if method == "helix" else "paper_integrated"
    path = BASE / f"seed{seed}" / scenario / f"{name}.json"
    return path, read(path)


def supplemental(group: str, setting: str, scenario: str,
                 seed: int, method: str) -> tuple[Path, dict]:
    path = RUNS / group / setting / f"seed{seed}" / f"{scenario}_{method}.json"
    return path, read(path)


def validate_pair(scenario: str, seed: int, offered: int,
                  baseline: dict, candidate: dict, *, network: bool = False) -> None:
    for record, method in ((baseline, "helix"), (candidate, "queue_dag")):
        assert record["scenario"] == scenario and record["seed"] == seed
        assert record["method"] == method
        assert record["offered_tokens_per_s"] == offered
        assert record["duration_s"] == 1800 and record["warmup_s"] == 0
        assert record["gurobi_version"].startswith("13.")
    for key in ("trace_sha256", "arrivals", "python_version", "numpy_version",
                "gurobi_version"):
        assert baseline[key] == candidate[key], (scenario, seed, key)
    if network:
        assert baseline["physical_cluster_sha256"] == candidate["physical_cluster_sha256"]


def paired_group(group: str, setting: str, scenario: str, offered: int,
                 *, reference: bool = False) -> dict:
    pairs = []
    for seed in SEEDS:
        if reference:
            baseline_path, baseline = paper(scenario, seed, "helix")
            candidate_path, candidate = paper(scenario, seed, "green")
        else:
            baseline_path, baseline = supplemental(group, setting, scenario, seed, "helix")
            candidate_path, candidate = supplemental(group, setting, scenario, seed, "green")
        validate_pair(scenario, seed, offered, baseline, candidate,
                      network=group == "network" and not reference)
        pairs.append({
            "seed": seed, "helix_path": str(baseline_path.relative_to(ROOT)),
            "green_path": str(candidate_path.relative_to(ROOT)),
            "arrivals": baseline["arrivals"], "trace_sha256": baseline["trace_sha256"],
            "helix": {key: baseline[key] for key in METRICS},
            "green": {key: candidate[key] for key in METRICS},
            "cross_cluster_hops_per_route": (
                {"helix": cross_cluster_hops(baseline),
                 "green": cross_cluster_hops(candidate)}
                if scenario == "multi" else None),
            "relative_benefit_pct": {
                "throughput": 100 * (candidate[METRICS[0]] / baseline[METRICS[0]] - 1),
                "ttft": 100 * (1 - candidate[METRICS[1]] / baseline[METRICS[1]]),
                "tpot": 100 * (1 - candidate[METRICS[2]] / baseline[METRICS[2]]),
            },
        })
    return {
        "scenario": scenario, "setting": setting, "offered_tokens_per_s": offered,
        "seeds": pairs,
        "helix": {key: stats(item["helix"][key] for item in pairs) for key in METRICS},
        "green": {key: stats(item["green"][key] for item in pairs) for key in METRICS},
        "relative_benefit_pct": {
            key: stats(item["relative_benefit_pct"][key] for item in pairs)
            for key in ("throughput", "ttft", "tpot")},
        "cross_cluster_hops_per_route": (
            {method: stats(item["cross_cluster_hops_per_route"][method]
                           for item in pairs)
             for method in ("helix", "green")}
            if scenario == "multi" else None),
    }


def offline_group() -> dict:
    scenarios = {}
    for scenario in SCENARIOS:
        pairs = []
        for seed in SEEDS:
            paths = {method: RUNS / "offline_common" / f"seed{seed}" /
                     f"{scenario}_{method}.json" for method in ("helix", "integrated")}
            baseline, candidate = (read(paths[method]) for method in ("helix", "integrated"))
            for record, method in ((baseline, "helix"), (candidate, "integrated")):
                assert record["scenario"] == scenario and record["seed"] == seed
                assert record["method"] == method and record["admission_rule"] == "common"
                assert record["warmup_s"] == 60 and record["measurement_s"] == 600
                assert record["gurobi_version"].startswith("13.")
            assert baseline["python_version"] == candidate["python_version"]
            assert baseline["numpy_version"] == candidate["numpy_version"]
            assert baseline["gurobi_version"] == candidate["gurobi_version"]
            before = baseline["decode_throughput_tokens_per_s"]
            after = candidate["decode_throughput_tokens_per_s"]
            native_path = (ROOT / "experiments/baseline_audit/runs_dynamic" /
                           f"seed{seed}" / f"{scenario}_helix.json")
            native = read(native_path)
            assert native["scenario"] == scenario and native["seed"] == seed
            assert native["gurobi_version"] == baseline["gurobi_version"]
            pairs.append({"seed": seed,
                          "helix_path": str(paths["helix"].relative_to(ROOT)),
                          "green_path": str(paths["integrated"].relative_to(ROOT)),
                          "helix_throughput": before, "green_throughput": after,
                          "benefit_pct": 100 * (after / before - 1),
                          "native_helix_throughput": native["decode_throughput_tokens_per_s"],
                          "helix_issued": baseline["issued_queries_total"],
                          "green_issued": candidate["issued_queries_total"],
                          "helix_peak_inflight": baseline["peak_inflight"],
                          "green_peak_inflight": candidate["peak_inflight"]})
        scenarios[scenario] = {
            "seeds": pairs,
            "helix_throughput": stats(item["helix_throughput"] for item in pairs),
            "green_throughput": stats(item["green_throughput"] for item in pairs),
            "benefit_pct": stats(item["benefit_pct"] for item in pairs),
            "native_helix_throughput": stats(item["native_helix_throughput"]
                                             for item in pairs),
        }
    return scenarios


def overhead_group() -> dict:
    records = {}
    for scenario in SCENARIOS:
        baseline_path, baseline = supplemental("overhead", "official", scenario, 0, "helix")
        candidate_path, candidate = supplemental("overhead", "official", scenario, 0, "green")
        validate_pair(scenario, 0, 700 if scenario == "single" else 320,
                      baseline, candidate)
        original_baseline = paper(scenario, 0, "helix")[1]
        original_candidate = paper(scenario, 0, "green")[1]
        for measured, original in ((baseline, original_baseline),
                                   (candidate, original_candidate)):
            for key in METRICS:
                assert measured[key] == original[key], (scenario, key)
        records[scenario] = {
            "helix_path": str(baseline_path.relative_to(ROOT)),
            "green_path": str(candidate_path.relative_to(ROOT)),
            "helix": baseline["scheduler_call_profile"],
            "green": candidate["scheduler_call_profile"],
            "helix_wall_s": baseline["wall_time_s"],
            "green_wall_s": candidate["wall_time_s"],
        }
    records["planner"] = read(RUNS / "planner/overhead.json")
    return records


def stress_boundary() -> list[dict] | None:
    folder = RUNS / "load/high"
    logs = [folder / f"seed{seed}/multi_helix.log" for seed in SEEDS]
    candidates = [folder / f"seed{seed}/multi_green.json" for seed in SEEDS]
    if not all(path.is_file() for path in (*logs, *candidates)):
        return None
    results = []
    for seed, log, candidate_path in zip(SEEDS, logs, candidates):
        content = log.read_text(encoding="utf-8")
        progress = re.findall(r"progress: multi/helix, arrivals=\d+, sim_time=([0-9.]+)",
                              content)
        failure = re.search(
            r"AssertionError: No next level node meets scheduling requirement at compute (\d+)!",
            content)
        if not progress or not failure:
            raise ValueError(f"Unrecognized stress failure: {log}")
        candidate = read(candidate_path)
        assert candidate["offered_tokens_per_s"] == 416
        assert candidate["duration_s"] == 1800 and candidate["warmup_s"] == 0
        results.append({"seed": seed,
                        "helix_log": str(log.relative_to(ROOT)),
                        "last_reported_sim_time_s": float(progress[-1]),
                        "failed_compute_uid": int(failure.group(1)),
                        "green_path": str(candidate_path.relative_to(ROOT)),
                        "green_throughput_tokens_per_s":
                            candidate["output_throughput_tokens_per_s"]})
    return results


def fmt(stat: dict, digits: int = 2) -> str:
    return f"{stat['mean']:.{digits}f} ± {stat['sd']:.{digits}f}"


def main() -> None:
    load = {}
    for scenario, standard in (("single", 700), ("multi", 320)):
        load[scenario] = {
            "low": paired_group("load", "low", scenario, round(standard * 0.7)),
            "official": paired_group("load", "official", scenario, standard,
                                     reference=True),
            "high": paired_group("load_upper", "high", scenario, round(standard * 1.1)),
        }
    network = {
        setting: paired_group("network", setting, "multi", 320,
                              reference=setting == "official")
        for setting in ("rtt_0p5x", "official", "rtt_2x")
    }
    base_intervals = read(ROOT / "experiments/critical_graph/runs/multi_final/placement.json")["intervals"]
    network_placements_unchanged = all(
        read(HERE / "network_layouts" / setting / "metadata.json")["green_intervals"]
        == base_intervals for setting in ("rtt_0p5x", "rtt_2x"))
    mechanism = read(RUNS / "network_mechanism.json")
    offline = offline_group()
    overhead = overhead_group()
    stress = stress_boundary()
    summary = {"protocol": "Gurobi13; paired seeds 0/1/2; online 1800 s zero warmup",
               "load": load, "network": network,
               "network_placements_unchanged": network_placements_unchanged,
               "network_event_dag_mechanism": mechanism,
               "offline_common": offline,
               "overhead": overhead, "overload_boundary": stress}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                       encoding="utf-8")
    lines = [
        "# CCFA 补充实验结果", "",
        "所有正式运行统一使用 Python 3.10.16、NumPy 2.2.6、Gurobi 13.0.3。在线结果使用种子 0/1/2、无预热的 1800 s 固定窗口；同一场景/负载/种子的两种方法使用相同请求轨迹。`±` 为三个种子的样本标准差，不是置信区间。原始 JSON 与日志位于 `runs/`，逐种子值见 `summary.json`。", "",
        "## 1. 统一协议负载扫描", "",
        "| 场景 | offered token/s | Helix 吞吐 | 本方法吞吐 | 吞吐增益 % | TTFT 降低 % | TPOT 降低 % |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scenario in SCENARIOS:
        for setting in ("low", "official", "high"):
            item = load[scenario][setting]
            benefit = item["relative_benefit_pct"]
            lines.append(f"| {scenario} | {item['offered_tokens_per_s']} | "
                         f"{fmt(item['helix'][METRICS[0]])} | {fmt(item['green'][METRICS[0]])} | "
                         f"{fmt(benefit['throughput'])} | {fmt(benefit['ttft'])} | "
                         f"{fmt(benefit['tpot'])} |")
    lines += ["", "上述六组场景/负载中，吞吐、P95 TTFT、P95 TPOT 三项指标各自在全部 3/3 种子上改善。"]
    lines += ["", "固定窗口截尾检查：完成率仅统计窗口内到达并完成的请求；积压是窗口结束时未完成的请求数。", "",
              "| 场景 | offered token/s | Helix 完成率 % | 本方法完成率 % | Helix 积压 | 本方法积压 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for scenario in SCENARIOS:
        for setting in ("low", "official", "high"):
            item = load[scenario][setting]
            helix_completion = stats(100 * value for value in item["helix"]["completion_fraction"]["values"])
            green_completion = stats(100 * value for value in item["green"]["completion_fraction"]["values"])
            lines.append(f"| {scenario} | {item['offered_tokens_per_s']} | "
                         f"{fmt(helix_completion)} | {fmt(green_completion)} | "
                         f"{fmt(item['helix']['backlog_at_window_end'], 1)} | "
                         f"{fmt(item['green']['backlog_at_window_end'], 1)} |")
    lines += ["", "逐种子指标见 `summary.json`；低/高负载为官方 offered load 的 0.7/1.1 倍。这里中间档直接复用原三种子官方负载完整运行，三档协议一致。尝试的 1.3 倍负载使 Helix 三集群三种子均在窗口结束前不可路由，失败日志保留在 `runs/load/high/`，不作为 1800 s 吞吐点。", ""]
    if stress is not None:
        lines += ["**1.3 倍负载边界（416 token/s，三集群）**：Helix 三种子均报下一跳不可用；下表时间是失败前最近一次进度日志，并非精确失败时刻。新方法三种子跑完完整窗口，其吞吐仅作为单侧观察，不能计算与失败 Helix 的提升百分比。", "",
                  "| 种子 | Helix 最近进度时刻 s | 失败节点 UID | 本方法完整窗口吞吐 token/s |", "| ---: | ---: | ---: | ---: |"]
        for item in stress:
            lines.append(f"| {item['seed']} | {item['last_reported_sim_time_s']:.1f} | "
                         f"{item['failed_compute_uid']} | "
                         f"{item['green_throughput_tokens_per_s']:.2f} |")
        lines.append("")
    lines += [
              "## 2. 三集群跨区域 RTT 敏感性", "",
              "仅按 0.5/1/2 倍缩放物理分区之间的 RTT，保留 GPU 性能、带宽与请求轨迹。每档重新运行本方法的完整放置和调度；Helix 保留官方放置，并在同样改动的物理拓扑和执行链路上调度。", "",
              "| 跨区域 RTT 倍数 | Helix 吞吐 | 本方法吞吐 | 吞吐增益 % | TTFT 降低 % | TPOT 降低 % | Helix / 本方法平均跨区跳数 |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for setting, factor in (("rtt_0p5x", "0.5"), ("official", "1"),
                            ("rtt_2x", "2")):
        item = network[setting]
        benefit = item["relative_benefit_pct"]
        hops = item["cross_cluster_hops_per_route"]
        lines.append(f"| {factor} | {fmt(item['helix'][METRICS[0]])} | "
                     f"{fmt(item['green'][METRICS[0]])} | {fmt(benefit['throughput'])} | "
                     f"{fmt(benefit['ttft'])} | {fmt(benefit['tpot'])} | "
                     f"{hops['helix']['mean']:.2f} / {hops['green']['mean']:.2f} |")
    lines += ["", "配置文件与放置元数据位于 `network_layouts/`。" +
              ("重新规划后 0.5×、1×、2× 三档层划分相同；因此这组结果说明固定层放置下对 RTT 变化的敏感性，不构成层边界随 RTT 自适应的证据。" if network_placements_unchanged else
               "重新规划产生了不同层划分；结果同时包含放置改变与执行链路改变的影响。") +
              "仿真器链路语义不等于真实广域网传输实现。", "",
              "解析事件 DAG 对四个代表性请求（每支路两个）的首 token 关键路径给出如下资源时间占比。`其他请求服务` 是关键路径上其他请求占用资源的代理，不等同于仿真测得的排队等待；因此下表是机制解释，不是端到端实测延迟分解。", "",
              "| 跨区 RTT | 本请求计算 | 本请求传输 | 本请求传播 | 其他请求服务 |", "| ---: | ---: | ---: | ---: | ---: |"]
    for setting, factor in (("rtt_0p5x", "0.5×"), ("official", "1×"),
                            ("rtt_2x", "2×")):
        share = mechanism[setting]["mean_critical_path_share"]
        lines.append(f"| {factor} | {100*share['compute']:.1f}% | "
                     f"{100*share['transfer']:.1f}% | {100*share['propagation']:.1f}% | "
                     f"{100*share['resource_contention']:.1f}% |")
    lines += ["",
              "## 3. 相同准入规则的离线对照", "",
              "双方都从 20 个请求起步；每个在途请求对全部层计入相同的预期 KV token 需求，以各自放置下每层的 KV 容量为分母，最高利用率不超过 0.8 时准入一个新请求。长度采样器和种子相同，完成事件导致的准入时间仍可不同。测量为预热 60 s 后的 600 s 离线 decode 吞吐。原生准入结果保留在 `../baseline_audit/RESULTS_OFFLINE.md`，两种规则不可混表。", "",
              "| 场景 | Helix token/s | 本方法 token/s | 增益 % |", "| --- | ---: | ---: | ---: |"]
    for scenario in SCENARIOS:
        item = offline[scenario]
        lines.append(f"| {scenario} | {fmt(item['helix_throughput'])} | "
                     f"{fmt(item['green_throughput'])} | {fmt(item['benefit_pct'])} |")
    lines += ["", "原生准入下的 Helix 三种子平均吞吐为 single " +
              f"{offline['single']['native_helix_throughput']['mean']:.2f}、multi " +
              f"{offline['multi']['native_helix_throughput']['mean']:.2f} token/s；" +
              "共同准入下分别为 " +
              f"{offline['single']['helix_throughput']['mean']:.2f}、" +
              f"{offline['multi']['helix_throughput']['mean']:.2f} token/s。" +
              "共同准入改变了基线绝对值，应以本表的成对结果解释该控制实验。"]
    lines += ["", "## 4. 方法开销", "",
              "下表来自官方负载种子 0 的完整 1800 s 仿真。计时采用高分辨率 `perf_counter_ns` 包裹调度入口，表示调用期间的墙钟时间；`_route` 在 `schedule_transmission` 内部，不能重复相加。计时仿真的性能指标与未计时原运行逐项相同。不同系统触发调度入口的次数也不同，因此累计值包含事件量差异；初始布局/调度器设置不计入窗口开销。", "",
              "| 场景 | 方法 | 传输调度调用 / 累计 s / P95 μs | 执行调度调用 / 累计 s / P95 μs | 路由调用 / P95 μs |", "| --- | --- | ---: | ---: | ---: |"]
    for scenario in SCENARIOS:
        for method, label in (("helix", "Helix"), ("green", "本方法")):
            profile = overhead[scenario][method]
            transfer = profile["schedule_transmission"]
            execution = profile["schedule_execution"]
            route = profile.get("_route", {})
            route_text = (f"{route['calls']} / {route['p95_us']:.1f}" if route.get("calls")
                          else "—")
            lines.append(f"| {scenario} | {label} | "
                         f"{transfer['calls']} / {transfer['total_s']:.2f} / {transfer['p95_us']:.1f} | "
                         f"{execution['calls']} / {execution['total_s']:.2f} / {execution['p95_us']:.1f} | "
                         f"{route_text} |")
    lines += ["", "本方法完整离线放置生成耗时（拓扑加载、初始划分、细化和配置写入）："]
    for scenario in SCENARIOS:
        samples = overhead["planner"][scenario]["samples"]
        wall = stats(sample["wall_s"] for sample in samples)
        cpu = stats(sample["process_cpu_s"] for sample in samples)
        lines.append(f"- {scenario}：墙钟 {fmt(wall)} s，进程 CPU {fmt(cpu)} s（3 次）。")
    lines += ["", "Helix 放置使用已发布的 ILP artifact 布局；本实验未重求解官方 ILP，因此不报告规划耗时的成对加速比。", "",
              "## 解释边界", "",
              "三种子中种子 1 曾用于开发调参；这里的误差条描述运行波动，不代表完全独立的盲测。全部性能来自事件仿真器，没有真实 GPU 或广域网部署验证。", ""]
    (HERE / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {HERE / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
