# Swarm 与 Separate Pipelines：V2 主表负载的原版三种子核查

## 协议与实现

- 模型：LLaMa70B；单集群 700、三集群 320 提供 token/s（输入与目标输出之和）；每个拓扑种子 0/1/2；1800 秒、零预热、固定窗口且不排空尾部。仅运行 Swarm 与 Separate Pipelines（SP），未重跑 Helix 或 V2。
- Swarm 直接使用 Helix artifact 的 70B Swarm 布局与 `SchedulingMethod.Swarm`。SP 使用 artifact 的 A100/L4/T4 三套原布局、原 `SchedulingMethod.Naive` 和 `allow_force_set`。两个基线均未加 KV 准入保护。
- SP 为与主表共用一条请求轨迹，将每个请求按 artifact 中三套子集群提供负载的比例确定性分配给 A100/L4/T4。分配只看已分配**请求数**，不读取该请求的目标输出长度；三个子集群的结果仅在全部完成时才可合并。原 artifact 分别生成三条轨迹，因此这里的共同轨迹分配是本次公平对照所需的实验适配，不等同于原论文的一次运行。
- 运行命令：`python -m benchmarks.run --methods swarm separate --scenarios single multi --seeds 0 1 2 --duration 1800 --warmup 0 --workers 2 --results-dir experiments/helix_additional_baselines/raw_formal`。发现最初的 SP 轨迹分配用了未来目标输出长度后，已将其改成上述按请求数分配，并单独以同一正式协议重跑：`python -m benchmarks.run --methods separate --scenarios single multi --seeds 0 1 2 --duration 1800 --warmup 0 --workers 2 --results-dir experiments/helix_additional_baselines/raw_formal_nonoracle`。以下 SP 状态**只取重跑结果**。

## 正式窗口状态

| 拓扑 | 种子 | Swarm | SP（按请求数分配） |
| --- | ---: | --- | --- |
| 单集群 | 0 | KV 容量断言失败 | KV 容量断言失败 |
| 单集群 | 1 | KV 容量断言失败 | KV 容量断言失败 |
| 单集群 | 2 | KV 容量断言失败 | KV 容量断言失败 |
| 三集群 | 0 | KV 容量断言失败 | KV 容量断言失败 |
| 三集群 | 1 | KV 容量断言失败 | KV 容量断言失败 |
| 三集群 | 2 | **完成** | KV 容量断言失败 |

失败均为仿真器 `kv_cache.py` 中的 `AssertionError: Exceed KV-cache capacity!`，不是得到较低的完整窗口性能。逐次原始日志保存在 `raw_formal/{single,multi}/seed{0,1,2}/swarm.log` 和 `raw_formal_nonoracle/{single,multi}/seed{0,1,2}/separate.log`；失败窗口没有结果 JSON，也不填补吞吐或尾延迟。这个结论限定于这里的负载、轨迹分配及仿真协议，不表示算法在所有负载下都无法运行。

唯一完成的 Swarm 三集群种子 2：吞吐 **48.227 输出 token/s**，P95 TTFT **19.344 s**，P95 TPOT **4.212 s**，完成率 **55.973%**，末端积压 **258**。其 `trace_sha256` 与现有 Helix 种子 2 完全一致（`84725cd2924e8a1476f231f1a7c273bec9c86770740d686219a622c3543cdb5e`），586 个请求的 UID、输入/输出 token 数相同，到达时间差小于 `1e-9 s`。同种子 Helix 为 **58.034 token/s、15.494 s、3.148 s、72.355%、162**。这一对只用于诊断，不能推断三种子均值或标准差。

**主表决定：**Swarm 与 SP 均缺少每个拓扑的三个完整正式窗口，因此不加入 V2–Helix 及递进消融主表，不计算 V2 相对这两项的提升。Helix 原 artifact 的低负载结果继续作为独立参考，不与主表合并。
