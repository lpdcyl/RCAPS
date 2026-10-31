# E2a 原单集群部署路径不一致审计

2026-10-30，在原 evaluation/index.json 20/20 terminal 后，report.py 逐种子核对历史 Helix 部署哈希时于 single/350/seed0 拒绝生成正式报告。核对表如下：

| 来源 | solution.ini SHA256 | simulator_cluster.ini SHA256 | 用途 |
|---|---|---|---|
| benchmarks.layout.scenario(single) | b7b9904bd596d46a2ee6d3936aa018659494d30be78734b2683a24290317ca69 | f772ffc21608b77270be6401c60adfa1f5dfb23f3dbe8ce210bb2ecbf4b24ab3 | 原 E2a 单集群实际输入 |
| baselines.helix.layout(single, ROOT) | 123bbd0d7db49dbd940a4680096e72aa9d243aad8d2a87b9d555eb86dde6726b | 8fd89156c27b64200a27c4f3348948b1a8b260be8231c12ccb440a37b9fec36f | 已审计五种子 Helix/Helix+ 基线 |

两个物理池 INI 哈希相同，但部署 INI 不同；示例目录和 artifact 单集群机器画像文件也不同。原单集群的 48 个 seed5/6 调优与 10 个 seed0–4 评估窗口均已运行，结果保留供诊断，**不得作为与历史 Helix/RCAPS 的正式配对证据**。原 single 的 selection.json 配置也不得复用到纠错评估。原 multi 部署哈希与历史基线一致；该部分可经报告审计独立使用。

补救使用 single_correction/ 独立目录、官方 Helix 部署、原预注册候选与种子隔离规则：48 个调优窗口重新运行，之后只用其 seed5/6 选参，再运行 10 个留出种子窗口。原 tuning/、failure_replay/、evaluation/、selection.json、冻结源码和 manifest 均保持原样。
