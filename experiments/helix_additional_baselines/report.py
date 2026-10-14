"""Audit Swarm/SP formal runs and summarize their paired V2 comparisons."""

from __future__ import annotations

import hashlib
import json
from configparser import ConfigParser
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.layout import scenario as physical_scenario
from benchmarks.registry import METHODS

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REFERENCE = ROOT / "experiments" / "v2_method_ablation" / "runs"
RUNS = HERE / "runs"
METRICS = (
    ("output_throughput_tokens_per_s", "吞吐 (输出 token/s)", "higher"),
    ("ttft_p95_s", "P95 TTFT (s)", "lower"),
    ("tpot_p95_s", "P95 TPOT (s)", "lower"),
    ("completion_fraction", "完成率 (%)", "higher"),
    ("backlog_at_window_end", "末端积压", "lower"),
)


def _read(path: Path, scenario: str, seed: int, method: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    expected = {"system": method, "scenario": scenario, "seed": seed,
                "offered_tokens_per_s": 700.0 if scenario == "single" else 320.0,
                "duration_s": 1800, "warmup_s": 0,
                "evaluation_protocol": "fixed_window_no_tail_drain",
                "query_samples_schema": 1}
    solution, cluster = METHODS[method].layout(scenario, ROOT)
    expected["solution_sha256"] = hashlib.sha256(solution.read_bytes()).hexdigest()
    expected["sim_cluster_sha256"] = hashlib.sha256(cluster.read_bytes()).hexdigest()
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f"Unexpected {key}: {path}")
    if len(record.get("query_samples", {})) != record["arrivals"]:
        raise ValueError(f"Incomplete query samples: {path}")
    return record


def _same_trace(a: dict, b: dict) -> None:
    for field in MATCH_FIELDS:
        if a.get(field) != b.get(field):
            raise ValueError(f"Unpaired {field}: {a['system']}/{b['system']}")
    common_cohort(a, b)


def _summarize(records: list[dict]) -> dict:
    result = {}
    for key, _, _ in METRICS:
        values = [record[key] * (100 if key == "completion_fraction" else 1)
                  for record in records]
        result[key] = {"mean": mean(values), "sample_sd": stdev(values),
                       "by_seed": dict(zip((0, 1, 2), values))}
    return result


def _paired(main: list[dict], baseline: list[dict]) -> dict:
    result = {}
    for key, _, direction in METRICS:
        gains = []
        for a, b in zip(main, baseline):
            if b[key] <= 0:
                raise ValueError(f"Nonpositive baseline {key}")
            gains.append(100 * (a[key] / b[key] - 1 if direction == "higher"
                                else 1 - a[key] / b[key]))
        result[key] = {"mean": mean(gains), "sample_sd": stdev(gains),
                       "by_seed": dict(zip((0, 1, 2), gains))}
    result["common_cohort_by_seed"] = [common_cohort(a, b)
                                       for a, b in zip(main, baseline)]
    return result


def _audit_sp_physical(scenario: str) -> dict:
    """Check each artifact SP subcluster is an exact typed subgraph."""
    full_path = physical_scenario(scenario)[0]
    full = ConfigParser()
    full.read(full_path)
    manifest_path = HERE / "layouts" / f"sp_{scenario}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping = {}
    for group, gpu_type in (("a100", "A100"), ("l4", "L4"), ("t4", "T4")):
        entry = manifest["groups"][group]
        sub_path = ROOT / entry["physical"]["path"]
        sub = ConfigParser()
        sub.read(sub_path)
        ids = [index for index in range(24)
               if full[f"ComputeNode-{index}"]["type"] == gpu_type]
        if len(ids) != int(sub["NodeNames"]["total_compute_nodes"]):
            raise ValueError(f"SP {scenario}/{group} device count mismatch")
        for local, actual in enumerate(ids):
            for left, right in ((f"Link-source-{local}", f"Link-source-{actual}"),
                                (f"Link-{local}-sink", f"Link-{actual}-sink")):
                for field in ("bandwidth", "latency"):
                    if sub[left][field] != full[right][field]:
                        raise ValueError(f"SP {scenario}/{group} {left} {field} mismatch")
            for later in range(local + 1, len(ids)):
                for field in ("bandwidth", "latency"):
                    if sub[f"Link-{local}-{later}"][field] != full[
                            f"Link-{actual}-{ids[later]}"][field]:
                        raise ValueError(f"SP {scenario}/{group} internal {field} mismatch")
        mapping[group] = ids
    if sorted(index for ids in mapping.values() for index in ids) != list(range(24)):
        raise ValueError("SP subclusters do not partition all 24 GPUs")
    return mapping


def main() -> None:
    output = {"protocol": "70B, 24 GPUs, offered 700/320 token/s, seeds 0/1/2, "
                          "1800 s, zero warmup, no tail drain",
              "methods": {}, "source_sha256": {}}
    lines = ["# Helix 其他在线基线：Swarm 与 Separate Pipelines",
             "", "原始 Helix artifact 的两个在线对照是 Swarm 与 Separate Pipelines（SP）。"
             "本实验沿用 V2 主表的两种 24-GPU 拓扑、70B、官方共同负载、种子 0/1/2、"
             "1800 秒零预热固定窗口。", "",
             "**适配边界。**Helix artifact 给 Swarm 和 SP 的原始输入强度较低；在当前共同负载下，"
             "两者的原始调度都可能触发 KV 容量断言。这里的 Swarm 和 SP 保留原布局与调度选择逻辑，"
             "在源端加入容量准入保护，因此应标为“容量安全适配版”，不能当作原论文图中的原始数值。"
             "保护使用仿真轨迹给定的目标输出长度作为预留上界，实际系统需要可用的长度上界。"
             "SP 还按 artifact 中各子集群的负载比例，把同一全局请求轨迹确定性分给三套独立流水线；"
             "每个请求只进入一套，三套结果按原请求 ID 合并。", ""]
    for scenario in ("single", "multi"):
        output.setdefault("sp_physical_device_mapping", {})[scenario] = _audit_sp_physical(scenario)
        rows = {}
        for method in ("rcaps_v2", "helix", "swarm", "separate"):
            paths = [(REFERENCE if method in ("rcaps_v2", "helix") else RUNS) /
                     scenario / f"seed{seed}" / f"{method}.json" for seed in (0, 1, 2)]
            if not all(path.is_file() for path in paths):
                missing = [str(path) for path in paths if not path.is_file()]
                raise FileNotFoundError(f"Incomplete formal windows: {missing}")
            rows[method] = [_read(path, scenario, seed, method)
                            for seed, path in enumerate(paths)]
            for path in paths:
                output["source_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                    path.read_bytes()).hexdigest()
        for method in ("helix", "swarm", "separate"):
            for a, b in zip(rows["rcaps_v2"], rows[method]):
                _same_trace(a, b)
        output["methods"][scenario] = {
            method: {"absolute": _summarize(records),
                     **({"v2_paired": _paired(rows["rcaps_v2"], records)}
                        if method != "rcaps_v2" else {}),
                     "capacity_guard_block_events_by_seed": [
                         record.get("capacity_guard_block_events") for record in records],
                     "sp_component_guard_events_by_seed": [
                         {group: part.get("capacity_guard_block_events")
                          for group, part in record["sp_components"].items()}
                         if method == "separate" else None for record in records]}
            for method, records in rows.items()}
        lines.extend([f"## {'单集群' if scenario == 'single' else '三集群'}", "",
                      "每格为三个正式种子的均值 ± 样本标准差；P95 是逐种子 P95 的均值。", "",
                      "| 方法 | 吞吐 ↑ | P95 TTFT ↓ | P95 TPOT ↓ | 完成率 % ↑ | 积压 ↓ |",
                      "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for method, label in (("helix", "Helix"), ("swarm", "Swarm（容量安全）"),
                              ("separate", "SP（容量安全）"), ("rcaps_v2", "RCAPS V2")):
            values = output["methods"][scenario][method]["absolute"]
            cells = [f"{values[key]['mean']:.3f} ± {values[key]['sample_sd']:.3f}"
                     for key, _, _ in METRICS]
            lines.append("| " + label + " | " + " | ".join(cells) + " |")
        lines.extend(["", "| V2 相对基线 | 吞吐增加 | TTFT 降低 | TPOT 降低 |",
                      "| --- | ---: | ---: | ---: |"])
        for method, label in (("helix", "Helix"), ("swarm", "Swarm（容量安全）"),
                              ("separate", "SP（容量安全）")):
            values = output["methods"][scenario][method]["v2_paired"]
            cells = [f"{values[key]['mean']:+.2f} ± {values[key]['sample_sd']:.2f}%"
                     for key, _, _ in METRICS[:3]]
            lines.append("| " + label + " | " + " | ".join(cells) + " |")
        lines.extend(["", "共同可观测请求的尾延迟（两方法在窗口内均已观察到该指标的同一批请求）：", "",
                      "| V2 与基线 | 共同 TTFT 请求数 | V2 / 基线 P95 TTFT (s) | 共同 TPOT 请求数 | V2 / 基线 P95 TPOT (s) |",
                      "| --- | ---: | ---: | ---: | ---: |"])
        for method, label in (("helix", "Helix"), ("swarm", "Swarm（容量安全）"),
                              ("separate", "SP（容量安全）")):
            cohorts = output["methods"][scenario][method]["v2_paired"]["common_cohort_by_seed"]
            cells = []
            for key in ("ttft_s", "tpot_s"):
                counts = [cohort[key]["both_observed"] for cohort in cohorts]
                main = [cohort[key]["main_p95_s"] for cohort in cohorts]
                base = [cohort[key]["baseline_p95_s"] for cohort in cohorts]
                if any(value is None for value in main + base):
                    raise ValueError(f"No common {key} cohort: {scenario}/{method}")
                cells.extend((f"{mean(counts):.1f} ± {stdev(counts):.1f}",
                              f"{mean(main):.3f} ± {stdev(main):.3f} / "
                              f"{mean(base):.3f} ± {stdev(base):.3f}"))
            lines.append("| " + label + " | " + " | ".join(cells) + " |")
        lines.append("")
    lines.extend(["三种子仅用于描述配对波动，不作统计显著性或真实集群性能声明。",
                  "失败尝试的日志留在 `runs/`，不填补完整窗口指标。", ""])
    (HERE / "summary.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {HERE / 'RESULTS_CN.md'}")


if __name__ == "__main__":
    main()
