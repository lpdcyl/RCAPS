# RCAPS 论文实验阶段结果（2026-10-29 11:12 韩国时间）

本表仅汇总已审计的正式证据；稳健性批次继续运行，V6 全部失败键的独立重放与总重建审计尚未开始。所有性能数据来自 Windows gllm 环境的 CPU 离散事件模拟，不是真实 GPU 集群测量。不能把失败填零或仅用幸存种子组成五种子均值。

| 证据 | 已有结果 | 解释边界与来源 |
|---|---|---|
| 70B 统一执行器主对照 | 完整 RCAPS 相对 Helix+ 的 P95 TPOT 五种子配对降幅：single/700 为 64.45% [63.66%, 65.23%]；multi/320 为 85.02% [83.41%, 86.63%] | v5_core_supplement/RESULTS_CN.md；仅对这两个拓扑/负载与当前模拟器成立，不能把原 Helix 比较的全部变化归给路由 |
| 30B 第二模型 | 正式 69/80 成功；single/485、single/970、multi/420 相对 Helix+ 的 P95 TPOT 降幅为 75.55%、81.76%、56.27%，各有配对 CI | v5_model30b_pools/RESULTS_CN.md；multi/840 的原版 RCAPS 5/5 实际 KV 容量溢出；11 个失败键独立重放仍全部失败，KV 准入变体须单列 |
| 70B 分布泛化 | generalization 115/180 成功、65/180 失败，FINAL_AUDIT passed=true。突发到达与输出长度减半的条件，在双方五种子均成功时 RCAPS P95 TPOT 更低；两种拓扑的 prompt2/prompt4 均三方法 0/5 | generalization/RESULTS_CN.md。长 Prompt 的 60 个窗口全部失败，另 single/output2 的原 Helix 5/5 失败；失败含准入、KV 与超出已有 Prompt 画像范围，具体复现分类待最终独立重放 |
| 会话代价 | 新变体 80/80 成功。V4 与关闭会话代价相比，single/700 的 P95 TPOT 为 0.5075 对 0.6453 s，GPU 秒/token 为 0.0530 对 0.0363；multi/320 为 0.6119 对 0.8282 s，GPU 秒/token 为 0.0642 对 0.0373 | session_cost/RESULTS_CN.md；尾延迟收益伴随更高单位输出 GPU 工作量，不能只写“取舍合理” |
| 预设 SLO 容量 | 新增 160/160 窗口完成；在单集群 TPOT≤0.6 s、三集群≤0.8 s，且每个种子完成率≥95% 的联合标准下，所有方法在预设网格均无已认证点 | session_capacity/RESULTS_CN.md；例如 V4 single/350 有两个种子完成率低于 95%。本实验不能支持任何方法容量上界或 RCAPS 容量提升的量化主张 |
| 放置权重 | 在线 60/60 成功；多数组合与默认部署/指标相同，但 single 的 w0_high、w2_low 使 P95 TPOT 相对默认高 20.77% [19.69%, 21.86%] | weight_online/RESULTS_CN.md；默认权重有敏感条件，不宜称对所有权重稳健 |
| 跨区带宽/阈值 | 140/140 成功；12.5 MB/s、阈值50 的 sparse_chunk/nochunk P95 TPOT 为 0.612/0.723 s；25 MB/s、阈值50 为 0.584/0.643 s；50 MB/s、阈值50 时两者同为 0.659 s 且实际暂停块数为零 | bandwidth_threshold/RESULTS_CN.md；分块是否触发与准入、阈值共同决定，不宜声称“带宽越低收益必然越大” |
| 合成池扩展性 | 48/96 GPU 物理候选池在线 10/10 成功，路由平均 1.18/1.36 ms | scalability/RESULTS_CN.md；最终只部署 8/11 张 GPU，各两条完整路径，不是 48/96 张同时活跃的路由基准 |

上述 V6 六个已终结批次的 FINAL_AUDIT 均为 passed=true。robustness 截至 11:12 为 167 完成、13 失败、4 运行中、86 待运行；其结果、最终失败重放、总图表重建和匿名证据包尚待收尾。原初稿表 3、图 10–13、摘要及结论仍需在最终证据齐备后逐格改写，见 CLAIM_EVIDENCE_CN.md。按用户要求，必须依赖真机的项目跳过。
