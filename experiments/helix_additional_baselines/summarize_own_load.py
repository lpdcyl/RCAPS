"""Audit method-specific-load runs and write a descriptive Chinese report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

from benchmarks.registry import METHODS
from experiments.helix_additional_baselines.report import _audit_sp_physical
from experiments.helix_additional_baselines.own_load_search import GRIDS, METHOD_NAMES


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SEEDS = (0, 1, 2)
METRICS = (
    ("output_throughput_tokens_per_s", "输出吞吐 token/s"),
    ("ttft_p95_s", "P95 TTFT s"),
    ("tpot_p95_s", "P95 TPOT s"),
    ("completion_fraction", "完成率 %"),
    ("backlog_at_window_end", "末端积压"),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_result(path: Path, scenario: str, method: str,
                   seed: int, offered: float) -> dict:
    log = path.with_suffix(".log")
    if not path.is_file():
        return {"status": "failed_or_missing", "log": str(log.relative_to(ROOT)),
                "log_sha256": digest(log) if log.is_file() else None}
    record = json.loads(path.read_text(encoding="utf-8"))
    solution, cluster = METHODS[method].layout(scenario, ROOT)
    expected = {
        "system": method, "scenario": scenario, "seed": seed,
        "offered_tokens_per_s": offered, "duration_s": 1800,
        "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
        "query_samples_schema": 1, "solution_sha256": digest(solution),
        "sim_cluster_sha256": digest(cluster),
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f"{path}: unexpected {key}: {record.get(key)!r} != {value!r}")
    if len(record.get("query_samples", {})) != record["arrivals"]:
        raise ValueError(f"{path}: incomplete request identities")
    if not record.get("trace_sha256"):
        raise ValueError(f"{path}: missing trace hash")
    values = {key: record[key] * (100 if key == "completion_fraction" else 1)
              for key, _ in METRICS}
    return {"status": "complete", "result": str(path.relative_to(ROOT)),
            "result_sha256": digest(path), "trace_sha256": record["trace_sha256"],
            "arrivals": record["arrivals"], "metrics": values}


def verify_choice(scenario: str, method: str, choice: dict) -> dict:
    if choice["status"] == "no_grid_load_passed":
        minimum = GRIDS[scenario][0]
        paths = sorted((HERE / "own_load_development" / scenario / method).glob(
            "load*/probe.json"))
        probes = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        if not any(probe["offered_tokens_per_s"] == minimum for probe in probes):
            raise ValueError(f"Missing lower-bound probe: {scenario}/{method}")
        if any(probe["scenario"] != scenario or probe["method"] != method or
               probe["passed_l90"] or set(probe["seeds"]) != {"100", "101"}
               for probe in probes):
            raise ValueError(f"Invalid no-pass evidence: {scenario}/{method}")
        return {"boundary_probes": {str(minimum): str((
                    HERE / "own_load_development" / scenario / method /
                    f"load{minimum}" / "probe.json").relative_to(ROOT))},
                "probe_count": len(probes),
                "search_wall_s": sum(probe["wall_s"] for probe in probes),
                "observed_pass_fail": {
                    probe["offered_tokens_per_s"]: False for probe in probes}}
    if choice["status"] not in ("selected", "grid_ceiling"):
        raise ValueError(f"No usable selection for {scenario}/{method}")
    grid = GRIDS[scenario]
    selected = choice["l90_grid_tokens_per_s"]
    if selected not in grid or choice["formal_offered_tokens_per_s"] != 0.75 * selected:
        raise ValueError(f"Invalid own-load rule for {scenario}/{method}")
    index = grid.index(selected)
    expected_next = grid[index + 1] if index + 1 < len(grid) else None
    if choice["next_grid_tokens_per_s"] != expected_next:
        raise ValueError(f"Missing adjacent grid check for {scenario}/{method}")
    probes = {}
    for offered, expected_pass in ((selected, True), (expected_next, False)):
        if offered is None:
            continue
        path = HERE / "own_load_development" / scenario / method / f"load{offered}" / "probe.json"
        probe = json.loads(path.read_text(encoding="utf-8"))
        if (probe["scenario"], probe["method"], probe["offered_tokens_per_s"],
                probe["passed_l90"]) != (scenario, method, offered, expected_pass):
            raise ValueError(f"Invalid boundary probe {path}")
        if set(probe["seeds"]) != {"100", "101"}:
            raise ValueError(f"Invalid development seeds {path}")
        probes[str(offered)] = str(path.relative_to(ROOT))
    all_probes = sorted((HERE / "own_load_development" / scenario / method).glob("load*/probe.json"))
    search_wall = 0.0
    observed = {}
    for path in all_probes:
        probe = json.loads(path.read_text(encoding="utf-8"))
        search_wall += probe["wall_s"]
        observed[probe["offered_tokens_per_s"]] = probe["passed_l90"]
    for low, low_pass in observed.items():
        for high, high_pass in observed.items():
            if low < high and not low_pass and high_pass:
                raise ValueError(f"Observed nonmonotone pass/fail: {scenario}/{method} {low},{high}")
    return {"boundary_probes": probes, "probe_count": len(all_probes),
            "search_wall_s": search_wall,
            "observed_pass_fail": observed}


def main() -> None:
    summary = {"protocol": "own_load_75pct_of_development_L90_grid",
               "sp_physical_device_mapping": {}, "scenarios": {}}
    lines = ["# 四方法各自运行压力：探索性容量与性能对照", "",
             "70B、两种 24-GPU 拓扑、1800 秒零预热固定窗口。开发种子 100/101 "
             "选定每种方法的运行点，正式种子 0/1/2 只用于评价。提供负载计入输入与目标输出 token；"
             "吞吐只计已完成的输出 token。", "",
             "**解释边界：**各方法的正式提供负载可能不同，因此下表用于展示操作性容量和各自运行状态；"
             "不同负载下的 P95 数值不能解释成同负载延迟改善。公平的同负载比较仍见共同负载主表。", "",
             "`L90` 是预定网格中两个开发种子均正常结束且各自完成率至少 90% 的最高通过点，"
             "不是精确峰值吞吐。正式提供负载 = 0.75 × L90。`≥` 表示达到了网格上限。",
             "每格正式指标为三个完整窗口的均值 ± 样本标准差；若窗口失败，整格标注不完整，不填补数值。", ""]
    for scenario in ("single", "multi"):
        summary["sp_physical_device_mapping"][scenario] = _audit_sp_physical(scenario)
        selection_path = HERE / "own_load_development" / scenario / "selection.json"
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        if selection["scenario"] != scenario or tuple(selection["grid"]) != GRIDS[scenario]:
            raise ValueError(f"Selection protocol changed for {scenario}")
        if set(selection["methods"]) != set(METHOD_NAMES):
            raise ValueError(f"Incomplete selection for {scenario}")
        section = {"selection": str(selection_path.relative_to(ROOT)), "methods": {}}
        lines.extend([f"## {'单集群' if scenario == 'single' else '三集群'}", "",
                      "| 方法 | L90 网格点 | 正式提供负载 | 输出吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ | 完成率 % ↑ | 末端积压 ↓ | 完整窗口 |",
                      "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
        traces_at_load = {}
        for method, label in (("helix", "Helix"), ("swarm", "Swarm"),
                              ("separate", "SP"), ("rcaps_v2", "RCAPS V2")):
            choice = selection["methods"][method]
            search = verify_choice(scenario, method, choice)
            if choice["status"] == "no_grid_load_passed":
                section["methods"][method] = {
                    "selection": choice, "search": search,
                    "formal_by_seed": {}, "summary": None}
                lines.append(f"| {label} | 最低 {GRIDS[scenario][0]} 未通过 | "
                             "未运行 | — | — | — | — | — | 0/3 |")
                continue
            offered = choice["formal_offered_tokens_per_s"]
            results = {str(seed): inspect_result(
                HERE / "own_load_formal" / scenario / method / "results" /
                scenario / f"seed{seed}" / f"{method}.json",
                scenario, method, seed, offered) for seed in SEEDS}
            for seed, item in results.items():
                if item["status"] == "complete":
                    trace_key = (seed, offered)
                    prior = traces_at_load.setdefault(trace_key, item["trace_sha256"])
                    if item["trace_sha256"] != prior:
                        raise ValueError(f"Same-load trace mismatch: {scenario}/{trace_key}")
            complete = [item for item in results.values() if item["status"] == "complete"]
            metrics = None
            if len(complete) == len(SEEDS):
                metrics = {key: {"mean": mean(item["metrics"][key] for item in complete),
                                 "sample_sd": stdev(item["metrics"][key] for item in complete)}
                           for key, _ in METRICS}
            section["methods"][method] = {"selection": choice, "search": search,
                                          "formal_by_seed": results, "summary": metrics}
            capacity = f"≥{choice['l90_grid_tokens_per_s']}" if choice["status"] == "grid_ceiling" else str(choice["l90_grid_tokens_per_s"])
            metric_cells = ([f"{metrics[key]['mean']:.3f} ± {metrics[key]['sample_sd']:.3f}"
                             for key, _ in METRICS] if metrics else ["不完整"] * len(METRICS))
            lines.append("| " + " | ".join([label, capacity, f"{offered:g}",
                                            *metric_cells, f"{len(complete)}/3"]) + " |")
        summary["scenarios"][scenario] = section
        lines.extend(["", "| 开发搜索 | 探测网格点数 | 仿真墙钟累计 | 相邻较高点 |",
                      "| --- | ---: | ---: | ---: |"])
        for method, label in (("helix", "Helix"), ("swarm", "Swarm"),
                              ("separate", "SP"), ("rcaps_v2", "RCAPS V2")):
            data = section["methods"][method]
            higher = data["selection"].get("next_grid_tokens_per_s")
            lines.append(f"| {label} | {data['search']['probe_count']} | "
                         f"{data['search']['search_wall_s'] / 60:.1f} min | "
                         f"{higher if higher is not None else '网格上限'} |")
        lines.append("")
    lines.extend(["请求身份、轨迹哈希（同负载时）、布局与物理拓扑哈希、协议字段均逐结果校验；"
                  "SP 三个子集群的设备覆盖及链路参数另行核验。三种子只描述波动，不作显著性或真实集群性能声明。", ""])
    (HERE / "OWN_LOAD_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "OWN_LOAD_RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {HERE / 'OWN_LOAD_RESULTS_CN.md'}")


if __name__ == "__main__":
    main()
