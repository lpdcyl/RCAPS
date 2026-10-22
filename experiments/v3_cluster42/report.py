"""Paired report and pre-registered verdicts for the 42-node cluster."""

from __future__ import annotations

import json
import sys
from statistics import mean, stdev

from experiments.v3_cluster42.run import HERE, PHYSICAL
from experiments.v3_cycle_pricing.report import common_p95
from experiments.v3_cycle_pricing.run import FORMAL_SEEDS, digest, read, rel


def gpu(row: dict) -> float:
    return row["gpu_seconds_per_output_token"]


def ms(values: list[float], pct: bool = True) -> str:
    if len(values) < 2:
        return "—"
    m, s = mean(values), stdev(values)
    return f"{m:+.2%} ± {s:.2%}" if pct else f"{m:+.4f} ± {s:.4f}"


def main() -> None:
    protocol = read(HERE / "protocol.json")
    cells = protocol["formal"]["cells"]
    analysis = {"protocol_sha256": digest(HERE / "protocol.json"),
                "physical_sha256": digest(PHYSICAL), "inputs": {}, "failures": [],
                "status": {}, "comparisons": {}, "verdicts": {}}
    rows = {}
    out = ["# 42 节点高异构集群：V3 核心实验", "",
           "协议见 `protocol.json`（先于正式窗口提交）。种子 0/1/2，1800 秒，零预热，不排空。"
           "`_off` 表示关闭模拟器单请求 Decode 2 倍计时的反事实。三个种子不作显著性检验。", "",
           "## 布局", ""]
    layout = read(HERE / "layout/placement.json")
    segments = layout["state"]["segments"]
    out.append("V3（冻结 M2 搜索，`plan.py`）：" + "；".join(
        f"层 {s['start']}–{s['end'] - 1} × {len(s['replicas'])} 副本" for s in segments) +
        f"，规划耗时 {layout.get('planning_wall_s', float('nan')):.0f} 秒。")
    out += ["", "## 逐窗口", "",
            "| 负载 | 种子 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | 平均 Decode 批 | GPU 秒/token | 路径数 |",
            "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for load, names in cells.items():
        for seed in FORMAL_SEEDS:
            for cell in names:
                path = HERE / "runs/formal" / f"load{float(load):g}" / f"{cell}_seed{seed}.json"
                failure = path.with_suffix(".failure.json")
                if path.exists() and failure.exists():
                    raise ValueError(f"Both result and failure exist: {path}")
                state = "passed" if path.exists() else "failed" if failure.exists() else "missing"
                analysis["status"][f"{load}/{cell}/seed{seed}"] = state
                if failure.exists():
                    analysis["failures"].append(rel(path.with_suffix(".failure.json")))
                if not path.exists():
                    continue
                row = read(path)
                analysis["inputs"][rel(path)] = digest(path)
                rows[(load, seed, cell)] = row
                batch = row.get("decode_batches", {}).get("mean_batch")
                out.append(f"| {load} | {seed} | {cell} | {row['output_throughput_tokens_per_s']:.2f} | "
                           f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                           f"{row['completion_fraction']:.3f} | {row['backlog_at_window_end']} | "
                           f"{f'{batch:.2f}' if batch else '—'} | {gpu(row):.4f} | {len(row['route_counts'])} |")

    def compare(load: str, left: str, right: str) -> list[dict] | None:
        per = []
        for seed in FORMAL_SEEDS:
            a, b = rows.get((load, seed, left)), rows.get((load, seed, right))
            if a is None or b is None:
                return None
            if a["trace_sha256"] != b["trace_sha256"]:
                raise ValueError(f"Trace mismatch {load}/{seed}")
            n, x, y = common_p95(a, b, "tpot_s")
            per.append({"seed": seed,
                        "throughput": b["output_throughput_tokens_per_s"] / a["output_throughput_tokens_per_s"] - 1,
                        "ttft": b["ttft_p95_s"] / a["ttft_p95_s"] - 1,
                        "tpot": b["tpot_p95_s"] / a["tpot_p95_s"] - 1,
                        "gpu": gpu(b) / gpu(a) - 1,
                        "completion": b["completion_fraction"] - a["completion_fraction"],
                        "common_n": n, "common_tpot": y / x - 1 if x else float("nan")})
        return per

    pairs = [(load, a, b) for load, names in cells.items()
             for a, b in (("helix", "v3"), ("v3", "gated"), ("v3_off", "gated_off"))
             if a in names and b in names]
    out += ["", "## 配对相对变化（右 − 左）/ 左", "",
            "| 负载 | 对照 | 种子 | 吞吐 | P95 TTFT | P95 TPOT | GPU 秒/token | 完成率 Δ | 共同完成 TPOT |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for load, a, b in pairs:
        per = compare(load, a, b)
        if per is None:
            continue
        analysis["comparisons"][f"{load}/{b}-{a}"] = per
        for p in per:
            out.append(f"| {load} | {b} vs {a} | {p['seed']} | {p['throughput']:+.2%} | {p['ttft']:+.2%} | "
                       f"{p['tpot']:+.2%} | {p['gpu']:+.2%} | {p['completion']:+.4f} | {p['common_tpot']:+.2%} |")
        col = lambda k: ms([p[k] for p in per])
        out.append(f"| {load} | {b} vs {a} | 均值 ± SD | {col('throughput')} | {col('ttft')} | {col('tpot')} | "
                   f"{col('gpu')} | {ms([p['completion'] for p in per], False)} | {col('common_tpot')} |")

    v, lines = analysis["verdicts"], []
    def failed_or_missing(load: str, names: tuple[str, str], keys: tuple[str, ...]) -> bool:
        states = [analysis["status"][f"{load}/{cell}/seed{seed}"]
                  for seed in FORMAL_SEEDS for cell in names]
        if "failed" in states:
            for key in keys:
                v[f"{key}/{load}"] = False
            lines.append(f"- 负载 {load}，{' vs '.join(names)}：**不通过**（正式窗口失败）。")
            return True
        if "missing" in states:
            for key in keys:
                v[f"{key}/{load}"] = None
            lines.append(f"- 负载 {load}，{' vs '.join(names)}：待补全。")
            return True
        return False

    for load in cells:
        c = analysis["comparisons"]
        hv = c.get(f"{load}/v3-helix")
        if hv:
            ok = all(p["throughput"] > 0 and p["tpot"] < 0 for p in hv)
            v[f"Q1/{load}"] = ok
            lines.append(f"- Q1 负载 {load}：V3 三种子吞吐均高于且 P95 TPOT 均低于 Helix → **{'是' if ok else '否'}**")
        else:
            failed_or_missing(load, ("helix", "v3"), ("Q1",))
        gv = c.get(f"{load}/gated-v3")
        if gv:
            lat = all(p["tpot"] < 0 for p in gv) and mean(p["throughput"] for p in gv) >= -0.005
            eff = all(p["gpu"] <= -0.20 for p in gv)
            v[f"Q2_latency/{load}"], v[f"Q2_efficiency/{load}"] = lat, eff
            lines.append(f"- Q2 负载 {load} 延迟：门控三种子 P95 TPOT 均低于完整 DAG 且吞吐 ≥ −0.5% → "
                         f"**{'通过' if lat else '不通过'}**（TPOT 均值 {mean(p['tpot'] for p in gv):+.2%}）")
            lines.append(f"- Q2 负载 {load} 效率：三种子 GPU 秒/token 均降 ≥ 20% → **{'通过' if eff else '不通过'}**"
                         f"（均值 {mean(p['gpu'] for p in gv):+.2%}）")
        else:
            failed_or_missing(load, ("v3", "gated"), ("Q2_latency", "Q2_efficiency"))
        if "v3_off" in cells[load] and "gated_off" in cells[load]:
            ov = c.get(f"{load}/gated_off-v3_off")
            if ov:
                eff = all(p["gpu"] <= -0.20 for p in ov)
                v[f"Q3/{load}"] = eff
                lines.append(f"- Q3 负载 {load}（关闭 2 倍规则）：三种子 GPU 秒/token 均降 ≥ 20% → "
                             f"**{'通过' if eff else '不通过'}**（均值 {mean(p['gpu'] for p in ov):+.2%}；"
                             f"TPOT 均值 {mean(p['tpot'] for p in ov):+.2%}，仅报告）")
            else:
                failed_or_missing(load, ("v3_off", "gated_off"), ("Q3",))
    expected = sum(len(n) for n in cells.values()) * len(FORMAL_SEEDS)
    out += ["", "## 预注册判定", ""]
    counts = {state: list(analysis["status"].values()).count(state)
              for state in ("passed", "failed", "missing")}
    out.append(f"窗口状态：成功 {counts['passed']}，失败 {counts['failed']}，缺失 {counts['missing']}，计划 {expected}。")
    out += lines
    versions = sorted({row["python_version"] for row in rows.values()})
    if len(versions) > 1:
        out += ["", "成功窗口包含不同 Python 环境：" + "、".join(versions) +
                "。跨环境配对以同种子 trace_sha256 一致为前提；代码文件哈希受检出换行符影响。"]
    if analysis["failures"]:
        out += ["", "失败窗口（保留，不重跑；对应问题记为不通过）：" + "、".join(analysis["failures"])]
    status = ["# 42 节点正式窗口状态", "",
              "协议未改动；已有成功结果和失败记录均保留。失败不折算为零。", "",
              f"成功：{counts['passed']}；失败：{counts['failed']}；缺失：{counts['missing']}；计划：{expected}。",
              "", "| 负载 | 种子 | 方法 | 状态 |", "| ---: | ---: | --- | --- |"]
    for load, names in cells.items():
        for seed in FORMAL_SEEDS:
            for cell in names:
                status.append(f"| {load} | {seed} | {cell} | {analysis['status'][f'{load}/{cell}/seed{seed}']} |")
    (HERE / "STATUS_CN.md").write_text("\n".join(status) + "\n", encoding="utf-8")
    (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
