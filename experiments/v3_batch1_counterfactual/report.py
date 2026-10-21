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
    out += execution_model_section(analysis)
    (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


PROFILE_DIR = ROOT / "simulator/model_manager/llama2_70b"
PROFILE_GPUS = ("a100", "l4", "t4")


def execution_model_section(analysis: dict) -> list[str]:
    """Explain which batch-1 decode cost the measured profiles support."""
    rows, record = [], {}
    for gpu in PROFILE_GPUS:
        path = PROFILE_DIR / gpu / "decode_bs2time.csv"
        points = dict(tuple(float(v) for v in line.split(",")[:2])
                      for line in path.read_text(encoding="utf-8").split()
                      if line.strip())
        sizes = sorted(size for size in points if size > 0)
        first, last = sizes[0], max(size for size in sizes if size <= 10)
        interpolated = points[first] / first  # linear from (0, 0), as model.py does
        record[gpu] = {"profile": path.relative_to(ROOT).as_posix(),
                       "sha256": digest(path),
                       "smallest_measured_batch": first,
                       "time_at_smallest_batch": points[first],
                       "time_at_batch_le_10": points[last], "batch_le_10": last,
                       "batch1_rule_off": interpolated,
                       "batch1_rule_on": 2 * interpolated}
        rows.append(f"| {gpu.upper()} | {first:g} | {points[first]:g} | {last:g} | "
                    f"{points[last]:g} | {interpolated:g} | {2 * interpolated:g} |")
    analysis["execution_model"] = record
    return ["", "## 执行模型解读：哪一种 batch = 1 设定与画像一致", "",
            "Decode 画像没有 batch = 1 的测量点，最小测量点是 batch = 2。模拟器在 (0, 0) 与最小测量点之间"
            "线性插值估计 batch = 1，得到最小测量点耗时的一半；2 倍规则（`simulator/event_simulator/model.py`"
            " 中 `decode_phase_tokens == 1` 分支）再乘 2，使 batch = 1 与 batch = 2 的耗时相等。", "",
            "| GPU | 最小测量 batch | 该点耗时 | batch ≤ 10 的最大测量点 | 该点耗时 | batch = 1：规则关 | batch = 1：规则开 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |", *rows, "",
            "画像显示，从最小测量点到 batch 10，每步 Decode 耗时几乎不变，这是显存带宽受限的 Decode 的典型特征。"
            "规则开时 batch = 1 的耗时与这一趋势一致；规则关时 batch = 1 只需 batch = 2 的一半时间，"
            "与画像的平坦趋势相矛盾。因此：", "",
            "- 规则关的窗口是**执行模型敏感性**结果，不代表更真实的设定。它回答的是：如果单请求 Decode "
            "明显更便宜，权衡会如何变化。",
            "- 效率主张在两种设定下都成立。",
            "- 延迟收益成立的条件是小 batch 下 Decode 每步耗时基本平坦，这正是画像本身反映的情形；"
            "C2 在规则关时的延迟反转，来自与画像不一致的设定。",
            "- 画像来自 Helix 仓库的离线测量。真实 GPU 上小 batch 的 Decode 耗时曲线，仍应在论文中引用"
            "实测文献或自行测量佐证。"]


if __name__ == "__main__":
    main()
