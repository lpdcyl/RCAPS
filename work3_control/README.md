# 工作三：完整路径收益与批处理代价控制

这是工作三的新根目录实现，不修改历史冻结的 simulator/、rcaps/、benchmarks/、experiments/ Python。当前只是仿真候选，不能将代码存在解释为论文贡献已经成立。

## 方法

新 Prompt 到达时，在同一个在线状态快照上运行两次原 M3：固定 partial 与 full。完整路径当前代价收益减去一个 Decode 轮的额外 GPU 工作代理，形成 net_proxy。基于模拟时间的 EWMA、迟滞和驻留控制是否使用扩展候选；原始收益非正时仍用 partial。Decode 不迁移，所有基线共享实际执行层的完整生命周期 KV 预约。

批处理轮工作量是近似，不是真实 TPOT 预测。M3 已有在线路由能力，因此必须超过 canonical/partial/full 中的最强基线及旧局部门槛。只比 full 好、却不优于 partial，不构成新增动态控制收益。

## 实际环境与运行

沿用已验证的 gllm，未创建/升级环境：Python 3.10.20、NumPy 1.26.4。本实验使用本地 CPU 离散事件仿真，没有分配实体 GPU。

从仓库根目录执行：

```powershell
./work3_control/run_local.ps1 -Phase test -Revision v3
./work3_control/run_local.ps1 -Phase freeze -Revision v3
./work3_control/run_local.ps1 -Phase smoke -Revision v3
./work3_control/run_local.ps1 -Phase development -Revision v3
./work3_control/run_local.ps1 -Phase report -Revision v3
```

脚本显式运行 conda activate gllm，设置 PYTHONHASHSEED=0。每格新建独立解释器，最多两个并行 CPU worker。不要删除失败 JSON 后悄悄重试；源码变化时保留旧 snapshots/audits/runs，登记新 revision。

## 预定开发矩阵

- 同一 C1_multi 24 GPU 冻结布局、名义网络。
- 0–200 秒 offered 50、200–400 秒 320、400–600 秒 160 input+output token/s。
- 开发种子 104/105；每段子种子 seed*100+段序号。
- canonical / partial / full / adaptive_link / route_control，共 10 格。
- 600 秒到达后，同一模拟器最多排空 1800 秒。所有到达请求必须完成。
- 轨迹生成器只接受 3 的倍数时长，故生成最小包围时长后裁剪到原定每段 200 秒；测量窗口仍为 600 秒。
- 正式 0/1/2 尚未启动；只能在开发、机制和开销门槛通过后登记正式协议。

延迟分支：两种子均优于各自最强固定 P95 TPOT，配对相对改善均值至少 3%，吞吐/TTFT/GPU 工作满足护栏。效率分支：在预定延迟与吞吐约束下，超过合格固定方法中 GPU 秒/token 最低者，两种子均改善、均值至少 10%。两个分支完整报告，并要求超过旧简单门槛、实际新增选路；失败停止当前候选。

## 完整性与故障历史

- v1：canonical/partial 烟测在轨迹生成前失败，原因是生成器要求时长为 3 的倍数；没有性能结果。原错误及源码快照保留。
- v2：5/5 烟测及逐请求独立复算通过；开发 canonical/seed104 出现 ModelLayer 返回值不可解包异常，partial/seed104 完成。矩阵停止，结果不作为完整对照结论。
- 诊断：同一 seed104 的短前缀与完整到达窗口，对比裸模拟及计时/执行观测；诊断单独保存，绝不混入效果判定。
- v3：所有方法统一增加 ModelLayer 纯函数返回值契约和异常现场记录。契约失败就终止，不做数值补救。完整重跑匹配对照，不复用 v2 单格结果；不能据此声称原生/运行时根因已经解决。

report.py 从原始 Decode 完成时间重算端点指标，从压缩的实际层执行事件重算 GPU 工作量与批大小；验证轨迹、KV、合法层覆盖、输出/层执行守恒和每个 Decode 的绑定路径。CPU 计时与仿真服务时间分开报告，不把仿真收益说成实体 GPU 净收益。

audits/ 记录冻结源码和环境；snapshots/ 保存各版本源码；runs/ 保留独立进程日志、原始结果、执行事件、复算与判定；diagnostics/ 为单独标记的运行诊断，不参与控制决策。

## v3 开发最终状态（2026-10-24）

10/10 开发完成，10 格独立事件复算与 10 类篡改拒绝通过。两个预定性能分支均失败：104/105 的 P95 TPOT 较最佳 full 高 3.153%/0.076%。按原规则停止当前候选，不启动正式 0/1/2、机制消融或 42 GPU 扩扫。

决断与描述性机制见 runs/v3/development_CLOSURE_CN.md；机器可读证据见 development_analysis.json、development_extended_verification.json 与 development_mechanism.json。控制器真实改变选路，但正向研究闭环尚未完成。v3 无新异常不代表 v2 返回类型异常根因已解决。

只重算描述性分析（不运行实验、不调参）：显式激活 gllm、设置 PYTHONHASHSEED=0 后，运行 `python work3_control/diagnostics/describe_development.py`。
