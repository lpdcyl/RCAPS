# E2a：Helix 执行规则与在线参数调优预注册

登记日期：2026-10-30（Asia/Seoul）。本文件在 E2a 正式结果产生前写入。使用现有 70B C1_single/C1_multi Helix 已部署布局；单集群 350、700 token/s，三集群 160、320 token/s。固定窗口 1800 s、零预热、不排空；相同拓扑、负载、种子复用完全一致的请求轨迹。Windows gllm 环境运行。

## 对照和开关语义

MaxFlow 在线路径选择、Helix 物理部署、计算/网络画像保持一致。执行开关分为 priority（Decode 请求优先被发送和执行）及 batch（同一 hop 当前已就绪的 Decode 请求合并发送、共同承担一次链路传播时延，不等待未来请求）。两开关独立；00 为原 Helix 调度，11 必须与已审计 Helix+ 适配器语义等价。10 仅 Decode 优先：逐请求发送。01 仅合并发送：保留队列原到达顺序，仅队首为 Decode 时合并该 hop 已就绪的连续 Decode，不借合并改变 FIFO 相位优先级。冒烟须验证四个组合的发送请求批大小与调度顺序，并检查 00/11 对历史窗口的指标及轨迹一致性；不等价时不进入正式批次，修正独立 E2a 适配器并保留诊断记录。

在线参数网格：expected_kv_hwm = 0.8、0.9、0.95；expected_output_length_ratio = 0.4、0.6、0.8。预注册的 12 个唯一候选/负载为四个执行开关组合在默认参数 (0.9, 0.6)，加上 11 模式其余八个参数组合。前者隔离执行规则；后者调优完整 Helix+。不得用正式评估种子调参。若 11 与原 Helix+ 不等价，需报告并保持原基线独立。

调优只用 seed 5、6：4 负载 × 12 候选 × 2 种子 = 96 个窗口。每个负载独立选出一个配置；先过滤两种子均成功且平均完成率不低于同种子默认 Helix+ 平均完成率的配置，再以两种子 P95 TPOT 算术均值最低者为 Helix-tuned。若无合格候选，则选择默认 Helix+ 并标记约束未达成；并列时依次选择较高完成率、较低 GPU 秒/token、候选字典序。任何 seed 5/6 失败的候选不进入选择；保留失败原件，必要时独立重放一次并公开成功数。

选定配置及其源哈希写入不可变 selection.json，再冻结 seed 0–4 的正式 manifest。正式评估 4 负载 × 5 种子 = 20 个窗口；只与同轨迹、同部署的已有 Helix、Helix+、RCAPS 五种子审计结果做配对比较。报告 P95 TPOT、P95 TTFT、吞吐、完成率、GPU 秒/token，以及逐种子相对变化和 df=4 配对 t 95% CI；若成功种子不足五个，只报告成功数与失败分类，不补值。

## MILP 放置求解诊断

原 70B ILP 源码使用 max_run_time=36000 s、early_stop_time=100 s、early_stop_threshold=0.95，回调还会在目标达到上界 99.5% 时提前停机；见 artifact_evaluation/{single_cluster,distributed_clusters}/step2_gen_layout.py 与 simulator/initial_layout/ilp_layout/ilp_layout.py。这不是在线参数。历史 experiments/v3_search_efficiency/RESULTS_CN.md 的限时 120/300 s 求解结果有巨大 gap，不能声称已证实原 ILP 收敛。E2a 单列求解预算诊断：先保存原布局与其来源，分别尝试原回调 120 s 和加宽到 480 s 的独立求解；记录原始求解日志、incumbent、界、gap、部署可行性和计划时间。只有产出经验证、与主协议同拓扑的有效部署，才可作为额外放置对照，不得替换已经冻结的 Helix-tuned 在线调优结果；未完成或无可行部署须如实列出。

## 执行和审计

冻结源码、两拓扑部署、画像、物理池、环境版本及输入 SHA256。先 60 s 冒烟，检查四种开关实际行为、KV 参数生效、同种子轨迹和两个默认端点。随后正式调优与评估分别使用新进程、独立索引；每个键首次只运行一次。失败写 failure.json，独立重放使用新索引，不覆盖原件。审计须确认 manifest、来源、指标、轨迹、部署哈希和按负载选参规则；输出 individual.csv、RESULTS_CN.md、FINAL_AUDIT.json 与 3–5 句论文可用表述。原始失败和降载/替代条件分列。
