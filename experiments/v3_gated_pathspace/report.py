"""Development-window report for slow-link-gated path admission."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.v3_cohort_routing.report import dev_rows
from experiments.v3_cycle_pricing.run import read

HERE = Path(__file__).resolve().parent


def main() -> None:
    lines, data = dev_rows([("gated", HERE / "runs/dev/x/gated_seed100.json")])
    audit = read(HERE / "audit.json")["cases"]
    single = read(HERE / "runs/dev/C1_single/gated_seed100.json")
    canonical = read(Path(data["C1_single/canonical"]["source"]).resolve()
                     if Path(data["C1_single/canonical"]["source"]).is_absolute()
                     else HERE.parents[1] / data["C1_single/canonical"]["source"])
    same = all(single[k] == canonical[k] for k in (
        "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s", "route_counts", "query_samples"))
    multi = data["C1_multi/gated"]
    go = multi["relative_throughput"] >= -0.005 and multi["relative_tpot_p95"] <= 0
    gap = (data["C1_multi/canonical"]["tpot_p95_s"] - multi["tpot_p95_s"]) / (
        data["C1_multi/canonical"]["tpot_p95_s"] - data["C1_multi/v3"]["tpot_p95_s"])
    out = ["# V3 M3 慢链路门控路径准入：开发阶段", "",
           "规则见 `protocol_dev.json`（先于开发窗口提交）。种子 100、300 秒。", "",
           "## 准入边（`audit.json`）", "",
           "| 拓扑 | 完整 DAG 边 | 规范边 | 准入边 | 绕行边 | 慢规范边 |", "| --- | ---: | ---: | ---: | --- | --- |"]
    for case, info in audit.items():
        detours = ", ".join(f"{d['edge'][0]}→{d['edge'][1]}" for d in info["detours"]) or "无"
        slow = ", ".join(f"{a}→{b}" for a, b in info["slow_canonical_edges"]) or "无"
        out.append(f"| {case} | {info['full_edges']} | {info['canonical_edges']} | "
                   f"{info['admitted_edges']} | {detours} | {slow} |")
    out += ["", "## 开发窗口", ""] + lines
    out += ["", "## 预注册判定", "",
            f"- 单集群准入边与规范路径相同，开发窗口与规范路径窗口逐项相同：{'是' if same else '否'}",
            f"- 三集群相对冻结 V3：吞吐 {multi['relative_throughput']:+.2%}，P95 TPOT "
            f"{multi['relative_tpot_p95']:+.2%}（要求吞吐 ≥ −0.5% 且 TPOT ≤ 0）",
            f"- 结论：**{'进入正式窗口' if go else '未满足 TPOT 不升，按规则停止，不跑正式窗口'}**", "",
            "## 描述（不作判定依据）", "",
            f"- 三集群：4 条绕行边收回了规范路径到完整 DAG 之间 {gap:.0%} 的 P95 TPOT 差距，"
            f"平均 Decode 批 {multi['mean_batch']:.2f}（完整 DAG 3.07，规范路径 7.19）。",
            "- 单集群：无慢链路，候选即规范路径，吞吐与 TPOT 相对冻结 V3 的改善与路径空间消融方向一致。",
            "- 单个 300 秒开发窗口在三集群只有约 100 个请求，1% 的 TPOT 差约 7 ms，"
            "不能区分噪声与系统性差距；是否以非劣效边界重新预注册正式验证，需要研究者决定。"]
    (HERE / "analysis.json").write_text(json.dumps(
        {"dev": data, "single_equals_canonical": same, "go": go,
         "multi_tpot_gap_recovered": gap}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
