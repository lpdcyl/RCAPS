# Helix-GREEN 研究交接文档

更新日期：2026-10-10。工作目录为本仓库根目录。此文档供新窗口快速恢复上下文；方法细节与数字以链接的代码、原始 JSON 和结果报告为准。

## 1. 当前目标与已确定的研究范围

研究异构 GPU、可能跨集群的 LLaMA-70B 流水线推理。目标是在相同资源与请求轨迹下提高固定窗口输出吞吐，并降低在线请求的 P95 TTFT 与 P95 TPOT。当前工作**没有**能耗或碳排目标，也没有真实 GPU／广域网部署测量；性能证据来自 Helix 事件仿真器。用户重视正式系统论文的故事线、算法依据和可解释的创新，但不要求每个基础算法都前所未有。

系统主线：**资源依赖建模 → 拓扑与容量约束放置 → 运行时队列感知调度**。整体描述见 [METHOD_FRAMEWORK.md](METHOD_FRAMEWORK.md)，总框架图及其他图件见 [paper_figures/FIGURE_GUIDE.md](paper_figures/FIGURE_GUIDE.md)。

## 2. 当前实际实现的三个方法

| 阶段 | 当前实现 | 输入与输出 | 关键代码 |
| --- | --- | --- | --- |
| 建模 | 为计算、链路带宽占用和传播建立事件 DAG；用请求顺序边、共享资源串行边及 max-plus 最长路识别关键资源。放置代理使用固定的四个交错请求，每个八个输出 token。单集群还用前后向 log-sum-exp 动态规划得到合法路径集合的软边际需求；三集群使用代表性关键路径需求。 | GPU／链路画像、代表性并发工作负载 → 代理 TTFT／TPOT、关键资源、瓶颈需求。路径软权重不是在线真实选路概率。 | [event_graph.py](critical_graph/event_graph.py)、[topology.py](critical_graph/topology.py)、[path_ensemble.py](critical_graph/path_ensemble.py) |
| 放置 | 按物理链路 RTT 的最大比例间隙收缩快连接 GPU；选 A100 作共享前缀，构造两条容量可行的完整后缀；按传播时延与激活传输时间排列设备；在关键资源邻域尝试移动一层边界、交换相邻 GPU、调整共享边界，选代理分数下降最大的合法变动。 | 模型代理、物理拓扑和显存约束 → 每台 GPU 的连续层区间、仿真布局、层兼容 DAG。当前是特定“共享前缀＋两条后缀”的结构化局部搜索，不是任意图的通用划分器。 | [partition.py](critical_graph/partition.py)；最终放置在 [single_final](critical_graph/runs/single_final/placement.json) 和 [multi_final](critical_graph/runs/multi_final/placement.json) |
| 调度 | 新提示请求到达时读取正在执行的批、GPU 队列、链路占用及活跃 KV 会话，在层边界严格递增的兼容 DAG 上做加性工作量最短路。边代价包含链路等待与传输、GPU 等待与提示计算、活跃 KV 会话的一轮 decode 服务；decode 固定在提示阶段选定路径。已就绪且同下一跳的 decode 请求即时合并传输。 | 已部署层兼容 DAG、当前资源快照、请求长度 → 该请求的提示执行路径；不预测未来请求或输出长度。 | [routing_dag.py](queue_dag/routing_dag.py)、[scheduler_queue_cost.py](queue_dag/scheduler_queue_cost.py)、[scheduler_final.py](queue_dag/scheduler_final.py) |

放置代理为相对粗放置的归一化加权分数：`0.40 × 代理 TTFT + 0.35 × 代理 TPOT + 0.25 × 最大资源需求`；它不等于实测 P95 或吞吐，也没有全局最优保证。在线边代价以秒计，是选路代理而非真实完成时间恒等式。

## 3. 正式实验与可信数字

主实验：[multiseed/RESULTS.md](multiseed/RESULTS.md)；种子 0／1／2，Gurobi 13.0.3，相同场景和种子的成对方法共用请求轨迹。在线官方负载为单集群 700 token/s、三集群 320 token/s；每次运行 1800 s、无预热。下表是**完整系统相对 Helix**的三个逐种子相对变化的均值±样本标准差，`±` 不是置信区间：

| 场景 | 输出吞吐增加 | P95 TTFT 降低 | P95 TPOT 降低 |
| --- | ---: | ---: | ---: |
| 单集群 | 8.67 ± 0.39% | 34.28 ± 1.32% | 54.22 ± 1.29% |
| 三集群 | 18.85 ± 1.24% | 54.26 ± 1.81% | 70.06 ± 1.09% |

六项主指标各在 3／3 种子改善。在线负载扫描、RTT 敏感性、完成率、积压、共同准入离线对照和开销见 [ccfa_validation/RESULTS.md](ccfa_validation/RESULTS.md)。三档负载的六组场景中，三项主指标各在 3／3 种子改善。共同准入离线吞吐相对 Helix：单集群 +5.81 ± 0.12%，三集群 +66.36 ± 4.79%；双方原生准入的结果是另一种协议，见 [baseline_audit/RESULTS_OFFLINE.md](baseline_audit/RESULTS_OFFLINE.md)，不可混表。离线 Helix 本地种子 0 基线 252.1／98.0 token/s 与官方 artifact 一致。

**归因边界必须保留：**在官方高负载的“Helix 放置＋Helix 调度 → 新放置＋Helix 调度 → 新放置＋新调度”实验中，单集群中间方案种子 1 的 Helix 在线调度因 KV 可行性断言失败，复跑再次失败；故单集群放置的官方高负载中间方案仅有 2／3 完整种子，不能当成完整三种子统计。[逐种子报告](multiseed/PAPER_PLACEMENT.md)。三集群固定最终放置仅更换调度时，吞吐与 TPOT 改善，但 TTFT 在平均意义上变慢；开发负载调度消融也显示同一方向。因此“三指标同时改善”只能归于整合系统，不能单独归于挑战三。

负载 1.3 倍的三集群探索中，Helix 三种子均在窗口结束前不可路由，新方法三种子完成；这些失败不能换算成完整窗口的成对提升百分比。RTT 为 0.5／1／2 倍时重新规划的层划分相同，不能声称层边界随 RTT 自适应。种子 1 曾用于开发调参，不是独立盲测种子。固定窗口结束时不排空队列；延迟、完成率和积压应一起解释。

## 4. 近作检索与论文定位

上一窗口按当前代码和公开论文核对：尚未找到与三个模块及具体实现完全相同的单篇工作，**但不能据此出具文字或代码“无抄袭”鉴定**。最需要正面对照的是：

1. [Helix，ASPLOS 2025](https://www.cs.cmu.edu/~rvinayak/papers/Helix_ASPLOS_2025_Serving_LLMs_over_Heterogeneous_GPUs_and_Network_via_Max_Flow.pdf)：已联合优化层放置与每请求执行路径，使用最大流／MILP 和按流量份额的调度。不能把“联合放置与调度”或“每请求路径”写成首创。
2. [HexGen，ICML 2024](https://proceedings.mlr.press/v235/jiang24f.html) 与 [HexGen-2，ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/0b941a1e5fbce23fe46b049999d04ed0-Abstract-Conference.html)：研究异构 GPU／网络与模型划分，HexGen-2 已使用图划分和迭代优化，但它面向预填充／解码分离及跨阶段 KV 传输。不能单凭“图划分”三个字主张算法新颖。
3. [Sun 等，Performance Evaluation 2025](https://ece.iisc.ac.in/~parimal/papers/2025/peva.pdf)：跨地域模型块放置与在线请求路由采用双时间尺度；在线部分已经使用含等待、通信、计算代价的最短路。**挑战三与它有明显概念重合**。当前方法的可讨论差异是 GPU／链路即时积压、活跃 KV 会话服务代价、层兼容图和同链路已就绪 decode 合并，不能称“队列感知最短路”本身为首创。

论文故事应写成：**资源依赖瓶颈反馈如何贯通结构化放置与在线路径代价，并在 Helix 相同仿真平台中改善吞吐及尾延迟**。对放置建议使用“拓扑感知的结构化放置与关键资源局部细化”，准确反映两后缀实现。最可能被问的问题：与 Sun 等人的等待惩罚最短路具体差异是什么、局部搜索为何称图划分。若后续补实验，优先考虑在相同放置与轨迹上实现 WS-RR 风格对照，而非重复已有三种子主实验。

## 5. 文件入口、运行环境与下一窗口建议

- [实验导航](README.md)解释目录角色；先读 [METHOD_FRAMEWORK.md](METHOD_FRAMEWORK.md)，再读 [multiseed/RESULTS.md](multiseed/RESULTS.md) 和 [ccfa_validation/RESULTS.md](ccfa_validation/RESULTS.md)。旧 [RESULTS.md](RESULTS.md) 以单种子分析为主，不应覆盖较新的三种子数字。
- 使用仓库中的 `.venv_multiseed/Scripts/python.exe`；正式复验要求 **Gurobi 13**，不要换成 11。运行命令、跳过已完成结果的规则分别见 [multiseed/README.md](multiseed/README.md)、[ccfa_validation/README.md](ccfa_validation/README.md)。不要为写论文无故重跑已验证的完整窗口。
- Helix 原始仿真代码在 `simulator/`，当前方法在 `experiments/critical_graph/`、`experiments/queue_dag/`。`experiments/graph_pipeline/` 是早期实现与当前部分基础依赖，不是最终方法；`experiments/archive/` 是历史探索。
- 用户指定的本机 CCFA-Skills 位于 `~/.codex/CCFA-Skills`。写作先读 `ccf-humanization`、`ccf-common`，再使用相应专门 skill。此前已写过一版中文摘要；下一窗口若继续写论文，应结合上节近作风险修订贡献表述。
- 后续最值得做的工作是：完善与 Sun 等人的方法级对照；统一论文术语与当前代码；在相关工作中明确区分 Helix、HexGen-2、Sun 等；保留仿真、固定布局形态和种子 1 开发调参的真实边界。是否补新的运行实验，按下一窗口的具体要求决定。

## 6. 可直接贴给新窗口的任务上下文

> 我在 `Helix-GREEN` 项目中研究异构 GPU 和跨集群 LLaMA-70B 流水线推理，当前目标是提升输出吞吐并降低 P95 TTFT／TPOT，不研究碳排。已实现三个方法：资源依赖事件 DAG 与关键路径／路径集合需求；拓扑与显存约束下的共享前缀＋两后缀放置及关键资源邻域细化；队列感知层兼容 DAG 最短路与同链路已就绪 decode 传输合并。三种子、1800 s 官方在线完整系统对 Helix：单集群吞吐 +8.67%、TTFT -34.28%、TPOT -54.22%；三集群分别 +18.85%、-54.26%、-70.06%。全部为 Helix 仿真器结果，使用 Gurobi 13。请先读 `experiments/HANDOFF.md` 及其中链接；尤其注意 Sun 等 2025 年已有等待惩罚最短路，不能把最短路本身当新贡献，也不能声称三集群调度单独改善 TTFT。
