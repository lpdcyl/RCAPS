# RCAPS 剩余失败键新一轮独立重跑结果

所有 254 个键在原先已审计的失败之外各进行一次新尝试，采用真正激活的 conda gllm，先串行后最多 2 worker，独立输出目录。
新重跑不是新随机种子，不替换正式批次，也不把失败填零。

| 来源 | 本轮登记 | 新成功 | 仍失败 | 原审计 |
|---|---:|---:|---:|---|
| E2b | 6 | 1 | 5 | experiments/reviewer_v2/E2b_parallax/failure_replay_round2/FINAL_AUDIT.json |
| E3b | 12 | 0 | 12 | experiments/reviewer_v2/E3b_goodput/FINAL_AUDIT.json |
| E5a | 47 | 8 | 39 | experiments/reviewer_v2/E5_scale_kv/E5a_failure_replay/FINAL_AUDIT.json |
| E5b | 55 | 13 | 42 | experiments/reviewer_v2/E5_scale_kv/E5b/boundary_failure_replay/FINAL_AUDIT.json |
| V5 | 68 | 0 | 68 | experiments/v5_failure_replay/FINAL_AUDIT.json |
| V6 | 66 | 0 | 66 | experiments/v6_completion/failure_replay/FINAL_AUDIT.json |

总计：22/254 新成功，232 仍失败。

失败类别按本轮结果逐键见 FINAL_AUDIT.json；不能用新的成功数重算原正式实验成功率。

- E2b 仍失败类型：python_or_simulator_exception 2；windows_access_violation 3
- E3b 仍失败类型：no_eligible_downstream_node 7；python_or_simulator_exception 2；windows_access_violation 3
- E5a 仍失败类型：kv_capacity_assertion 5；python_or_simulator_exception 14；windows_access_violation 20
- E5b 仍失败类型：kv_capacity_assertion 7；no_eligible_downstream_node 26；python_or_simulator_exception 2；windows_access_violation 6；windows_stack_buffer_overrun 1
- V5 仍失败类型：kv_capacity_assertion 47；no_eligible_downstream_node 9；python_or_simulator_exception 4；windows_access_violation 7；windows_stack_buffer_overrun 1
- V6 仍失败类型：kv_capacity_assertion 14；no_eligible_downstream_node 40；profile_boundary 9；windows_access_violation 3
