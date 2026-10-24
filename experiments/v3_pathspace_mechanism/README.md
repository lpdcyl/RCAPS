# T2 步骤 A：完整 DAG 退化诊断

本目录只读冻结 V3 与既有实验，实现被动诊断探针。规范路径直接导入 `experiments.v3_pathspace_ablation.run.CanonicalGraphDagScheduler` 和 `canonical_edges`；完整 DAG 使用冻结的 `GraphModeledQueueAwareDagScheduler`。探针不改事件、调度器或部署。

## 协议

- C1 单集群：700 offered token/s；C1 三集群：320 offered token/s。
- 规范路径与完整 DAG；正式种子 0、1、2；1800 秒、零预热、末端不排空。
- 先对同一 60 秒开发窗口连续运行两次，检查主要指标、轨迹、路径及探针统计逐项一致。
- 正式运行每个窗口结束即与既有正式结果逐项对照：吞吐、P95 TTFT、P95 TPOT、完成率、末端积压和 `route_counts`。任一差异立即停止，不生成分析。
- H1–H4 的统计量、方向、5% 阈值与三种子同向要求固定在已先行提交的 `protocol.json`。

`probe.py` 在事件执行前读取下一个事件时间，并每 10 秒记录 KV 会话数；只读 GPU 的 KV 字典，没有新增模拟事件。Decode 批大小按该批 Decode token 数加权。链路干扰统计直接复用 `PhaseLinkProbe` 的基线实现。`ResourceProfile` 给出 GPU 忙碌比例。

H4 的分子由旧探针中发生等待的 Decode 消息样本算出：`decode_same_prompt_blocked_fraction × decode_same_prompt_samples`；分母为所有计算节点间链路的 `decode_messages`，包含没有等待的消息。旧探针的 `decode_same_prompt_samples` 不是全部 Decode 消息数。

## 复现命令

在 PowerShell 会话中先设置：

```powershell
$env:PYTHONHASHSEED = '0'
$env:MPLBACKEND = 'Agg'
python -m experiments.v3_pathspace_mechanism.run --phase smoke --case C1_single --variant full
python -m experiments.v3_pathspace_mechanism.run --phase formal --workers 1
python -m experiments.v3_pathspace_mechanism.run --phase report
```

正式运行串行执行以便发现任一复现偏差或解释器级异常后立即停止。`--workers` 为兼容统一命令接口而保留，T2 不并行窗口；T1 可在独立进程中同时进行。

`runs/formal/` 保留原始 JSON、完整日志与失败记录。每个新窗口 JSON 明确记录 `pythonhashseed` 与 `mplbackend`。`index.json` 保存逐窗口路径、SHA256、轨迹哈希和状态。只有 12 个窗口全部通过复现检查时才生成 `analysis.json` 和 `RESULTS_CN.md`；报告包含全局指标逐种子值、三种子均值 ± 样本标准差、配对差值和共同完成请求上的 P95。

首次 60 秒抽查曾在探针后处理解析 GPU 标签时失败（实际标签为 `Compute-10`）。失败 JSON 保存于 `runs/smoke/failures/`；修正解析后使用新编号的两次运行做确定性抽查。

首次正式启动后，发现 H4 分母需要上述修正，在首个窗口生成结果前停止。中断日志保存于 `runs/formal/interrupted/`，`index.json` 标记该尝试未纳入正式数据；修正后的两次 60 秒抽查使用更新编号。

随后在正式首窗口结果生成前发现新窗口身份缺少 `PYTHONHASHSEED` 字段，再次保留中断日志并补齐元数据；有效抽查使用新的 attempt 7、8。
