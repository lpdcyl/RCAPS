# RCAPS V3 代码与证据交接：供独立审阅

> 历史提示（2026-10-26）：本页保留 V3 阶段的交接事实。下文“当前主方法是 V3”、
> “V4 已撤销”和旧分支建议已不代表当前仓库。最终 RCAPS 已由 V4 实现集成，
> 当前分支与完整系统代码/证据梳理见
> [RCAPS 系统总览](paper/RCAPS_V4_SYSTEM_OVERVIEW_20261026_CN.md)。

本页给从 GitHub 直接审阅仓库的研究者一个入口。请**独立检查代码、原始结果与失败窗口**，再判断下一步该改什么；下述结论是现有证据的索引，不是要求审阅者接受的论文主张。

## 版本边界

- 当前可执行的主方法是 **RCAPS V3**。M1 为物理资源与层兼容 DAG，M2 为最多双边界的共享前段／后段完整副本放置，M3 为实时队列感知的 DAG 路由。C1 单集群的发布布局为 `1→4→3`，三集群为 `1→3`。
- 请使用本仓库的 **`codex/v3-phase-link-mechanism` 分支**。GitHub 默认 `main` 比该分支少最近的诊断与 LP 验证提交。V4 曾被讨论，但其实现已撤销；仓库中的 LP、容量搜索和联合路由目录是**未采用的研究候选**，不能称为当前 V3 方法。
- 主正式实验按 1800 秒、固定窗口、零预热、不排空、种子 **0/1/2** 阅读。个别历史机制诊断使用种子 1/2/3 或独立补充种子 4/5/6，见各自协议；不可把它们混作主实验的配对重复。三个种子用于观察方向和波动，不作显著性证明。
- 所有结果来自 Helix 事件模拟器，不是实体 GPU 部署。运行中失败的窗口保留为失败，不能填零或从均值中隐去。

## 从代码开始

| 模块 | 入口 | 审阅重点 |
| --- | --- | --- |
| M1 资源与执行图 | [`rcaps/v3/resource_graph.py`](rcaps/v3/resource_graph.py)、[`rcaps/v3/topology.py`](rcaps/v3/topology.py) | 层兼容边、物理链路、复制分支的完整路径合法性 |
| M2 状态和静态评分 | [`rcaps/v3/placement.py`](rcaps/v3/placement.py) | `validate()`、`measure()`、`objective()`；最坏规范路径与均分瓶颈的假设 |
| M2 有界搜索 | [`rcaps/v3/search.py`](rcaps/v3/search.py)、[`rcaps/v3/plan.py`](rcaps/v3/plan.py) | 分段结构空间、搜索预算、初始和邻域排序，不能宣称全局最优 |
| M3 在线路由 | [`rcaps/v3/online_scheduler.py`](rcaps/v3/online_scheduler.py)、[`rcaps/v3/routing.py`](rcaps/v3/routing.py)、[`rcaps/v3/queue_cost.py`](rcaps/v3/queue_cost.py) | 实时队列和网络状态、Prompt 路径选择、Decode 路径固定、KV 约束 |
| 协议和冻结布局 | [`benchmarks/fixed_window.py`](benchmarks/fixed_window.py)、[`experiments/v3_release/manifest.json`](experiments/v3_release/manifest.json)、[`rcaps/v3_layouts/`](rcaps/v3_layouts/) | 相同请求轨迹、窗口截尾、布局哈希与发布身份 |

基础运行步骤见 [`README.md`](README.md)；V3 主证据索引见 [`experiments/README.md`](experiments/README.md)。

## 优先阅读的实验证据

| 研究问题 | 报告与可追溯结果 | 目前能说明什么；不能说明什么 |
| --- | --- | --- |
| M2 放置是否有独立价值？ | [`M2 固定 M3 消融`](experiments/v3_m2_paper_ablation/RESULTS_CN.md)、[`M2 分支复制诊断`](experiments/v3_m2_branch_parallelism/FINDINGS_CN.md) | 相同 M3 下，M2 相对 Helix ILP 在 C1 两拓扑改善在线指标。嵌套删分支与同 GPU 数对照支持后段复制的结构作用；单集群同 GPU 数吞吐增量较小。复制导致的 KV 与链路贡献尚未完全分离。 |
| M2 与 M3 是否协同？ | [`四格交叉实验`](experiments/v3_method_validation/formal_report.md)、[`V3 递进消融`](experiments/v3_core_ablations/formal_report.md) | 单集群两模块均有条件收益，但吞吐交互量为负；三集群的 V3 M2 + Helix 在线调度格因 KV 断言失败，无法给出完整四格交互。不可写成普遍正协同。 |
| 扩大路径空间是否有效？ | [`规范路径 vs 完整 DAG`](experiments/v3_pathspace_ablation/formal_report.md) | 完整 DAG 在三集群提高吞吐、降低尾延迟；在单集群三个种子均降低吞吐、提高 TPOT。路径数增加不等于服务性能提高。 |
| 静态 M2 评分能否代表在线结果？ | [`M2 目标分量消融`](experiments/v3_method_validation/m2_formal_report.md)、[`搜索敏感性`](experiments/v3_search_sensitivity/FINDINGS_CN.md)、[`权重与 Pareto 审计`](experiments/v3_m2_linear_proxy/M2_OBJECTIVE_RESPONSE_CN.md) | 原三项评分能选出有用布局，局部权重变化下固定池选择稳定；三集群存在静态分数下降而在线 TTFT 变差的排序反例。权重并非理论最优，固定池重评分不等于重新搜索。 |
| 用 LP 或联合规划替换加权代理是否更好？ | [`LP 部署选择正式对照`](experiments/v3_m2_linear_proxy/SELECTION_RESULTS_CN.md)、[`容量 LP × 路由候选`](experiments/v3_joint_routing_candidate/capacity_joint/RESULTS_CN.md) | 两项候选都未给出稳定在线收益；LP 高负载 P95 TPOT 在两拓扑分别恶化 2.85% 和 4.16%，联合候选的正式配对 TPOT 全部高于 V3。不能因为模型形式更精致就替换主方法。 |
| M2 的资源瓶颈究竟在哪里？ | [`慢链路 Prompt/Decode 干扰`](experiments/v3_phase_link_diagnosis/formal_report.md)、[`动态瓶颈反事实`](experiments/v3_dynamic_bottleneck_counterfactuals/formal600_report.md) | 慢链路 Prompt 发送与 Decode 等待重叠，带宽和分块干预能降低 TPOT；KV 容量翻倍在已完成的低负载条件下无收益，在更高负载可改变失败可行性。网络、KV 与路由时序不能用单个相关性指标做精确因果分摊。 |
| 方法是否有超出 C1 的广泛收益？ | [`负载边界`](experiments/v3_load_boundary/FINDINGS_CN.md)、[`合成热点`](experiments/v3_multistage_stress/FINDINGS_CN.md)、[`搜索效率`](experiments/v3_search_efficiency/FINDINGS_CN.md) | 已测试区间没有确认吞吐平台；冻结 V3 不具备逐层热点自适应。搜索在 C1 较快，但 Helix 原 ILP 的完成时间是 900 秒右删失值，不能报精确加速比或同服务质量下的规划优势。 |

每个报告旁的 `analysis.json`、`formal_index.json`、`summary.json` 或 `manifest.json` 记录逐种子指标、来源路径、输入／结果哈希和失败。阅读报告后应打开相邻索引及原始窗口，而不是只取表中均值。尤其应复核完成率、末端积压、共同完成请求 P95 和失败窗口；固定窗口 P95 的完成集合可能不同。

## 证据可复现性与已知缺口

从仓库根目录执行：

```powershell
python -m experiments.v3_release.verify --allow-diagnostic-probe
python -m benchmarks.run --dry-run
python -m unittest experiments.v3_m2_linear_proxy.test_model experiments.v3_joint_routing_candidate.test_joint experiments.v3_joint_routing_candidate.test_capacity_joint -v
python -m experiments.v3_m2_linear_proxy.objective_audit
```

冻结清单记录的是原始 `benchmarks/fixed_window.py` 哈希；本诊断分支只在该文件加入默认关闭的 `phase_link_probe` 钩子，使严格的 `verify` **预期失败**。`--allow-diagnostic-probe` 仅接受审阅过的完整文件哈希，并继续严格比较其他 V3 代码、六个布局及证据；不要用 `--write-manifest` 覆盖发布清单。布局重算需要 Gurobi 许可，已发布布局可直接加载。

慢链路诊断的逐消息 `.jsonl.gz` 共约 3.35 GB，仅在本地保存，**GitHub 没有这些原始事件流**。仓库保留运行器、逐窗口 JSON、分析 JSON、CSV、图和报告，可阅读结论并重跑生成事件流；不能仅凭 GitHub 文件独立重算每条消息的阻挡比例。该实验自身的 [`README`](experiments/v3_phase_link_diagnosis/README.md) 说明重新生成时要先移走已有汇总结果以避免复用。其它实验各自的失败与复用规则也应按目录 README 检查。

仓库没有纳入本地未跟踪的 `PLAN_V4.md`、`NOVELTY_REPORT.md` 和 `refine-logs/`：它们包含撤销后的 V4 设想或尚未充分核验的查新措辞，不属于当前可执行方法或正式证据。不要据此推断 V3 已实现生命周期价格、在线价格 DP 或新的 LP 放置目标。

## 请重点质疑的下一步选择

1. **结构效应：** 单集群多级 M2 的额外收益很小；在相同 GPU 数、层副本数、KV 上界和网络路径受到控制时，剩余可证明的机制是什么？
2. **目标一致性：** `measure()` 的均匀分流和最坏规范路径与 M3 实际选路有多大偏差？是否存在低成本但能改善独立布局选择的代理，而不在三个正式种子上反向调参？
3. **在线路径：** 单集群完整 DAG 退化、三集群改善的条件是什么？能否用可观测瓶颈定义路径准入规则，同时保留至少一条完整可执行路径？
4. **资源竞争：** 慢链路干扰、KV 可行性和固定 Decode 路径何者是主导限制？哪些反事实已经足以排除某种机制，哪些仍只是相关证据？
5. **研究主张：** 在现有负结果与失败窗口下，哪一个最小修改最有希望形成可复现、可消融、可向导师解释的创新点？请区分已证明、可测试假设和暂时不应采用的方案。
