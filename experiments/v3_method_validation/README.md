# V3 方法验证

本目录只保存独立实验适配器和结果；冻结的 `rcaps/v3`、V3 部署文件与原正式窗口不改写。
三类证据分别回答：Helix/V3 放置和调度的条件收益、M2 静态目标的作用、M3 实时状态的作用。

## Helix × V3 四格

`HH` 为 Helix ILP＋Helix Online MaxFlow，`HR` 为 Helix ILP＋V3 M3，
`RH` 为 V3 M2＋Helix Online MaxFlow，`RR` 为完整 V3。只有相同拓扑、负载、种子和
轨迹下四格齐全才报告交互量。旧版本交叉实验结果不进入本目录主表。

```powershell
python -m experiments.v3_method_validation.crossover --phase audit
python -m experiments.v3_method_validation.crossover --phase smoke --workers 4
python -m experiments.v3_method_validation.crossover --phase formal --workers 4
python -m experiments.v3_method_validation.crossover --phase report
```

高负载正式窗口为单集群 700、三集群 320 offered token/s；0/1/2 三种子、1800 秒、
零预热、不排空。若某拓扑的高负载格失败，保留异常并对该拓扑全部四格执行预设
低负载（单集群 350、三集群 160）：

```powershell
python -m experiments.v3_method_validation.crossover --phase low --workers 4
python -m experiments.v3_method_validation.crossover --phase report --report-phase low
```

`crossover_audit.json` 记录物理与部署哈希、GPU/NIC 参数、合法 DAG 路径数和未接入
路径的已加载 GPU。每个原始窗口与失败记录均在 `runs/`；索引保存 SHA256。
RH 若因原 Helix 调度器无法处理 V3 布局而失败，不修改布局或调度器，也不把失败填作
零吞吐。

## M2 静态目标

四个评分为冻结完整目标 `0.40/0.35/0.25`、Prompt Only、Decode Only 和
Prompt＋Decode（`0.40/0.75, 0.35/0.75, 0`）。同资源池固定相同参考布局、搜索
初始化、邻域和评价上限。C1 两拓扑、C2、C3 先做离线搜索；正式在线窗口只在 C1
两拓扑使用同一 M3。相同部署与执行语义复用窗口。完整目标必须逐字节复现 V3 布局。

```powershell
python -m experiments.v3_method_validation.m2_objective --phase plan --workers 4
python -m experiments.v3_method_validation.m2_objective --phase smoke --workers 4
python -m experiments.v3_method_validation.m2_objective --phase formal --workers 4
python -m experiments.v3_method_validation.m2_objective --phase report
python -m experiments.v3_method_validation.m2_search_efficiency
```

搜索效率诊断仅比较冻结静态分数、唯一候选评价数和规划时间。随机邻域搜索使用
固定离线种子 10–14；较低静态分数不自动解释为在线收益或全局最优性。

## M3 实时状态

所有方法固定 V3 布局和完整 M1 执行 DAG。`queue_only` 只计当前 GPU 工作；
`observed_eft` 再计链路等待；`full_no_session` 在当前实现下与
`observed_eft` 等价，因为冻结基类已关闭已承诺路径工作量，且两者均关闭
KV 会话定价；
`full_no_link` 保留其余完整状态但关闭动态链路等待。完整 M3 为冻结实现。
基础计算、传输、Decode 固定路径与传输合并在各组相同。静态 DAG 和完整 M3
正式窗口经协议核验后复用。

```powershell
python -m experiments.v3_method_validation.m3_run --phase smoke --workers 4
python -m experiments.v3_method_validation.m3_run --phase formal --workers 4
python -m experiments.v3_method_validation.m3_run --phase report
python -m experiments.v3_method_validation.m3_contributions
```

正式表包括逐种子吞吐、P95 TTFT／TPOT、完成率、积压和共同完成请求；
短窗口记录选路耗时。`m3_contributions` 不改 M3 入口或变体定义，先核验
36 个窗口及配对轨迹，再把四项状态贡献和三种子均值 ± 样本标准差追加到
`m3_formal_report.md`，同时输出 `m3_formal_contributions.json`。三个种子
只描述波动，不用于统计显著性声明。

T3 的额外复跑曾出现 KV Cache 异常和进程池中断；首轮完整结果及隔离诊断
的可比性、换行符哈希等价关系与尚未解决的重复性问题记录在
`T3_DETERMINISM_AUDIT_CN.md`。目前应暂停机制结论，不把额外失败折算为零。
