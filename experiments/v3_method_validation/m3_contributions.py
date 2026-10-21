"""Append T3 paired factor contributions without changing the frozen M3 runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

from benchmarks.compare import MATCH_FIELDS, common_cohort
from experiments.m2_multistage_candidate.analysis import common_completed
from experiments.v3_release.verify import digest

from .crossover import ROOT


HERE = Path(__file__).resolve().parent
INDEX = HERE / "m3_formal_index.json"
REPORT = HERE / "m3_formal_report.md"
OUTPUT = HERE / "m3_formal_contributions.json"
MARKER = "## T3 配对贡献与完整性"
SCENARIOS = ("single", "multi")
SEEDS = (0, 1, 2)
ARMS = ("static", "queue_only", "observed_eft", "full_no_session",
        "full_no_link", "full")
EFFECTS = (
    ("KV 会话定价", "full_no_session", "full"),
    ("动态链路等待", "full_no_link", "full"),
    ("仅队列基础上的链路等待", "queue_only", "observed_eft"),
    ("全部实时状态", "static", "full"),
)
METRICS = (
    ("吞吐 token/s", "output_throughput_tokens_per_s"),
    ("P95 TTFT s", "ttft_p95_s"),
    ("P95 TPOT s", "tpot_p95_s"),
    ("完成率", "completion_fraction"),
    ("末端积压", "backlog_at_window_end"),
)
COMMON = (("共同完成 P95 TTFT s", "ttft_s"),
          ("共同完成 P95 TPOT s", "tpot_s"))


def _fmt(value):
    return "—" if value is None else f"{value:+.4f}"


def _summary(values):
    return {"mean": mean(values), "sample_sd": stdev(values),
            "by_seed": dict(zip(map(str, SEEDS), values))}


def main():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if index["protocol"] != {"loads": {"single": 700.0, "multi": 320.0},
                               "seeds": [0, 1, 2], "duration_s": 1800,
                               "warmup_s": 0, "tail_drain": False}:
        raise ValueError("T3 protocol mismatch")
    if len(index["jobs"]) != 36:
        raise ValueError(f"Expected 36 T3 jobs, found {len(index['jobs'])}")
    adapter_bytes = (HERE / "m3_state.py").read_bytes()
    canonical_bytes = adapter_bytes.replace(bytes([13, 10]), bytes([10]))
    adapter = hashlib.sha256(canonical_bytes).hexdigest()
    crlf_adapter = hashlib.sha256(
        canonical_bytes.replace(bytes([10]), bytes([13, 10]))).hexdigest()
    acceptable_adapter_hashes = {adapter, crlf_adapter}
    if index["adapter_sha256"] not in acceptable_adapter_hashes:
        raise ValueError("M3 adapter changed")
    rows = {}
    counts = {"passed": 0, "reused": 0}
    for scenario in SCENARIOS:
        for seed in SEEDS:
            matched = {}
            for arm in ARMS:
                key = f"{scenario}/seed{seed}/{arm}"
                item = index["jobs"][key]
                if item["status"] not in counts:
                    raise ValueError(f"Incomplete T3 job: {key}: {item['status']}")
                counts[item["status"]] += 1
                path = ROOT / item["source"]
                if digest(path) != item["sha256"]:
                    raise ValueError(f"Result hash mismatch: {key}")
                row = json.loads(path.read_text(encoding="utf-8"))
                if row["trace_sha256"] != item["trace_sha256"]:
                    raise ValueError(f"Trace hash mismatch: {key}")
                if (arm not in ("static", "full") and
                        row["adapter_sha256"] not in acceptable_adapter_hashes):
                    raise ValueError(f"Adapter hash mismatch: {key}")
                matched[arm] = row
            reference = matched["static"]
            for arm, row in matched.items():
                for field in MATCH_FIELDS:
                    default = 1 if field == "query_samples_schema" else None
                    if row.get(field, default) != reference.get(field, default):
                        raise ValueError(f"Unpaired {scenario}/seed{seed}/{arm}/{field}")
                common_cohort(row, reference)
            rows[scenario, seed] = matched

    output = {"protocol": index["protocol"], "jobs": counts,
              "adapter_sha256_lf": adapter,
              "adapter_sha256_crlf": crlf_adapter,
              "adapter_equivalence": "CRLF/LF normalization only",
              "scenarios": {}}
    lines = [MARKER, "",
             "以下差值一律为表中右侧变体减左侧变体；吞吐和完成率正值较好，",
             "TTFT、TPOT 与积压负值较好。P95 是各自窗口的请求 P95；",
             "共同完成 P95 只在两变体都完成的请求上分别计算后相减。",
             "三种子标准差是样本标准差，不作显著性检验。", "",
             f"索引共 36 项：passed={counts['passed']}，reused={counts['reused']}，failed=0；",
             f"M3 适配器 LF SHA256：`{adapter}`；CRLF SHA256：`{crlf_adapter}`。",
             "两种字节序列经换行规范化后内容一致；正式窗口记录的原始哈希",
             "均能从此同一内容导出。同拓扑同种子的六个变体均通过",
             "轨迹哈希与逐请求输入一致性检查。单集群种子 2 的四份中断日志",
             "已完整保存于 `runs/m3_formal/single/seed2/interrupted/`。", ""]
    for scenario in SCENARIOS:
        lines += [f"### {scenario}：方法绝对值（三种子均值 ± 样本标准差）", "",
                  "| 方法 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 末端积压 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        absolute = {}
        for arm in ARMS:
            absolute[arm] = {metric: _summary([rows[scenario, seed][arm][metric]
                                               for seed in SEEDS])
                             for _, metric in METRICS}
            values = " | ".join(
                f"{absolute[arm][metric]['mean']:.4f} ± {absolute[arm][metric]['sample_sd']:.4f}"
                for _, metric in METRICS)
            lines.append(f"| {arm} | {values} |")
        effects = {}
        for label, left, right in EFFECTS:
            seed_rows = {}
            for seed in SEEDS:
                a, b = rows[scenario, seed][left], rows[scenario, seed][right]
                paired = common_completed(a, b)
                values = {metric: b[metric] - a[metric] for _, metric in METRICS}
                for _, field in COMMON:
                    observation = paired[field]
                    values[field] = (None if observation["left_p95_s"] is None or
                                     observation["right_p95_s"] is None else
                                     observation["right_p95_s"] - observation["left_p95_s"])
                seed_rows[str(seed)] = {"common_completed_count": paired["count"],
                                        "delta": values,
                                        "common_p95_sample_counts": {
                                            field: paired[field]["count"] for _, field in COMMON}}
            metric_summary = {}
            for _, metric in (*METRICS, *COMMON):
                values = [seed_rows[str(seed)]["delta"][metric] for seed in SEEDS]
                if any(value is None for value in values):
                    raise ValueError(f"Missing paired P95: {scenario}/{label}/{metric}")
                metric_summary[metric] = _summary(values)
            effects[label] = {"left": left, "right": right,
                              "seeds": seed_rows, "summary": metric_summary}
        output["scenarios"][scenario] = {"absolute": absolute, "effects": effects}
        lines += ["", f"### {scenario}：状态项贡献（{scenario}，右侧−左侧）", "",
                  "| 对照 | 种子 | 吞吐 Δ | TTFT Δ s | TPOT Δ s | 完成率 Δ | 积压 Δ | 共同完成数 | 共同 TTFT Δ s | 共同 TPOT Δ s |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for label, left, right in EFFECTS:
            effect = effects[label]
            for seed in SEEDS:
                record = effect["seeds"][str(seed)]
                lines.append(f"| {label} ({right}−{left}) | {seed} | "
                             f"{' | '.join(_fmt(record['delta'][metric]) for _, metric in METRICS)} | "
                             f"{record['common_completed_count']} | "
                             f"{' | '.join(_fmt(record['delta'][field]) for _, field in COMMON)} |")
            values = " | ".join(
                f"{effect['summary'][metric]['mean']:+.4f} ± "
                f"{effect['summary'][metric]['sample_sd']:.4f}"
                for _, metric in METRICS)
            common_count = mean(effect["seeds"][str(seed)]["common_completed_count"]
                                for seed in SEEDS)
            common_values = " | ".join(
                f"{effect['summary'][field]['mean']:+.4f} ± "
                f"{effect['summary'][field]['sample_sd']:.4f}"
                for _, field in COMMON)
            lines.append(f"| {label} ({right}−{left}) | 均值 ± SD | {values} | "
                         f"{common_count:.1f} | {common_values} |")
        lines.append("")
    lines += ["## 变体解释与确定性审计限制", "",
              "代码核查发现 `observed_eft` 与 `full_no_session` 在当前实现下等价：",
              "`rcaps/v3/queue_cost.py:19–20` 已把 `include_committed` 和",
              "`include_session_round` 设为 False；两变体都让",
              "`_active_session_counts` 返回空计数，且使用相同链路快照。",
              "六个拓扑×种子窗口的吞吐、延迟、完成率、路径计数与逐请求样本均相同。",
              "因此不能把两者差值解释为已承诺路径工作量的独立贡献。", "",
              "以上为首次完整 16 窗口的描述性结果。一次额外复跑出现 KV Cache 异常及",
              "进程池中断；单独隔离的同配置窗口随后成功，说明该故障尚不能视为",
              "每次必现。复跑不能提供 16 对完整独立窗口，因此暂缓将状态项贡献",
              "写成已验证的机制结论。环境、逐项对比和保留的异常文件详见",
              "`T3_DETERMINISM_AUDIT_CN.md`。", ""]
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    previous = REPORT.read_text(encoding="utf-8")
    previous = previous.split("\n" + MARKER)[0].rstrip() + "\n\n"
    REPORT.write_text(previous + "\n".join(lines), encoding="utf-8")
    print(f"T3 contributions appended: {counts['passed']} passed, {counts['reused']} reused")


if __name__ == "__main__":
    main()
