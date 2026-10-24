# 工作三：自适应空间复核

目的：先检验已有固定策略交叉是否能在完整请求生命周期、固定到达前缀下保持，再决定动态路径空间控制的正式验证是否有依据。

这是 CPU 离散事件仿真，使用冻结的 C1_multi 24 GPU 模拟拓扑。没有实体 GPU 测速，也没有 42 GPU 或少 GPU/Helix 优势结论。

## 已冻结的最小矩阵

- middle/nominal、high/nominal、high/crosslink_4x。
- canonical、partial、full，M3、放置、KV 准入和网络干预均不变。
- 正式种子 **0/1/2**，1800 秒到达窗口，然后最多 1800 秒排空。
- 每格先精确复现历史窗口，再继续同一个模拟状态，保存每个请求的全部 Decode 完成时刻。
- 全部到达请求的完整生命周期 P95 TPOT 为主指标，arrival < 1200 秒固定前缀为敏感性检查；原窗口吞吐/完成率仍为护栏。
- 独立重建请求轨迹、窗口指标、生命周期指标、token 守恒、KV 和路径合法性。未排空、失败或缺格均不能得出正向结论。

## 执行

在仓库根目录运行，启动器会显式激活 gllm 并验证 Python 路径：

```powershell
.\experiments\v3_adaptive_space_cohort\run_isolated.ps1 -Phase smoke -Workers 3
.\experiments\v3_adaptive_space_cohort\run_isolated.ps1 -Phase development -Workers 3
.\experiments\v3_adaptive_space_cohort\run_isolated.ps1 -Phase formal -Workers 3
```

源码冻结已在 audit.json 注册；不能修改源码后继续将旧结果称为同一版本。原 v3_path_crossover 实验没有被覆盖。

## 判定边界

两个状态有不同唯一主指标胜者，且同一对策略在全样本、固定前缀中均有至少 2/3 配对种子保持反转、前缀均值方向也保持，才通过本次范围内的交叉复核。规则见 protocol.json。

即使通过，也仅确认候选自适应空间，动态控制器仍需证明在线可观测、有效响应、相对最强固定策略有净收益，并解释批处理/链路代价和控制开销。

若未通过，应记录当前矩阵未确认该空间；不能推出所有拓扑、负载或控制方法都没有机会，也不能反过来直接将动态门控写成已验证贡献。

排空会降低尾段争用，固定前缀只是一个事先固定的敏感性检查；后续仍需持续负载与真实时变状态的闭环验证。

确定性复算与破坏性数据检查不是独立跨模型研究审核；后者当前未提供。

事后按状态选择参照，按各状态的“三种子 P95 均值”选择策略，再另报混合请求分布的 P95。它没有直接优化混合 P95，可能比最佳全局固定策略更差；负差距不能解释成所有分阶段策略都不可能改善混合尾延迟。该参照不是动态控制收益上界，也不参与注册交叉判定。

## 输出

- `formal_index.json`：每格 Python 进程退出码与是否存在结果。
- `formal_analysis.json` / `formal_RESULTS_CN.md`：完整性检查、全部结果、交叉判定和事后选择参照。
- `runs/formal/`：原始逐请求结果与日志；发生异常时保留 `.failure.json`。
- `corruption_checks.json`：对篡改指标、缺 token、错轨迹、KV 越界、非法路径和不完整请求的拒绝检查。
