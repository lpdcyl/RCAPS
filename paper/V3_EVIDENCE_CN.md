# RCAPS V3 论文证据总表

本页是 V3 论文写作的入口，不替代原始 JSON 和完整实验报告。方法定义以
[`V3 冻结记录`](../experiments/v3_release/README_CN.md)为准；所有数字均为
同负载、同种子 0/1/2、1800 秒、零预热、不排空的 Helix **仿真**窗口。
三个种子只描述波动，不构成统计显著性证明。

## 方法定位

| 模块 | 职责 | 可支持的主张 |
| --- | --- | --- |
| M1 | 异构资源图和给定放置后的层兼容 DAG | 表示一致性与合法性；不主张独立性能增益 |
| M2 | 多级共享复制结构的有界静态搜索 | 在具体资源池中检验放置结构及在线收益 |
| M3 | 在合法 DAG 上利用实时 GPU、链路和 KV 状态选路 | 通过固定放置的受控对照检验调度收益 |

## 已完成的核心结果

| 实验 | 已有证据 | 写作边界 |
| --- | --- | --- |
| [V3–Helix ILP](../experiments/v3_release/README_CN.md) | C1 单集群与三集群，700/320 offered token/s；V3 平均输出吞吐 155.980/70.576，Helix ILP 为 142.273/58.255 token/s | Helix 历史窗口缺少物理配置文件哈希；负载与请求轨迹已配对 |
| [V3 四格递进消融](../experiments/v3_core_ablations/formal_report.md) | A 单边界+静态 DAG、B 多级候选+静态 DAG、C 单边界+实时 M3、D V3；两拓扑三种子 | C1 单集群 B 相对 A 改善；三集群 B 仍是单边界，B−A 仅反映微观放置变化；不要宣称普遍正向交互 |
| [V3 路径空间消融](../experiments/v3_pathspace_ablation/formal_report.md) | 相同放置和实时 M3 下，规范路径与完整层兼容 DAG 配对 | 三集群完整 DAG 改善，单集群完整 DAG 退化；不可写成普遍收益 |
| [四方法共同负载对比](../experiments/v3_four_method_comparison/RESULTS_CN.md) | C1 单/三集群，350/160 offered token/s；V3、Helix ILP、Swarm、SP 同轨迹 | 与 700/320 的 V3–Helix 结果分开报告；单集群 V3 与 SP 吞吐基本相同 |
| [资源池与结构选择](../experiments/m2_multistage_candidate/RESULTS_CN.md) | C1–C5 离线审计；C1–C3 正式在线窗口 | C4/C5 只有短窗口检查；V3 不保证每池都选出多级布局 |

所有正式结果的原始路径、哈希、完成率、末端积压和共同完成请求的尾延迟
见对应报告及 JSON 索引。固定窗口 P95 需与完成率和未完成请求一起解释。

## 尚未完成

V3 负载、跨集群 RTT 和参考 Decode batch 的系统敏感性实验尚未完成。
归档分支的负载和 RTT 图读取的是 V3 之前的结果，不能沿用为 V3 图。
