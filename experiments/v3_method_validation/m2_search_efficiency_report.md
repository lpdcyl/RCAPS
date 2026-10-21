# V3 M2 离线搜索效率诊断

所有方法使用相同的合法布局表示、冻结静态目标及各池参考。
完整 V3 行记录冻结搜索的实际评价数与总规划时间；简单方法最多使用该池相同评价数上限。
简单方法的规划秒数包含共同合法初始候选池的构建时间；时间受并行任务影响，仅作开销描述。
未用完预算按实际评价数报告。该实验不宣称搜索算法具有全局最优性。

| 资源池 | 方法 | 随机种子 | 实际评价数 | 最低冻结目标分数 | 规划秒 |
| --- | --- | ---: | ---: | ---: | ---: |
| C1_single | full_v3 | — | 752 | 0.7084 | 40.64 |
| C1_single | initializer_only | — | 167 | 0.7113 | 42.24 |
| C1_single | one_start_greedy | — | 348 | 0.7113 | 42.40 |
| C1_single | random_neighborhood | 10 | 752 | 0.7148 | 92.64 |
| C1_single | random_neighborhood | 11 | 752 | 0.7380 | 93.39 |
| C1_single | random_neighborhood | 12 | 752 | 0.7148 | 93.37 |
| C1_single | random_neighborhood | 13 | 752 | 0.7125 | 97.43 |
| C1_single | random_neighborhood | 14 | 752 | 0.6981 | 96.13 |
| C1_multi | full_v3 | — | 997 | 0.9028 | 43.35 |
| C1_multi | initializer_only | — | 187 | 0.9670 | 42.53 |
| C1_multi | one_start_greedy | — | 966 | 0.9654 | 43.21 |
| C1_multi | random_neighborhood | 10 | 997 | 0.9670 | 115.56 |
| C1_multi | random_neighborhood | 11 | 997 | 1.0114 | 101.78 |
| C1_multi | random_neighborhood | 12 | 997 | 0.9884 | 105.80 |
| C1_multi | random_neighborhood | 13 | 997 | 1.0340 | 114.76 |
| C1_multi | random_neighborhood | 14 | 997 | 0.9950 | 110.81 |

随机运行若找到更低静态分数，应保留为负结果；静态分数不等于在线吞吐或 P95。
