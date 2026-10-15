# RCAPS V2 / V1 实验配图清单（2026-10-15）

所有图为重新绘制的科研图表；一图一轴，不将不同单位放到同一坐标轴；统计结果取自仓库的结果文件及已审计汇总。
**重要限制：** V1 历史结果不能写作 V2 泛化；仅三个正式种子，不代表统计显著；少数开发窗口只用于相关性诊断；完成率/积压应配合 P95 解读。

完整画册：`RCAPS_V2_V1_实验图册_2026-10-15.pdf`；单张图同时包含 PNG 与 SVG。

## 图 01｜V2 vs Helix：端到端增益
同负载三种子配对改善；延迟列表示降低，越高越好
说明：三集群相对 Helix 的吞吐增益为 21.26%，P95 TTFT / TPOT 分别降低 65.78% / 78.28%。这是系统级联合收益，不能拆分归因。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_ablation/ADVISOR_MAIN_TABLE_CN.md
PNG：`PNG/01_V2_vs_Helix_端到端增益.png`；SVG：`SVG/01_V2_vs_Helix_端到端增益.svg`

## 图 02｜V2 vs V1：版本增量
保留 V1 的强基线；三种子配对变化
说明：V2 的吞吐提升幅度较小，但两种拓扑的尾延迟改善较明显；它验证了 V2 相对于 V1 的进一步性能增量。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/adaptive_v2/RESULTS.md
PNG：`PNG/02_V2_vs_V1_版本增量.png`；SVG：`SVG/02_V2_vs_V1_版本增量.svg`

## 图 03a｜四系统共同低负载：吞吐量
相同物理资源、种子、请求轨迹；单集群 350、三集群 160 offered token/s
说明：单集群 V2 与 SP 吞吐基本相同；三集群 V2 较高。单集群和三集群负载不同，图中不对两场景绝对吞吐做横向排序。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/helix_additional_baselines/COMMON_LOW_SUMMARY_CN.md
PNG：`PNG/03a_四系统共同低负载_吞吐量.png`；SVG：`SVG/03a_四系统共同低负载_吞吐量.svg`

## 图 03b｜四系统共同低负载：P95 TPOT
同负载同轨迹；越低越好
说明：V2 在两类拓扑都取得更低的 P95 TPOT；尤其相对 SP，低负载下的延迟优势比吞吐优势更明确。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/helix_additional_baselines/COMMON_LOW_SUMMARY_CN.md
PNG：`PNG/03b_四系统共同低负载_P95_TPOT.png`；SVG：`SVG/03b_四系统共同低负载_P95_TPOT.svg`

## 图 04｜各方法自行负载的运行点
横轴负载不同：展示运行容量探索，不是公平性能排名
说明：V2 两类场景使用更高的运行点；但 L90 来自有限网格、负载不统一，不能用点间斜率或差值断言端到端优越性。三集群 SP 非完整窗口未绘出。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/helix_additional_baselines/OWN_LOAD_RESULTS_CN.md
PNG：`PNG/04_各方法自行负载的运行点.png`；SVG：`SVG/04_各方法自行负载的运行点.svg`

## 图 05a｜建模机制消融：候选选择的 TPOT
固定候选池，仅更换评分器；完整在线调度相同
说明：Event DAG 选择的布局在两种拓扑下都带来更低 TPOT；单集群 Compute-only 和 Compute+Comm 选中同一布局。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_core_ablations/RESULTS_CN.md
PNG：`PNG/05a_建模机制消融_候选选择的_TPOT.png`；SVG：`SVG/05a_建模机制消融_候选选择的_TPOT.svg`

## 图 05b｜建模评分与真实吞吐排序一致性
6 个预定结构候选；开发种子 100/101；600 秒在线窗口
说明：Event DAG 的候选吞吐排序 Spearman 单集群 0.943、三集群 0.886；在三集群，静态模型达到相近的一致性。仅代表当前候选样本。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_core_ablations/RESULTS_CN.md
PNG：`PNG/05b_建模评分与真实吞吐排序一致性.png`；SVG：`SVG/05b_建模评分与真实吞吐排序一致性.svg`

## 图 06a｜放置结构消融：P95 TPOT
Fixed Structure → Fixed Branches → Full Adaptive；在线调度相同
说明：开放共享长度、GPU 分组和后缀数量使尾延迟下降；但同时改变层副本量和路径阶段数，属于结构联合效应。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_core_ablations/RESULTS_CN.md
PNG：`PNG/06a_放置结构消融_P95_TPOT.png`；SVG：`SVG/06a_放置结构消融_P95_TPOT.svg`

## 图 06b｜三种部署结构的模型层副本预算
共享层只存一份；复制后缀按所有后缀累加，80 层模型
说明：Fixed Branches 使用 112 份层副本，Full Adaptive 使用 144 份：两者改变了副本预算，比较应解释为不同结构的综合效果，而不是单纯的选路收益。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_core_ablations/RESULTS_CN.md
PNG：`PNG/06b_三种部署结构的模型层副本预算.png`；SVG：`SVG/06b_三种部署结构的模型层副本预算.svg`

## 图 07a｜调度机制消融：P95 TPOT
相同 V2 布局 / DAG / Decode 传输；差别仅在路径状态代价
说明：在当前实验中，加入队列估计和 KV 会话服务代价逐步降低 TPOT；三集群完整 V2 相比 Queue-Aware 再降低 33.18%。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_core_ablations/RESULTS_CN.md
PNG：`PNG/07a_调度机制消融_P95_TPOT.png`；SVG：`SVG/07a_调度机制消融_P95_TPOT.svg`

## 图 07b｜调度机制消融：GPU 排队等待
同布局同执行机制；等待是 request-s / 到达请求数
说明：三集群静态 DAG、队列感知、完整 V2 的等待分别为 49.00、36.07、22.03；等待与尾延迟下降方向一致，但不能直接充当因果百分比分解。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_core_ablations/RESULTS_CN.md
PNG：`PNG/07b_调度机制消融_GPU_排队等待.png`；SVG：`SVG/07b_调度机制消融_GPU_排队等待.svg`

## 图 08｜完整搜索：Event DAG 相对静态模型
相同共享复制决策空间，分别完整搜索；正值为 V2 更好
说明：单集群 Event DAG 有有限增量；三集群吞吐略低、TTFT 基本持平。不能据冻结候选池的结果声称完整 Event DAG 搜索始终优于静态模型。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_comparisons/RESULTS_CN.md
PNG：`PNG/08_完整搜索_Event_DAG_相对静态模型.png`；SVG：`SVG/08_完整搜索_Event_DAG_相对静态模型.svg`

## 图 09｜放置搜索器：V2 vs Beam Search
同事件 DAG 评价和候选预算，Beam 宽度 4
说明：两种算法均选出 48 层共享前缀、三后缀；整体指标差异接近零。可支持结构问题可求解，但不能支持 V2 搜索器显著优于 Beam。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_comparisons/RESULTS_CN.md
PNG：`PNG/09_放置搜索器_V2_vs_Beam_Search.png`；SVG：`SVG/09_放置搜索器_V2_vs_Beam_Search.svg`

## 图 10｜完整 DAG 路由 vs 规范完整流水线
相同放置；强替代基于实时负载选 3 条完整流水线之一
说明：V2 在三集群吞吐 +7.81%，P95 TTFT -45.57%，TPOT -59.17%。这包含路径空间及传输合并的共同变化，不能完全归因于拼接选路。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_comparisons/RESULTS_CN.md
PNG：`PNG/10_完整_DAG_路由_vs_规范完整流水线.png`；SVG：`SVG/10_完整_DAG_路由_vs_规范完整流水线.svg`

## 图 11｜三个完整模块替换后的 TTFT 增量
完整 V2 相对各简化模块；其他两个 V2 模块保留
说明：三集群分别相对容量模型、固定结构和固定轮转降低 TTFT 51.83%、36.16%、25.12%；属于不同条件下的模块级收益，不能相加。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_ablation/REPORT_CN.md
PNG：`PNG/11_三个完整模块替换后的_TTFT_增量.png`；SVG：`SVG/11_三个完整模块替换后的_TTFT_增量.svg`

## 图 12a｜四级递进：三集群的 TPOT 下降
基础 → A(资源感知) → A+B(自适应结构) → A+B+C(完整调度)
说明：三集群每加入一组方法，TPOT 均进一步下降。注意四级并非严格的三个独立贡献加和；不同阶段有不同的条件。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_ablation/INCREMENTAL_REPORT_CN.md
PNG：`PNG/12a_四级递进_三集群的_TPOT_下降.png`；SVG：`SVG/12a_四级递进_三集群的_TPOT_下降.svg`

## 图 12b｜四级递进：相对基础的吞吐指数
各场景基础方案均设为 100，展示系统构建过程
说明：单集群基础吞吐 132.78→155.92；三集群 58.57→70.63 token/s。图是阶段均值的指数，仅作可视化；严格配对增益应见原报告。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_ablation/INCREMENTAL_REPORT_CN.md
PNG：`PNG/12b_四级递进_相对基础的吞吐指数.png`；SVG：`SVG/12b_四级递进_相对基础的吞吐指数.svg`

## 图 13｜共享前缀排队：不同部署结构
共享 GPU 的累计排队 request-s / 到达请求
说明：前缀更深导致共享段承载更多请求工作；不能把该共享等待值直接看成系统瓶颈排名。Full Adaptive 并非共享队列最小，却具有较好全系统尾延迟。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_core_ablations/RESULTS_CN.md
PNG：`PNG/13_共享前缀排队_不同部署结构.png`；SVG：`SVG/13_共享前缀排队_不同部署结构.svg`

## 图 14a｜在线实际执行路径的多样性
相同 V2 放置下的三种子平均不同 GPU 执行序列数；对数横轴
说明：单集群完整 V2 约 616 条实际执行路径，而完整流水线替代只用三条；三集群约 54 条。路径数是执行序列种类而不是吞吐。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_comparisons/RESULTS_CN.md
PNG：`PNG/14a_在线实际执行路径的多样性.png`；SVG：`SVG/14a_在线实际执行路径的多样性.svg`

## 图 14b｜最大单一路径上的请求集中度
同 V2 部署，比较三条流水线选择与层兼容 DAG 选路
说明：负载感知完整流水线在三集群将约 69.35% 请求集中于一条路径；V2 为 20.84%。可解释队列压力集中，但仍需结合其他机制。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_comparisons/RESULTS_CN.md
PNG：`PNG/14b_最大单一路径上的请求集中度.png`；SVG：`SVG/14b_最大单一路径上的请求集中度.svg`

## 图 15a｜离线候选打分开销：静态模型 vs 事件 DAG
同六份开发候选 × 5 次，单次打分中位耗时；对数横轴
说明：Event DAG 候选打分约 31 ms，静态模型约 0.2 ms，存在数量级的计算成本。必须与完整搜索后的端到端收益共同报告。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_comparisons/RESULTS_CN.md
PNG：`PNG/15a_离线候选打分开销_静态模型_vs_事件_DAG.png`；SVG：`SVG/15a_离线候选打分开销_静态模型_vs_事件_DAG.svg`

## 图 15b｜完整布局搜索开销：V2 vs Beam
两个算法采用相同事件 DAG 与评价预算；离线规划秒数
说明：单集群 V2 / Beam 约 6.88 / 7.06 秒，三集群约 15.48 / 15.74 秒，规划开销基本持平。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/v2_method_comparisons/RESULTS_CN.md
PNG：`PNG/15b_完整布局搜索开销_V2_vs_Beam.png`；SVG：`SVG/15b_完整布局搜索开销_V2_vs_Beam.svg`

## 图 16a｜V1 负载敏感性：吞吐提升随压力变化
V1 相对 Helix 的三种子平均配对吞吐增益
说明：在已测试的 0.7×、1.0×、1.1× 负载，V1 两种拓扑都保持正向吞吐优势；这是 V1 历史泛化，而非 V2 的已验证结果。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/ccfa_validation/RESULTS.md
PNG：`PNG/16a_V1_负载敏感性_吞吐提升随压力变化.png`；SVG：`SVG/16a_V1_负载敏感性_吞吐提升随压力变化.svg`

## 图 16b｜V1 三指标 × 负载：性能改善全景
六组正式窗口；正值表示 V1 相对 Helix 更好
说明：吞吐与尾延迟在六组配置中均呈改善；不同拓扑使用不同绝对 offered 负载，不做跨拓扑绝对指标的因果判断。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/ccfa_validation/RESULTS.md
PNG：`PNG/16b_V1_三指标_负载_性能改善全景.png`；SVG：`SVG/16b_V1_三指标_负载_性能改善全景.svg`

## 图 17a｜V1 跨集群 RTT 敏感性：吞吐优势
只缩放跨区域链路 RTT，带宽/GPU 保持不变
说明：RTT 增大时，相对 Helix 的吞吐改善从 16.26% 增至 24.66%。重新规划后 V1 布局并未随 RTT 改变，不能声称自适应层划分。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/ccfa_validation/RESULTS.md
PNG：`PNG/17a_V1_跨集群_RTT_敏感性_吞吐优势.png`；SVG：`SVG/17a_V1_跨集群_RTT_敏感性_吞吐优势.svg`

## 图 17b｜V1 跨集群路由：平均跨区域跳数
同硬件、不同 RTT；每条被分配路径的平均跨区域跨越次数
说明：Helix 约 3.57 次跨域，而 V1 约 1.02–1.05 次。跨区减少与 RTT 下的相对收益一致，但不等于单独控制“跨区次数”的因果实验。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/ccfa_validation/RESULTS.md
PNG：`PNG/17b_V1_跨集群路由_平均跨区域跳数.png`；SVG：`SVG/17b_V1_跨集群路由_平均跨区域跳数.svg`

## 图 18｜V1 离线：统一 KV 准入规则后的吞吐
20 初始请求、KV 门槛 0.8；60 秒预热 + 600 秒测量
说明：共同准入下，单集群 V1 266.78 vs Helix 252.14；三集群 V1 159.73 vs 96.06 token/s。与原生准入结果分开报告。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/ccfa_validation/RESULTS.md
PNG：`PNG/18_V1_离线_统一_KV_准入规则后的吞吐.png`；SVG：`SVG/18_V1_离线_统一_KV_准入规则后的吞吐.svg`

## 图 19｜V1 离线：双方原生 KV 准入规则
不同准入方法下的端到端吞吐增益，不作纯调度归因
说明：三集群原生准入下 V1 平均吞吐改善 64.29%，单集群 5.29%；由于两系统准入速度与准入规则不同，不能当作完全相同到达序列的微机制消融。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/baseline_audit/RESULTS_OFFLINE.md
PNG：`PNG/19_V1_离线_双方原生_KV_准入规则.png`；SVG：`SVG/19_V1_离线_双方原生_KV_准入规则.svg`

## 图 20｜V1 放置 × 调度 2×2：三集群吞吐
HH=Helix/Helix, HR=Helix放置/RCAPS调度；以此类推
说明：HH/HR/RH/RR 吞吐逐级不同，但存在收益重叠，三集群四格交互项为 -4.399 token/s。单集群 RH 仅 2/3 完成，不画成完整因子结果。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/validation_2026/CROSS_RESULTS.md
PNG：`PNG/20_V1_放置_调度_2_2_三集群吞吐.png`；SVG：`SVG/20_V1_放置_调度_2_2_三集群吞吐.svg`

## 图 21a｜V1 结构：共享前缀深度敏感性
固定双后缀设备分组与在线调度；越低越好
说明：三集群从共享 10→12 层，TPOT 从 0.984 降至 0.956 秒/token，但共享 GPU 排队增加；只支持当前结构邻域的局部权衡。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/structure_ablation_2026/RESULTS.md
PNG：`PNG/21a_V1_结构_共享前缀深度敏感性.png`；SVG：`SVG/21a_V1_结构_共享前缀深度敏感性.svg`

## 图 21b｜V1 单路径与双后缀：主负载吞吐
9 张 GPU 精选单路径 vs 原 24 GPU 双后缀结构
说明：双后缀吞吐两拓扑均更好，但单集群精选单路径 TTFT 反而较低。此对照同时改变复制量及活跃 GPU 数量，不应仅归因于多路径。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/structure_ablation_2026/RESULTS.md
PNG：`PNG/21b_V1_单路径与双后缀_主负载吞吐.png`；SVG：`SVG/21b_V1_单路径与双后缀_主负载吞吐.svg`

## 图 22｜V1 放置消融：拓扑与事件图细化
B/A 为增加拓扑感知；C/B 为在拓扑初始化后加入事件图细化
说明：拓扑感知在三集群的收益明显；事件图局部细化在单集群较有帮助，但三集群 TPOT 退化 0.77%。不存在所有场景均正向的组件贡献。
来源：https://github.com/lpdcyl/RCAPS/blob/main/paper/ABLATION_ATTRIBUTION_CN.md
PNG：`PNG/22_V1_放置消融_拓扑与事件图细化.png`；SVG：`SVG/22_V1_放置消融_拓扑与事件图细化.svg`

## 图 23｜V1 在线组件消融：TPOT 增量
固定 V1 布局；分别测试传输合并及活跃 KV 会话代价
说明：就绪 Decode 合并在两种拓扑均降低 TPOT；KV 会话代价在三集群有明显收益，但在单集群观察到 TPOT 回退，不能概括为普遍提升。
来源：https://github.com/lpdcyl/RCAPS/blob/main/paper/STABLE_IMPROVEMENTS_CN.md
PNG：`PNG/23_V1_在线组件消融_TPOT_增量.png`；SVG：`SVG/23_V1_在线组件消融_TPOT_增量.svg`

## 图 24｜V1 关键资源剪枝：候选评分次数
相同最终放置的完整邻域 vs 关键资源筛选搜索
说明：单集群候选评分从 115 降到 68（40.9%）；三集群均为 272，未节省工作。该图是搜索成本收益，不是运行时吞吐收益。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/validation_2026/RESULTS.md
PNG：`PNG/24_V1_关键资源剪枝_候选评分次数.png`；SVG：`SVG/24_V1_关键资源剪枝_候选评分次数.svg`

## 图 25｜V1 运行开销：传输调度 P95 调用耗时
同场景种子 0；不同系统事件调用次数不同
说明：单集群 V1 传输调度调用 P95 约 20.0 μs，Helix 27.7 μs；三集群 V1 29.5 μs，Helix 23.9 μs。不能外推为 V2 的 CPU 开销。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/ccfa_validation/RESULTS.md
PNG：`PNG/25_V1_运行开销_传输调度_P95_调用耗时.png`；SVG：`SVG/25_V1_运行开销_传输调度_P95_调用耗时.svg`

## 图 26a｜预测代理：GPU 排队排名相关性
在线热点 Spearman；固定原布局比较代理与在线观测的排序
说明：新队列代理在三集群将 Spearman 从 0.587 提高到 0.788，但单集群由 0.648 降至 0.499；这是条件性预测改善。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/queue_predictor_2026/RESULTS.md
PNG：`PNG/26a_预测代理_GPU_排队排名相关性.png`；SVG：`SVG/26a_预测代理_GPU_排队排名相关性.svg`

## 图 26b｜预测代理：最终在线吞吐并未改善
在新代理生成的放置上完整仿真，三种子均值
说明：单集群新代理吞吐 152.633，低于原 V1 的 154.611；三集群 69.212 vs 69.234 基本持平。排序改善并不等于全系统改善。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/queue_predictor_2026/RESULTS.md
PNG：`PNG/26b_预测代理_最终在线吞吐并未改善.png`；SVG：`SVG/26b_预测代理_最终在线吞吐并未改善.svg`

## 图 27｜实验审计：正式窗口完成比例
各项研究协议不同；完成率只反映所选运行配置的执行状态
说明：V2 核心消融与强替代方法新增运行均完整；V1 单一路径高负载和特定跨调度组合存在 KV 容量/路由失败。不能把失败项当作吞吐为零。
来源：https://github.com/lpdcyl/RCAPS/blob/main/experiments/structure_ablation_2026/RESULTS.md
PNG：`PNG/27_实验审计_正式窗口完成比例.png`；SVG：`SVG/27_实验审计_正式窗口完成比例.svg`

## 图 28｜42 GPU 高异构配置：原 Helix artifact
仓库中存在的物理 GPU 配置，不是 RCAPS V1/V2 泛化结果
说明：包含 A100、V100、L4、T4 及多卡节点类型，共 42 个计算节点；没有核实到 V2 在该资源池上的正式对照，不能误标为 RCAPS 已验证结果。
来源：https://github.com/lpdcyl/RCAPS/blob/main/artifact_evaluation/high_heterogeneity/step1_gen_cluster.py
PNG：`PNG/28_42_GPU_高异构配置_原_Helix_artifact.png`；SVG：`SVG/28_42_GPU_高异构配置_原_Helix_artifact.svg`