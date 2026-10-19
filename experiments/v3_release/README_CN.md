# RCAPS V3 冻结记录（2026-10-16）

当前主方法为 `rcaps_v3`。V3 由纯图 M1、多级共享复制 M2 和原在线 M3 组成：

| 模块 | 冻结语义 | 入口 |
| --- | --- | --- |
| M1 | 物理资源图与放置后的层兼容执行 DAG；不模拟请求、不预测 P95，也不给布局评分 | `rcaps/v3/resource_graph.py` |
| M2 | 连续层段的单/双边界共享复制搜索，允许分叉、汇合、闲置 GPU 和任意类型初始共享 GPU；以静态异构资源目标选择布局 | `rcaps/v3/placement.py`、`rcaps/v3/search.py` |
| M3 | 沿 M1 合法边使用既有实时队列、链路和 KV 信息选路；保持 Decode 路径与传输合并语义 | `rcaps/v3/scheduler.py`、`rcaps/v3/online_scheduler.py` |

V3 **固定选择 `multi_any`**，即最多两个边界且不限制初始共享 GPU 的类型。这是统一的离线规则，不按在线结果逐池挑选四格。搜索允许退回单边界；因此“V3 多级方法”不意味着每个场景都实际采用两次分叉。静态目标权重保持 0.40/0.35/0.25，搜索是有界启发式，不保证全局最优，也不把静态代价称作在线尾延迟预测。

## 冻结布局与证据

`rcaps/v3_layouts/` 保存 C1 单集群、C1 三集群及 C2–C5 的 `multi_any` 部署。全部 INI 文件与[候选实验](../m2_multistage_candidate/RESULTS_CN.md)逐字节一致，代码与布局 SHA256、资源池物理文件、正式证据来源见[冻结清单](manifest.json)。

布局目录中的 `placement.json` 保留候选生成时的原始 `solution` 路径作为来源信息；实际 V3 运行入口读取同目录的 `solution.ini` 与 `simulator_cluster.ini`。

V3 的搜索初始布局和评分参考已固化在 `rcaps/v3/planning_inputs.json`；`rcaps/v3/plan.py` 可将搜索输出到单独目录，不会覆盖采纳布局。逐池重算与冻结 INI 的字节级核验见[重算审计](replay_audit.json)。

| 资源池 | V3 结构 | 正式窗口 |
| --- | --- | --- |
| C1 单集群 | 1→4→3，层边界 48/51 | 种子 0/1/2，1800 秒 |
| C1 三集群 | 1→3，层边界 48 | 种子 0/1/2，1800 秒 |
| C2 | 1→2，层边界 24 | 种子 0/1/2，1800 秒 |
| C3 | 1→2，层边界 72 | 种子 0/1/2，1800 秒 |
| C4 | 1→2，层边界 48 | 离线审计与种子 100、60 秒检查 |
| C5 | 1→3，层边界 48 | 离线审计与种子 100、60 秒检查 |

C1 两拓扑的 V3 正式记录是**经审计复用**候选的相同部署、相同执行语义、相同轨迹窗口，并在 JSON 中保留原文件路径及哈希；[复用索引](formal_reuse_index.json)逐种子列出来源。[短窗口校验](smoke_parity.json)在 V3 运行入口确认轨迹、部署哈希、吞吐、P95、路径计数与候选逐项相同。C2/C3 的正式原始记录仍位于候选目录，没有伪装成 V3 新仿真。

## 与 Helix 的正式对照

同种子 0/1/2、1800 秒窗口的 C1 结果见[机器对照](v3_vs_helix.json)：

| 拓扑 | 方法 | 平均输出吞吐 token/s | 平均 P95 TTFT s | 平均 P95 TPOT s/token |
| --- | --- | ---: | ---: | ---: |
| 单集群 | V3 | 155.980 | 3.580 | 0.559 |
| 单集群 | Helix ILP | 142.273 | 6.575 | 1.706 |
| 三集群 | V3 | 70.576 | 5.326 | 0.699 |
| 三集群 | Helix ILP | 58.255 | 15.583 | 3.194 |

C1 Helix 文件与 V3 的负载、种子、窗口、轨迹及请求身份一致，但没有记录物理配置 SHA256；不能将它标成物理文件哈希已核验。C2/C3 的结构实验保留 V3 原始窗口，本次主表不加入外部基线。三个种子描述波动，不宣称统计显著。

四格受控实验只在 C1 单集群证明实际选出的多级布局相对同预算单边界降低了三个种子的 P95 TTFT 和 TPOT。C1 三集群及 C2–C5 没有多级结构额外收益证据。初始共享段在全部已选布局中仍由 A100 承担，故本轮不能宣称使用非 A100 共享段带来性能增益。M1 图建模是合法执行关系的统一表示，不作为独立性能增益。

## 复现与完整性检查

在仓库根目录运行：

```powershell
python -m experiments.v3_release.verify
python -m experiments.v3_release.replay_audit
python -m experiments.v3_release.smoke_parity
python -m experiments.v3_release.reuse_formal
python -m benchmarks.run --dry-run
python -m benchmarks.compare --baselines helix --seeds 0 1 2
```

只有明确创建下一版时才使用 `verify --write-manifest`。运行 V3 新窗口时可使用 `python -m benchmarks.run --methods rcaps_v3`；无 `--force` 时，入口会复用同布局的现有正式记录。C2–C5 的资源池运行仍按候选目录中的自定义物理配置入口复现。
