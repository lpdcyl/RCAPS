# 论文工作区：以 RCAPS V4 为主

V4 将冻结 V3 的放置与路由同静态稀疏准入、慢链路固定 4 MiB 分块集成。
正式种子统一为 **0/1/2**。规划见
[`V4_EXPERIMENT_PLAN_20261026_CN.md`](V4_EXPERIMENT_PLAN_20261026_CN.md)，
执行协议见 [`../experiments/v4_formal/README.md`](../experiments/v4_formal/README.md)，
外部比较资源计量见 [`../experiments/v4_external/README.md`](../experiments/v4_external/README.md)。
本批因原生进程崩溃中止，97 格成功、1 格失败、22 格未启动；详见
[`中止审计与阶段结论`](../experiments/v4_paper/EXECUTION_AUDIT_CN.md)。
只对齐全三种子的组写正式均值，不能将部分完成写成全部验证。

新的论文方法、实验设置、图表和结果陈述从
[`V3_EVIDENCE_CN.md`](V3_EVIDENCE_CN.md)及其链接的原始结果开始。
上述文档保留为历史 V3 证据，不能直接将其数值改名为 V4。

V3 的 M1 是统一资源与合法路径表示；核心性能证据分别来自 M2 放置、M3
实时调度及完整系统的受控实验。写作时须保留负结果与适用范围，尤其是三集群
未选出多级布局，以及完整 DAG 在单集群的路径空间消融出现退化。
