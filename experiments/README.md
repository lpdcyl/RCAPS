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

## 供独立审阅的诊断与负结果

完整导览、代码入口、证据边界和复现缺口见 [`../REVIEW_GUIDE_CN.md`](../REVIEW_GUIDE_CN.md)。以下候选和反事实**不代表已采用的 V3 新方法**。

| 诊断 | 核心结果 | 入口 |
| --- | --- | --- |
| M2 相对 Helix 放置 | 固定同一 M3 的放置消融；单集群同 GPU 数与嵌套删分支对照 | [`v3_m2_paper_ablation/RESULTS_CN.md`](v3_m2_paper_ablation/RESULTS_CN.md)、[`v3_m2_branch_parallelism/FINDINGS_CN.md`](v3_m2_branch_parallelism/FINDINGS_CN.md) |
| 放置与在线调度交叉 | 单集群存在负交互，三集群的一格 KV 断言失败 | [`v3_method_validation/formal_report.md`](v3_method_validation/formal_report.md) |
| M2 目标与代理 | 权重/Pareto 审计、静态与在线排序反例、LP 替代未稳健获益 | [`v3_m2_linear_proxy/M2_OBJECTIVE_RESPONSE_CN.md`](v3_m2_linear_proxy/M2_OBJECTIVE_RESPONSE_CN.md)、[`v3_m2_linear_proxy/SELECTION_RESULTS_CN.md`](v3_m2_linear_proxy/SELECTION_RESULTS_CN.md) |
| 联合容量与路由候选 | 独立正式种子上的 TPOT 全部高于 V3 | [`v3_joint_routing_candidate/capacity_joint/RESULTS_CN.md`](v3_joint_routing_candidate/capacity_joint/RESULTS_CN.md) |
| 慢链路和动态瓶颈 | Prompt/Decode 传输干扰、带宽和 KV 反事实；逐消息流未上传 | [`v3_phase_link_diagnosis/formal_report.md`](v3_phase_link_diagnosis/formal_report.md)、[`v3_dynamic_bottleneck_counterfactuals/formal600_report.md`](v3_dynamic_bottleneck_counterfactuals/formal600_report.md) |
| 路径空间痛点闭环 | 证伪"多跳"假设，确认 Decode 批碎片化；慢链路门控准入通过 C1 非劣效检验；泛化：带宽 ×0.5/×2 通过，C2/C3 的 TPOT 改善不成立，但所有条件 GPU 工作量下降；关闭单请求 2 倍规则后 GPU 节省保留 90–98%，TPOT 收益则大幅依赖该规则 | [`V3_PAINPOINT_LOOP_CN.md`](V3_PAINPOINT_LOOP_CN.md) |
| 边界与压力测试 | 未确认吞吐平台；冻结 V3 不具备逐层热点自适应 | [`v3_load_boundary/FINDINGS_CN.md`](v3_load_boundary/FINDINGS_CN.md)、[`v3_multistage_stress/FINDINGS_CN.md`](v3_multistage_stress/FINDINGS_CN.md) |

## 证据边界

- M1 提供合法执行表示；不把它写成独立性能收益。
- C1 单集群实际选出多级结构；三集群 `multi_any` 退回单边界。不能把两种拓扑都写成多级结构产生收益。
- 完整 DAG 路径空间在三集群有在线收益，在单集群相对规范路径有退化；机制结论必须分拓扑报告。
- V3 的同池多档负载、RTT 和 Decode batch 敏感性实验尚未完成。
- C1 V3–Helix 高负载对照与四方法共同低负载对照是两个实验，不能直接拼成一条负载曲线。

论文写作从 [`../paper/V3_EVIDENCE_CN.md`](../paper/V3_EVIDENCE_CN.md) 开始。
