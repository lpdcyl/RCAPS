# V3 × Helix 放置与调度交叉实验

HH=Helix ILP+Helix Online MaxFlow；HR=Helix ILP+V3 M3；RH=V3 M2+Helix Online MaxFlow；RR=完整 V3。
相同拓扑、负载、种子、请求轨迹和固定窗口；失败不填补指标。

## single

| 种子 | 格 | 状态 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 未完成驻留 P95 s |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | HH | passed | 141.568 | 6.399 | 1.666 | 0.828 | 223 | 583.921 |
| 0 | HR | passed | 148.270 | 5.536 | 1.055 | 0.882 | 152 | 372.023 |
| 0 | RH | passed | 150.661 | 3.744 | 0.861 | 0.906 | 121 | 306.486 |
| 0 | RR | reused | 154.524 | 3.585 | 0.555 | 0.937 | 81 | 202.053 |
| 1 | HH | passed | 145.885 | 6.599 | 1.708 | 0.809 | 247 | 603.524 |
| 1 | HR | passed | 152.811 | 5.736 | 1.103 | 0.864 | 176 | 358.561 |
| 1 | RH | passed | 156.060 | 3.883 | 0.878 | 0.890 | 142 | 311.825 |
| 1 | RR | reused | 160.741 | 3.494 | 0.559 | 0.925 | 97 | 207.060 |
| 2 | HH | passed | 139.366 | 6.726 | 1.743 | 0.822 | 225 | 678.497 |
| 2 | HR | passed | 145.612 | 6.135 | 1.143 | 0.877 | 156 | 378.670 |
| 2 | RH | passed | 148.335 | 3.969 | 0.875 | 0.898 | 129 | 325.055 |
| 2 | RR | reused | 152.674 | 3.661 | 0.564 | 0.931 | 88 | 209.409 |

| 对照 | 指标 | 配对差均值 |
| --- | --- | ---: |
| HH→HR | output_throughput_tokens_per_s | 6.6244 |
| HH→HR | ttft_p95_s | -0.7724 |
| HH→HR | tpot_p95_s | -0.6054 |
| HH→HR | completion_fraction | 0.0548 |
| HH→HR | backlog_at_window_end | -70.3333 |
| HH→RH | output_throughput_tokens_per_s | 9.4124 |
| HH→RH | ttft_p95_s | -2.7092 |
| HH→RH | tpot_p95_s | -0.8344 |
| HH→RH | completion_fraction | 0.0787 |
| HH→RH | backlog_at_window_end | -101.0000 |
| HR→RR | output_throughput_tokens_per_s | 7.0826 |
| HR→RR | ttft_p95_s | -2.2224 |
| HR→RR | tpot_p95_s | -0.5410 |
| HR→RR | completion_fraction | 0.0566 |
| HR→RR | backlog_at_window_end | -72.6667 |
| RH→RR | output_throughput_tokens_per_s | 4.2946 |
| RH→RR | ttft_p95_s | -0.2855 |
| RH→RR | tpot_p95_s | -0.3120 |
| RH→RR | completion_fraction | 0.0327 |
| RH→RR | backlog_at_window_end | -42.0000 |
| 四格交互 | output_throughput_tokens_per_s | -2.3298 |
| 四格交互 | ttft_p95_s | 0.4868 |
| 四格交互 | tpot_p95_s | 0.2934 |
| 四格交互 | completion_fraction | -0.0221 |
| 四格交互 | backlog_at_window_end | 28.3333 |

## multi

| 种子 | 格 | 状态 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 未完成驻留 P95 s |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | HH | passed | 59.324 | 15.867 | 3.230 | 0.683 | 185 | 1206.424 |
| 0 | HR | passed | 65.752 | 10.360 | 2.002 | 0.805 | 114 | 626.260 |
| 0 | RH | failed | — | — | — | — | — | — |
| 0 | RR | reused | 71.713 | 5.229 | 0.699 | 0.921 | 46 | 230.247 |
| 1 | HH | passed | 57.407 | 15.388 | 3.206 | 0.699 | 171 | 1117.065 |
| 1 | HR | passed | 64.034 | 10.529 | 1.819 | 0.803 | 112 | 594.872 |
| 1 | RH | failed | — | — | — | — | — | — |
| 1 | RR | reused | 70.519 | 5.413 | 0.703 | 0.916 | 48 | 240.357 |
| 2 | HH | passed | 58.034 | 15.494 | 3.148 | 0.724 | 162 | 1007.856 |
| 2 | HR | passed | 63.894 | 10.360 | 1.801 | 0.805 | 114 | 629.876 |
| 2 | RH | failed | — | — | — | — | — | — |
| 2 | RR | reused | 69.496 | 5.338 | 0.695 | 0.916 | 49 | 210.100 |

| 对照 | 指标 | 配对差均值 |
| --- | --- | ---: |
| HH→HR | output_throughput_tokens_per_s | 6.3050 |
| HH→HR | ttft_p95_s | -5.1665 |
| HH→HR | tpot_p95_s | -1.3205 |
| HH→HR | completion_fraction | 0.1024 |
| HH→HR | backlog_at_window_end | -59.3333 |
| HR→RR | output_throughput_tokens_per_s | 6.0159 |
| HR→RR | ttft_p95_s | -5.0903 |
| HR→RR | tpot_p95_s | -1.1750 |
| HR→RR | completion_fraction | 0.1133 |
| HR→RR | backlog_at_window_end | -65.6667 |
| 四格交互 | — | 不计算：四格未在全部种子齐全 |

三个种子仅描述波动，不作显著性声明。条件收益不能解释为脱离另一组件的固定贡献。
