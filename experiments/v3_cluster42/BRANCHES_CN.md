# 实验分支与本次工作

依据实际读取到的分支头及其报告整理；不把不同实验的结果合并。

| 分支 | 已核对提交 | 实验内容 |
|---|---|---|
| `claude/clever-rubin-eeajdh` | `6a8fa97` | 42 节点高异构集群，Helix/V3/门控与单请求 Decode 计时反事实，原先部分窗口未完成。 |
| `claude/cluster42-resume-actions-20261021` | `2e2519d` | 续跑上述 42 节点窗口并记录高负载 KV 断言失败。 |
| `claude/charming-thompson-fb1mnj` | `3e3e6fc` | Batch-1 Decode 计时反事实：检查模拟器单请求 Decode 的两倍计时规则对结论的影响。 |
| `codex/v3-phase-link-mechanism` | `fb5e07e` | 慢链路 Prompt/Decode 干扰、带宽/分块干预，以及 V3 各模块和候选改进的证据索引。 |
| `codex/cluster42-complete` | `dab408f` | 完成原协议全部 24 窗口：12 成功、12 失败、0 缺失；结果见本目录 RESULTS_CN.md。 |
| `codex/cluster42-kv-admission` | 本分支 | 用户新增目标：同高负载用更少 GPU 达到 Helix 全池吞吐和延迟。增加 KV 准入和并发容量约束布局，独立保留原协议和失败记录。 |

本分支的第一轮 22 节点候选在 180 秒有优势，但三个 1800 秒窗口均因准入排队而未达标，详见 `kv_candidate/RESULTS_CN.md`。后续容量约束实验在 `kv_capacity/`，只有同种子、同请求轨迹、相同窗口的三项指标全部通过，才支持新的少卡结论。

数量口径：42 为模拟计算节点数，含双卡和四卡节点，按机器类型折算为 64 张物理 GPU。代码历史字段 `active_gpus` 实际计数的是活跃计算节点；新增报告同时给出物理 GPU 数。

最新一轮已完成三个筛选窗口和三个 1800 秒正式窗口。按实际执行层预约 KV 的候选使用 31 节点/53 张物理 GPU；三个种子吞吐和 TPOT 均改善，两个种子三项全部通过，种子 0 的 TTFT P95 增加约 24 毫秒，因此严格目标尚未全部达成。完整结果及限制见 `kv_slice/SUMMARY_CN.md`，原始记录与配对核对保存在 `kv_slice/runs/formal/` 和 `kv_slice/analysis.json`。
