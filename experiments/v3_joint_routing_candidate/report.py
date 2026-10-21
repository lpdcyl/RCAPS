"""Paired, source-indexed report for the joint M2–M3 candidate."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .joint import HERE, ROOT, CASES, digest, read, relative, write


FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completion_fraction", "backlog_at_window_end")


def p95(values: list[float]) -> float | None:
    return float(np.percentile(values, 95)) if values else None


def samples(row: dict, duration: int) -> dict:
    query_samples = row.get("query_samples", {})
    return {str(uid): sample for uid, sample in query_samples.items()
            if sample["arrival_s"] < duration}


def common_completed(left: dict, right: dict, duration: int) -> dict:
    a, b = samples(left, duration), samples(right, duration)
    common = [uid for uid in a.keys() & b.keys()
              if a[uid]["completed"] and b[uid]["completed"]]
    result = {"count": len(common)}
    for field in ("ttft_s", "tpot_s"):
        result[field] = {"baseline_p95": p95([a[uid][field] for uid in common
                                               if a[uid].get(field) is not None]),
                         "candidate_p95": p95([b[uid][field] for uid in common
                                                if b[uid].get(field) is not None])}
    for label, items in (("baseline", a), ("candidate", b)):
        waits = [duration - sample["arrival_s"] for sample in items.values()
                 if not sample["completed"]]
        result[label + "_unfinished_count"] = len(waits)
        result[label + "_unfinished_wait_p95_s"] = p95(waits)
    return result


def build() -> dict:
    output = {"cases": {}, "runtime_sha256": {
        relative(path): digest(path) for path in (
            HERE / "joint.py", ROOT / "rcaps/v3/scheduler.py",
            ROOT / "rcaps/v3/resource_graph.py",
            ROOT / "rcaps/v3/queue_cost.py",
            ROOT / "benchmarks/fixed_window.py")}}
    table = []
    lines = ["# 路由感知 M2–M3 联合候选：配对验证",
             "", "这是独立候选，规划种子 100 与正式种子 0／1／2 分离。",
             "短规划窗口只用于有界候选选择；下表仅使用 1800 秒窗口。",
             "均匀窗口仅在调度回归、布局、物理配置及协议审计通过时复用。",
             "三个种子用于描述波动，不作统计显著性声明。", ""]
    for case in CASES:
        selected = read(HERE / "plans" / f"{case}_selected.json")
        validation = read(HERE / "validation" / f"{case}.json")
        parity = read(HERE / "parity" / f"{case}.json")
        if not parity["passed"]:
            raise ValueError(f"Unverified M3 execution semantics: {case}")
        planning_trace = {}
        planning_wall_s = 0.0
        for candidate in selected["candidates"]:
            for mode, source in candidate["results"].items():
                path = ROOT / source["path"]
                if digest(path) != source["sha256"]:
                    raise ValueError(f"Planning result changed: {path}")
                raw = read(path)
                if raw.get("status") != "completed":
                    continue
                previous = planning_trace.setdefault(mode, raw["trace_sha256"])
                if previous != raw["trace_sha256"]:
                    raise ValueError(f"Planning traces differ: {case}/{mode}")
                planning_wall_s += raw.get("wall_s", 0.0)
        groups = defaultdict(dict)
        for entry in validation["rows"]:
            path = ROOT / entry["result"]
            if digest(path) != entry["result_sha256"]:
                raise ValueError(f"Raw result changed: {path}")
            groups[entry["arrival_mode"], entry["seed"]][entry["arm"]] = (entry, read(path))
        pair_rows = []
        lines.extend([f"## {case}", "",
                      f"选择：`{selected['winner']['layout']} / {selected['winner']['mask']}`；"
                      f"规划较差场景评分 {selected['winner']['score']:.4f}；"
                      f"候选窗口累计运行 {planning_wall_s:.1f} 秒。", "",
                      "| 到达模式 | 种子 | 方法 | 输出 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 实际路径数 | 来源 |",
                      "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"])
        for mode, seed in sorted(groups):
            pair = groups[mode, seed]
            if set(pair) != {"released_v3", "joint_candidate"}:
                raise ValueError(f"Incomplete pair: {case}/{mode}/seed{seed}")
            a_info, a = pair["released_v3"]
            b_info, b = pair["joint_candidate"]
            if (a_info["status"] != "completed" or b_info["status"] != "completed" or
                    a.get("trace_sha256") != b.get("trace_sha256")):
                raise ValueError(f"Failed run or trace mismatch: {case}/{mode}/seed{seed}")
            for label, info, data in (("V3", a_info, a), ("联合候选", b_info, b)):
                lines.append("| " + " | ".join((mode, str(seed), label,
                    f"{data['output_throughput_tokens_per_s']:.3f}",
                    f"{data['ttft_p95_s']:.3f}", f"{data['tpot_p95_s']:.3f}",
                    f"{data['completion_fraction']:.3f}",
                    str(data['backlog_at_window_end']), str(len(data['route_counts'])),
                    info['result'])) + " |")
            row = {"case": case, "arrival_mode": mode, "seed": seed,
                   "baseline_source": a_info["result"],
                   "candidate_source": b_info["result"],
                   "trace_sha256": a["trace_sha256"],
                   "common_completed": common_completed(a, b, 1800)}
            for key in FIELDS:
                row[key + "_delta"] = b[key] - a[key]
            pair_rows.append(row)
            table.append(row)
        lines.extend(["", "配对差值定义为联合候选减去 V3；延迟和积压越低越好，吞吐及完成率越高越好。", ""])
        for mode in ("uniform", "burst"):
            subset = [row for row in pair_rows if row["arrival_mode"] == mode]
            if len(subset) != 3:
                raise ValueError(f"Missing three formal seeds: {case}/{mode}")
            values = {key: sum(row[key + "_delta"] for row in subset) / len(subset)
                      for key in FIELDS}
            lines.append(f"- {mode} 三种子平均配对差值：吞吐 {values[FIELDS[0]]:+.3f} token/s，"
                         f"TTFT {values[FIELDS[1]]:+.3f} s，TPOT {values[FIELDS[2]]:+.3f} s，"
                         f"完成率 {values[FIELDS[3]]:+.3f}，积压 {values[FIELDS[4]]:+.1f}。")
        lines.append("")
        output["cases"][case] = {"selected": selected["winner"],
                                 "parity": parity, "planning_trace_sha256": planning_trace,
                                 "planning_window_wall_s": planning_wall_s,
                                 "paired": pair_rows}
    write(HERE / "summary.json", output)
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    with (HERE / "paired_deltas.csv").open("w", encoding="utf-8", newline="") as stream:
        fieldnames = ["case", "arrival_mode", "seed", *[key + "_delta" for key in FIELDS],
                      "baseline_source", "candidate_source", "trace_sha256"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(table)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    result = build()
    print(f"Wrote {len(result['cases'])} cases to {HERE / 'RESULTS_CN.md'}")


if __name__ == "__main__":
    main()
