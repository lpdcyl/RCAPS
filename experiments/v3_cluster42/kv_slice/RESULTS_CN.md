# 42 节点高负载：并发 KV 容量约束实验

目标：相同 2150 offered token/s、相同请求轨迹，以更少计算节点同时达到 Helix 的吞吐、P95 TTFT 和 P95 TPOT。

42 是计算节点数；L4x2、T4x2、T4x4 含多张卡，按类型倍数折算为 64 张物理 GPU。下表同时报告两种数量，避免混淆。所有结果来自事件模拟器。

按输入长度加公开输出上限 1000 token 预约全生命周期 KV。准入等待计入 TTFT，不丢弃请求。

预约粒度与布局生成规则见 protocol.json 和各候选 placement.json；executed_layers 只预约实际执行层，resident_layers 预约全部驻留层。

| 窗口 | 候选 | 种子 | 节点/物理GPU | token/s | TTFT P95 s | TPOT P95 s | 首token/到达 | 完成率 | 积压 | 三指标配对 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| screening | c400k_slice_w3_b1 | 101 | 31/53 | 376.908 | 5.062 | 0.959 | 1339/1347 | 0.6578 | 461 | pass |
| screening | c600k_slice_w2_b20 | 101 | 17/38 | 301.812 | 119.722 | 1.081 | 1056/1347 | 0.5464 | 611 | not_pass |
| screening | c600k_slice_w3_b12 | 101 | 40/62 | 294.077 | 131.933 | 1.101 | 1031/1347 | 0.5301 | 633 | not_pass |
| screening | Helix | 101 | 42/64 | 354.105 | 5.305 | 1.496 | 1342/1347 | 0.6095 | 526 | baseline |

600 秒筛选推荐：c400k_slice_w3_b1。

正式判定：尚未达到三个正式种子全部通过；缺失窗口不计通过。

180 秒 smoke 和 600 秒 screening 仅用于选型；1800 秒、seed 0/1/2 才用于最终判定。完整输入一致性检查、相对变化及结果哈希见 analysis.json。

原 22 节点方案的三个正式负结果见 ../kv_candidate/RESULTS_CN.md；原 V3 的 KV 断言失败见 ../RESULTS_CN.md，均保留。
