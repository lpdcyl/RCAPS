# 可用于论文的 V3 M2 消融（已完成正式窗口）

## 设计

主对照固定 V3 的层兼容 DAG 执行接口和同一实时 M3，仅替换放置来源：Helix ILP、V3 M2 单边界搜索、完整 V3 M2（最多双边界）。“无 M2”在此具体定义为 Helix ILP 放置，并非空部署。三行使用相同资源池、种子、请求身份和 1800 秒零预热不排空窗口。

| 拓扑与负载 | 放置 + 固定 M3 | 输出 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ | 完成率 ↑ | 末端积压 ↓ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 单集群，700 token/s | Helix ILP + M3（无 M2） | 148.897 ± 3.640 | 5.802 ± 0.305 | 1.100 ± 0.044 | 0.874 ± 0.010 | 161.333 ± 12.858 |
| 单集群，700 token/s | 单边界 M2 + M3 | 155.376 ± 4.169 | 3.863 ± 0.162 | 0.600 ± 0.007 | 0.925 ± 0.006 | 96.000 ± 8.185 |
| 单集群，700 token/s | 完整 M2 + M3（V3） | 155.980 ± 4.226 | 3.580 ± 0.084 | 0.559 ± 0.004 | 0.931 ± 0.006 | 88.667 ± 8.021 |
| 三集群，320 token/s | Helix ILP + M3（无 M2） | 64.560 ± 1.035 | 10.417 ± 0.098 | 1.874 ± 0.112 | 0.804 ± 0.001 | 113.333 ± 1.155 |
| 三集群，320 token/s | 单边界 M2 + M3 | 70.566 ± 1.096 | 5.484 ± 0.140 | 0.694 ± 0.004 | 0.917 ± 0.004 | 48.000 ± 1.732 |
| 三集群，320 token/s | 完整 M2 + M3（V3） | 70.576 ± 1.109 | 5.326 ± 0.092 | 0.699 ± 0.004 | 0.918 ± 0.003 | 47.667 ± 1.528 |

均值 ± 样本标准差；种子 0/1/2。

## 配对差值（右侧 − 左侧）

| 拓扑 | 对照 | 吞吐差 token/s | 吞吐相对变化 | P95 TTFT 差 s | P95 TPOT 差 s | 完成率差 | 积压差 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C1_single | 完整 M2 − Helix ILP | +7.083 | +4.76% | -2.222 | -0.541 | +0.057 | -72.7 |
| C1_single | 完整 M2 − 单边界 M2 | +0.604 | +0.39% | -0.283 | -0.041 | +0.006 | -7.3 |
| C1_multi | 完整 M2 − Helix ILP | +6.016 | +9.32% | -5.090 | -1.175 | +0.113 | -65.7 |
| C1_multi | 完整 M2 − 单边界 M2 | +0.009 | +0.01% | -0.157 | +0.005 | +0.001 | -0.3 |

## 解释

- **M2 作为放置方法有用。** 固定 M3 后，完整 M2 相对 Helix ILP 在两拓扑的三个配对种子中均提高吞吐、完成率，并降低 TTFT、TPOT 与积压。主表只支持所测资源池和负载下的条件收益。
- **多级结构的增量收益限于单集群。** 单集群完整 M2 相对单边界 M2 的平均吞吐增加 0.604 token/s，TTFT/TPOT 下降 0.283/0.041 s。三集群完整 M2 实际仍选 `1→3` 单边界；两行只反映微观 GPU 放置差异，不能称为多级结构收益。
- **请求完成集合不同。** 主对照的共同完成请求 P95 仍同向；逐种子共同完成数和 P95 见下表。固定窗口 P95 应连同完成率与积压解释。三个种子描述方向与波动，不作显著性声明。

| 拓扑 | 种子 | 共同完成数 | 共同 P95 TTFT：Helix→M2 s | 共同 P95 TPOT：Helix→M2 s |
| --- | ---: | ---: | ---: | ---: |
| C1_single | 0 | 1141 | 5.539→3.648 | 1.055→0.556 |
| C1_single | 1 | 1115 | 5.728→3.508 | 1.077→0.559 |
| C1_single | 2 | 1111 | 6.122→3.696 | 1.072→0.556 |
| C1_multi | 0 | 470 | 9.762→5.130 | 1.875→0.699 |
| C1_multi | 1 | 457 | 10.449→5.300 | 1.819→0.711 |
| C1_multi | 2 | 472 | 10.357→5.246 | 1.826→0.702 |

## 论文可采用的表述

在固定层兼容 DAG 构建规则和同一实时 M3 调度器后，将 Helix ILP 放置替换为完整 M2 放置，在 C1 单集群和三集群的相同到达轨迹上，平均输出吞吐分别提高 4.76% 和 9.32%，P95 TTFT 分别降低 2.222 s 和 5.090 s。单集群的第二边界带来较小的额外收益；三集群搜索回退为单边界，不支持多级结构在该拓扑上有效的主张。

**English draft.** Holding the layer-compatible DAG construction rule and the online M3 scheduler fixed, replacing the Helix ILP placement with M2 increases mean output throughput by 4.76% and 9.32% in the single- and three-cluster settings, respectively. The corresponding P95 TTFT decreases by 2.222 s and 5.090 s. The additional boundary yields a smaller gain in the single-cluster setting; in the three-cluster setting, the full search selects a single-boundary layout, so its marginal difference cannot be attributed to multistage replication. These are paired three-seed simulator results, not a statistical significance claim.

## 复现与来源

运行 `python -m experiments.v3_m2_paper_ablation.make_table`。生成器逐个核验原始 JSON 的 SHA256、物理配置、布局、窗口协议、请求身份及汇总数值。原始路径和哈希保存在 `summary.json`。此文件只汇总已完成的正式仿真，没有新跑窗口。
