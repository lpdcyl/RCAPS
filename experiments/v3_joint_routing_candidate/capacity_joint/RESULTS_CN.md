# 容量约束放置 × 实时路由：独立候选验证

M1 只提供资源与层兼容图。M2 用类别流 LP 和开发种子 100 的短窗口选布局；M3 在合法图上保留每状态最多四个 Pareto 标签，并在最早路由成本 10% 内按容量压力选路。
Decode 沿原 Prompt 路径；冻结 V3 和原始结果没有覆盖。

本报告的正式对照使用 1800 秒固定窗口及种子 0／1／2。三个种子只表示波动，不作为显著性检验。

## C1_single

选中布局：`local_neighbor`；层段副本数 [1, 4, 3]；LP 静态容量 1.738 请求/s。
LP 首要瓶颈：`gpu:6`。固定形状搜索检查 100 个合法布局，耗时 88.0 秒；短名单在线规划窗口累计 668.5 秒。未进入训练短名单的布局没有在线验证。

静态容量并列诊断：LP 容量最高的布局有 4 个（capacity_1, local_neighbor, released_v3, single_boundary）；这些布局在容量代理下无法区分。下表只列开发种子 100 的在线短窗口范围，用于说明选择依据，不作为独立性能证据。

| 开发到达模式 | 并列布局数 | 完成率范围 | P95 TTFT 范围 s | P95 TPOT 范围 s |
| --- | ---: | ---: | ---: | ---: |
| uniform | 4 | 0.619–0.638 | 3.392–3.905 | 0.450–0.477 |
| burst | 4 | 0.648–0.676 | 3.477–3.856 | 0.464–0.487 |

| 到达模式 | 种子 | 方法 | 输出 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 路径数 | 原始结果 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| burst | 0 | V3 | 156.220 | 3.544 | 0.678 | 0.954 | 60 | 510 | experiments/v3_joint_routing_candidate/runs/C1_single/released_v3/full/burst/seed0_1800s.json |
| burst | 0 | 联合候选 | 156.238 | 3.767 | 0.737 | 0.954 | 59 | 195 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_single/local_neighbor/burst_seed0_1800s_700.json |
| burst | 1 | V3 | 163.230 | 3.761 | 0.685 | 0.944 | 72 | 531 | experiments/v3_joint_routing_candidate/runs/C1_single/released_v3/full/burst/seed1_1800s.json |
| burst | 1 | 联合候选 | 163.289 | 3.889 | 0.736 | 0.944 | 72 | 190 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_single/local_neighbor/burst_seed1_1800s_700.json |
| burst | 2 | V3 | 154.847 | 3.818 | 0.671 | 0.948 | 66 | 494 | experiments/v3_joint_routing_candidate/runs/C1_single/released_v3/full/burst/seed2_1800s.json |
| burst | 2 | 联合候选 | 154.866 | 3.919 | 0.706 | 0.947 | 67 | 188 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_single/local_neighbor/burst_seed2_1800s_700.json |
| uniform | 0 | V3 | 154.524 | 3.585 | 0.555 | 0.937 | 81 | 502 | benchmarks/runs/single/seed0/rcaps_v3.json |
| uniform | 0 | 联合候选 | 154.531 | 3.501 | 0.570 | 0.936 | 83 | 188 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_single/local_neighbor/uniform_seed0_1800s_700.json |
| uniform | 1 | V3 | 160.741 | 3.494 | 0.559 | 0.925 | 97 | 506 | benchmarks/runs/single/seed1/rcaps_v3.json |
| uniform | 1 | 联合候选 | 160.704 | 3.642 | 0.571 | 0.924 | 98 | 185 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_single/local_neighbor/uniform_seed1_1800s_700.json |
| uniform | 2 | V3 | 152.674 | 3.661 | 0.564 | 0.931 | 88 | 512 | benchmarks/runs/single/seed2/rcaps_v3.json |
| uniform | 2 | 联合候选 | 152.659 | 3.748 | 0.575 | 0.930 | 89 | 192 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_single/local_neighbor/uniform_seed2_1800s_700.json |

配对差值为联合候选减去 V3。延迟与积压越低越好。

- uniform：3 个完整种子的平均配对差值为吞吐 -0.015 token/s，P95 TTFT +0.051 s，P95 TPOT +0.013 s，完成率 -0.001，积压 +1.3。
- burst：3 个完整种子的平均配对差值为吞吐 +0.032 token/s，P95 TTFT +0.151 s，P95 TPOT +0.048 s，完成率 -0.000，积压 +0.0。

## C1_multi

选中布局：`single_boundary`；层段副本数 [1, 3]；LP 静态容量 1.722 请求/s。
LP 首要瓶颈：`gpu:1`。固定形状搜索检查 100 个合法布局，耗时 88.4 秒；短名单在线规划窗口累计 253.7 秒。未进入训练短名单的布局没有在线验证。

静态容量并列诊断：LP 容量最高的布局有 4 个（capacity_1, local_neighbor, released_v3, single_boundary）；这些布局在容量代理下无法区分。下表只列开发种子 100 的在线短窗口范围，用于说明选择依据，不作为独立性能证据。

| 开发到达模式 | 并列布局数 | 完成率范围 | P95 TTFT 范围 s | P95 TPOT 范围 s |
| --- | ---: | ---: | ---: | ---: |
| uniform | 4 | 0.574–0.596 | 4.627–5.072 | 0.571–0.605 |
| burst | 4 | 0.574–0.596 | 4.582–5.956 | 0.610–0.672 |

| 到达模式 | 种子 | 方法 | 输出 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 路径数 | 原始结果 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| burst | 0 | V3 | 72.761 | 6.081 | 0.899 | 0.942 | 34 | 36 | experiments/v3_joint_routing_candidate/runs/C1_multi/released_v3/full/burst/seed0_1800s.json |
| burst | 0 | 联合候选 | 72.695 | 6.025 | 0.963 | 0.940 | 35 | 74 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_multi/single_boundary/burst_seed0_1800s_320.json |
| burst | 1 | V3 | 71.807 | 5.859 | 0.836 | 0.931 | 39 | 34 | experiments/v3_joint_routing_candidate/runs/C1_multi/released_v3/full/burst/seed1_1800s.json |
| burst | 1 | 联合候选 | 71.751 | 6.104 | 0.895 | 0.928 | 41 | 69 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_multi/single_boundary/burst_seed1_1800s_320.json |
| burst | 2 | V3 | 70.680 | 5.754 | 0.827 | 0.930 | 41 | 32 | experiments/v3_joint_routing_candidate/runs/C1_multi/released_v3/full/burst/seed2_1800s.json |
| burst | 2 | 联合候选 | 70.532 | 5.858 | 0.883 | 0.928 | 42 | 73 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_multi/single_boundary/burst_seed2_1800s_320.json |
| uniform | 0 | V3 | 71.713 | 5.229 | 0.699 | 0.921 | 46 | 32 | benchmarks/runs/multi/seed0/rcaps_v3.json |
| uniform | 0 | 联合候选 | 71.690 | 5.365 | 0.735 | 0.923 | 45 | 61 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_multi/single_boundary/uniform_seed0_1800s_320.json |
| uniform | 1 | V3 | 70.519 | 5.413 | 0.703 | 0.916 | 48 | 35 | benchmarks/runs/multi/seed1/rcaps_v3.json |
| uniform | 1 | 联合候选 | 70.542 | 5.369 | 0.745 | 0.914 | 49 | 64 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_multi/single_boundary/uniform_seed1_1800s_320.json |
| uniform | 2 | V3 | 69.496 | 5.338 | 0.695 | 0.916 | 49 | 32 | benchmarks/runs/multi/seed2/rcaps_v3.json |
| uniform | 2 | 联合候选 | 69.411 | 5.538 | 0.727 | 0.915 | 50 | 57 | experiments/v3_joint_routing_candidate/capacity_joint/runs/C1_multi/single_boundary/uniform_seed2_1800s_320.json |

配对差值为联合候选减去 V3。延迟与积压越低越好。

- uniform：3 个完整种子的平均配对差值为吞吐 -0.028 token/s，P95 TTFT +0.097 s，P95 TPOT +0.037 s，完成率 -0.001，积压 +0.3。
- burst：3 个完整种子的平均配对差值为吞吐 -0.090 token/s，P95 TTFT +0.098 s，P95 TPOT +0.060 s，完成率 -0.002，积压 +1.3。

## 判定

这项候选只在部署前用在线短窗口反馈选择布局；运行时没有模型层迁移或重新放置。因此它检验的是离线放置选择与在线路由的耦合，不是运行时放置闭环。

两拓扑、均匀与突发到达的 12 个正式配对窗口中，联合候选的 P95 TPOT 均高于冻结 V3。吞吐差值很小且方向不一致；开发短窗口选出的布局未在独立正式种子上带来稳定收益。当前证据不支持把这个联合候选升级为主方法，也不能据此声称已经解决静态评价与在线表现不一致。

LP 最大容量在两个拓扑各有四个布局并列，而开发窗口的完成率和尾延迟有差异。这是静态容量代理区分力不足的直接诊断；并不证明当前短窗口反馈规则已经修复该问题。

