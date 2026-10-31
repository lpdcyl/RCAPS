# 会话代价变体的预设 SLO 容量网格

正式新增 160 个低、中负载窗口；高负载变体和主方法负载曲线按原始来源复用，不增加独立种子数。
单集群 P95 TPOT ≤ 0.6 s，三集群 ≤ 0.8 s，均要求五种子逐一完成率 ≥ 95%。
最大负载只指预设网格中的最大可行点；网格外容量和真实硬件容量未估计。失败不填零。

| 拓扑 | 方法 | 网格最大五种子可行负载（token/s） | 达到上界 |
|---|---|---:|---|
| single | HH | 无已认证点 | False |
| single | HHplus | 无已认证点 | False |
| single | V4 | 无已认证点 | False |
| single | batch | 无已认证点 | False |
| single | marginal | 无已认证点 | False |
| single | cycle | 无已认证点 | False |
| single | no_session | 无已认证点 | False |
| single | k1 | 无已认证点 | False |
| single | k1_5 | 无已认证点 | False |
| single | k3 | 无已认证点 | False |
| single | k4 | 无已认证点 | False |
| multi | HH | 无已认证点 | False |
| multi | HHplus | 无已认证点 | False |
| multi | V4 | 无已认证点 | False |
| multi | batch | 无已认证点 | False |
| multi | marginal | 无已认证点 | False |
| multi | cycle | 无已认证点 | False |
| multi | no_session | 无已认证点 | False |
| multi | k1 | 无已认证点 | False |
| multi | k1_5 | 无已认证点 | False |
| multi | k3 | 无已认证点 | False |
| multi | k4 | 无已认证点 | False |
