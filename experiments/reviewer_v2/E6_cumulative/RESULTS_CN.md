# E6 机制逐项叠加结果

70B 画像驱动 CPU 仿真；四负载、seed0–4，1800 s 零预热、不排空。H0/P1/T5 为经 SHA 核验的旧核心实验，新做 R2/S3/Q4。
H0→P1 只换部署；P1→R2 换 MaxFlow 为 RCAPS DAG；R2→S3 加稀疏准入；S3→Q4 加会话持续代价；Q4→T5 加慢链路 4 MiB Prompt 传输分块。

| 场景/负载 | 阶段 | 成功 | P95 TPOT s | P95 TTFT s | GPU 秒/token | 完成率 |
|---|---|---:|---:|---:|---:|---:|
| single/350 | H0 | 5/5 | 0.8197 | 5.4767 | 0.0605 | 0.9162 |
| single/350 | P1 | 5/5 | 0.4552 | 3.2534 | 0.0674 | 0.9454 |
| single/350 | R2 | 4/5 | — | — | — | — |
| single/350 | S3 | 5/5 | 0.4602 | 3.2014 | 0.0611 | 0.9476 |
| single/350 | Q4 | 3/5 | — | — | — | — |
| single/350 | T5 | 5/5 | 0.3968 | 3.2767 | 0.1195 | 0.9508 |
| single/700 | H0 | 5/5 | 1.4278 | 6.4759 | 0.0275 | 0.8564 |
| single/700 | P1 | 5/5 | 0.6725 | 3.7998 | 0.0297 | 0.9189 |
| single/700 | R2 | 3/5 | — | — | — | — |
| single/700 | S3 | 4/5 | — | — | — | — |
| single/700 | Q4 | 2/5 | — | — | — | — |
| single/700 | T5 | 5/5 | 0.5075 | 3.6111 | 0.0530 | 0.9383 |
| multi/160 | H0 | 5/5 | 1.6361 | 13.3443 | 0.0454 | 0.8342 |
| multi/160 | P1 | 5/5 | 0.9725 | 9.5458 | 0.0587 | 0.8985 |
| multi/160 | R2 | 5/5 | 0.7377 | 5.1480 | 0.0529 | 0.9194 |
| multi/160 | S3 | 5/5 | 0.7857 | 5.3233 | 0.0446 | 0.9152 |
| multi/160 | Q4 | 3/5 | — | — | — | — |
| multi/160 | T5 | 5/5 | 0.5270 | 5.1088 | 0.1137 | 0.9389 |
| multi/320 | H0 | 5/5 | 4.1156 | 15.6554 | 0.0246 | 0.6420 |
| multi/320 | P1 | 5/5 | 1.6006 | 10.3701 | 0.0258 | 0.8254 |
| multi/320 | R2 | 5/5 | 1.0648 | 5.9641 | 0.0409 | 0.8769 |
| multi/320 | S3 | 5/5 | 1.1492 | 6.1918 | 0.0386 | 0.8707 |
| multi/320 | Q4 | 3/5 | — | — | — | — |
| multi/320 | T5 | 5/5 | 0.6119 | 5.2731 | 0.0642 | 0.9222 |

## 逐步配对差异

右阶段减左阶段；延迟和 GPU 秒/token 负值为下降，完成率正值为上升。仅 5/5 配对给 df=4 双侧 t 95% CI。

| 负载 | 对比 | 指标 | 配对均差 | 95% CI |
|---|---|---|---:|---:|
| single/350 | H0→P1 | tpot_p95_s | -0.36455 | [-0.38935, -0.33975] |
| single/350 | H0→P1 | ttft_p95_s | -2.22324 | [-2.41385, -2.03263] |
| single/350 | H0→P1 | gpu_seconds_per_output_token | +0.00693 | [+0.00630, +0.00755] |
| single/350 | H0→P1 | completion_fraction | +0.02920 | [+0.01935, +0.03904] |
| single/350 | P1→R2 | tpot_p95_s | — | — |
| single/350 | P1→R2 | ttft_p95_s | — | — |
| single/350 | P1→R2 | gpu_seconds_per_output_token | — | — |
| single/350 | P1→R2 | completion_fraction | — | — |
| single/350 | R2→S3 | tpot_p95_s | — | — |
| single/350 | R2→S3 | ttft_p95_s | — | — |
| single/350 | R2→S3 | gpu_seconds_per_output_token | — | — |
| single/350 | R2→S3 | completion_fraction | — | — |
| single/350 | S3→Q4 | tpot_p95_s | — | — |
| single/350 | S3→Q4 | ttft_p95_s | — | — |
| single/350 | S3→Q4 | gpu_seconds_per_output_token | — | — |
| single/350 | S3→Q4 | completion_fraction | — | — |
| single/350 | Q4→T5 | tpot_p95_s | — | — |
| single/350 | Q4→T5 | ttft_p95_s | — | — |
| single/350 | Q4→T5 | gpu_seconds_per_output_token | — | — |
| single/350 | Q4→T5 | completion_fraction | — | — |
| single/700 | H0→P1 | tpot_p95_s | -0.75530 | [-0.78156, -0.72903] |
| single/700 | H0→P1 | ttft_p95_s | -2.67605 | [-2.73464, -2.61746] |
| single/700 | H0→P1 | gpu_seconds_per_output_token | +0.00221 | [+0.00194, +0.00248] |
| single/700 | H0→P1 | completion_fraction | +0.06243 | [+0.04937, +0.07549] |
| single/700 | P1→R2 | tpot_p95_s | — | — |
| single/700 | P1→R2 | ttft_p95_s | — | — |
| single/700 | P1→R2 | gpu_seconds_per_output_token | — | — |
| single/700 | P1→R2 | completion_fraction | — | — |
| single/700 | R2→S3 | tpot_p95_s | — | — |
| single/700 | R2→S3 | ttft_p95_s | — | — |
| single/700 | R2→S3 | gpu_seconds_per_output_token | — | — |
| single/700 | R2→S3 | completion_fraction | — | — |
| single/700 | S3→Q4 | tpot_p95_s | — | — |
| single/700 | S3→Q4 | ttft_p95_s | — | — |
| single/700 | S3→Q4 | gpu_seconds_per_output_token | — | — |
| single/700 | S3→Q4 | completion_fraction | — | — |
| single/700 | Q4→T5 | tpot_p95_s | — | — |
| single/700 | Q4→T5 | ttft_p95_s | — | — |
| single/700 | Q4→T5 | gpu_seconds_per_output_token | — | — |
| single/700 | Q4→T5 | completion_fraction | — | — |
| multi/160 | H0→P1 | tpot_p95_s | -0.66360 | [-0.74444, -0.58275] |
| multi/160 | H0→P1 | ttft_p95_s | -3.79848 | [-4.96322, -2.63374] |
| multi/160 | H0→P1 | gpu_seconds_per_output_token | +0.01337 | [+0.01270, +0.01404] |
| multi/160 | H0→P1 | completion_fraction | +0.06438 | [+0.03737, +0.09139] |
| multi/160 | P1→R2 | tpot_p95_s | -0.23475 | [-0.25796, -0.21153] |
| multi/160 | P1→R2 | ttft_p95_s | -4.39782 | [-4.73421, -4.06143] |
| multi/160 | P1→R2 | gpu_seconds_per_output_token | -0.00586 | [-0.00761, -0.00411] |
| multi/160 | P1→R2 | completion_fraction | +0.02082 | [+0.01073, +0.03090] |
| multi/160 | R2→S3 | tpot_p95_s | +0.04799 | [+0.03804, +0.05795] |
| multi/160 | R2→S3 | ttft_p95_s | +0.17530 | [-0.03068, +0.38129] |
| multi/160 | R2→S3 | gpu_seconds_per_output_token | -0.00827 | [-0.01098, -0.00557] |
| multi/160 | R2→S3 | completion_fraction | -0.00416 | [-0.00775, -0.00056] |
| multi/160 | S3→Q4 | tpot_p95_s | — | — |
| multi/160 | S3→Q4 | ttft_p95_s | — | — |
| multi/160 | S3→Q4 | gpu_seconds_per_output_token | — | — |
| multi/160 | S3→Q4 | completion_fraction | — | — |
| multi/160 | Q4→T5 | tpot_p95_s | — | — |
| multi/160 | Q4→T5 | ttft_p95_s | — | — |
| multi/160 | Q4→T5 | gpu_seconds_per_output_token | — | — |
| multi/160 | Q4→T5 | completion_fraction | — | — |
| multi/320 | H0→P1 | tpot_p95_s | -2.51502 | [-2.93850, -2.09154] |
| multi/320 | H0→P1 | ttft_p95_s | -5.28524 | [-5.57566, -4.99481] |
| multi/320 | H0→P1 | gpu_seconds_per_output_token | +0.00119 | [+0.00032, +0.00205] |
| multi/320 | H0→P1 | completion_fraction | +0.18339 | [+0.16379, +0.20298] |
| multi/320 | P1→R2 | tpot_p95_s | -0.53580 | [-0.63073, -0.44087] |
| multi/320 | P1→R2 | ttft_p95_s | -4.40605 | [-4.59484, -4.21725] |
| multi/320 | P1→R2 | gpu_seconds_per_output_token | +0.01504 | [+0.01407, +0.01601] |
| multi/320 | P1→R2 | completion_fraction | +0.05148 | [+0.03708, +0.06587] |
| multi/320 | R2→S3 | tpot_p95_s | +0.08448 | [+0.06483, +0.10413] |
| multi/320 | R2→S3 | ttft_p95_s | +0.22768 | [-0.08257, +0.53793] |
| multi/320 | R2→S3 | gpu_seconds_per_output_token | -0.00225 | [-0.00289, -0.00160] |
| multi/320 | R2→S3 | completion_fraction | -0.00618 | [-0.01528, +0.00292] |
| multi/320 | S3→Q4 | tpot_p95_s | — | — |
| multi/320 | S3→Q4 | ttft_p95_s | — | — |
| multi/320 | S3→Q4 | gpu_seconds_per_output_token | — | — |
| multi/320 | S3→Q4 | completion_fraction | — | — |
| multi/320 | Q4→T5 | tpot_p95_s | — | — |
| multi/320 | Q4→T5 | ttft_p95_s | — | — |
| multi/320 | Q4→T5 | gpu_seconds_per_output_token | — | — |
| multi/320 | Q4→T5 | completion_fraction | — | — |

## 解释边界

本表是预先固定顺序下的条件增量。P1→R2 是完整路由器迁移，不可称纯会话项；S3→Q4 才仅改变会话持续代价。顺序相关差异不证明普遍超加性协同。
新增原批成功 47/60、失败 13/60；失败原件保留，不能当成数值零。
E4 WSL2 网络微基准及其他协议不能混进本固定窗口表。
