"""Audit reused formal records and write the V2 whole-method ablation report."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from statistics import mean, stdev

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.registry import METHODS
from benchmarks.run import ROOT, output_file
from rcaps.placement.adaptive import intervals
from rcaps.placement.partition import scenario as physical_scenario
from rcaps.placement.topology import TopologyModel


HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
HISTORICAL = ROOT / "benchmarks" / "runs"
OLD = ("rcaps_v2", "helix", "rcaps_v2_fixed_structure")
NEW = ("rcaps_v2_capacity_only", "rcaps_v2_static_routes")
ALL = OLD + NEW
BASELINES = ("helix", "rcaps_v2_capacity_only",
             "rcaps_v2_fixed_structure", "rcaps_v2_static_routes")
SEEDS = (0, 1, 2)
SCENARIOS = ("single", "multi")
METRICS = (("output_throughput_tokens_per_s", "吞吐 token/s", True),
           ("ttft_p95_s", "P95 TTFT s", False),
           ("tpot_p95_s", "P95 TPOT s", False),
           ("completion_fraction", "完成率", True),
           ("backlog_at_window_end", "窗口末积压", False))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_layout(scenario: str, method: str) -> dict:
    solution, sim_cluster = METHODS[method].layout(scenario, ROOT)
    if not solution.is_file() or not sim_cluster.is_file():
        raise FileNotFoundError(f"Missing {method} layout: {solution}")
    record = {"solution_sha256": digest(solution),
              "sim_cluster_sha256": digest(sim_cluster)}
    if method != "helix":
        placement = load(solution.parent / "placement.json")
        cluster, _ = physical_scenario(scenario)
        model = TopologyModel(cluster)
        state = {"stem": placement["stem"],
                 "branches": placement["branches"],
                 "prefix_layers": placement["prefix_layers"],
                 "lengths": {int(node): end - start
                             for node, (start, end) in placement["intervals"].items()}}
        actual = {str(node): list(span)
                  for node, span in intervals(model, state).items()}
        if actual != placement["intervals"]:
            raise ValueError(f"Placement interval mismatch: {scenario}/{method}")
        record.update({"physical_cluster_sha256": digest(cluster),
                       "placement_sha256": digest(solution.parent / "placement.json"),
                       "stem": placement["stem"],
                       "prefix_layers": placement["prefix_layers"],
                       "suffix_count": len(placement["branches"]),
                       "gpu_count": len(actual)})
    return record


def validate_pair(candidate: dict, reference: dict, name: str) -> dict:
    if any(candidate.get(field) != reference.get(field) for field in MATCH_FIELDS):
        raise ValueError(f"Unpaired protocol or trace: {name}")
    return common_cohort(candidate, reference)


def prepare() -> None:
    manifest = {"purpose": "audited byte-for-byte reuse of existing formal records",
                "historical_root": str(HISTORICAL), "records": [], "layouts": {},
                "code_sha256": {
                    name: digest(HERE / name) for name in
                    ("capacity_only.py", "adapters.py", "report.py")}}
    for scenario in SCENARIOS:
        manifest["layouts"][scenario] = {
            method: validate_layout(scenario, method) for method in ALL}
        if (manifest["layouts"][scenario]["rcaps_v2"]["solution_sha256"] !=
                manifest["layouts"][scenario]["rcaps_v2_static_routes"]["solution_sha256"] or
                manifest["layouts"][scenario]["rcaps_v2"]["sim_cluster_sha256"] !=
                manifest["layouts"][scenario]["rcaps_v2_static_routes"]["sim_cluster_sha256"]):
            raise ValueError(f"M3 layout differs from V2: {scenario}")
        for seed in SEEDS:
            baseline = load(output_file(HISTORICAL, scenario, seed, "rcaps_v2"))
            for method in OLD:
                source = output_file(HISTORICAL, scenario, seed, method)
                record = load(source)
                expected = manifest["layouts"][scenario][method]
                if record["system"] != method or any(
                        record.get(field) != expected[field]
                        for field in ("solution_sha256", "sim_cluster_sha256")):
                    raise ValueError(f"Historical layout identity mismatch: {source}")
                validate_pair(baseline, record, f"{scenario}/seed{seed}/{method}")
                destination = output_file(RUNS, scenario, seed, method)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if digest(destination) != digest(source):
                        raise ValueError(f"Existing reused record differs: {destination}")
                else:
                    shutil.copyfile(source, destination)
                manifest["records"].append({"scenario": scenario, "seed": seed,
                                            "method": method, "source": str(source),
                                            "destination": str(destination),
                                            "sha256": digest(source)})
    (HERE / "reuse_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Audited and reused {len(manifest['records'])} formal records")


def percent(main: float, baseline: float, higher: bool) -> float | None:
    if baseline <= 0:
        return None
    return 100 * ((main / baseline - 1) if higher else (1 - main / baseline))


def fmt(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def report() -> None:
    if not (HERE / "reuse_manifest.json").is_file():
        raise FileNotFoundError("Run report --prepare first")
    manifest = load(HERE / "reuse_manifest.json")
    result = {"protocol": "70B, two 24-GPU topologies, official loads, 1800 s, "
                          "zero warmup, seeds 0/1/2, no tail drain",
              "reuse_manifest_sha256": digest(HERE / "reuse_manifest.json"),
              "scenarios": {}}
    lines = ["# RCAPS V2 三方法整方法消融（导师汇报）", "",
             "70B，24 GPU；single 700、multi 320 offered token/s；种子 0/1/2；"
             "1800 秒、零预热、无尾部排空。所有指标为仿真正式窗口。", "",
             "M1 为容量与连通性放置对照；M2 为既有固定结构 V2；M3 为同一 V2 布局上的"
             "固定合法路径轮转与逐请求传输。三项都是其他方法存在时的条件消融，差额不可相加。", ""]
    for scenario in SCENARIOS:
        records = {method: [load(output_file(RUNS, scenario, seed, method))
                            for seed in SEEDS] for method in ALL}
        expected = manifest["layouts"][scenario]
        cohorts = {}
        for method in ALL:
            for seed, record in zip(SEEDS, records[method]):
                if record.get("system") != method or any(
                        record.get(field) != expected[method][field]
                        for field in ("solution_sha256", "sim_cluster_sha256")):
                    raise ValueError(f"Result layout mismatch: {scenario}/seed{seed}/{method}")
                if record.get("duration_s") != 1800 or record.get("warmup_s") != 0:
                    raise ValueError(f"Incomplete protocol: {scenario}/seed{seed}/{method}")
        for method in BASELINES:
            cohorts[method] = [validate_pair(main, other,
                                f"{scenario}/seed{seed}/{method}")
                               for seed, main, other in zip(
                                   SEEDS, records["rcaps_v2"], records[method])]
        scenario_result = {"raw_by_method": {
            method: [{"seed": record["seed"],
                      "trace_sha256": record["trace_sha256"],
                      "solution_sha256": record["solution_sha256"],
                      "sim_cluster_sha256": record["sim_cluster_sha256"],
                      "arrivals": record["arrivals"],
                      "first_tokens_in_window": record["first_tokens_in_window"],
                      "queries_with_tpot_samples": record["queries_with_tpot_samples"],
                      **{field: record[field] for field, _, _ in METRICS}}
                     for record in records[method]]
            for method in ALL}, "pairs": {}}
        lines += [f"## {scenario}", "", "### 放置结构与搜索开销", "",
                  "| 放置 | 共享 GPU | 前缀层数 | 后缀数 | 候选评价数 | 规划秒数 |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"]
        for method in ("rcaps_v2", "rcaps_v2_fixed_structure",
                       "rcaps_v2_capacity_only"):
            solution, _ = METHODS[method].layout(scenario, ROOT)
            placement = load(solution.parent / "placement.json")
            lines.append("| " + " | ".join([
                method, ",".join(str(node) for node in placement["stem"]),
                str(placement["prefix_layers"]), str(len(placement["branches"])),
                str(placement["candidate_evaluations"]),
                fmt(placement["planning_s"])]) + " |")
        lines += ["", "M3 对照使用与 V2 字节相同的布局文件；表中不重复列出。",
                  "", "### 逐种子原值", "",
                  "| 种子 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 |",
                  "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for seed_index, seed in enumerate(SEEDS):
            for method in ALL:
                record = records[method][seed_index]
                lines.append("| " + " | ".join([
                    str(seed), method,
                    fmt(record["output_throughput_tokens_per_s"], 3),
                    fmt(record["ttft_p95_s"], 3),
                    fmt(record["tpot_p95_s"], 3),
                    fmt(record["completion_fraction"], 3),
                    str(record["backlog_at_window_end"])]) + " |")
        lines += ["", "### 执行路径与资源等待诊断", "",
                  "| 方法 | 种子 | 实际路径种类 | GPU 排队 request-s/到达 | 出站等待 request-s/到达 |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for method in ("rcaps_v2", "rcaps_v2_capacity_only",
                       "rcaps_v2_fixed_structure", "rcaps_v2_static_routes"):
            for seed, record in zip(SEEDS, records[method]):
                arrivals = record["arrivals"]
                lines.append("| " + " | ".join([
                    method, str(seed), str(len(record["route_counts"])),
                    fmt(sum(record["gpu_queue_request_s"].values()) / arrivals, 3),
                    fmt(sum(record["outbound_wait_request_s"].values()) / arrivals, 3)])
                    + " |")
        lines += ["", "等待为请求累计时间的归一化值；出站等待包含调度与 NIC 资源等待，"
                  "不能称为纯物理链路排队。路径种类不能单独解释性能差异。", ""]
        lines += ["", "### V2 对各对照的配对改善", "",
                  "| 对照 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for method in BASELINES:
            pair = {"by_seed": {}, "mean": {}, "sample_sd": {},
                    "common_cohort_by_seed": cohorts[method]}
            for field, _, higher in METRICS:
                values = [percent(main[field], other[field], higher)
                          for main, other in zip(records["rcaps_v2"], records[method])]
                pair["by_seed"][field] = dict(zip(SEEDS, values))
                pair["mean"][field] = mean(values) if all(v is not None for v in values) else None
                pair["sample_sd"][field] = stdev(values) if all(v is not None for v in values) else None
            scenario_result["pairs"][method] = pair
            lines.append("| " + method + " | " + " | ".join(
                "—" if pair["mean"][field] is None else
                f"{pair['mean'][field]:+.2f} ± {pair['sample_sd'][field]:.2f}%"
                for field, _, _ in METRICS) + " |")
        lines += ["", "### 共同可观测请求的 P95", "",
                  "| 对照 | 种子 | TTFT 共同数 | V2 / 对照 TTFT s | TPOT 共同数 | V2 / 对照 TPOT s |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for method in BASELINES:
            for seed, cohort in zip(SEEDS, cohorts[method]):
                ttft, tpot = cohort["ttft_s"], cohort["tpot_s"]
                lines.append(f"| {method} | {seed} | {ttft['both_observed']} | "
                             f"{fmt(ttft['main_p95_s'], 3)} / {fmt(ttft['baseline_p95_s'], 3)} | "
                             f"{tpot['both_observed']} | "
                             f"{fmt(tpot['main_p95_s'], 3)} / {fmt(tpot['baseline_p95_s'], 3)} |")
        lines.append("")
        result["scenarios"][scenario] = scenario_result
    lines += ["## 解释边界", "",
              "M1 对照改变了资源感知的构造、预筛与评价，因此可能同时改变选出的共享复制结构；"
              "它检验完整资源感知放置方法，不单独证明事件图的贡献。",
              "M3 对照同时移除实时 DAG 选路与 Decode 传输合并；不将差额归因于某一内部机制。",
              "种子 1 曾参与开发；三个种子只描述配对波动，不作统计显著性或真实集群性能声明。", ""]
    (HERE / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (HERE / "REPORT_CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {HERE / 'REPORT_CN.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if not (args.prepare or args.report):
        parser.error("Select --prepare and/or --report")
    if args.prepare:
        prepare()
    if args.report:
        report()


if __name__ == "__main__":
    main()
