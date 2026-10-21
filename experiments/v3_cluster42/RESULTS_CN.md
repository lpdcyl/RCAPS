# 42 节点高异构集群：V3 核心实验

协议见 `protocol.json`（先于正式窗口提交）。种子 0/1/2，1800 秒，零预热，不排空。`_off` 表示关闭模拟器单请求 Decode 2 倍计时的反事实。三个种子不作显著性检验。

## 布局

V3（冻结 M2 搜索，`plan.py`）：层 0–47 × 1 副本；层 48–79 × 4 副本，规划耗时 91 秒。

## 逐窗口

| 负载 | 种子 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | 平均 Decode 批 | GPU 秒/token | 路径数 |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2150 | 0 | helix | 459.80 | 4.914 | 1.371 | 0.879 | 476 | — | 0.0438 | 152 |
| 2150 | 1 | helix | 458.68 | 5.143 | 1.384 | 0.876 | 489 | — | 0.0436 | 151 |
| 2150 | 2 | helix | 460.70 | 5.156 | 1.375 | 0.898 | 400 | — | 0.0435 | 152 |
| 1450 | 0 | helix | 315.50 | 4.779 | 1.016 | 0.886 | 305 | — | 0.0687 | 151 |
| 1450 | 0 | v3 | 332.49 | 2.727 | 0.392 | 0.946 | 145 | 10.43 | 0.0209 | 16 |
| 1450 | 0 | gated | 332.19 | 2.613 | 0.394 | 0.944 | 151 | 22.38 | 0.0119 | 4 |
| 1450 | 1 | helix | 308.08 | 4.657 | 1.019 | 0.902 | 251 | — | 0.0709 | 150 |
| 1450 | 1 | gated | 321.54 | 2.559 | 0.380 | 0.951 | 127 | 20.96 | 0.0132 | 4 |
| 1450 | 2 | helix | 304.80 | 4.827 | 1.025 | 0.899 | 265 | — | 0.0715 | 150 |
| 1450 | 2 | gated | 318.89 | 2.599 | 0.396 | 0.949 | 135 | 20.94 | 0.0134 | 4 |

## 配对相对变化（右 − 左）/ 左

| 负载 | 对照 | 种子 | 吞吐 | P95 TTFT | P95 TPOT | GPU 秒/token | 完成率 Δ | 共同完成 TPOT |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |

## 预注册判定


失败窗口（保留，不重跑；对应问题记为不通过）：experiments/v3_cluster42/runs/formal/load2150/v3_seed0.failure.json、experiments/v3_cluster42/runs/formal/load2150/gated_seed0.failure.json、experiments/v3_cluster42/runs/formal/load2150/v3_off_seed0.failure.json、experiments/v3_cluster42/runs/formal/load2150/gated_off_seed0.failure.json、experiments/v3_cluster42/runs/formal/load2150/v3_seed1.failure.json、experiments/v3_cluster42/runs/formal/load2150/gated_seed1.failure.json、experiments/v3_cluster42/runs/formal/load2150/v3_off_seed1.failure.json、experiments/v3_cluster42/runs/formal/load2150/gated_off_seed1.failure.json、experiments/v3_cluster42/runs/formal/load2150/gated_seed2.failure.json、experiments/v3_cluster42/runs/formal/load2150/gated_off_seed2.failure.json
