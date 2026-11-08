"""Revalidate immutable HexGen audits and write the final evidence boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .formal_v1 import audit as a1
from .formal_v2 import audit as a2
from .formal_v3_700 import audit as a3

HERE = Path(__file__).resolve().parent
VERSIONS = {"formal_v1": a1, "formal_v2": a2, "formal_v3_700": a3}
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    audits = {}
    for version, module in VERSIONS.items():
        path = HERE / version / "FINAL_AUDIT.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved != module.audit():
            raise RuntimeError(f"Audit no longer matches source artifacts: {version}")
        if saved["status"] != "terminal" or saved["pending_count"]:
            raise RuntimeError(f"Nonterminal protocol: {version}")
        audits[version] = saved
    v1, v2, v3 = (audits[name] for name in VERSIONS)
    if (v1["success_count"], v1["failure_count"], v1["complete_five_seed_groups"]) != (15, 5, 3):
        raise RuntimeError("First formal matrix changed")
    if (v2["success_count"], v2["failure_count"], v2["complete_five_seed_groups"]) != (16, 4, 1):
        raise RuntimeError("Second formal matrix changed")
    if (v3["success_count"], v3["failure_count"], v3["complete_five_seed_groups"]) != (2, 3, 0):
        raise RuntimeError("Debug-runtime matrix changed")

    overlaps = []
    for key, old in v1["jobs"].items():
        new = v2["jobs"][key]
        if old["status"] == new["status"] == "success":
            if (old["trace_sha256"] != new["trace_sha256"]
                    or any(old["metrics"][metric] != new["metrics"][metric]
                           for metric in METRICS)):
                raise RuntimeError("Overlapping success changed: " + key)
            overlaps.append(key)
    if len(overlaps) != 12:
        raise RuntimeError("Unexpected overlap count")
    complete = ["single_load350", "multi_load160", "multi_load320"]
    if set(complete) != {key for key, row in v1["groups"].items()
                         if row["status"] == "complete"}:
        raise RuntimeError("Complete group set changed")
    for version, audit in audits.items():
        if audit["groups"].get("single_load700", {}).get("status") == "complete":
            raise RuntimeError("High-load group unexpectedly complete: " + version)

    evidence = {
        "status": "three_complete_groups_high_load_incomplete",
        "method": "HexGen paper-method simulator adaptation, not original artifact reproduction",
        "protocols": {version: {
            "manifest_sha256": sha(HERE / version / "manifest.json"),
            "audit_sha256": sha(HERE / version / "FINAL_AUDIT.json"),
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "complete_five_seed_groups": row["complete_five_seed_groups"],
        } for version, row in audits.items()},
        "valid_complete_groups": {key: v1["groups"][key] for key in complete},
        "identical_overlapping_successes_v1_v2": overlaps,
        "single_load700_v2": {f"seed{seed}": v2["jobs"][f"single_load700_seed{seed}"]
                              for seed in range(5)},
        "single_load700_v3": {f"seed{seed}": v3["jobs"][f"single_load700_seed{seed}"]
                              for seed in range(5)},
        "high_load_formal_five_seed_claim_allowed": False,
    }
    (HERE / "FINAL_STATUS.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# HexGen 外部基线最终证据状态",
        "",
        "HexGen（ICML 2024）论文方法已移植到当前 CPU 离散事件模拟器：GA 流水线分组、",
        "DP 层放置、开发种子上的 SLO 搜索、在线请求分配及容量准入均有代码与工件。",
        "这是论文方法的模拟器适配，不是原作者 artifact 的逐位复现或真实 GPU 测量。",
        "24 节点 70B 拓扑仅有 152 个层槽，两个完整模型副本至少需要 160 个，",
        "所以该正式比较只有一条流水线；42 节点双流水线目前只有开发冒烟证据。",
        "",
        "## 可用于论文的完整五种子条件",
        "",
        "同一 1800 s 固定窗口、零预热、窗口末不排空，seed0–4；五个种子与既有 V4 的请求轨迹 SHA 均逐键相同。",
        "下表指标是五个种子各自窗口指标的均值；P95 是各种子 P95 的均值。",
        "",
        "| 条件（offered token/s） | HexGen 输出 token/s | V4 输出 token/s | HexGen P95 TTFT s | V4 P95 TTFT s | HexGen P95 TPOT s | V4 P95 TPOT s | HexGen 完成率 | V4 完成率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label in (("single_load350", "单集群 350"),
                       ("multi_load160", "三集群 160"),
                       ("multi_load320", "三集群 320")):
        group = v1["groups"][key]
        h, d = group["hexgen"], group["paired"]["V4"]
        val = lambda m: h[m]["mean"]
        ref = lambda m: val(m) - d[m]["mean"]
        lines.append(f"| {label} | {val(METRICS[0]):.3f} | {ref(METRICS[0]):.3f} | "
                     f"{val(METRICS[1]):.3f} | {ref(METRICS[1]):.3f} | "
                     f"{val(METRICS[2]):.3f} | {ref(METRICS[2]):.3f} | "
                     f"{100*val(METRICS[3]):.2f}% | {100*ref(METRICS[3]):.2f}% |")
    lines += [
        "",
        "三组完整条件中，V4 的吞吐、TTFT、TPOT 和完成率均优于此 HexGen 适配。",
        "配对差及 95% 区间见 [第一版审计](formal_v1/FINAL_AUDIT.json) 的 `groups.*.paired.V4`。",
        "第一版的三个完整组在第二版重合成功的 12 个键上数值逐项一致，且这些键没有触发容量延期。",
        "",
        "## 700 token/s：没有正式五种子结果",
        "",
        "第一版 5/5 失败（KV 容量断言或内部路由对象异常）。第二版加入保守 KV 预留后 4/5 成功，",
        "seed4 内部对象类型异常；第三版在 `PYTHONMALLOC=debug` 下重跑全五种子，2/5 成功，",
        "seed1 发生 Windows 原生访问冲突（0xC0000005），seed3/4 出现不同的内部对象类型异常。",
        "第三版中断后只续跑未尝试的 seed2–4，原索引、日志和 SHA 已归档。",
        "诊断重放中 seed4 成功，但未回填任何正式矩阵。不能为 700 条件报告五种子均值、置信区间或胜负结论。",
        "",
        "| 第二版正式键 | 输出 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 状态 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for seed in range(5):
        row = v2["jobs"][f"single_load700_seed{seed}"]
        if row["status"] == "success":
            m = row["metrics"]
            lines.append(f"| seed{seed} | {m[METRICS[0]]:.3f} | {m[METRICS[1]]:.3f} | "
                         f"{m[METRICS[2]]:.3f} | {100*m[METRICS[3]]:.2f}% | 成功 |")
        else:
            lines.append(f"| seed{seed} | — | — | — | — | 失败 |")
    lines += [
        "",
        "## 证据与后续运行边界",
        "",
        "- [总状态 JSON](FINAL_STATUS.json) 记录三版协议、审计 SHA、完整组与逐键状态。",
        "- [第一版协议](formal_v1/manifest.json)、[第二版协议](formal_v2/manifest.json)、[第三版协议](formal_v3_700/manifest.json) 均冻结了输入与源码 SHA。",
        "- [第二版审计](formal_v2/FINAL_AUDIT.json)、[第三版审计](formal_v3_700/FINAL_AUDIT.json) 与原失败工件分别保留。",
        "- [原生崩溃归档](formal_v3_700/recovery_before_resume/RECOVERY_EVIDENCE.json) 含中断索引、worker 日志和已成功工件 SHA。",
        "- 若计算环境修复，需要在新的完整五种子协议中重新运行 700 条件；不得用诊断重放补齐旧正式组。",
        "",
    ]
    (HERE / "FINAL_STATUS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(HERE / "FINAL_STATUS_CN.md")


if __name__ == "__main__":
    main()
