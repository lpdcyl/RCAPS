# 独立复验的来源说明

历史 `experiments/v3_gated_pathspace/analysis.json` 保留了 6 个 gated 正式窗口的
汇总值与 SHA256，但当前检出版本没有这些候选原始窗口文件。
原运行器 `experiments/v3_gated_pathspace/run.py` 还导入当前检出版本缺失的
`experiments.v3_cohort_routing.run`，故不能原样复跑。

本目录重新实例化**同一个** `SlowLinkGatedScheduler`，从同一个规范路径边集
生成准入边，用 `benchmarks.fixed_window.run`、相同布局、物理资源、
负载、种子、1800 秒固定窗口和发布 V3 控制结果重建六格。
判定沿用历史 `protocol.json`，本目录的 `protocol.json` 在结果前冻结。
原候选调度器源码的历史审计 SHA256 是
`3d12affc9e64fa4e4e38977665b93046967a511ce9368e074ee13e712f790b47`；
当前 Windows 检出版本原始字节 SHA256 不同，但把 CRLF 换行归一化为 LF 后，
SHA256 与历史值完全一致。发布 V3 控制 JSON 的六个 SHA256 也与历史分析逐个相同。

这是**复现历史正式协议**，不是方法选择的独立发现。历史开发种子 100
未满足更严格的 TPOT 不升规则，后续研究者重新注册了 +2% 的三集群非劣效边界，
这一过程在原 `RESULTS_CN.md` 与 `protocol.json` 中保留。
