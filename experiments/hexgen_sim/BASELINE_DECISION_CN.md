# RCAPS 外部端到端基线选型记录（2026-11-08）

## 同条件资格

外部方法应来自独立论文；能在当前 70B、FP16 画像、24/42 节点物理拓扑上生成有效部署；能用同一请求轨迹和模拟器事件语义计算逐请求 TTFT、TPOT、完成率及吞吐。若论文核心机制需要尚未建模的硬件资源，不能用一个简化调度器冒充论文方法。

## 候选

| 论文方法 | 来源 | 当前拓扑资格 | 处理 |
|---|---|---|---|
| HexGen | ICML 2024，https://proceedings.mlr.press/v235/jiang24f.html | 24 节点仅一条完整 70B 流水线；42 节点可多流水线 | 已完成模拟器 SLO 选型与 24 节点正式运行；三个条件有完整五种子结果，700 token/s 无完整组。详见 `FINAL_STATUS_CN.md`。 |
| HexGen-3 | ICML 2026，https://proceedings.mlr.press/v306/jiang26z.html | 当前 70B 模型权重 122.4 GB，最大单机显存 40/64 GB；论文局部 TP/EP 限单机，无 worker 内 PP，无法部署完整 prefill worker | 当前同条件实验记为方法硬约束不可行，不生成伪端到端数字。其论文主评测是 Qwen3-30B-A3B MoE，也与当前 70B dense profile 不同。 |
| FastPP（Revisiting Pipeline Parallelism for LLM Serving） | OSDI 2026，https://www.usenix.org/conference/osdi26/presentation/hwang；官方代码 https://github.com/Sys-KU/FastPP | 只要求能放置一条完整 PP 流水线；24/42 节点均满足必要容量条件 | **第二篇优先替代**。动态 prefill chunk（贪心或 ALP）和 batch rebalancing 对单流水线也有作用，因而 24 节点主矩阵不退化。必须在当前事件模型中实现分块和延迟调度并核对官方代码，不能只改一个负载均衡参数。 |
| OServe | ICML 2026，https://proceedings.mlr.press/v306/jiang26k.html | 论文明确支持多副本的 TP/PP，包含 70B 模型的显存约束例子；但 24 节点只能有一条完整副本 | 42 节点扩展备选。24 节点的 workload-aware 多副本分配退化，因此不宜充当主矩阵第二基线。 |
| HexGen-2 | ICLR 2025，https://openreview.net/pdf?id=Cs6MrbFuMq | 支持异构 TP/PP 和 prefill/decode 分离；24 节点两份 70B 模型的现有层容量不足，42 节点有必要容量但需 KV 传输事件 | 作为 42 节点专用备选，不能充当 24 节点同条件全矩阵。 |

`python -m experiments.hexgen_sim.feasibility` 是容量审计的复核命令。该审计只证明必要约束，不证明执行可行性。HexGen 开发结果见 `development/`，正式可用条件与失败边界见 `FINAL_STATUS_CN.md`；开发和诊断重放不能加入正式对照表。

后续：700 token/s 条件需要在修复计算环境后按新的完整五种子协议重跑。FastPP 尚未完成分块 prefill、动态 chunk size 和 batch rebalancing 的同条件正式实验。
