"""Recompute the frozen development screen for every bypass subset."""

from __future__ import annotations

import json

from work3_detour_ablation.report import common_tpot, gpu_work, ratio
from work3_edge_admission.run import AUDIT, HERE, PROTOCOL, digest, freeze, write


def read(cell: str, seed: int) -> dict:
    return json.loads((HERE / "runs" / "development" / f"{cell}_seed{seed}.json").read_text(encoding="utf-8"))


def comparison(base: dict, candidate: dict) -> dict:
    if base["trace_sha256"] != candidate["trace_sha256"] or base["arrivals"] != candidate["arrivals"]:
        raise AssertionError("Paired arrival trace differs")
    a, b, n = common_tpot(base, candidate)
    return {"tpot_relative": ratio(candidate["tpot_p95_s"], base["tpot_p95_s"]),
            "common_tpot_relative": ratio(b, a), "common_completed_n": n,
            "ttft_relative": ratio(candidate["ttft_p95_s"], base["ttft_p95_s"]),
            "throughput_relative": ratio(candidate["output_throughput_tokens_per_s"],
                                         base["output_throughput_tokens_per_s"]),
            "gpu_work_relative": ratio(gpu_work(candidate), gpu_work(base)),
            "completion_absolute": candidate["completion_fraction"] - base["completion_fraction"],
            "route_count": len(candidate["route_counts"]),
            "gpu_seconds_per_token": gpu_work(candidate)}


def passes(c: dict) -> bool:
    g = PROTOCOL["selection_guard_each_seed_vs_full"]
    return (c["tpot_relative"] <= g["tpot_p95_relative_max"]
            and c["common_tpot_relative"] <= g["common_completed_tpot_p95_relative_max"]
            and c["ttft_relative"] <= g["ttft_p95_relative_max"]
            and c["throughput_relative"] >= g["throughput_relative_min"]
            and c["completion_absolute"] >= g["completion_fraction_absolute_min"]
            and c["gpu_work_relative"] <= g["gpu_seconds_per_token_relative_max"])


def report() -> str:
    freeze()
    runs = {seed: {cell: read(cell, seed) for cell in PROTOCOL["cells"]}
            for seed in PROTOCOL["seeds"]}
    for seed, cells in runs.items():
        for cell, row in cells.items():
            if row["audit_sha256"] != digest(AUDIT) or row["duration_s"] != PROTOCOL["duration_s"]:
                raise AssertionError(f"Run identity differs: {seed}/{cell}")
            if len(row["query_samples"]) != row["arrivals"]:
                raise AssertionError(f"Missing request samples: {seed}/{cell}")
            if cell != "full":
                mask = int(cell[4:])
                expected = [edge for i, edge in enumerate(PROTOCOL["edge_order"]) if mask & (1 << i)]
                if row["detours"] != sorted(expected) or row["allowed_edges"] != 26 + mask.bit_count():
                    raise AssertionError(f"Admitted subgraph differs: {seed}/{cell}")
        if len({row["trace_sha256"] for row in cells.values()}) != 1:
            raise AssertionError(f"Trace differs within seed {seed}")
    rows = []
    for mask in range(16):
        cell = f"mask{mask:02d}"
        paired = {seed: comparison(runs[seed]["full"], runs[seed][cell])
                  for seed in PROTOCOL["seeds"]}
        eligible = all(passes(c) for c in paired.values())
        works = [c["gpu_seconds_per_token"] for c in paired.values()]
        rows.append({"cell": cell, "mask": mask,
                     "detours": [edge for i, edge in enumerate(PROTOCOL["edge_order"])
                                 if mask & (1 << i)],
                     "paired": paired, "eligible": eligible,
                     "mean_gpu_seconds_per_token": sum(works) / len(works),
                     "max_gpu_seconds_per_token": max(works)})
    candidates = [row for row in rows if row["eligible"]]
    chosen = min(candidates, key=lambda row: (row["mean_gpu_seconds_per_token"],
                                               row["max_gpu_seconds_per_token"],
                                               row["mask"].bit_count(), row["mask"])) if candidates else None
    data = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT), "rows": rows,
            "selected_mask": None if chosen is None else chosen["mask"],
            "status": "development_only"}
    write(HERE / "analysis.json", data)
    lines = ["# 四条绕行边的全子集开发筛选", "",
             "C1 三集群、种子 171/172、180 秒，同轨迹配对；16 个子集加完整图。",
             "所有筛选门槛在运行前冻结。mask15 是旧静态门控，mask00 是规范图。",
             "该筛选是离线黑盒配置搜索，不等于已证明独立方法创新。", "",
             "| 掩码 | 开放绕行边数 | 两种子 TPOT 对完整图 | 两种子 GPU 工作对完整图 | 两种子吞吐对完整图 | 联合护栏 |",
             "| ---: | ---: | --- | --- | --- | --- |"]
    for row in rows:
        paired = list(row["paired"].values())
        tpot = "/".join(f"{c['tpot_relative']:+.1%}" for c in paired)
        gpu = "/".join(f"{c['gpu_work_relative']:+.1%}" for c in paired)
        throughput = "/".join(f"{c['throughput_relative']:+.1%}" for c in paired)
        lines.append(f"| {row['mask']:02d} | {len(row['detours'])} | {tpot} | {gpu} | "
                     f"{throughput} | {'通过' if row['eligible'] else '未通过'} |")
    selected_label = "无候选" if chosen is None else f"mask{chosen['mask']:02d}"
    lines += ["", f"预定规则选择：{selected_label}。",
              "逐种子共同完成 TPOT、TTFT、完成率、路径数及全部原始值见 `analysis.json`。",
              "如果选择 mask15，则与旧静态门控在此拓扑上同构，不宣称新方法收益。",
              "如果选出其他掩码，也必须在新开发种子复验，才考虑冻结正式协议。", ""]
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
