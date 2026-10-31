# E2a：Helix 离线 MILP 求解预算诊断

登记于 2026-10-30，任何本批结果产生前。独立于已审计的 E2a 在线参数选择和正式五种子评估；不替换原 Helix、Helix+ 或 Helix-tuned 部署。

复用原 Helix 70B 单集群和三集群物理拓扑、机型画像、Petals/Swarm 初始解及原 ILP 建模和导出程序。每个拓扑新进程各运行 120 s、480 s 的原 `search_layout` 回调预算；仅改变传给该回调的 `max_run_time`，保留原 `early_stop_time=100`、`early_stop_threshold=0.95`、99.5% 上界提前停止规则，不加 Gurobi `TimeLimit`。每次外层保护超时为预算 + 180 s，保护超时不视为无可行解。四个单次诊断，串行运行避免两个 MILP 抢占 CPU。

每次保存 Gurobi 原始 stdout/stderr、求解器状态、incumbent、bound、gap、规划耗时、布局文件及 `audit_export` 检验。原有 120/300 s 有限预算结果只作背景，不能说历史 ILP 已收敛。若导出有效但与历史官方 Helix 部署不同，只称新候选布局；不在没有额外五种子模拟的情况下声称性能更优。失败原件保留。冻结此计划、运行脚本、原 ILP 源码、拓扑/画像/启发式输入及 gllm 环境路径与版本；每键只运行一次。
