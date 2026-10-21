"""Paired report: GPU waste of full-DAG routing with the doubling rule off."""

from __future__ import annotations

import json
from statistics import mean, stdev

from experiments.v3_batch1_counterfactual.run import CELLS, CONDITIONS, HERE
from experiments.v3_cycle_pricing.run import FORMAL_SEEDS, ROOT, digest, read, rel

RULE_ON = {
    ("C1_single", "v3"): "experiments/v3_cycle_pricing/runs/formal/C1_single/v3_seed{seed}.json",
    ("C1_single", "gated"): "experiments/v3_gated_pathspace/runs/formal/C1_single/gated_seed{seed}.json",
    ("C2", "v3"): "experiments/v3_gated_generalization/runs/formal/C2/v3_seed{seed}.json",
    ("C2", "gated"): "experiments/v3_gated_generalization/runs/formal/C2/gated_seed{seed}.json",
}


def gpu_per_token(row: dict) -> float:
    return sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]


def batch(row: dict) -> str:
    b = row.get("decode_batches")
    return f"{b['mean_batch']:.2f}" if b else "—"


def sd(values: list[float], pct: bool = False) -> str:
    m, s = mean(values), stdev(values)
    return f"{m:+.2%} ± {s:.2%}" if pct else f"{m:+.4f} ± {s:.4f}"


def main() -> None:
    analysis = {"protocol_sha256": digest(HERE / "protocol.json"), "inputs": {},
                "failures": [], "pools": {}}
    out = ["# 单请求 Decode 2 倍规则反事实", "",
           "协议见 `protocol.json`（先于正式窗口提交）。在运行进程内关闭模拟器对单请求 Decode 批的 2 倍计时，"
           "其余（布局、轨迹、路由代价、门控规则）不变。种子 0/1/2，1800 秒，零预热，不排空。"
           "主指标为每个输出 token 的 GPU 忙碌秒数。", "",
           "| 池 | 种子 | 规则 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 平均 Decode 批 | GPU 秒/输出 token |",
           "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    rows = {}
    for pool in CONDITIONS:
        for seed in FORMAL_SEEDS:
            for cell in CELLS:
                path = HERE / "runs/formal" / pool / f"{cell}_seed{seed}.json"
                if path.with_suffix(".failure.json").exists():
                    analysis["failures"].append(rel(path.with_suffix(".failure.json")))
                if path.exists():
                    rows[(pool, seed, cell, "off")] = read(path)
                    analysis["inputs"][rel(path)] = digest(path)
                on = ROOT / RULE_ON[(pool, cell)].format(seed=seed)
                rows[(pool, seed, cell, "on")] = read(on)
                analysis["inputs"][rel(on)] = digest(on)
            for rule in ("on", "off"):
                for cell in CELLS:
                    row = rows.get((pool, seed, cell, rule))
                    if row is None:
                        continue
                    out.append(f"| {pool} | {seed} | {'开' if rule == 'on' else '关'} | {cell} | "
                               f"{row['output_throughput_tokens_per_s']:.3f} | {row['ttft_p95_s']:.3f} | "
                               f"{row['tpot_p95_s']:.3f} | {row['completion_fraction']:.3f} | {batch(row)} | "
                               f"{gpu_per_token(row):.4f} |")
    out += ["", "## 门控相对完整 DAG 的变化（门控 − V3）/ V3", "",
            "| 池 | 种子 | GPU 秒/token（规则关） | GPU 秒/token（规则开） | 保留比例 | 吞吐（关） | P95 TPOT（关） | P95 TTFT（关） |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    verdict = []
    for pool in CONDITIONS:
        per = []
        for seed in FORMAL_SEEDS:
            if (pool, seed, "v3", "off") not in rows or (pool, seed, "gated", "off") not in rows:
                continue
            rel_change = lambda rule, f: f(rows[(pool, seed, "gated", rule)]) / f(rows[(pool, seed, "v3", rule)]) - 1
            item = {"seed": seed,
                    "gpu_off": rel_change("off", gpu_per_token),
                    "gpu_on": rel_change("on", gpu_per_token),
                    "throughput_off": rel_change("off", lambda r: r["output_throughput_tokens_per_s"]),
                    "tpot_off": rel_change("off", lambda r: r["tpot_p95_s"]),
                    "ttft_off": rel_change("off", lambda r: r["ttft_p95_s"])}
            item["retained"] = item["gpu_off"] / item["gpu_on"] if item["gpu_on"] else float("nan")
            per.append(item)
            out.append(f"| {pool} | {seed} | {item['gpu_off']:+.2%} | {item['gpu_on']:+.2%} | "
                       f"{item['retained']:.0%} | {item['throughput_off']:+.2%} | {item['tpot_off']:+.2%} | "
                       f"{item['ttft_off']:+.2%} |")
        if len(per) >= 2:
            out.append(f"| {pool} | 均值 ± SD | {sd([p['gpu_off'] for p in per], True)} | "
                       f"{sd([p['gpu_on'] for p in per], True)} | {mean(p['retained'] for p in per):.0%} | "
                       f"{sd([p['throughput_off'] for p in per], True)} | {sd([p['tpot_off'] for p in per], True)} | "
                       f"{sd([p['ttft_off'] for p in per], True)} |")
        analysis["pools"][pool] = per
    complete = all(len(analysis["pools"].get(p, [])) == len(FORMAL_SEEDS) for p in CONDITIONS) \
        and not analysis["failures"]
    if complete:
        all_seeds = [p for pool in CONDITIONS for p in analysis["pools"][pool]]
        if all(p["gpu_off"] <= -0.20 for p in all_seeds):
            decision = "efficiency_claim_stands"
            text = "效率主张成立：两个池的每个种子，门控的 GPU 秒/token 都比完整 DAG 低至少 20%"
        elif all(p["gpu_off"] < 0 for p in all_seeds):
            decision = "partially_artefact"
            text = "效率主张成立但幅度变小：每个种子都更低，但至少一个种子降幅不足 20%"
        else:
            decision = "artefact"
            text = "GPU 浪费主要来自 2 倍规则，不能提出效率主张"
        analysis["decision"] = decision
        out += ["", "## 预注册判定", "", f"**{text}**（`{decision}`）。"]
    else:
        out += ["", "## 预注册判定", "", "正式窗口未全部完成或有失败，暂不判定。"]
    if analysis["failures"]:
        out += ["", "失败窗口（保留，不重跑）：" + "、".join(analysis["failures"])]
    (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
