# 多级共享复制 M2 候选

> 2026-10-16 更新：该四格实验中的 `multi_any` 规则已固定为 RCAPS V3 的 M2；V3 独立代码、布局和正式结果来源见 [V3 冻结记录](../v3_release/README_CN.md)。本目录继续保留原始候选实验及四格对照。

本目录保存 V3 多级放置的结构选择实验与原始结果。

## 方法与约束

- `placement.py` 用连续层段和各段完整副本表示布局。单边界为 `1→K`，双边界为 `1→K₁→K₂`，其中 `K₂<K₁` 允许汇合，`K₂>K₁` 允许再分叉。每个启用 GPU 恰好持有一个连续层区间；其余 GPU 闲置。
- 纯图 M1 `rcaps/v3/resource_graph.py` 提供物理资源和层兼容 DAG。生成布局时校验显存层容量、KV 容量、全模型覆盖、物理链路、源汇可达性和每个副本的完整路径。导出的部署仍使用 `solution.ini` 与 `simulator_cluster.ini`。
- `search.py` 保留原静态评价目标的权重 0.40/0.35/0.25。在旧评价器支持的单边界定义域（A100 共享且所有 GPU 启用）内，三个原始代价与强静态评价器一致。新增的闲置 GPU 与非 A100 初始共享布局由扩展评价器评分。双边界的路径代价按规范副本间的可达转移做动态规划，瓶颈需求在分叉处等权分流、汇合处累加。它是离线代价代理，不预测在线 P95。
- 分组初始化使用宽度 64 的确定性 beam，层边界间隔为 4；局部邻域包含边界 ±1、层分配、GPU 移动与交换。每个初始共享 GPU 类型限制先共享最多 500 次单边界评分，然后单边界和开放双边界各再最多 500 次评分。搜索是有界启发式；类型限制放宽后的结果不保证目标值单调改善。
- 四格对照：`single_a100`、`multi_a100`、`single_any`、`multi_any`。A100 限制只约束第一个共享层段，汇合后的共享尾段可以放在任何 GPU 类型。
- 在线运行使用 `rcaps/v3/scheduler.py` 的 DAG 接口适配器；实时路径代价、平局规则、Decode 固定路径和传输合并仍由原 M3 实现决定。

## 复现顺序

在仓库根目录执行：

```powershell
python -m unittest experiments.m2_multistage_candidate.test_multistage -v
python -m experiments.m2_multistage_candidate.probe
python -m experiments.m2_multistage_candidate.prepare
python -m experiments.m2_multistage_candidate.reference_audit
python -m experiments.m2_multistage_candidate.runtime_graph_audit
python -m experiments.m2_multistage_candidate.run --phase smoke
python -m experiments.m2_multistage_candidate.parallel_formal --workers 12
python -m experiments.m2_multistage_candidate.run --phase formal
python -m experiments.m2_multistage_candidate.report
```

可用 `--case C1_single` 等选项逐池运行离线准备和 60 秒检查。正式运行仅支持 C1 两拓扑、C2、C3；程序要求所有池的可行布局已通过种子 100 的 60 秒检查，才允许启动种子 0/1/2 的 1800 秒窗口。

`offline_audit.json` 记录结构、合法性、评分次数、规划时间和初始化失败原因。`smoke_index.json`、`formal_index.json` 保存结果路径、SHA256 与是否复用。`summary.json` 和 `RESULTS_CN.md` 汇总逐种子在线性能、共同完成请求、截尾情况及实际路径使用。原始 JSON 与日志在 `runs/`，失败日志保留供审计。相同部署文件在同一池、同一轨迹下只运行一次；复用前核验部署哈希、运行代码哈希、轨迹哈希与协议。

并行入口只分发相互独立的窗口，`parallel_formal_status.json` 逐窗口记录成功和失败；随后执行常规 `run --phase formal` 汇总并复核统一索引。`--workers` 可按机器资源调低。

`fixed_trace_probe.json` 来自固定四请求轨迹，分别检查 `1→2→1` 和 `1→2→4`，并验证实际路径属于导出的 M1 DAG、Decode 沿原请求路径继续执行。
`runtime_graph_audit.json` 逐布局核对导出图与模拟器加载后 M3 使用的图的节点层区间及每条边。
`reference_audit.json` 保存各池评分参考布局、状态哈希、来源哈希与三项静态参考值，并核对同池四格使用一致的参考。

多级布局的主要对照是同预算单边界布局。Helix 是完整系统的补充外部对照，Helix ILP 与 Helix–Petals 不合并命名。纯图 M1 本身不作为独立性能增益主张。
