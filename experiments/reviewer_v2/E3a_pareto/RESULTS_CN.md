# E3a：P95 TPOT 与 GPU 工作量 Pareto 重分析

两轴均为五种子均值；误差棒为 t(4) 95% CI 半宽。范围仅为两个模拟负载点。

| 拓扑 | 方法 | TPOT s [95% CI 半宽] | GPU s/token [95% CI 半宽] | 均值前沿 |
|---|---|---:|---:|---|
| multi | bandwidth:canonical_chunk | 0.6783 ± 0.0240 | 0.0378 ± 0.0011 | 是 |
| multi | bandwidth:canonical_nochunk | 0.8407 ± 0.0377 | 0.0357 ± 0.0008 | 是 |
| multi | core:HH | 3.4467 ± 0.4324 | 0.0871 ± 0.0058 | 否 |
| multi | core:HHplus | 4.1156 ± 0.5475 | 0.0246 ± 0.0006 | 是 |
| multi | core:HR | 1.9196 ± 0.1390 | 0.0279 ± 0.0016 | 否 |
| multi | core:RHplus | 1.6006 ± 0.1375 | 0.0258 ± 0.0012 | 是 |
| multi | core:RR | 0.7124 ± 0.0237 | 0.0891 ± 0.0027 | 否 |
| multi | core:V4 | 0.6119 ± 0.0120 | 0.0642 ± 0.0023 | 是 |
| multi | session:batch | 0.6640 ± 0.0231 | 0.0527 ± 0.0022 | 是 |
| multi | session:cycle | 0.6242 ± 0.0135 | 0.0620 ± 0.0027 | 否 |
| multi | session:k1 | 0.6185 ± 0.0165 | 0.0586 ± 0.0022 | 是 |
| multi | session:k1_5 | 0.6128 ± 0.0162 | 0.0621 ± 0.0020 | 是 |
| multi | session:k3 | 0.6136 ± 0.0089 | 0.0664 ± 0.0020 | 否 |
| multi | session:k4 | 0.6127 ± 0.0095 | 0.0668 ± 0.0021 | 否 |
| multi | session:marginal | 0.8289 ± 0.0178 | 0.0364 ± 0.0021 | 是 |
| multi | session:no_session | 0.8282 ± 0.0172 | 0.0373 ± 0.0021 | 是 |
| single | core:HH | 1.7340 ± 0.0589 | 0.0578 ± 0.0016 | 否 |
| single | core:HHplus | 1.4278 ± 0.0317 | 0.0275 ± 0.0007 | 否 |
| single | core:HR | 1.0976 ± 0.0404 | 0.0317 ± 0.0010 | 否 |
| single | core:RHplus | 0.6725 ± 0.0101 | 0.0297 ± 0.0009 | 否 |
| single | core:RR | 0.5602 ± 0.0040 | 0.0982 ± 0.0020 | 否 |
| single | core:V4 | 0.5075 ± 0.0026 | 0.0530 ± 0.0015 | 否 |
| single | session:batch | 0.5007 ± 0.0028 | 0.0529 ± 0.0013 | 是 |
| single | session:cycle | 0.5075 ± 0.0026 | 0.0530 ± 0.0015 | 否 |
| single | session:k1 | 0.5043 ± 0.0050 | 0.0530 ± 0.0016 | 否 |
| single | session:k1_5 | 0.5093 ± 0.0085 | 0.0530 ± 0.0017 | 否 |
| single | session:k3 | 0.5094 ± 0.0052 | 0.0532 ± 0.0015 | 否 |
| single | session:k4 | 0.5081 ± 0.0055 | 0.0532 ± 0.0016 | 否 |
| single | session:marginal | 0.6252 ± 0.0145 | 0.0362 ± 0.0013 | 否 |
| single | session:no_session | 0.6453 ± 0.0115 | 0.0363 ± 0.0009 | 否 |
| single | weight:w0_high | 0.6130 ± 0.0051 | 0.0201 ± 0.0005 | 是 |
| single | weight:w2_low | 0.6130 ± 0.0051 | 0.0201 ± 0.0005 | 是 |

## 论文可用表述

在单集群 700 和三集群 320 token/s 的五种子模拟结果中，P95 TPOT 与每输出 token GPU 忙碌秒呈现不同权衡点。
图中红色点按两轴均值定义 Pareto 前沿，误差棒反映种子间不确定性。
这些结果不能说明跨负载普适优势或真实 GPU 集群效率。
