# 失败窗口重放原因分类

所有 99 个原失败键仅独立重放一次；原正式索引与原始失败记录不改。重放成功不是新种子，也不自动替换首轮结果。
分类依据原始与重放 failure.json/worker 退出状态；逐键证据及 SHA256 见 cause_classification.csv。

| 批次 | 重放成功 | 重放失败 |
|---|---:|---:|
| v5_seed_completion | 10 | 41 |
| v5_kv_stress | 12 | 15 |
| v5_link_models | 4 | 0 |
| v5_parallax | 5 | 1 |
| v5_model30b_pools | 0 | 6 |
| v5_model30b | 0 | 5 |

| 原因（原始） | 重放状态 | 重放原因 | 窗口数 |
|---|---|---|---:|
| actual_kv_allocation_overflow | failed | actual_kv_allocation_overflow | 53 |
| controller_worker_interrupted | completed | completed | 30 |
| controller_worker_interrupted | failed | actual_kv_allocation_overflow | 1 |
| controller_worker_interrupted | failed | helix_admission_no_eligible_next_node | 2 |
| helix_admission_no_eligible_next_node | failed | helix_admission_no_eligible_next_node | 12 |
| windows_native_access_violation | completed | completed | 1 |

解释：controller_worker_interrupted 是控制器与 worker 同时退出留下的未完成尝试，后续成功仅说明该窗口可重现运行；actual_kv_allocation_overflow 是仿真中真实 KV 分配越界；helix_admission_no_eligible_next_node 是 Helix 预期 KV 高水位过滤后没有可接纳下游。Windows 原生访问冲突只能归类为环境或原生运行时崩溃，不能据此推断算法缺陷。失败不能填零，不能用幸存种子生成完整五种子统计。
