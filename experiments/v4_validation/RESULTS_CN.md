# RCAPS 必要验证：最终结果与证据边界

完成核对：2026-10-27（Asia/Shanghai）。论文对象是完整 RCAPS；V4 是实现版本。

**本批 75 个登记窗口全部尝试：63 成功、12 失败、0 缺失。** 51 个机制/环境验证全部成功；外部高负载为 1 成功、11 失败；近邻机制为 11 成功、1 失败。最大仿真并发为 2，失败后继续其他条件，本批没有自动重试或按结果调参。

本批执行结束与论文证据充分分开判断。42 个成功的 1800 秒窗口仍有未完成请求，属于右删失；21 个 5400 秒尾部观察窗口均全部完成，最终积压为零。原 120 个成功正式窗口及其失败记录继续独立保留，不与本批计数混合。

## 1. 外部比较：主结果优先

下表复用已核验的共同协议原始结果：seed 0/1/2、1800 秒、零预热、不排空。每格为三种子均值；方法是共同模拟器中的实际适配器。逐种子源文件与哈希见 validation_results.json 的 primary_external_groups。

| 场景/负载 | 方法 | TPOT s ↓ | TTFT s ↓ | 输出 token/s ↑ | GPU s/token ↓ | 完成率 ↑ | 积压 ↓ |
|---|---|---:|---:|---:|---:|---:|---:|
| single/350 | RCAPS（完整 V4） | 0.39425 | 3.1611 | 76.09 | 0.1217 | 0.94831 | 32.333 |
| single/350 | Helix | 1.0657 | 5.491 | 71.886 | 0.15519 | 0.88698 | 70.667 |
| single/350 | Swarm | 1.3901 | 6.405 | 69.16 | 0.14052 | 0.83686 | 102 |
| single/350 | SP | 1.0647 | 4.3535 | 75.636 | 0.14123 | 0.9408 | 37 |
| single/700 | RCAPS（完整 V4） | 0.50637 | 3.5108 | 157.03 | 0.053301 | 0.94052 | 76.333 |
| single/700 | Helix | 1.7057 | 6.5745 | 142.27 | 0.058246 | 0.81954 | 231.67 |
| multi/160 | RCAPS（完整 V4） | 0.52558 | 4.9643 | 35.976 | 0.11396 | 0.94195 | 16.667 |
| multi/160 | Helix | 1.5429 | 12.309 | 33.548 | 0.23096 | 0.84094 | 45.667 |
| multi/160 | Swarm | 2.5839 | 18.061 | 29.971 | 0.21993 | 0.72359 | 79.333 |
| multi/160 | SP | 2.3094 | 17.209 | 31.65 | 0.29548 | 0.77814 | 63.667 |
| multi/320 | RCAPS（完整 V4） | 0.6054 | 5.1065 | 70.985 | 0.065055 | 0.92295 | 44.667 |
| multi/320 | Helix | 3.1945 | 15.583 | 58.255 | 0.08957 | 0.70208 | 172.67 |

在单集群 350、三集群 160，完整 RCAPS 相对三种外部适配器的六项指标均呈有利变化。Helix 另有共同较高负载结果。高负载 Swarm/SP 的 12 个新窗口中只有 multi/320/swarm/seed2 成功，不能生成任何完整三种子组；失败不被换算为零性能或无穷延迟。

| 场景/负载 | 外部对照 | TPOT | TTFT | 输出吞吐 | GPU 工作/token |
|---|---|---:|---:|---:|---:|
| single/350 | Helix | -62.99% | -42.41% | +5.85% | -21.58% |
| single/350 | Swarm | -71.61% | -50.62% | +10.02% | -13.37% |
| single/350 | SP | -62.95% | -27.38% | +0.61% | -13.81% |
| single/700 | Helix | -70.30% | -46.60% | +10.37% | -8.50% |
| multi/160 | Helix | -65.84% | -59.36% | +7.27% | -50.64% |
| multi/160 | Swarm | -79.59% | -72.51% | +20.05% | -48.14% |
| multi/160 | SP | -77.08% | -71.13% | +13.74% | -61.39% |
| multi/320 | Helix | -81.05% | -67.22% | +21.86% | -27.30% |

相对变化均为逐种子 RCAPS/对照 − 1 后的均值，不是总体均值之比。不能从这些点或外部执行失败推出所有方法跨负载占优、最大可持续容量提高或原基线算法必然失效。

## 2. 完整系统模块与固定工作量核验

M2/M3/S/T 的既有完整系统消融仍为第二部分主证据，见 ../v4_paper/FINAL_RESULTS_CN.md。本轮尾部观察复用相同 1800 秒到达前缀，之后停止到达，观察至 5400 秒；21 个窗口均在约 1955.76–2189.07 秒完成，目标输出 token 与产生输出 token 一致。

全部完成同一工作量时，完整系统相对静态 M3 的 TPOT 在单/三集群分别下降 58.42%/31.54%，GPU 工作增加 326.39%/254.52%；单集群相对受限 M2 的 TPOT 下降 30.68%，GPU 工作增加 181.94%。延迟价值与工作代价都应进入正文。

M2 使用共同硬件池但可改变层复制量：单集群完整/受限布局分别 147/112 层副本；三集群两者均 144。该对照是放置设计的整体效果，不能说成严格固定复制结构的纯边界效应。

M1 六种实际布局的层进度、导出图一致性、规范/稀疏空间可达性及非法配置负例已通过；相关输入哈希保持一致。M1 不关闭合法性约束做性能消融，结构检查也不证明任意负载 KV 安全或真实数值推理正确性。

## 3. 机制与环境变化：保留负结果

S 更稳定的作用是减少路径分散和 GPU 工作，而非独立、普适地改善延迟。单样本执行倍率从 2 改为 1 后，完整系统相对无 S 的 TPOT 增加 1.94%，GPU 工作下降 24.35%；Prompt 占比提高时分别为 +0.10% 和 −20.91%。

T 在慢链路减半和 Prompt 占比提高条件中，相对无 T 的 TPOT 分别下降 23.95%/13.40%，GPU 工作增加 7.43%/4.87%。慢链路变化的三个种子对数交互项均为负，Prompt 变化则符号混合；不能称为普适协同或将收益相加。

| 条件 | 方法 | 已用路径数 | token 加权 Decode batch | Decode GPU s | 已结算 Decode 等待 s |
|---|---|---:|---:|---:|---:|
| singleton1 | temporal | 21 | 7.0579 | 8133.3 | 2766.4 |
| singleton1 | v4 | 7.6667 | 9.8841 | 5944.6 | 2874.9 |
| network_half | spatial | 8 | 11.362 | 5979.7 | 18929 |
| network_half | v4 | 8 | 9.9972 | 6571.2 | 6946.7 |
| prompt_heavy | temporal | 25.667 | 3.9672 | 8116.4 | 1530.3 |
| prompt_heavy | v4 | 7.6667 | 4.9646 | 6218.9 | 1564 |

temporal 为保留 T、移除 S；spatial 为保留 S、移除 T。等待表仅为已发送时结算的探针计数；窗口边界未结算等待另见 JSON，分块暂停也单独计量。这些量用于解释联合变化，不能加总为完整独立因果分解。

## 4. 邻近工作：Parallax-inspired 选路机制对照

共同 RCAPS M2 放置、S 准入、T 执行和画像下，以受驻留层段末端约束的逐层最小累计延迟 DP 替换 M3。它不包含 Parallax 的放置/水位分配、分布式发现、周期遥测或原推理引擎；结果只比较这两个路由机制。完整定义见 neighbor_manifest.json 和每份结果的 comparison_identity。

| 场景/负载 | 成功种子 | TPOT | TTFT | 输出吞吐 | GPU 工作/token |
|---|---|---:|---:|---:|---:|
| single/350 | 1、2（seed0 原生崩溃） | 三种子结果缺失 | 三种子结果缺失 | 三种子结果缺失 | 三种子结果缺失 |
| single/700 | 0、1、2 | -22.65% | +0.02% | +1.08% | +48.41% |
| multi/160 | 0、1、2 | -19.02% | +1.34% | +0.98% | +175.28% |
| multi/320 | 0、1、2 | -27.86% | -9.74% | +1.92% | +120.06% |

TPOT 改善伴随 GPU 工作增加，且前两个完整条件的 TTFT 略增，不能写成所有指标均优。首次工程检查的早退/层段边界适配错误及修正见 neighbor_repair_CN.md，原尝试保存在 neighbor_preflight_attempt1/；正式崩溃保留且未重试，不能归因为 Parallax 算法缺陷。

## 5. 最终核对、剩余边界与文件

一次最终核对共 1811 项通过、0 项失败，覆盖冻结输入、登记身份、原始结果/失败、逐请求轨迹、逐种子配对、百分位和 GPU 计量；没有缺失窗口。详见 final_reconciliation.json。最初两个外部失败没有原 index 中的独立 failure 哈希，因此这里只保存其当前哈希，不追认历史哈希保证。

- 原始结果、失败、manifest、index 和 CSV 均保留。本轮是执行者数值核对，不是独立外部评审。
- TPOT 为每请求已观察到的平均 Decode 间隔的 P95，不是逐 token ITL 的 P95；吞吐和完成率需结合右删失观察。
- GPU seconds/output token 是计算工作指标，不等于能耗、部署 GPU 数或成本。尾部组吞吐以 5400 秒为分母，不与 1800 秒主表混算。
- 当前是 CPU 离散事件仿真；真实 70B 分布式引擎、异构 24 GPU/网络画像校准未完成。
- 完整 Parallax 复现、所有外部方法跨负载优势、完整方法新颖性与统计显著性均未由本轮证明。
- 论文当前证据状态见 ../../paper/RCAPS_V4_EVIDENCE_STATUS_CN.md。保持完整系统主线，以条件收益与代价组织贡献。

## 附录：登记扩展窗口的原始汇总

下列完整三种子表、配对表及失败列表保留自动汇总内容；主结果的先后由正文证据问题决定。

## 完整三种子结果

| 条件 | 场景/负载 | 方法/替换 | TPOT s | TTFT s | 输出 token/s | GPU s/token | 完成率 | 积压 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| singleton1 | multi/320 | v4 | 0.60416 | 4.987 | 70.996 | 0.053025 | 0.92294 | 44.667 |
| singleton1 | multi/320 | temporal | 0.59269 | 4.9167 | 71.039 | 0.070096 | 0.92294 | 44.667 |
| network_half | multi/320 | v3 | 0.88204 | 8.2146 | 69.805 | 0.077851 | 0.90624 | 54.333 |
| network_half | multi/320 | spatial | 0.89794 | 8.3014 | 69.779 | 0.054377 | 0.90564 | 54.667 |
| network_half | multi/320 | temporal | 0.68454 | 7.041 | 70.554 | 0.079361 | 0.91718 | 48 |
| network_half | multi/320 | v4 | 0.68279 | 6.9913 | 70.531 | 0.058422 | 0.91775 | 47.667 |
| prompt_heavy | multi/320 | v3 | 0.74056 | 6.0863 | 36.462 | 0.13478 | 0.94881 | 29.667 |
| prompt_heavy | multi/320 | spatial | 0.73559 | 6.2598 | 36.473 | 0.1039 | 0.95112 | 28.333 |
| prompt_heavy | multi/320 | temporal | 0.63619 | 5.6184 | 36.618 | 0.13778 | 0.95454 | 26.333 |
| prompt_heavy | multi/320 | v4 | 0.63669 | 5.6731 | 36.62 | 0.10898 | 0.9557 | 25.667 |
| cohort_tail | single/700 | v4 | 0.50272 | 3.5099 | 55.009 | 0.055327 | 1 | 0 |
| cohort_tail | single/700 | static | 1.2091 | 4.5882 | 55.009 | 0.012974 | 1 | 0 |
| cohort_tail | single/700 | single_boundary | 0.72527 | 4.4574 | 55.009 | 0.01962 | 1 | 0 |
| cohort_tail | multi/320 | v4 | 0.60255 | 5.1116 | 25.261 | 0.066846 | 1 | 0 |
| cohort_tail | multi/320 | static | 0.8802 | 5.6043 | 25.261 | 0.018878 | 1 | 0 |
| cohort_tail | multi/320 | spatial | 0.70341 | 5.3694 | 25.261 | 0.064312 | 1 | 0 |
| cohort_tail | multi/320 | temporal | 0.62277 | 5.0611 | 25.261 | 0.093089 | 1 | 0 |
| neighbor | single/700 | parallax_p2 | 0.65485 | 3.5141 | 155.36 | 0.03592 | 0.92492 | 96.333 |
| neighbor | multi/160 | parallax_p2 | 0.64907 | 4.8999 | 35.63 | 0.041555 | 0.928 | 20.667 |
| neighbor | multi/320 | parallax_p2 | 0.83936 | 5.6581 | 69.647 | 0.029583 | 0.90048 | 57.667 |

cohort_tail 的吞吐分母是 5400 秒观测窗，不能与 1800 秒主表直接比较；该组检验固定工作量、完成情况、尾部和 GPU 工作。
neighbor 为 Parallax-inspired 选路机制替换，**不是完整 Parallax 系统复现**。原文机制、状态估计和共同栈限制见结果的 comparison_identity。

## 配对相对变化

以下为逐种子完整 RCAPS / 对照 − 1 的均值；负值不总是好，须结合指标方向。

| 条件 | 场景/负载 | 对照 | TPOT | TTFT | 输出吞吐 | GPU 工作/token |
|---|---|---|---:|---:|---:|---:|
| singleton1 | multi/320 | temporal | +1.94% | +1.44% | -0.06% | -24.35% |
| network_half | multi/320 | v3 | -22.58% | -14.88% | +1.04% | -24.97% |
| network_half | multi/320 | spatial | -23.95% | -15.69% | +1.08% | +7.43% |
| network_half | multi/320 | temporal | -0.25% | -0.69% | -0.03% | -26.39% |
| prompt_heavy | multi/320 | v3 | -14.01% | -6.78% | +0.44% | -19.14% |
| prompt_heavy | multi/320 | spatial | -13.40% | -9.30% | +0.40% | +4.87% |
| prompt_heavy | multi/320 | temporal | +0.10% | +0.99% | +0.01% | -20.91% |
| cohort_tail | single/700 | static | -58.42% | -23.51% | +0.00% | +326.39% |
| cohort_tail | single/700 | single_boundary | -30.68% | -21.26% | +0.00% | +181.94% |
| cohort_tail | multi/320 | static | -31.54% | -8.76% | +0.00% | +254.52% |
| cohort_tail | multi/320 | spatial | -14.32% | -4.63% | +0.00% | +3.95% |
| cohort_tail | multi/320 | temporal | -3.25% | +1.01% | +0.00% | -28.19% |
| neighbor | single/700 | parallax_p2 | -22.65% | +0.02% | +1.08% | +48.41% |
| neighbor | multi/160 | parallax_p2 | -19.02% | +1.34% | +0.98% | +175.28% |
| neighbor | multi/320 | parallax_p2 | -27.86% | -9.74% | +1.92% | +120.06% |

## 失败记录

| 窗口 | 错误 |
|---|---|
| single/load700/swarm/seed0 | AssertionError('Unknown node found!') |
| single/load700/swarm/seed1 | AssertionError('Exceed KV-cache capacity!') |
| single/load700/swarm/seed2 | AssertionError('Exceed KV-cache capacity!') |
| single/load700/separate/seed0 | AssertionError('Exceed KV-cache capacity!') |
| single/load700/separate/seed1 | AssertionError('Exceed KV-cache capacity!') |
| single/load700/separate/seed2 | AssertionError('Exceed KV-cache capacity!') |
| multi/load320/swarm/seed0 | AssertionError('Exceed KV-cache capacity!') |
| multi/load320/swarm/seed1 | AssertionError('Exceed KV-cache capacity!') |
| multi/load320/separate/seed0 | AssertionError('Exceed KV-cache capacity!') |
| multi/load320/separate/seed1 | AssertionError('Exceed KV-cache capacity!') |
| multi/load320/separate/seed2 | AssertionError('Exceed KV-cache capacity!') |
| single/load350/parallax_p2/seed0 | 3221225477 |
