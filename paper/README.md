# 论文工作区：以 RCAPS V4 为主

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
