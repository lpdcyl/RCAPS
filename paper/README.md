# 论文工作区：完整 RCAPS，V4 实现

当前写作入口：[RCAPS 写作蓝图](RCAPS_WRITING_BLUEPRINT_CN.md)，包含中心问题、三项工作、章节顺序和摘要工作稿。

论文对象是完整 RCAPS，V3/V4 是实现迭代标签。当前梳理与主张边界见
[RCAPS 系统总览](RCAPS_V4_SYSTEM_OVERVIEW_20261026_CN.md)，
原始数据离线复核见 [审计记录](RCAPS_V4_OVERVIEW_AUDIT_20261026.json)。
论文核心、最近工作差异与必需实验判断见
[CCF-A 论文主线与证据合同](RCAPS_CCF_A_RESEARCH_CONTRACT_CN.md)。
扩展验证已于 2026-10-27 结束：75 个登记窗口均已尝试，63 成功、12 失败，无遗漏。
当前结论与未完成硬件/外部比较证据见 [论文证据状态](RCAPS_V4_EVIDENCE_STATUS_CN.md)。
完整结果、失败记录与新增证据见
[`../experiments/v4_validation/RESULTS_CN.md`](../experiments/v4_validation/RESULTS_CN.md)。
登记队列结束与主张证据充分分开记录；固定窗口成功运行也不意味着全部请求完成。
当前方向决策为：以完整 RCAPS 的放置—路由—执行控制系统为外层主线，
以 S/T 对空间路径分散和 Prompt 传输阻塞的控制作为核心机制镜头；不是把论文改成仅比较 V3/V4 或仅讨论 S/T。
正文按“RCAPS 对外部基线 → 最终系统 M2/M3/S/T 消融 → 机制、敏感性与泛化”组织。
S/T 四格解释工作三，V3 对照属于内部诊断；双关闭等价成立时作为四格条件。
下列原计划及完成报告保留执行历史，不以其中的 V3→V4 排序决定论文主次。

V4 将冻结 V3 的放置与路由同静态稀疏准入、慢链路固定 4 MiB 分块集成。
正式种子统一为 **0/1/2**。规划见
[`V4_EXPERIMENT_PLAN_20261026_CN.md`](V4_EXPERIMENT_PLAN_20261026_CN.md)，
执行协议见 [`../experiments/v4_formal/README.md`](../experiments/v4_formal/README.md)，
外部比较资源计量见 [`../experiments/v4_external/README.md`](../experiments/v4_external/README.md)。
本次登记的 120 格已补齐：122 次尝试、120 个成功窗口、2 次保留失败。
当前论文结果入口是 [V4 正式完成报告](../experiments/v4_paper/FINAL_RESULTS_CN.md)，
数值与逐种子结果见 [自动表格](../experiments/v4_paper/RESULTS_CN.md)，
失败及授权恢复见 [执行审计](../experiments/v4_paper/EXECUTION_AUDIT_CN.md)。
不能将本批完成写成全部稳健性和硬件实验完成，异常根因仍未解决。

历史基线及旧机制证据见
[`V3_EVIDENCE_CN.md`](V3_EVIDENCE_CN.md)及其链接的原始结果。
上述文档保留为历史 V3 证据，不能直接将其数值改名为 V4。

V3 的 M1 是统一资源与合法路径表示；核心性能证据分别来自 M2 放置、M3
实时调度及完整系统的受控实验。写作时须保留负结果与适用范围，尤其是三集群
未选出多级布局，以及完整 DAG 在单集群的路径空间消融出现退化。
