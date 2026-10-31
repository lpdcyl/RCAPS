# V4 第 7 节五种子补齐结果

复用既有种子 0–2，新增窗口为 seed3、seed4；这五个都是已观察种子，不是留出集。
正式窗口 1800 s、零预热、不排空；边界开销实验使用 1800 s 到达期与 5400 s 观察期。
失败不填零；完整五种子组才汇总均值和样本标准差。

| 类别/配置 | 成功 | P95 TPOT s | P95 TTFT s | 输出 token/s | 完成率 | GPU s/token |
|---|---:|---:|---:|---:|---:|---:|
| components/single/700/static | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| components/single/700/single_boundary | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| components/multi/320/static | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| components/multi/320/single_boundary | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| mechanism/multi/320/chunk1 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| mechanism/multi/320/chunk2 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| mechanism/multi/320/chunk8 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| mechanism/multi/320/all4 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| boundary_cost/multi/320/hold_1ms | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| boundary_cost/multi/320/hold_10ms | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| pools/C2/160/v3 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| pools/C2/160/v4 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| pools/C3/400/v3 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
| pools/C3/400/v4 | 6/5 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |
