# V3 M2–M3 联合优化候选

## 容量约束与实时路由版本

`capacity.py` 在 M1 层兼容图上展开 `(GPU, 进入层边界)` 状态，对四类训练请求求共享资源容量 LP。每张物理 GPU、每条有向链路、发送 NIC 和接收 NIC 都只有一份容量；部分重叠区间只计算实际执行的层。LP 容量是离线资源代理，不是在线吞吐或 P95 预测。`capacity_search.py` 用固定形状网格、beam 和 A100 主干种子产生候选布局。`joint_capacity.py` 将其与发布版及现有邻居合并，保留容量前两名和与第二名并列的所有布局，再使用种子 100 的均匀与时间突发轨迹，先按最差完成率、再按 P95 TPOT、TTFT、吞吐的词典序选布局。

`capacity_route.py` 在原 M3 实时 GPU、链路等待及 KV 会话成本上保留最多四个非支配路由标签。只有实时成本在最早路径 10% 内的候选才按 LP 资源压力选路。Decode 固定路径与传输合并沿用 V3。纯图 M1 和冻结 V3 均未修改。

这里的反馈只用于**部署前**的短窗口布局选择。正式服务运行后不迁移模型层，也不根据实时队列重新搜索或重新加载布局；M3 仅在固定部署上逐请求选路。因此本候选不能称为运行时动态重放置。

在仓库根目录执行，两拓扑分别运行 `C1_single`、`C1_multi`：

```powershell
python -m unittest experiments.v3_joint_routing_candidate.test_capacity_joint -v
python -m experiments.v3_joint_routing_candidate.capacity_search --case C1_single
python -m experiments.v3_joint_routing_candidate.joint_capacity prepare --case C1_single
python -m experiments.v3_joint_routing_candidate.joint_capacity smoke --case C1_single
python -m experiments.v3_joint_routing_candidate.joint_capacity choose --case C1_single
python -m experiments.v3_joint_routing_candidate.joint_capacity diagnose-m3 --case C1_single
python -m experiments.v3_joint_routing_candidate.joint_capacity validate --case C1_single
python -m experiments.v3_joint_routing_candidate.capacity_report
```

容量候选的训练负载为单集群 350、三集群 160 offered token/s，正式对照仍用 700／320，种子 0／1／2 和 1800 秒。正式结果保存在 `capacity_joint/`。搜索范围有限，不声称全局最优；只有完整同轨迹结果才能支持在线收益主张。当前资源池若仍由共同共享前段限制容量，LP 对布局的区分力可能很弱，这应如实报告。

## 早期路径裁剪原型

这是独立候选；不覆盖冻结的 V3 布局或正式结果。M1 仍只提供异构资源和层兼容 DAG。M2 从发布版布局、同资源池单边界布局以及发布版布局的确定性邻域中构建一个有界候选池。每个布局分别允许完整 DAG、规范路径骨架，以及「骨架＋规划轨迹中至少使用两次的额外边」。M3 的实时路径代价、Decode 固定路径和传输合并均不变。

规划使用种子 100、300 秒的均匀与时间突发固定窗口。突发轨迹保持请求数量、输入输出长度与顺序，只压缩中段请求到达时间。单场景评分提前固定为 `0.40 × P95 TTFT 相对发布版 + 0.35 × P95 TPOT 相对发布版 + 0.25 × 发布版吞吐/候选吞吐 + 2 × (发布版完成率 − 候选完成率)`；布局与路径集合以两个场景的较差分数选出。测试使用独立种子 0/1/2、1800 秒、两种到达模式的同轨迹配对窗口。两拓扑分别使用原 C1 负载 700/320 offered token/s。规划种子与正式种子分离，三个正式种子只描述波动，不声明统计显著。

在仓库根目录执行：

```powershell
python -m experiments.v3_joint_routing_candidate.joint prepare --case C1_single
python -m experiments.v3_joint_routing_candidate.joint plan --case C1_single
python -m experiments.v3_joint_routing_candidate.joint parity --case C1_single
python -m experiments.v3_joint_routing_candidate.joint validate --case C1_single
```

三集群把 `C1_single` 改成 `C1_multi`。`plans/`、`runs/`、`parity/`、`validation/` 保留布局、路径集合、原始窗口和哈希。选择只依据种子 100；验证种子不参与调参。只有 60 秒路径及指标逐项回归通过、且布局及正式协议哈希一致时，均匀到达的历史正式窗口才复用。每个保留的路径集合须是物理和层兼容 DAG 的子图，并让所有部署 GPU 位于完整路径上。失败保留失败状态，不补造指标。
