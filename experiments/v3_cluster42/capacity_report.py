"""Paired evidence for concurrent-KV layouts; missing windows never pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from experiments.v3_cluster42.run import HERE, PHYSICAL, digest
from rcaps.v3.topology import TopologyModel

ROOT = HERE / "kv_capacity"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def pair(candidate, baseline, devices):
    identity = ("trace_sha256", "offered_tokens_per_s", "duration_s", "warmup_s",
                "arrivals", "evaluation_protocol", "seed")
    # Historical Linux results hash LF bytes, Windows checkout hashes CRLF.
    # Accept only hashes reproduced from these exact two byte encodings of
    # the current physical file, keeping all other content identical.
    physical = PHYSICAL.read_bytes().replace(b"\r\n", b"\n")
    encodings = {hashlib.sha256(data).hexdigest(): label for label, data in
                 (("LF", physical), ("CRLF", physical.replace(b"\n", b"\r\n")))}
    cluster_hashes = [row.get("physical_cluster_sha256") for row in (candidate, baseline)]
    same_cluster = all(value in encodings for value in cluster_hashes)
    same = all(candidate.get(key) == baseline.get(key) and key in candidate
               for key in identity)
    checks = {"same_input": same, "same_physical_cluster": same_cluster,
              "fewer_physical_gpus": devices < 64}
    deltas = {}
    for key, higher in (("output_throughput_tokens_per_s", True),
                        ("ttft_p95_s", False), ("tpot_p95_s", False)):
        a, b = candidate.get(key), baseline.get(key)
        valid = all(isinstance(x, (int, float)) and math.isfinite(x) for x in (a, b))
        checks[key] = valid and (a >= b if higher else a <= b)
        deltas[key] = (a / b - 1) if valid and b else None
    return {"checks": checks, "relative_change": deltas, "pass": all(checks.values()),
            "physical_cluster_hash_evidence": {
                "candidate": cluster_hashes[0], "baseline": cluster_hashes[1],
                "recognized_byte_encodings": encodings,
                "reason": "Same file content; only LF/CRLF encoding is accepted"}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    model = TopologyModel(PHYSICAL)
    candidates = [row["name"] for row in read(root / "shortlist.json")]
    protocol = read(root / "protocol.json")
    records = []
    for phase, seeds in (("smoke", [100]), ("screening", [101]), ("formal", [0, 1, 2])):
        for name in candidates:
            if phase == "formal" and name != protocol["formal"]["candidate"]:
                continue
            layout = read(root / name / "placement.json")
            types = [model.types[int(node)] for node in layout["state"]["lengths"]]
            devices = sum(int(kind.split("x")[1]) if "x" in kind else 1 for kind in types)
            for seed in seeds:
                source = root / "runs" / phase / f"{name}_seed{seed}.json"
                baseline = (root / protocol["formal"]["baseline"].format(seed=seed)
                            if phase == "formal" else
                            (HERE / "kv_candidate/runs/smoke/helix_seed100.json"
                             if phase == "smoke" else
                             root / protocol["screening"].get("baseline", "runs/screening/helix_seed101.json")))
                baseline = baseline.resolve()
                record = {"phase": phase, "candidate": name, "seed": seed,
                          "active_nodes": len(types), "physical_gpu_devices": devices,
                          "source": source.relative_to(HERE).as_posix(),
                          "baseline": baseline.relative_to(HERE).as_posix(),
                          "status": "not_run"}
                if source.with_suffix(".failure.json").exists():
                    record["status"] = "failed"
                elif source.exists():
                    result = read(source)
                    record.update({"status": "awaiting_baseline", "metrics": {
                        key: result.get(key) for key in (
                            "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                            "completion_fraction", "first_tokens_in_window", "arrivals",
                            "backlog_at_window_end", "kv_admission")},
                        "result_sha256": digest(source)})
                    if baseline.exists():
                        baseline_result = read(baseline)
                        record["baseline_metrics"] = {key: baseline_result.get(key)
                            for key in record["metrics"]}
                        record.update(pair(result, baseline_result, devices))
                        record["checks"].update({
                            "same_candidate": result.get("candidate") == name,
                            "same_layout": result.get("layout_sha256") == digest(root / name / "placement.json"),
                            "same_node_count": result.get("active_gpus") == len(types),
                            "same_admission": result.get("kv_reservation_mode", "resident_layers") ==
                                              layout.get("kv_reservation_mode", "resident_layers"),
                            "full_dag": result.get("mode") == "full"})
                        record["pass"] = all(record["checks"].values())
                        record["status"] = "pass" if record["pass"] else "not_pass"
                records.append(record)
    formal = [row for row in records if row["phase"] == "formal"]
    passed = len(formal) == 3 and all(row["status"] == "pass" for row in formal)
    passing = [row for row in records if row["phase"] == "screening" and row["status"] == "pass"]
    selected = min(passing, key=lambda row: (row["physical_gpu_devices"],
        -row["metrics"]["output_throughput_tokens_per_s"]))["candidate"] if passing else None
    (root / "analysis.json").write_text(json.dumps({"formal_pass": passed,
        "screening_selection": selected,
        "formal_candidate": protocol["formal"]["candidate"], "windows": records},
        indent=2) + "\n", encoding="utf-8")
    lines = ["# 42 节点高负载：并发 KV 容量约束实验", "",
             "目标：相同 2150 offered token/s、相同请求轨迹，以更少计算节点同时达到 Helix 的吞吐、P95 TTFT 和 P95 TPOT。",
             "", "42 是计算节点数；L4x2、T4x2、T4x4 含多张卡，按类型倍数折算为 64 张物理 GPU。下表同时报告两种数量，避免混淆。所有结果来自事件模拟器。",
             "", "按输入长度加公开输出上限 1000 token 预约全生命周期 KV。准入等待计入 TTFT，不丢弃请求。",
             "", "预约粒度与布局生成规则见 protocol.json 和各候选 placement.json；executed_layers 只预约实际执行层，resident_layers 预约全部驻留层。",
             "", "| 窗口 | 候选 | 种子 | 节点/物理GPU | token/s | TTFT P95 s | TPOT P95 s | 首token/到达 | 完成率 | 积压 | 三指标配对 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for row in records:
        if "metrics" not in row:
            continue
        m = row["metrics"]
        lines.append(f"| {row['phase']} | {row['candidate']} | {row['seed']} | "
                     f"{row['active_nodes']}/{row['physical_gpu_devices']} | "
                     f"{m['output_throughput_tokens_per_s']:.3f} | {m['ttft_p95_s']:.3f} | "
                     f"{m['tpot_p95_s']:.3f} | {m['first_tokens_in_window']}/{m['arrivals']} | "
                     f"{m['completion_fraction']:.4f} | {m['backlog_at_window_end']} | {row['status']} |")
    seen = set()
    for row in records:
        if "baseline_metrics" not in row or row["baseline"] in seen:
            continue
        seen.add(row["baseline"])
        m = row["baseline_metrics"]
        lines.append(f"| {row['phase']} | Helix | {row['seed']} | 42/64 | "
                     f"{m['output_throughput_tokens_per_s']:.3f} | {m['ttft_p95_s']:.3f} | "
                     f"{m['tpot_p95_s']:.3f} | {m['first_tokens_in_window']}/{m['arrivals']} | "
                     f"{m['completion_fraction']:.4f} | {m['backlog_at_window_end']} | baseline |")
    lines.extend(["", f"600 秒筛选推荐：{selected or '暂无三项同时达标的候选'}。",
                  "", "正式判定：" + ("三个种子全部通过。" if passed else
                  "尚未达到三个正式种子全部通过；缺失窗口不计通过。"), "",
                  "180 秒 smoke 和 600 秒 screening 仅用于选型；1800 秒、seed 0/1/2 才用于最终判定。完整输入一致性检查、相对变化及结果哈希见 analysis.json。",
                  "", "集群身份按文件内容核对：历史 Linux 结果记录 LF 字节哈希，Windows 检出记录 CRLF 哈希。仅接受由当前同一文件复算出的这两种换行形式，保留原始哈希及核对证据；不改写历史结果。",
                  "", "原 22 节点方案的三个正式负结果见 ../kv_candidate/RESULTS_CN.md；原 V3 的 KV 断言失败见 ../RESULTS_CN.md，均保留。"])
    (root / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"formal_pass": passed, "windows": [
        {k: row[k] for k in ("phase", "candidate", "seed", "status")}
        for row in records if row["status"] != "not_run"]}, indent=2))


if __name__ == "__main__":
    main()
