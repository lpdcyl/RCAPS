# 外部基线模拟复现实验（开发版）

## 目的与来源

在 RCAPS 与 Helix 使用的离散事件模拟器中，复现外部论文方法，并用同一物理拓扑、70B 模型、请求轨迹、观察窗口与指标做端到端比较。这里的运行均为 CPU 模拟，不涉及真实 GPU 推理。本目录记录最初提出的 HexGen / HexGen-3 可行性核查；当前第二基线优先候选已因内存硬约束调整为 FastPP，详见 `BASELINE_DECISION_CN.md`。

* HexGen: Jiang et al., ICML 2024, https://proceedings.mlr.press/v235/jiang24f.html 。官方源码 `HexGen` commit `949414d1be18e504752508c0559cb966ddf999f4`。
* HexGen-3: Jiang et al., ICML 2026, https://proceedings.mlr.press/v306/jiang26z.html 。官方源码 `HexGen-3` commit `efa3ed99e4337e5443f5fe4ee8c2fb2c29076de7`。
* FastPP: Hwang and Ahn, OSDI 2026, https://www.usenix.org/conference/osdi26/presentation/hwang 。官方源码 `FastPP` commit `cb3ce5b39c085a671b2c79477ac6d673b55f8eac`。

论文 PDF 和提取文本保存在 `source/`。源码克隆保存在项目外 `D:/PythonProject/_rcaps_external_sources/`，防止将论文实现误作本项目已有基线。

## 方法契约和可行性门槛

HexGen 把 GPU 分成若干完整模型流水线，在各流水线内决定异构阶段、层数与通信路径，搜索目标结合服务质量、计算、通信和显存约束。拓扑中的 `T4x2`、`T4x4`、`L4x2` 是已有的机器聚合类型，其内部并行性能由当前模拟器的 profile 表示。跨机器只允许流水线通信。开发复现应包含论文的多流水线分组、显存硬约束、给定分组的层划分优化、分组进化搜索、在线请求分配；每项偏差单列。

HexGen-3 在 prefill、decode attention、decode FFN 三类 worker 之间转移 KV 和激活；全局资源分配与局部并行优化、负载变化时的独立扩缩容属于方法机制。现有 `fixed_window.py` 的 query manager 将 decode 固定在 prefill 路径上，且节点 profile 把 attention 与 FFN 合并。因此直接换 scheduler 无法成为 HexGen-3 端到端基线。

70B 模型 80 层。24 节点单集群可放置层总量为 152；两个完整模型副本至少需要 160 层，所以 HexGen 的多流水线分组在此拓扑不可行。42 节点高异构集群总量为 350 层，可以测试多流水线。

HexGen-3 的局部并行策略仅含 DP/TP/EP，论文 §4.2.2 的 C3 把 TP/EP 限于单台物理机器，没有单个 worker 的跨机器流水线并行。当前 70B 模型权重为 122.4 GB；24 节点最大单机显存 40 GB，42 节点最大单机显存 64 GB。连完整模型的 prefill worker 都放不下，所以按论文约束在**全部当前拓扑均不可行**。该判定由 `python -m experiments.hexgen_sim.feasibility` 复核。改变模型、精度或机器组形状会改变比较对象；不能放宽 C3 后仍称作原论文方法的同条件基线。

## 实验协议

1. 固定论文/源码 commit、代码和输入 SHA、搜索种子、模拟器版本，保存布局及规划日志。
2. 对两个拓扑分别做放置可行性检查。对可行布局先进行极短 smoke，校验每个请求恰好归属一个副本、完整 80 层路径、KV 容量、事件单调性和 trace SHA。
3. 仅在方法机制完整且 smoke 通过后，运行与 RCAPS 配对的五种子、相同负载/时长/预热正式窗口。规划/冒烟/正式工件分目录，已有工件只读。
4. 正式结果与开发近似、失败重放分别记账。任何无法复现的机制或失败键都保留原始证据，不将其填补为正式成功。

当前状态：HexGen 已用开发种子上的事件模拟器 SLO 搜索选型，并在 24 节点主矩阵运行三版冻结协议。三个条件有完整的配对五种子结果；单集群 700 token/s 因 KV 超容量及反复出现的原生/内部对象异常，仍无可引用的完整五种子组。各版结果与失败证据见 `FINAL_STATUS_CN.md`，不能跨版回填。HexGen-3 在当前 70B 拓扑上硬约束不可行；无其正式结果。FastPP 工作暂停，待 HexGen 结果交付后另行继续。
