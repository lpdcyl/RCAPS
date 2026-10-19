# RCAPS V3 实验索引

**论文主版本是 RCAPS V3。** 完整方法、消融、机制分析只从下表的 V3 证据取数；每项报告均给出原始窗口、哈希、负载、种子和指标口径。

| 证据 | 用途 | 入口 |
| --- | --- | --- |
| V3 冻结记录 | 方法身份、六个布局、C1 两拓扑与 Helix ILP 的正式对照 | [`v3_release/README_CN.md`](v3_release/README_CN.md) |
| V3 核心递进消融 | C1 两拓扑的单/多级 M2 × 静态/实时 M3 四格对照 | [`v3_core_ablations/formal_report.md`](v3_core_ablations/formal_report.md) |
| V3 路径空间消融 | 同一 V3 布局上的规范路径与完整层兼容 DAG | [`v3_pathspace_ablation/formal_report.md`](v3_pathspace_ablation/formal_report.md) |
| V3 四方法对比 | V3、Helix ILP、Swarm、SP 在共同较低负载下的对照 | [`v3_four_method_comparison/RESULTS_CN.md`](v3_four_method_comparison/RESULTS_CN.md) |
| 多级 M2 来源实验 | 四格结构选择、C1–C5 资源池和正式原始窗口 | [`m2_multistage_candidate/RESULTS_CN.md`](m2_multistage_candidate/RESULTS_CN.md) |
| 纯图 M1 合法性 | 资源图与执行 DAG 的合法性、在线图一致性 | [`m2_multistage_candidate/runtime_graph_audit.json`](m2_multistage_candidate/runtime_graph_audit.json) |

## 证据边界

- M1 提供合法执行表示；不把它写成独立性能收益。
- C1 单集群实际选出多级结构；三集群 `multi_any` 退回单边界。不能把两种拓扑都写成多级结构产生收益。
- 完整 DAG 路径空间在三集群有在线收益，在单集群相对规范路径有退化；机制结论必须分拓扑报告。
- V3 的同池多档负载、RTT 和 Decode batch 敏感性实验尚未完成。
- C1 V3–Helix 高负载对照与四方法共同低负载对照是两个实验，不能直接拼成一条负载曲线。

论文写作从 [`../paper/V3_EVIDENCE_CN.md`](../paper/V3_EVIDENCE_CN.md) 开始。
