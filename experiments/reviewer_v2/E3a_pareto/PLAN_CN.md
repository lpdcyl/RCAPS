# E3a：延迟—GPU 工作量 Pareto 重分析

预注册日期：2026-10-29。只使用现有已审计五种子数据；不新增模拟窗口。等 V4 seed3/4 独立重放 terminal 且审计通过后生成最终图和报告。

数据源固定为 experiments/v5_core_supplement/individual.csv、experiments/v6_completion/session_cost/individual.csv、experiments/v6_completion/weight_online/individual.csv、experiments/v6_completion/bandwidth_threshold/individual.csv。负载只取 single/700 和 multi/320。

每个拓扑纳入 Helix、Helix+、HR、RHplus、RR、V4；会话变体 batch、marginal、cycle、no_session、k1、k1_5、k3、k4；multi/320 加带宽 12.5 MB/s、阈值 50 MB/s 的 canonical_chunk 和 canonical_nochunk。single/700 加权重 w0_high、w2_low，它们在原离线结构审计中均为 [1,2]；multi 的权重变体均为 [1,3]，不冒充 [1,2]。

每个点必须有 seed0–4 的成功数据；逐文件 SHA256 与 CSV 中已有哈希核对，并逐种子验证同拓扑的轨迹 SHA256 一致。横轴 GPU 秒/输出 token、纵轴 P95 TPOT。图中两轴误差棒为五种子均值的 t 95% CI（df=4）；前沿按两指标均越小越好、均值严格支配定义。不要把不同点间未做配对检验的均值差称作显著。论文表述限于模拟器和这两个负载点。
