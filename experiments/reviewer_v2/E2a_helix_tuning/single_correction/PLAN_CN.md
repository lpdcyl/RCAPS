# E2a 单集群部署路径纠错：独立补跑预注册

登记日期：2026-10-30（Asia/Seoul）。在 E2a evaluation 全部 20 个窗口结束、report.py 审计之前发现：原 E2a 驱动调用 benchmarks.layout.scenario("single")，指向 examples/simulation/layouts/ilp，SHA256 b7b9904b... / f772ffc2...；而五种子历史 Helix/Helix+ 使用 artifact_evaluation/single_cluster/layout_llama70b/ilp，SHA256 123bbd0d... / 8fd89156...。物理池配置哈希相同，但部署和画像不同，故原单集群调优及评估不能与论文基线配对，也不能写进正式结论。原始 manifest、索引、结果、失败及重放完整保留，不覆盖。原三集群部署哈希与历史一致，可独立审计。

本独立纠错批次沿用原 E2a_helix_tuning/PLAN_CN.md 在看到正式结果前冻结的候选集合、seed 分离和选择规则，不根据原单集群结果筛选配置：单集群 350/700 token/s，每负载 12 唯一候选 × seed 5/6 调优，共 48 个窗口；只用这 48 个调优数据选参，随后再以 seed 0–4 作 10 个独立评估窗口。运行前冻结官方单集群 Helix 部署、物理池、执行器源码与环境 SHA256。协议仍为 1800 s 固定窗口、零预热、不排空；失败保留原件、独立重放。先以官方部署做 60 s 冒烟，核对 00 原 Helix 与 11 原 Helix+ 两端的逐指标等价，及非默认 KV 参数生效。

选择门槛保持原规则：完整 seed5/6，平均完成率不低于同种子默认 Helix+，再按 P95 TPOT 均值最低选择；并列按完成率、GPU 秒/token、候选字典序。正式 seed0–4 不参与选择。报告必须区分原路径错误批次、纠错批次、三集群有效批次与独立失败重放。不能以原错误部署的单集群结果补足纠错批次。
