# V3 与 Helix ILP：离线规划效率

两者使用相同的 C1 物理 GPU 配置；每次在新的 Python 进程中串行运行。
总时间从规划器准备输入和建立模型开始，到导出部署文件结束；不含 Python 启动、
预先生成的启发式初始布局，也不含在线仿真。V3 使用冻结 `multi_any` 规则；
Helix 调用原 artifact 的 70B ILP 入口；`helix_ilp` 保持原停机策略，
`helix_ilp_budget*` 额外设置明示的 Gurobi 求解时间上限。

运行主机：Intel64 Family 6 Model 183 Stepping 1, GenuineIntel；物理/逻辑 CPU 24/32；内存 127.8 GiB；Gurobi 13.0.3。
Helix 使用 Gurobi 原生线程设置（日志显示最多 32 线程）；V3 使用单进程确定性搜索。

| 拓扑 | 方法 | 有效部署/运行数 | 总规划时间中位数 [范围] s | 核心搜索/求解中位数 [范围] s | 布局检查 |
| --- | --- | ---: | ---: | ---: | --- |
| C1_single | v3 | 3/3 | 42.666 [42.619, 43.474] | 42.575 [42.527, 43.377] | 全部通过 |
| C1_single | helix_ilp | 0/1 | — | — | 有失败或未测 |
| C1_single | helix_ilp_budgeted | 3/3 | 120.326 [120.319, 120.458] | 120.260 [120.253, 120.393] | 全部通过 |
| C1_multi | v3 | 3/3 | 43.426 [43.286, 43.502] | 43.366 [43.197, 43.410] | 全部通过 |
| C1_multi | helix_ilp | 0/1 | — | — | 有失败或未测 |
| C1_multi | helix_ilp_budget300 | 3/3 | 300.143 [300.127, 300.233] | 300.079 [300.065, 300.172] | 全部通过 |
| C1_multi | helix_ilp_budgeted | 0/3 | — | — | 有失败或未测 |

## 逐次记录

| 拓扑 | 方法 | 重复 | 状态 | 总时间 s | 搜索/求解 s | 内部诊断 |
| --- | --- | ---: | --- | ---: | ---: | --- |
| C1_multi | helix_ilp | 0 | timeout | — | — | 原始日志保留 |
| C1_multi | helix_ilp_budget300 | 0 | 成功 | 300.143 | 300.079 | Gurobi status=9, gap=5556.4% |
| C1_multi | helix_ilp_budget300 | 1 | 成功 | 300.127 | 300.065 | Gurobi status=9, gap=5559.0% |
| C1_multi | helix_ilp_budget300 | 2 | 成功 | 300.233 | 300.172 | Gurobi status=9, gap=5563.9% |
| C1_multi | helix_ilp_budgeted | 0 | failed | — | — | 0 条完整路径；有效=False |
| C1_multi | helix_ilp_budgeted | 1 | failed | — | — | 0 条完整路径；有效=False |
| C1_multi | helix_ilp_budgeted | 2 | failed | — | — | 0 条完整路径；有效=False |
| C1_multi | v3 | 0 | 成功 | 43.286 | 43.197 | 997 次静态评分 |
| C1_multi | v3 | 1 | 成功 | 43.426 | 43.366 | 997 次静态评分 |
| C1_multi | v3 | 2 | 成功 | 43.502 | 43.410 | 997 次静态评分 |
| C1_single | helix_ilp | 0 | timeout | — | — | 原始日志保留 |
| C1_single | helix_ilp_budgeted | 0 | 成功 | 120.458 | 120.393 | Gurobi status=9, gap=8478.2% |
| C1_single | helix_ilp_budgeted | 1 | 成功 | 120.326 | 120.260 | Gurobi status=9, gap=8472.0% |
| C1_single | helix_ilp_budgeted | 2 | 成功 | 120.319 | 120.253 | Gurobi status=9, gap=8495.4% |
| C1_single | v3 | 0 | 成功 | 43.474 | 43.377 | 752 次静态评分 |
| C1_single | v3 | 1 | 成功 | 42.666 | 42.575 | 752 次静态评分 |
| C1_single | v3 | 2 | 成功 | 42.619 | 42.527 | 752 次静态评分 |

## 解释边界

- 这项实验衡量的是本仓库中两种规划实现的实际耗时，不是相同数学目标下的算法复杂度竞赛。
- Helix ILP 的变量/约束数、Gurobi 求解状态和 gap，与 V3 的实际候选评分数不是同一量纲；分别列出供复现与诊断。
- 原始 Helix 使用 Petals（单集群）或 Swarm（三集群）的既有初始布局。初始布局的生成成本不计入这两种方法的总时间。
- `helix_ilp_budget*` 仅为 Gurobi 设置明确的求解时间上限，导出该时刻的 incumbent；它不是原 36000 秒停机策略的完整结果，也不能据此说 Helix 在该时刻没有可部署解。
- 单集群原策略的超时记录显示 Gurobi 已加载非零启发式 MIP 初始解；超时只表示完整求解过程仍在运行。
- V3 使用已冻结的初始状态与评分参考；两种部署均逐次检查层段、显存层容量、物理连通和完整执行路径。
- 如有超时或失败，不对不完整运行填入规划时间，也不以超时下界计算加速比。
