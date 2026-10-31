# V6 实验最终状态

所有登记的 CPU 离散事件模拟批次已经终结；数值与失败原因见各批 RESULTS_CN.md。
真机网络微基准 P1-2 和 Sarathi 计算侧 chunked-prefill P2-3 按用户范围跳过。

| 批次 | 完成 | 失败 | 状态 |
|---|---:|---:|---|
| generalization | 115 | 65 | terminal |
| session_cost | 80 | 0 | terminal |
| robustness | 255 | 15 | terminal |
| weight_online | 60 | 0 | terminal |
| session_capacity | 160 | 0 | terminal |
| bandwidth_threshold | 140 | 0 | terminal |
| scalability | 10 | 0 | terminal |

独立诊断重放 80 个 V6 失败键；重放成功不自动替换首轮结果或成为新种子。
图表、表格、匿名衍生证据包及总重建审计均已生成。
