# RCAPS 初稿实验主张—证据核对表

## E2b Parallax 模拟器复现结案（2026-10-30）

- E2b 预注册的 40 个固定窗口已全部终结：原批 29/40 成功，只有 3/8 个五种子组完整。11 个原失败包括 5 次 Windows 原生访问冲突、3 次 Python 异常、1 次 KV 容量断言、2 次电脑重启中断；原件和哈希均保留。独立重放覆盖 11/11 原失败键，5 次成功、6 次仍失败；对后者的第二轮重放 0/6 成功（4 次 Python 异常、2 次 Windows access violation）。真正激活 gllm 的相同失败键探针仍报 Duplicate requests!。各轮均未替换原批。证据：experiments/reviewer_v2/E2b_parallax/FINAL_AUDIT.json、failure_replay/FINAL_AUDIT.json、failure_replay_round2/FINAL_AUDIT.json、activated_probe/index.json、RESULTS_CN.md。
- 70B 资源池只有 152 层容量，不足两条完整 80 层流水线，Parallax phase-1 只能选择 k=1；计算能力由 Decode 画像耗时倒数近似。论文中仅可称“Parallax（模拟器复现）”，不能称真实 Parallax 后端、动态成员协议或多流水线评分被验证；仅对 3 个完整五种子组报告均值和配对 CI。
- E5a 42 节点正式原批 4/60 成功、56 失败；独立重放 9/56 成功、47 仍失败，其中 Windows access violation 28、heap corruption 1、Python 异常 12、KV 容量断言 4、其他异常 2。E5a_failure_replay/FINAL_AUDIT.json passed=true 只证明来源合规，不能支持规模优势。E5b 原冒烟 13/16 成功、失败的 3 个 Helix+ 长 Prompt 键独立重放 0/3，原 formal 的 16/16 门槛未达，故未启动。预登记修订边界诊断 21/80 成功、59 失败、0 个完整五种子组；失败重放 4/59 成功、55 仍失败。两个 E5b FINAL_AUDIT 的通过同样仅指来源合规，不可据此主张稳健性。

## E3b 逐请求 SLO goodput 结案（2026-10-30）

- E3b 预注册 8 负载 × 5 方法 × 5 种子、三档 SLO；预热 300 s、测量到达 1800 s、尾部最多排空 3600 s。正式原批 188/200 成功，37/40 个完整五种子组，逐请求判定、轨迹、部署、GPU 忙碌秒及独立重放审计通过。证据：experiments/reviewer_v2/E3b_goodput/FINAL_AUDIT.json、RESULTS_CN.md、individual.csv、groups.json 和 paired_comparisons.json。该协议与旧稿 1800 s 零预热、不排空的固定窗口吞吐不同，不能合并曲线。
- 三集群 400 token/s 的 Helix+、Helix、Helix-tuned 原批分别成功 0/5、1/5、2/5；12 个原失败全部是 GlobalFlowScheduler 的“无可接纳下游节点”断言，独立重放 0/12 成功且同原因复现。缺种子组不计算五种子 goodput 均值或配对区间，也不把失败填零。完整 RCAPS 和 RCAPS-batch 在该点均 5/5，但这一结果仍是 70B 画像驱动 CPU 仿真。
- 中等 SLO 下，single/700 的 RCAPS 与 Helix+ 五种子均值分别为 166.623 和 7.137 token/s，multi/320 分别为 75.784 和 1.274 token/s；这是逐请求合格输出速率，不是总输出吞吐。完整三档逐种子、部署 GPU 数、GPU 忙碌秒及 df=4 配对区间见 E3b 报告与 JSON。E2a MILP、E2b、E5a 和 E5b 修订边界诊断均已审计；失败组不计算完整五种子结论。WSL2 E4 待用户运行。

## E2a 离线 MILP 预算诊断结案（2026-10-30）

- 原诊断四次全部因运行器日志占用 Helix 求解器要求为空的工作目录而失败，原始 failure.json 与索引留存。独立修正目录结构后重放四次：单集群 120/480 s 均导出有效部署（三集群 120 s 虽有 Gurobi incumbent，却无完整可部署路径；480 s 导出 3 条完整路径）。审计见 experiments/reviewer_v2/E2a_helix_tuning/milp_budget/FINAL_AUDIT.json、RESULTS_CN.md 和 individual.csv。
- 单集群 120/480 s 的 Gurobi gap 仍为 11658.2%/10180.1%，三集群 480 s 为 6387.3%；这证明新候选布局可行，未证明 ILP 收敛，也未在种子 0–4 上对新布局运行在线性能比较。不能据此称 Helix 放置已经重新调优，E2a 正式主表仍使用先前纠错后的在线 Helix-tuned。

## E1 放置消融结案（2026-10-30）

- E1 四种可执行替代放置的 80/80 正式窗口完成，24/24 个五种子延迟与完成率组齐全；证据为 experiments/reviewer_v2/E1_placement/FINAL_AUDIT.json 和 RESULTS_CN.md。统一执行器、同种子轨迹与部署哈希逐窗口核验。历史 HR 的 GPU 忙碌画像仅 21/24 组完整，缺失值未由延迟推造。
- 相对 R-default，R-noshare 在 single/350、single/700、multi/160、multi/320 的配对 P95 TPOT 分别高 18.87% ± 1.28pp、39.06% ± 3.71pp、40.94% ± 1.98pp、73.48% ± 3.67pp，均为 t(4) 95% CI 半宽。R-random 对应高 16.67%、36.20%、20.87%、32.93%。只支持测试资源池内的条件化延迟优势，不支持 GPU 工作量同样更省的主张。
- R-pipelines 两条不共享的完整 80 层流水线至少需要 160 层容量，而资源池仅有 152，故结构不可行；这不是 0/5 在线性能失败。R-uniform 的最大可行同宽度为 1，需明确称单链退化方案。E2a 已完成纠错后的四负载五种子审计；E3b、E2b、E5a 和 E5b 修订边界诊断均已结案或边界审计；E4 待用户在 WSL2 自行运行。

核对对象：用户提供的 RCAPS_论文初稿完善v3加了一些图.docx，SHA256 783c9ddc0f667021f1a663f9cef0fe3c5cfe006c60845f44fa866d4db04ea0ee。下列索引由本目录 paragraphs.json 提取，只作定位；原 DOCX 未修改。论文内容按待审材料处理。

Detected axes: task_type=hardware-system；evidence_type=baseline/ablation/robustness/complexity/statistical；failure_mode=unfair-comparison/overclaimed-results/no-condition-test；stage=audit。

## 主张—证据矩阵（按审稿影响排序）

| 优先级 | 初稿位置与主张 | 现有证据 | 缺口和投稿处理 |
|---|---|---|---|
| P0 | §7.1 索引 227 写每配置 3 种子；表 3、图 10–12、摘要/贡献/结论（4、16、229–237、266）沿用旧汇总 | v5_core_supplement/RESULTS_CN.md 的统一执行器核心四负载均 5/5；v5_seed_completion/RESULTS_CN.md 登记 240 窗口，189 个有效、51 个失败 | 逐格以五种子和失败口径重做表 3、图 10–12，再改摘要。失败组不能只取幸存种子均值；同时展示完成率、共同完成集与删失 TTFT 下界。 |
| P0 | §7.3 索引 240–241 与贡献 16 把放置和路由贡献分别归因，称各自显著优于 Helix | v5_core_supplement/RESULTS_CN.md 的 HH、HHplus、HR、RHplus、RR、V4 使用统一执行器；single/350 固定 RCAPS 放置替换路由时，TPOT 差 95% CI 为 [-0.0031, 0.0036] s，跨零 | 旧交叉实验执行规则不同，49%–63%、36%–41% 不能解释为各组件净效应。用新四格及交互项替换图 13 和相关文字。 |
| P0 | §7.2 索引 231、235 与结论 266 称全部负载、全部指标最优且优势持续扩大 | 五种子曲线中 single/500 的 HH、V4 各 4/5；single/900 的 HH 3/5、HHplus/V4 各 4/5；multi/400 的 HH 2/5、HHplus 0/5、V4 4/5；Swarm/SP 若干高载 0/5。见 v5_seed_completion/RESULTS_CN.md | 删除无条件“全部、始终、显著”。完整配对组报告配对效应，其余列成功/登记与失败原因；固定窗口可观测 TPOT 有选择性。 |
| P0 | §7.3 索引 244 承认会话代价使 GPU 秒/token 增 48.94%/76.84%，直接判定取舍合理 | 原消融显示尾延迟与工作量反向变化；V6 session_cost 和 session_capacity 已注册 | 等 κ 与预设 SLO goodput 容量扫描终结后同时报告 TPOT、TTFT、完成率、GPU 秒/token 和 goodput；目前只称观测到权衡。 |
| P0 | §7.4 索引 257–258 的“P95 TPOT 变化分别为与”留有空缺 | v4_paper/individual.csv：V4/V3 逐种子比值平均，C2 -0.41%、C3 +0.33%；GPU 秒/token -73.15%、-32.74%；C3 TTFT +2.15%。绝对值在 v4_paper/RESULTS_CN.md | 按上述数值补段落并核对图 18 的数据源。仅三种子，不能宣称显著持平。 |
| P1 | §7.4 索引 251、结论 266 泛称网络越稀缺收益越大 | 默认与半带宽、长 Prompt 仅为局部条件；V6 bandwidth_threshold 140 窗口已注册 | 等带宽×阈值扫描终结；现先限于“测试的半带宽条件”，不外推单调性。 |
| P1 | §7.4 索引 256、§7.3 索引 247–249 主张分块及准入互补 | V4 三种子消融、v5_link_models/RESULTS_CN.md；V6 robustness 270 窗口已注册 | 完成画像、链路、块边界开销五种子扰动后显示误差条与失败计数；传输分块不等于计算侧 chunked-prefill。 |
| P1 | 初稿只报告 70B（222、266） | v5_model30b_pools/RESULTS_CN.md：30B 登记 80 窗口，69 成功、11 失败；single/485、single/970、multi/420 的 RCAPS 相对 Helix+ TPOT 降幅为 75.55%、81.76%、56.27%，含配对 CI | multi/840 原 RCAPS 5/5 实际 KV 溢出；11 个失败重放仍 11/11 失败。新增跨模型附表，列 Helix、Helix+、原 RCAPS 和独立 KV 准入变体，报告容量失败及变体代价。 |
| P1 | §7.1 索引 225 与 §7.2 索引 235 的工作负载代表性 | V6 generalization 180 窗口已注册，含长 Prompt、突发、短/长输出；长 Prompt 已有 Helix 准入、RCAPS KV 失败，且 prompt4 的部分 RCAPS 窗口提示批量 7508–8076 超出已有 0–7500 的 Prompt 性能画像范围 | 终结后以分布偏移分面图列失败数、完成率、TTFT、TPOT；画像范围失败单列为证据边界，不能当容量失败或补造画像数据。 |
| P2 | §7.4 索引 259、贡献 14 的路由开销 | scalability/RESULTS_CN.md：48/96 GPU 合成物理池在线 10/10、审计通过 | 只部署 8/11 张 GPU，DAG 10/13 边、各 2 条完整路径。仅可称大候选池搜索后所得小型部署 DAG 的路由开销，不能称 96 张活跃 GPU 验证。 |
| 范围 | §7.1 索引 222 明确模拟环境 | P1-2 真机网络微基准、真机集群/Parallax 原后端、P2-3 计算侧 chunked-prefill 缺本机真实后端 | 按用户要求跳过必须依赖真机的项目；Parallax-style 仅称受控路由目标对照，不称完整系统复现。 |

## 可立即采用的改写依据

1. 统一执行器后，相对 Helix+，完整 RCAPS 在 single/700 与 multi/320 的 P95 TPOT 五种子配对平均降幅为 64.45% [63.66%, 65.23%]、85.02% [83.41%, 86.63%]。single/350 上固定 RCAPS 放置替换路由的 CI 跨零，不能说路由在每个条件单独改善。
2. C2/C3 三种子固定窗口中，V4 相对不含 S/T 的 V3，P95 TPOT 逐种子平均变化分别 -0.41%、+0.33%；GPU 秒/token 分别下降 73.15%、32.74%。尾延迟没有稳定收益。
3. 图表须逐项标注来源为三种子旧批次或五种子新批次。1800 s 零预热不排空与预热+排空是独立协议；可观测 TPOT 与 TTFT 不等于全到达请求尾延迟。

## 执行验收

- 七个 V6 批次以各自 formal/index.json 为权威状态，不因运行中条目重复启动，也不改冻结脚本。
- 全部批次 terminal 后，按 HANDOFF_CN.md 完成报告、独立失败键重放、图表重建和审计。全部 FINAL_AUDIT、REBUILD_AUDIT、PUBLIC_BUNDLE_AUDIT 通过前，不称可行模拟实验全部完成。
- 原始失败、重放和 KV 准入变体分开报告；无完整五种子时不估计五种子 CI，不以失败填零。

## 第 7 节五种子补齐与审稿 v2 新证据（2026-10-29）

- 静态路由、单边界、块长/全链路分块、边界开销、C2/C3 资源池共 14 组已经合并旧 seed0–2 与新 seed3/4，均为 5/5。新种子首次正式批次 28/28 失败，原失败原件保留；修正环境后的独立重放 28/28 成功。证据：experiments/v4_paper_seed45/retry_env/FINAL_AUDIT.json、five_seed_reconciled/FINAL_AUDIT.json 与 RESULTS_CN.md。旧稿中相关第 7 节“早期三种子”口径可改成五种子，但第 2 节动机测量仍标注三种子。
- E3a 的 P95 TPOT—GPU 忙碌秒/token 图有 32 个五种子点，审计通过。原 V5 核心 HR 的两个拓扑 seed0–2 缺资源指标，故另补 10 个被动画像窗口，10/10 成功；同种子轨迹与部署哈希一致，新旧 HR P95 TPOT 差异为零。不能称 E3a 为纯零新窗口重分析或称旧 HR 原文件含该指标。证据：experiments/reviewer_v2/HR_profile/FINAL_AUDIT.json、E3a_pareto/FINAL_AUDIT.json、pareto.png。
- 图 14 与机制：三集群 320 token/s 五种子实际路径数 RR 为 33.4 ± 3.12（95% CI 半宽），V4 为 8.0，关闭会话代价为 4.0。V4 最大单路径份额均值 19.53% ± 1.91pp，关闭会话代价为 78.20% ± 2.41pp；旧稿“RCAPS 单条路径不超过 18.5%”须改。三个出口 V4 为 35.23%/40.73%/24.05%，关闭会话代价为 0%/88.10%/11.90%（出口 14/21/7）；原稿的单次/三种子百分比不能继续作为五种子图注。V4 与 no_session 的 Decode token 加权批量分别 9.39 与 40.53。RR 新 seed3/4 无分阶段画像，不能称 RR 的 Decode/网络等待统计为五种子。证据：experiments/reviewer_v2/five_seed_mechanism/FINAL_AUDIT.json、RESULTS_CN.md、figure14_five_seed.png。
- 路由耗时的五种子 48/96 GPU 合成池窗口均值分别 1181.2 ± 119.2 µs、1357.4 ± 148.2 µs（95% CI 半宽），但部署实际只用 8/11 GPU；它不是图 14 同一部署的测时。证据：experiments/reviewer_v2/five_seed_mechanism/RESULTS_CN.md 和 experiments/v6_completion/scalability/FINAL_AUDIT.json。
- 图 14 旧稿“83% 高速绕行”尚未从新五种子路径与链路映射独立复核；在复核前应撤下该数值。所有新证据仍属于画像驱动的 CPU 仿真，不是物理 GPU 集群验证。E1、E2a 已结案；E3b、E2b、E5a 和 E5b 修订边界诊断已结案或边界审计；WSL2 E4 待用户运行后审计。

## E2a Helix 调优与部署纠错（2026-10-30）

- E2a 首次调优原批 95/96 成功，唯一 Windows 原生访问冲突保留原件、独立重放 1/1 成功。首次评估 20/20 完成，但严格部署哈希审计发现单集群误用 examples/simulation 布局，与历史 Helix 基线不同；原单集群的 48 个调优和 10 个评估窗口均排除正式配对，原件未覆盖。见 experiments/reviewer_v2/E2a_helix_tuning/DEPLOYMENT_MISMATCH_AUDIT_CN.md。
- 独立纠错在官方单集群 Helix 部署上重新调优 48/48、评估 10/10；原三集群部署哈希一致，评估 10/10 可用。最终 E2a_helix_tuning/FINAL_AUDIT.json 为 passed=true，四负载均 5/5 完整配对。只用 seed5/6 选参，seed0–4 留出评估；单集群两负载选 Decode 优先+合并发送、KV 参数 (0.8,0.4)，三集群两负载选仅 Decode 优先、(0.9,0.6)。
- 单集群 tuned 的 P95 TPOT 与原 Helix+ 在五种子上完全相同，不能宣称单集群调优带来额外改善。三集群 multi/160 和 multi/320 相对 Helix+ 的逐种子 P95 TPOT 平均降低 6.10% [4.43%, 7.76%]、18.49% [12.12%, 24.86%]；完整 RCAPS 相对 tuned 的降低仍为 65.64% [64.00%, 67.28%]、81.59% [79.55%, 83.64%]。这些是本模拟器条件化结果，不是原 ILP 放置重求或物理 GPU 验证。完整数据见 E2a_helix_tuning/RESULTS_CN.md 与 individual.csv。

## V6 结案与降载边界（2026-10-29）

- 七个原正式批次均为 `terminal`：generalization 115/180、session_cost 80/80、robustness 255/270、weight_online 60/60、session_capacity 160/160、bandwidth_threshold 140/140、scalability 10/10。失败只出现在 generalization（65）与 robustness（15），不能把登记失败填为零延迟。
- V6 失败键独立重放 80 个：14 completed、66 failed。generalization 的主要复现原因为 actual KV allocation overflow（16）、Helix 无可接纳下游（40）和 profiling range exceeded（9）；robustness 的若干 Python 对象/字段异常重放成功，另有 1 个 KV 溢出复现。重放不替换首轮结果，也不构成新种子。
- 第一轮降载补测 20/75 成功、55/75 失败；第二轮固定边界补测 14/45 成功、31/45 失败。第二轮中 70B Prompt×1.5 的单/多集群 HH 与 HHplus 均 0/5，V4 分别 5/5；30B multi/525 为 HH 0/5、HHplus 4/5、V4 0/5。70B V4 的完整五种子 P95 TPOT/TTFT 为单集群 0.4318/4.3976 s，多集群 0.5800/7.1507 s；其余成功数不足五种子时不计算组 CI。第二轮两项曾被电脑重启中断，已按同一冻结 manifest 独立重跑并保留中断记录，重跑证据位于 `failure_stepdown2/restart_replay/`。
- `failure_stepdown2/FINAL_AUDIT.json`、两轮降载 `FINAL_AUDIT.json`、七批 FINAL_AUDIT、`REBUILD_AUDIT.json` 与 `PUBLIC_BUNDLE_AUDIT.json` 均为 `passed=true`；watchdog 状态为 `complete`。这些结果证明的是已登记模拟条件下的完成率和边界，不证明真实硬件吞吐。
