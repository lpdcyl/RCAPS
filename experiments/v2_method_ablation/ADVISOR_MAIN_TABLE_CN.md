# RCAPS V2：核心问题、三个挑战与主结果

## 核心问题

**在异构 GPU 环境下，提高 LLM 推理吞吐量，降低请求尾延迟。**

具体到本文的 70B 服务场景，有限显存和非均匀网络约束模型放置，动态请求会争用 GPU、链路与 KV 容量；因此需要协同设计资源建模、模型放置与在线调度。

## 三个挑战与方法

| 挑战 | 具体问题 | V2 的方法与作用 | 递进消融 |
| --- | --- | --- | --- |
| **一：建模与评价** | 异构计算、显存、物理链路和多请求竞争如何影响候选放置？ | 以设备与链路画像、层兼容执行图和多请求事件图约束并评价放置；让放置决策考虑容量之外的计算和通信代价。 | **A**：在固定共享复制结构与固定路径调度下，加入异构资源感知放置。 |
| **二：放置优化** | 有限显存下，共享前缀的设备与层数、后缀复制结构如何联合确定？ | 在合法候选中搜索自适应共享复制结构，决定执行图的层覆盖和可选路径。 | **A+B**：保留 A 的评价和同一固定路径调度，加入自适应结构。 |
| **三：在线调度** | 请求到达后，如何利用执行图应对不断变化的 GPU、链路和 KV 负担？ | 在最终放置的层兼容 DAG 上动态选路，并协调就绪的 Decode 传输。 | **A+B+C（V2）**：保持 A+B 布局，加入 V2 在线调度。 |

递进链的**基础方案**采用仅由显存容量与物理连通性指导的固定共享复制结构，以及固定合法路径轮转调度。**Helix 是独立的外部基线，不是递进链的基础方案。**挑战一的这项递进实验检验资源感知放置流程的整体作用；它不单独证明事件图的预测准确性。

## 主结果：Helix 与递进消融同表

70B；两种 24-GPU 拓扑；官方负载；种子 0/1/2；每次 1800 秒、零预热、不排空窗口尾部。每格为**三个种子各自窗口指标的均值 ± 样本标准差**。吞吐为输出 token/s；TTFT、TPOT 为秒；完成率为百分数；积压为窗口结束时未完成请求数。P95 是三个种子各自 P95 的均值。

<table style="border-collapse: collapse; border-top: 2px solid; border-bottom: 2px solid; white-space: nowrap;">
  <thead>
    <tr>
      <th rowspan="2" style="text-align: left; border-bottom: 1px solid;">方法</th>
      <th colspan="5" style="text-align: center; border-bottom: 1px solid;">单集群</th>
      <th colspan="5" style="text-align: center; border-left: 1px solid; border-bottom: 1px solid;">三集群</th>
    </tr>
    <tr style="border-bottom: 1px solid;">
      <th>吞吐 ↑</th><th>P95 TTFT ↓</th><th>P95 TPOT ↓</th><th>完成率 % ↑</th><th>积压 ↓</th>
      <th style="border-left: 1px solid;">吞吐 ↑</th><th>P95 TTFT ↓</th><th>P95 TPOT ↓</th><th>完成率 % ↑</th><th>积压 ↓</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Helix（外部基线）</td>
      <td>142.273 ± 3.316</td><td>6.575 ± 0.165</td><td>1.706 ± 0.038</td><td>81.954 ± 0.975</td><td>231.7 ± 13.3</td>
      <td style="border-left: 1px solid;">58.255 ± 0.978</td><td>15.583 ± 0.252</td><td>3.194 ± 0.042</td><td>70.208 ± 2.029</td><td>172.7 ± 11.6</td>
    </tr>
    <tr>
      <td>基础方案</td>
      <td>132.779 ± 2.571</td><td>99.771 ± 59.294</td><td>2.360 ± 0.157</td><td>76.031 ± 3.494</td><td>308.0 ± 47.8</td>
      <td style="border-left: 1px solid;">58.568 ± 1.164</td><td>16.791 ± 0.508</td><td>3.410 ± 0.048</td><td>70.149 ± 0.877</td><td>173.0 ± 4.0</td>
    </tr>
    <tr>
      <td>+A：资源感知放置</td>
      <td>139.448 ± 1.263</td><td>45.462 ± 45.950</td><td>1.627 ± 0.045</td><td>80.775 ± 3.347</td><td>247.0 ± 44.8</td>
      <td style="border-left: 1px solid;">64.103 ± 1.075</td><td>10.939 ± 0.330</td><td>1.711 ± 0.033</td><td>79.469 ± 0.496</td><td>119.0 ± 2.6</td>
    </tr>
    <tr>
      <td>+A+B：自适应结构</td>
      <td>153.146 ± 3.917</td><td>3.955 ± 0.125</td><td>0.780 ± 0.023</td><td>90.755 ± 0.897</td><td>118.7 ± 11.6</td>
      <td style="border-left: 1px solid;">68.683 ± 1.082</td><td>7.123 ± 0.170</td><td>1.011 ± 0.008</td><td>87.860 ± 0.800</td><td>70.3 ± 3.8</td>
    </tr>
    <tr>
      <td><strong>+A+B+C：完整 V2</strong></td>
      <td><strong>155.918 ± 4.206</strong></td><td><strong>3.689 ± 0.106</strong></td><td><strong>0.565 ± 0.004</strong></td><td><strong>92.909 ± 0.516</strong></td><td><strong>91.0 ± 6.1</strong></td>
      <td style="border-left: 1px solid;"><strong>70.633 ± 1.127</strong></td><td><strong>5.332 ± 0.112</strong></td><td><strong>0.694 ± 0.006</strong></td><td><strong>91.834 ± 0.421</strong></td><td><strong>47.3 ± 2.5</strong></td>
    </tr>
  </tbody>
</table>

## 汇报时可直接说的结论

| 比较 | 单集群：吞吐 / P95 TTFT / P95 TPOT | 三集群：吞吐 / P95 TTFT / P95 TPOT |
| --- | --- | --- |
| **完整 V2 相对 Helix** | **+9.59 ± 0.50% / 降低 43.88 ± 1.23% / 降低 66.86 ± 0.58%** | **+21.26 ± 1.61% / 降低 65.78 ± 0.79% / 降低 78.28 ± 0.30%** |
| 基础 → A：加入资源感知放置 | 吞吐 +5.05 ± 2.00% | 吞吐 +9.46 ± 1.09% |
| A → A+B：加入自适应结构 | 吞吐 +9.85 ± 3.81% | 吞吐 +7.15 ± 0.67% |
| A+B → 完整 V2：加入动态调度 | 吞吐 +1.81 ± 0.28% | 吞吐 +2.84 ± 0.53% |

百分比先按同一种子配对计算，再报告均值 ± 样本标准差，因此不一定等于主表均值的直接比值。递进链显示三项方法在相应条件下的增量，差额不能相加。单集群基础方案和 A 的 KV 安全准入保护触发较多，且 TTFT 波动很大；其尾延迟差额需要谨慎解释。该保护在仿真中使用轨迹给定的目标输出长度作为预留上界。A+B 的六个正式窗口没有触发该保护。当前离线事件图主要评价预设后缀，不能据此宣称已验证完整 DAG 路径的建模精度。完整 V2 在两种拓扑均同时高于 Helix 的吞吐、低于 Helix 的尾延迟；这些结果来自仿真，三个种子只描述波动，不代表统计显著性或真实集群性能。

详细实验协议、逐项去除消融及审计说明见 [导师汇报完整摘要](MENTOR_BRIEF_CN.md)，逐种子记录见 [递进消融汇总](incremental_summary.json)。

## Helix 原 artifact 的其他基线：单列参考

下表直接摘录 Helix artifact 的 **70B 在线仿真**输出，用于说明 Swarm 与 Separate Pipelines（SP）在原研究中的表现；它们**不属于上面的共同负载、三种子配对主表**。原 artifact 只报告种子 0 的单次运行，不提供三个种子的样本标准差、完成率和末端积压。这里的 P95 是原 artifact 的 *prompt/decode request latency*，不能直接当成主表按请求汇总的 P95 TTFT/TPOT。

| 原 artifact 拓扑 | 方法 | 提供负载（输出 token/s） | 仿真 Decode 吞吐（token/s） | Prompt latency P95（s） | Decode latency P95（s） |
| --- | --- | ---: | ---: | ---: | ---: |
| 单集群 | Helix | 700 | 141.6 | 4.41 | 3.19 |
| 单集群 | Swarm | 350 | 69.8 | 5.01 | 2.51 |
| 单集群 | SP | A100/L4/T4 分别为 240/120/10 | 84.0 | 4.19 | 1.20 |
| 三集群 | Helix | 320 | 59.3 | 9.41 | 7.72 |
| 三集群 | Swarm | 160 | 31.0 | 14.83 | 6.50 |
| 三集群 | SP | A100/L4/T4 分别为 1/120/60 | 33.6 | 15.82 | 5.01 |

来源：[Helix artifact 单集群 70B 在线实验](../../artifact_evaluation/ae_readme.md)（第 293–379 行）与[三集群 70B 在线实验](../../artifact_evaluation/ae_readme.md)（第 1665–1751 行）；负载配置见 `artifact_evaluation/{single_cluster,distributed_clusters}/step3_simulation.py`。SP 的三套子集群各自生成请求，不能把该行与 Helix/V2 视为同一请求群体的配对比较。

**主表取舍。**当前主表使用单集群 700、三集群 320 token/s 的共同负载和三个种子。Helix 原 artifact 对 Swarm 使用 350/160，对 SP 则分别向三套子集群投送请求；因此上表不能填入主表。我们按主表负载直接运行原版 Swarm 与 SP，未加入 KV 准入保护；SP 为共用同一轨迹而按原子集群负载比例分配请求，分配不读取目标输出长度。[逐窗口核查](../helix_additional_baselines/RAW_BASELINE_AUDIT_CN.md)显示：Swarm 仅三集群种子 2 完成，其余五个窗口及 SP 的六个窗口均触发 KV 容量断言。两者都无法形成两个拓扑各三个完整窗口的汇总，失败窗口不填补指标，也不计算 V2 相对 Swarm/SP 的三种子提升。核心主表保留协议一致的 V2–Helix 与递进消融。

## 四方法共同负载补充实验

另按原 artifact 的 Swarm 提供负载设置单集群 **350**、三集群 **160** token/s，让 V2、Helix、Swarm、SP 在各自拓扑上使用共同轨迹与种子 0/1/2。24 个 1800 秒正式窗口全部完成；[完整绝对数值、配对改善及审计](../helix_additional_baselines/COMMON_LOW_SUMMARY_CN.md)独立成表。单集群 V2 与 SP 的吞吐分别为 **75.619 ± 0.740** 与 **75.636 ± 1.183 token/s**，不能声称 V2 在该档吞吐优于所有基线；V2 的 P95 TTFT/TPOT 为 **3.375 ± 0.059 / 0.455 ± 0.004 s**，SP 为 **4.354 ± 0.081 / 1.065 ± 0.029 s**。三集群 V2 在吞吐及两项 P95 延迟上均优于另外三种方法。此补充表不与上面的 700/320 主表跨负载相减。
