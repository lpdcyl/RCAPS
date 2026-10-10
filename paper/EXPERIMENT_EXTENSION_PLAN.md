# RCAPS 三种子补实验与论文表述计划

日期：2026-10-10。依照当前时间预算，正式分析只使用已有的种子 **0、1、2**；不引入新种子。所有性能证据来自 Helix 离散事件仿真器，不代表真实 GPU 或广域网部署。

## 证据边界

三个种子用于展示在相同轨迹下的运行波动。种子 1 曾参与开发调参，因此这不是独立盲测；逐种子请求也不是独立统计重复。现有官方负载端到端实验在两种拓扑的吞吐、P95 TTFT、P95 TPOT 上均为 3/3 同向，但单项单侧精确符号检验的最小 p 值为 0.125；六项 Holm 校正后为 0.75。**不能写“统计显著”或“泛化稳健”。**

报告逐种子原值、配对相对变化的均值±样本标准差及变化范围。已有 95% t 区间仅作为三条仿真轨迹之间波动的描述，不能解释为对真实硬件或其他拓扑的精确推断。

## 现有归因与新增实验

已有的 78 次三种子仿真见 `experiments/multiseed/RESULTS.md`。其中固定早期 DAG 调度的放置对照、固定最终放置的调度对照、放置内部细化对照及传输合并对照，应按**各自固定的配置和开发负载**解释。三集群固定最终放置时，新调度的 TTFT 均值反而变慢 2.48%；三集群局部细化的吞吐变化约为 -0.006%。这些反例必须和正向结果一起报告。官方高负载“新放置＋Helix 调度”在单集群种子 1 不可路由，不能用中断前指标拼接一个完整三种子归因表。

新增运行统一使用官方负载（单集群 700、三集群 320 offered token/s）、1800 秒固定窗口、零预热、相同物理 GPU 池和请求生成协议。运行入口保存每个请求的到达信息及 TTFT／TPOT，供截尾敏感性检查。

| 目的 | 配对比较 | 种子及次数 | 可支持的判断 |
| --- | --- | --- | --- |
| 公平性复核 | RCAPS 正式方案 vs Helix 官方 ILP 放置和 MaxFlow 调度 | 0、1、2；两拓扑共 12 次 | 轨迹哈希、请求身份、共同可观测请求的 P95、完成率和积压；核对历史端到端结果 |
| 调度消融 | RCAPS vs `rcaps_no_queue`、`rcaps_no_session`、`rcaps_no_coalesce` | 0、1、2；两拓扑共 18 次新增变体运行 | 当前队列释放时间、活跃 KV 会话代价和就绪解码合并在同一放置上的作用 |
| 放置消融 | `rcaps_capacity` → `rcaps_coarse` → RCAPS；三集群另比 `rcaps_alt_demand` | 0、1、2；共 15 次新增变体运行 | 容量构造、拓扑感知初始化、关键资源细化的逐级作用；替代路径需求的敏感性 |

这些消融只改变表述中的对应实现项。不同消融的百分比不可相加，也不能将开发负载的组件收益直接解释为官方负载端到端增益。若消融指标方向不一致，报告完整的吞吐、两类 P95、完成率和积压，而非只挑选改善项。

最核心的**放置阶梯**固定同一个 RCAPS 在线调度器、请求轨迹、24 台物理 GPU 与双后缀结构。`rcaps_capacity` 只按显存容量选择共享设备、平衡两支路并确定设备顺序，所有 24 台 GPU 各放至少一层，不读取 RTT 或带宽；`rcaps_coarse` 在容量约束上加入 RTT 连通分组和链路代价引导的设备顺序，但不做局部细化；正式 RCAPS 在这个粗布局上加入事件图关键资源反馈和局部移动。因此第一段差异估计**拓扑感知初始化整体**的作用，第二段差异估计**关键资源细化在拓扑初始化之上**的增量作用。三种布局均由相同规则导出合法拼接边，且使用相同调度器。共享设备及层放置不同是所研究的处理变量。

“完整 RCAPS”就是第三档放置加 RCAPS 调度，不能再把它作为放置阶梯的第四个独立组件。完整系统与 Helix 的比较另成一表；它同时改变放置和调度，不可用来直接归因于关键路径。若关键资源细化在三集群仅改善 TPOT，论文贡献应写成资源瓶颈解释与条件性细化，不能称其主导整体吞吐增益。

## 公平性、截尾与统计

基线使用发布的 Helix ILP 布局与原版在线调度；RCAPS 使用自身布局与在线调度。两者共享模型、精度、物理拓扑、设备画像、请求长度采样、负载、种子和测量窗口。逻辑放置与由此导出的合法执行边允许不同，因为这是比较对象。每组配对必须核对 `trace_sha256`、到达数、逐请求 ID、输入／输出长度和到达时刻。

固定窗口中，未在 1800 秒内得到首 token 或足够解码输出的请求不进入相应 P95；因此同时报告到达数、有效样本数、完成率和窗口末积压。再对**两方法均有观察值的同一请求集合**重算 P95，判断结果是否主要来自不同截尾集合。共同集合仍不包含完全未观察到输出的请求，不能消除所有截尾偏差。

统计单位为种子，结果主表用逐种子点和均值±样本标准差。可列出精确符号检验及 Holm 校正结果作为样本量限制的透明说明；不以每个请求充当重复、不得声称三种子证明统计显著。

## 复现命令

在仓库根目录、Python 3.10 环境执行：

```powershell
python -m benchmarks.run --methods rcaps helix rcaps_no_queue rcaps_no_session rcaps_no_coalesce rcaps_coarse --scenarios single multi --seeds 0 1 2 --workers 12
python -m benchmarks.run --methods rcaps_capacity --scenarios single multi --seeds 0 1 2 --workers 6
python -m benchmarks.run --methods rcaps_alt_demand --scenarios multi --seeds 0 1 2 --workers 3
python -m benchmarks.compare --baselines helix rcaps_capacity rcaps_coarse rcaps_no_queue rcaps_no_session rcaps_no_coalesce --seeds 0 1 2 --output paper/THREE_SEED_COMPARISON.json
python -m benchmarks.compare --main-method rcaps_coarse --baselines rcaps_capacity --seeds 0 1 2 --output paper/TOPOLOGY_INCREMENT.json
python -m benchmarks.compare --baselines rcaps_alt_demand --scenarios multi --seeds 0 1 2 --output paper/THREE_SEED_ALT_DEMAND.json
python -m benchmarks.paired_stats --source benchmark --seeds 0 1 2 --output paper/THREE_SEED_PAIRED_STATS.json
python -m benchmarks.manifest
```

每次运行保存命令和日志、代码版本、布局及仿真配置 SHA-256、请求轨迹 SHA-256、种子、协议字段和完整结果。失败运行保留失败状态；不以部分窗口填补结果。主要配置及版本由 `paper/RUN_MANIFEST.json` 记录。

## 论文可写与不可写的结论

可以写：“在两种已测 24-GPU 拓扑、官方负载和三个既有种子上，RCAPS 相对 Helix 的完整系统仿真呈现一致的吞吐与尾延迟改善。”可以给出逐种子差异和公平性检查结果。

共享前缀与双后缀仅是当前启发式放置的受约束搜索起点；尚未做等资源的 1／2／3 后缀结构对照，不能称双后缀普适最优。路径集合的 GPU 忙碌排序证据只能说明资源解释力，不能称为尾延迟预测精度。不能声称真实 GPU 部署收益、跨任意拓扑泛化或统计显著。
