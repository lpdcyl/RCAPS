# Helix-GREEN 实验结果总报告

更新日期：2026-10-09。**三种子新结果请优先阅读 [`multiseed/RESULTS.md`](multiseed/RESULTS.md)**，其中包含 Gurobi 13.0.3 下 78 次仿真的逐种子表、均值与样本标准差；原始 JSON 和日志位于 [`multiseed/runs/`](multiseed/runs/)。本页保留原单种子结果及方法说明，下面第 3–6 节为种子 1 的开发实验，第 7 节为种子 0 的官方负载对照。三种子结果发现：固定最终放置后三集群调度归因的 TTFT 仅在 1/3 种子改善，不能沿用本页第 6 节单种子结果作跨种子结论。仿真结果不构成真实 GPU 的性能保证。

## 1. 研究问题与最终方法

目标是在跨集群流水线推理中提高输出吞吐并降低请求延迟。碳排放与能耗不作为本轮目标，也未被实验测量。

| 挑战 | 方法 | 在系统中的作用 |
| --- | --- | --- |
| 计算、通信、排队相互耦合，难以解释瓶颈 | 包含计算、传输、传播和资源串行依赖的事件 DAG；关键路径与路径集合需求分析 | 识别会延长 TTFT/TPOT 的资源，并为放置提供需求估计 |
| 层边界和设备位置必须联合决定 | 关键路径反馈驱动的容量约束图划分与局部细化 | 构造覆盖全部模型层的可行流水线，调整瓶颈附近的层边界和设备位置 |
| 静态放置无法适应动态队列 | 队列感知的分层 DAG 最短路调度，保留 KV 路径；就绪 decode 请求合并传输 | 在请求进入时选择路径，减少排队和重复链路传播开销 |

第一、二项实现在 [`critical_graph/`](critical_graph/README.md)，第三项实现在 [`queue_dag/`](queue_dag/README.md)。最终放置是 [`single_final`](critical_graph/runs/single_final/placement.json) 与 [`multi_final`](critical_graph/runs/multi_final/placement.json)；保存结果中的调度策略名为 `coalesced_corrected`，新运行入口的等价名称为 `final`。方案独立实现建模、放置和调度，沿用 Helix 的事件仿真器及其 GPU/网络配置作为执行环境。

## 2. 实验协议与指标

| 项目 | 单集群 | 三集群 |
| --- | ---: | ---: |
| 模型与设备 | LLaMa-70B，24 GPU | LLaMa-70B，24 GPU |
| 请求生成器的 offered load | 400 token/s | 160 token/s |
| 种子 | 1 | 1 |
| 仿真总时长 / 预热 / 测量 | 1980 / 180 / 1800 s | 1980 / 180 / 1800 s |
| 测量窗口内到达请求 | 732 | 284 |
| 有 TTFT/TPOT 样本的请求 | 730 / 730 | 283 / 283 |

这里的 400/160 是**开发实验的目标总 token 到达率**，不是每秒请求数。Helix 的 `TraceGenerator` 用 `目标 token/s ÷ 数据集平均每请求 token 数` 设置平均请求到达率；本仓库 Azure Conversation 长度数据的平均输入加输出长度为 **995.53 token/请求**。因此 1800 秒内的期望量级约为 723/289 条请求。固定种子在完整 1980 秒轨迹中生成 **804/313** 条，去掉前 180 秒预热后落入测量窗口的为 **732/284**。TTFT/TPOT 样本数略小，是因为窗口末仍有少数请求没有获得足够的输出 token。生成器实现见 [`trace_generator.py`](../simulator/trace_generator/trace_generator.py) 与 [`length_sampler.py`](../simulator/trace_generator/length_sampler.py)。

**与原论文区分：** [Helix 原文 §6.2](https://www.cs.cmu.edu/~rvinayak/papers/Helix_ASPLOS_2025_Serving_LLMs_over_Heterogeneous_GPUs_and_Network_via_Max_Flow.pdf)报告过滤后的 Azure Conversation 数据集共 **16,657 条请求**、平均输入/输出长度约 **763/232 token**；16,657 是数据集总量，原文没有列出单集群或三集群一次 1800 秒实验的请求总数。原文描述在线实验预热 30 秒、测量 30 分钟；本节是预热 180 秒的开发实验。第 7 节按官方 artifact 的 700/320 token/s、种子 0、1800 秒设置复现，在窗口内分别到达 **1293/584** 条请求；该 artifact 的仿真脚本设定预热为 0 秒。两类结果不能混为同一实验协议。

主端到端对照和最终调度归因均使用 `PYTHONHASHSEED=0`、Python 3.10.20、NumPy 2.2.6、相同种子和场景内完全一致的请求轨迹。窗口结束后停止仿真，不排空剩余队列。单集群轨迹 SHA-256 为 `f9be8ef79b7ddabb126dc6359a40743a961de21f9fe066e4c72bd101742781d7`；三集群为 `b9b84301df8f11d7435fd2ccb3c1913fceb05a42c64931516468c5b9898b7816`。布局和仿真集群文件的哈希、逐项配置核对见[单集群报告](queue_dag/runs/single_end_to_end_comparison_seed1_1800.json)与[三集群报告](queue_dag/runs/multi_end_to_end_comparison_seed1_1800.json)。

- **输出吞吐**：测量窗口内完成的输出 token 数除以 1800 秒；单位 token/s。它不同于请求生成器的 offered load。
- **P95 TTFT**：窗口内到达、且在窗口结束前得到首个输出 token 的请求，其首 token 完成时刻减去到达时刻，再取第 95 百分位。
- **P95 TPOT**：对每个至少得到两个输出 token 的请求，先计算相邻输出 token 完成时刻的平均间隔，再在请求间取第 95 百分位。
- **完成率**：窗口内到达并在窗口结束前完成的请求数，除以窗口内到达请求数。窗口末未完成请求会被截尾。
- **P95 E2E**：仅在窗口内到达且完成的请求上计算；两组完成率不同时，它对应不同的请求子集，因此只作辅助指标。

以下表格的“提升”均相对同表对应基线计算：吞吐为 `新值/基线值 − 1`，延迟降低为 `1 − 新值/基线值`。完成率变化单独以百分点表示。

## 3. 最终端到端结果：原版 Helix 对比整合方案

原版基线使用 Helix 的 ILP 放置及 MaxFlow 在线调度；整合方案使用最终关键路径图放置及 `coalesced_corrected` 队列 DAG 调度。两者在同一场景的原始拓扑和机器配置上运行，但各自生成的布局/仿真集群文件不同，这是放置方法差异的一部分。下表是完整系统对照，不把“Helix 调度运行在新放置上”的记录误当作原版基线。

| 场景 | 系统 | 输出吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ | 完成率 ↑ | 窗口末积压 ↓ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 单集群 | 原版 Helix | 89.057 | 5.535 | 1.192 | 84.84% | 111 |
| 单集群 | 整合方案 | **92.642** | **3.825** | **0.658** | **93.58%** | **47** |
| 三集群 | 原版 Helix | 34.516 | 10.847 | 1.676 | 82.39% | 50 |
| 三集群 | 整合方案 | **36.223** | **5.965** | **0.704** | **90.49%** | **27** |

| 场景 | 输出吞吐提升 | P95 TTFT 降低 | P95 TPOT 降低 | 完成率增加 | 已完成请求吞吐提升 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 单集群 | **4.02%** | **30.90%** | **44.83%** | **8.74 个百分点** | 8.64% |
| 三集群 | **4.95%** | **45.01%** | **57.99%** | **8.10 个百分点** | 6.59% |

辅助的完成条件 P95 E2E 在单集群为 488.23→224.16 秒、三集群为 596.33→291.53 秒。由于完成集合不同，不能单独用该指标宣称所有请求的 E2E 均改善。原始记录：[单集群 Helix](queue_dag/runs/single_original_helix_hash0_seed1_1800.json)、[单集群整合方案](queue_dag/runs/single_coalesced_corrected_hash0_seed1_1800.json)、[三集群 Helix](queue_dag/runs/multi_original_helix_hash0_seed1_1800.json)、[三集群整合方案](queue_dag/runs/multi_coalesced_corrected_hash0_seed1_1800.json)。对照检查程序为 [`queue_dag/compare_end_to_end.py`](queue_dag/compare_end_to_end.py)。

**观察与解释。** 两个场景的三个预先关注指标都改善，窗口末积压也减少。仅凭这一端到端表，无法区分放置和调度各自的作用；下面使用已完成的控制变量实验分别检查。

## 4. 挑战一：建模的解释性证据

事件 DAG 将计算、链路带宽占用、传播时延和资源串行化表示为依赖边；最长路揭示代表性的 TTFT/TPOT 关键资源。路径集合需求模型在层兼容 DAG 上进行前向/后向动态规划，汇总可达路径对 GPU 的负载贡献，不枚举完整请求路线。这里验证的是**资源需求排序是否更接近仿真测得的忙碌 GPU**，不是独立的系统吞吐增益。

| 场景 | 需求模型 | GPU 忙碌排名 Spearman 相关系数 ↑ | 预测 Top-5 与实测 Top-5 重合数 ↑ |
| --- | --- | ---: | ---: |
| 单集群 | 典型路径需求 | 0.753 | 2/5 |
| 单集群 | 路径集合需求 | **0.859** | **4/5** |
| 三集群 | 典型路径需求 | 0.678 | 3/5 |
| 三集群 | 路径集合需求 | **0.808** | **4/5** |

来源为单种子、240 秒资源画像的 [`resource_audit_seed1_240.json`](critical_graph/runs/resource_audit_seed1_240.json)。该结果说明路径集合需求对负载集中位置的解释更好，但不能推出 P95 延迟预测准确。另一次 420 秒检查中，离线模型错误排序了单集群共享前缀调整：模型预测 TTFT 变差，仿真却显示改善；三集群关键路径调整的方向则与仿真一致，见 [`model_audit_seed1_420.json`](critical_graph/runs/model_audit_seed1_420.json)。动态排队、批处理和负载波动仍是离线代理模型的误差来源。

## 5. 挑战二：固定调度后的模型放置归因

这组历史实验把**同一个早期 layer-DAG 调度器**分别运行在 Helix 原放置和最终关键路径图放置上，因此差值归因于放置及其生成的可用连接图。它与第 6 节最终调度实验是不同的成对对照，不能将两节的百分比直接相加。

| 场景 | 放置（调度器相同） | 输出吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ |
| --- | --- | ---: | ---: | ---: |
| 单集群 | Helix 放置 | 90.063 | 5.140 | 0.963 |
| 单集群 | 最终图放置 | **91.241** | **4.402** | **0.827** |
| 三集群 | Helix 放置 | 34.905 | 9.128 | 1.197 |
| 三集群 | 最终图放置 | **35.962** | **6.351** | **0.799** |

单集群对应**吞吐 +1.31%、TTFT −14.35%、TPOT −14.10%**；三集群为**吞吐 +3.03%、TTFT −30.42%、TPOT −33.26%**。测量均为 1800 秒、种子 1；原始记录与最终布局文件哈希核对见 [`comparison_final_seed1_1800.json`](critical_graph/runs/comparison_final_seed1_1800.json)。单集群另有 Python 3.12.14/NumPy 2.3.5 下的成对复验，三指标方向一致：+1.58%、−14.05%、−13.72%，见 [`comparison_py312_seed1_1800.json`](critical_graph/runs/comparison_py312_seed1_1800.json)。不同运行环境的数值没有混在同一成对比较中。

### 放置方法内部消融

| 场景 | 调整 | 吞吐变化 | P95 TTFT 变化 | P95 TPOT 变化 |
| --- | --- | ---: | ---: | ---: |
| 单集群 | 典型路径放置 → 路径集合需求细化 | +0.93% | −15.97% | −10.79% |
| 三集群 | 粗划分 → 典型关键路径细化 | **−0.07%** | **+0.32%** | −3.99% |

来源为 [`ablation_final_seed1_1800.json`](critical_graph/runs/ablation_final_seed1_1800.json)。三集群细化不是三项指标全面改善：它主要改善 TPOT，吞吐和 TTFT 略退。420 秒 pilot 的 TTFT 方向与 1800 秒结果不一致，说明短窗口结论不可直接外推。单集群采用路径集合需求、三集群采用典型路径需求的规则是在观察种子 1 的开发实验后确定的；不能把该种子视为独立测试集。

## 6. 挑战三：固定最终放置后的请求调度归因

这组对照在每个场景中使用**字节相同的最终放置文件和仿真集群文件**，只将 Helix MaxFlow 在线调度换成最终队列 DAG 调度。两边还匹配请求轨迹哈希、Python/NumPy 版本及 TTFT/TPOT 样本数。结果如下。

| 场景 | 调度器（放置相同） | 输出吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ |
| --- | --- | ---: | ---: | ---: |
| 单集群 | Helix MaxFlow | 90.031 | 4.588 | 1.076 |
| 单集群 | 队列 DAG＋decode 合并传输 | **92.642** | **3.825** | **0.658** |
| 三集群 | Helix MaxFlow | 35.945 | 6.179 | 0.801 |
| 三集群 | 队列 DAG＋decode 合并传输 | **36.223** | **5.965** | **0.704** |

单集群对应**吞吐 +2.90%、TTFT −16.63%、TPOT −38.87%**；三集群为**吞吐 +0.77%、TTFT −3.47%、TPOT −12.13%**。核对报告：[单集群](queue_dag/runs/single_coalesced_corrected_comparison_hash0_seed1_1800.json)、[三集群](queue_dag/runs/multi_coalesced_corrected_comparison_hash0_seed1_1800.json)。这仅说明**种子 1** 在相同最终放置下三项指标改善；[三种子复验](multiseed/RESULTS.md)显示三集群 TTFT 在种子 0 和 2 退化。

### 调度内部版本的作用与取舍

| 场景 | 队列 DAG 版本 | 输出吞吐 token/s | P95 TTFT s | P95 TPOT s |
| --- | --- | ---: | ---: | ---: |
| 单集群 | 串行传输版本 | 92.045 | 4.026 | 0.748 |
| 单集群 | 最终合并传输＋修正版本 | **92.642** | **3.825** | **0.658** |
| 三集群 | 串行传输版本 | 35.945 | 6.021 | 0.805 |
| 三集群 | 合并传输版本 | **36.239** | 6.027 | **0.702** |
| 三集群 | 最终合并传输＋修正版本 | 36.223 | **5.965** | 0.704 |

来源：[单集群串行](queue_dag/runs/single_queue_serial_hash0_seed1_1800.json)、[三集群串行](queue_dag/runs/multi_queue_serial_hash0_seed1_1800.json)、[三集群合并传输](queue_dag/runs/multi_coalesced_hash0_seed1_1800.json)及第 3 节最终原始结果。三集群从串行到合并传输主要降低 TPOT；最终修正版本进一步降低 TTFT，但相对未修正的合并版本，吞吐和 TPOT 略有回退。单集群的“串行→最终”同时包含合并传输与修正，不能把全部差值只归于其中一个修改。

## 7. Helix 官方负载下的补充实验

此前第 3 节的 Helix 基线输出吞吐为 89.057/34.516 token/s，低于 [Helix 官方 artifact](https://github.com/Thesys-lab/Helix-ASPLOS25/blob/master/artifact_evaluation/ae_readme.md) 的在线 LLaMA-70B 仿真数值 141.6/59.3。先前设置分别使用 400/160 的 `cluster_token_throughput`、种子 1、180 秒预热；官方设置为 700/320、种子 0、无预热。本报告先前的单集群 Helix 示例放置也与官方 artifact 的 ILP 放置文件不同。为避免将不同协议的绝对值误称为“复现失败”，补充实验直接使用官方负载、种子和 Helix 放置，再在完全相同的请求轨迹上运行整合方案。两组场景均使用 Python 3.10.20、NumPy 2.2.6、`PYTHONHASHSEED=0` 和固定的 `[0, 1800)` 秒测量窗口。

### 7.1 官方 Helix 基线复现

| 场景 | 指标 | 官方 artifact 数值 | 本次复现 | 绝对相对误差 |
| --- | --- | ---: | ---: | ---: |
| 单集群 | Decode 吞吐 token/s | 141.6 | **141.568** | 0.023% |
| 单集群 | P95 prompt 请求延迟 s | 4.41 | **4.413** | 0.058% |
| 单集群 | P95 decode 请求延迟 s | 3.19 | **3.192** | 0.053% |
| 三集群 | Decode 吞吐 token/s | 59.3 | **59.324** | 0.041% |
| 三集群 | P95 prompt 请求延迟 s | 9.41 | **9.411** | 0.013% |
| 三集群 | P95 decode 请求延迟 s | 7.72 | **7.718** | 0.023% |

官方数值来自仓库的 [`artifact_evaluation/ae_readme.md`](../artifact_evaluation/ae_readme.md)；对应参数和指标实现见[单集群](../artifact_evaluation/single_cluster/step3_simulation.py)、[三集群](../artifact_evaluation/distributed_clusters/step3_simulation.py)脚本。本次复现沿用同一 `OnlineRequestFeeder`、Helix MaxFlow 在线参数及官方布局，并增加与 artifact 一致的单次 prompt/decode 请求延迟统计。单集群的完整拓扑文件与官方 artifact 字节相同，机器 profile 的解析值相同，仿真集群文件使用官方版本。原始结果为[单集群](queue_dag/runs/paperload_single_helix_seed0_1800.json)和[三集群](queue_dag/runs/paperload_multi_helix_seed0_1800.json)。官方脚本会在轨迹结束后排空剩余请求，但其吞吐与延迟均在指定 1800 秒窗口计数；本次在窗口末停止。单集群 60 秒短测的 compact 与 noncompact 两种统计方式，在吞吐、TTFT、TPOT、官方口径延迟及样本数上完全一致。

### 7.2 同轨迹整合方案对照

| 场景 | 方法 | Decode 吞吐 token/s ↑ | 官方口径 P95 prompt s ↓ | 官方口径 P95 decode s ↓ | P95 TTFT s ↓ | P95 TPOT s ↓ | 完成率 ↑ | 窗口末积压 ↓ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 单集群 | 官方 Helix 放置＋MaxFlow | 141.568 | 4.413 | 3.192 | 6.399 | 1.666 | 82.75% | 223 |
| 单集群 | 最终图放置＋队列 DAG | **153.476** | **3.356** | **1.290** | **4.226** | **0.779** | **92.65%** | **95** |
| 三集群 | 官方 Helix 放置＋MaxFlow | 59.324 | 9.411 | 7.718 | 15.867 | 3.230 | 68.32% | 185 |
| 三集群 | 最终图放置＋队列 DAG | **70.406** | **5.208** | **3.375** | **7.177** | **0.926** | **89.55%** | **61** |

相对 Helix，单集群的输出吞吐 **+8.41%**、P95 TTFT **−33.95%**、P95 TPOT **−53.25%**；三集群分别为 **+18.68%**、**−54.77%**、**−71.32%**。若用 Helix 官方的单次请求延迟口径，P95 prompt/decode 在单集群降低 **23.94%/59.58%**，三集群降低 **44.66%/56.27%**。完成率分别增加 **9.90** 和 **21.23** 个百分点。

两份成对报告：[单集群](queue_dag/runs/paperload_single_comparison_seed0_1800.json)、[三集群](queue_dag/runs/paperload_multi_comparison_seed0_1800.json)；整合方案原始结果：[单集群](queue_dag/runs/paperload_single_integrated_seed0_1800.json)、[三集群](queue_dag/runs/paperload_multi_integrated_seed0_1800.json)。报告检查轨迹 SHA-256、种子、负载、窗口、运行环境和官方 Helix 放置文件。单集群双方有 1291 个 TTFT 样本，TPOT 样本分别为 1287/1290；三集群双方均有 582 个 TTFT/TPOT 样本。官方口径的 decode 请求完成样本数会随吞吐改变，详见报告。不同完成集合使 E2E P95 和请求延迟分布仍带有窗口截尾影响。

### 7.3 为什么先前的绝对吞吐低于官方

按 [`OnlineRequestFeeder`](../simulator/trace_generator/simulator_query_feeder.py) 生成的轨迹，先前低负载窗口内到达请求的输出需求率约为单集群 **92.90**、三集群 **37.08** token/s；官方负载对应 **162.08**、**76.55** token/s。先前 Helix 实测 89.057/34.516 接近其低负载需求率，因此不能与官方高负载下 141.6/59.3 的绝对值直接比较。这些需求率是窗口内到达工作量，不是考虑跨窗完成后的严格吞吐上限。

官方的 P95 prompt/decode 请求延迟也不是 TTFT/TPOT：TTFT 包含从请求到达到首 token 完成的等待，TPOT 是逐请求的相邻输出 token 间隔均值。因此第 7.2 节并列保留两套指标。高负载下吞吐增益较大，说明先前 +4.02%/+4.95% 不是方法效果的唯一工作点；但仅凭这两档负载、且使用不同种子，仍不能声称已经找到系统峰值吞吐。

## 8. 结论边界与论文写法

1. **可直接陈述的结果**：在种子 1 的开发负载和种子 0 的官方负载下，整合方案相对各自成对 Helix 基线均提高输出吞吐、降低 P95 TTFT 和 P95 TPOT；官方负载还复现了 Helix artifact 的吞吐和 prompt/decode 延迟数值。
2. **建模贡献的表述**：路径集合需求比典型路径需求更接近实测 GPU 忙碌排序；事件 DAG 能给出关键资源解释。它是放置决策的依据，不能单独写成“建模带来 X% 吞吐提升”。
3. **不可合并的数值**：第 5、6 节是各自成对的控制变量实验，参照配置不同；两行百分比不是端到端增益的加法分解。完整系统效果以第 3、7 节各自的直接对照为准。
4. **当前局限**：官方负载和开发负载现均有种子 0/1/2 的成对复验，但两档负载的预热协议和单集群 Helix 放置不同，不能构成严格的负载扫描；种子 1 曾参与开发调参。没有真实 GPU 能耗/碳排或真实网络传输验证。decode 合并传输收益依赖仿真器对同链路就绪请求共享传播时延的处理。完成率不同使 E2E P95 有完成条件选择效应。

统一协议的三档负载扫描、三集群 RTT 敏感性、调度开销和统一准入离线对照已完成，详见 [`ccfa_validation/RESULTS.md`](ccfa_validation/RESULTS.md)。1.3 倍官方负载使三集群 Helix 三种子均在 1800 s 内不可路由，故正式负载曲线采用双方均完成的 1.1 倍档。真实或更细粒度网络环境对合并传输的验证仍属于后续工作。

## 9. 复核入口

从仓库根目录执行下列核对命令，即可从已有仿真 JSON 重新计算并写出四份端到端报告；它们不重新运行 1800 秒仿真。

```powershell
python -m experiments.queue_dag.compare_end_to_end --helix experiments/queue_dag/runs/single_original_helix_hash0_seed1_1800.json --integrated experiments/queue_dag/runs/single_coalesced_corrected_hash0_seed1_1800.json --output experiments/queue_dag/runs/single_end_to_end_comparison_seed1_1800.json
python -m experiments.queue_dag.compare_end_to_end --helix experiments/queue_dag/runs/multi_original_helix_hash0_seed1_1800.json --integrated experiments/queue_dag/runs/multi_coalesced_corrected_hash0_seed1_1800.json --output experiments/queue_dag/runs/multi_end_to_end_comparison_seed1_1800.json
python -m experiments.queue_dag.compare_end_to_end --paper-baseline --helix experiments/queue_dag/runs/paperload_single_helix_seed0_1800.json --integrated experiments/queue_dag/runs/paperload_single_integrated_seed0_1800.json --output experiments/queue_dag/runs/paperload_single_comparison_seed0_1800.json
python -m experiments.queue_dag.compare_end_to_end --paper-baseline --helix experiments/queue_dag/runs/paperload_multi_helix_seed0_1800.json --integrated experiments/queue_dag/runs/paperload_multi_integrated_seed0_1800.json --output experiments/queue_dag/runs/paperload_multi_comparison_seed0_1800.json
```

若要重新运行完整仿真，命令、策略参数及检查点用法分别见 [`critical_graph/README.md`](critical_graph/README.md) 和 [`queue_dag/README.md`](queue_dag/README.md)。
