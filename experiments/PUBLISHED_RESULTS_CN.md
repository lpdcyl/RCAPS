# RCAPS 已发布实验结果入口

本入口围绕完整 RCAPS 的已核验正式证据组织。成功运行与性能改善分别判断；负结果、未完成请求、原生失败和启动工程失败均按各批次记录保留。原始结果与冻结协议不因发布而重写。

## 当前论文的三批证据

| 批次 | 状态 | 主要用途 | 入口 |
| --- | --- | --- | --- |
| 正式论文实验 | 120 个成功独立窗口，122 次尝试；保留 2 次原生失败及授权重试记录 | 完整 RCAPS 外部比较、完整系统消融、时空四格、参数与资源池结果 | [正式报告](v4_paper/FINAL_RESULTS_CN.md)、[逐条件数据](v4_paper/individual.csv)、[执行审计](v4_paper/EXECUTION_AUDIT_CN.md) |
| 必要扩展验证 | 75 个登记窗口，63 成功、12 失败、0 缺失 | 固定工作量尾部、环境条件、外部高负载与邻近选路机制 | [验证报告](v4_validation/RESULTS_CN.md)、[机器可读汇总](v4_validation/validation_results.json) |
| 主线核心补证 | 15 个登记窗口，14 成功、1 失败、0 缺失；复用 9 个参照 | 6 个会话项独立消融；9 个分块边界假设成本条件 | [核心报告](v4_core_validation/RESULTS_CN.md)、[逐种子汇总](v4_core_validation/results.json)、[CSV](v4_core_validation/individual.csv) |

上述批次使用不同协议，不能直接相加为同一种工作负载下的样本量。完整三种子配对与不完整组的解释见对应报告。

## 本次新增发布范围

- `v4_core_validation/`：冻结协议、源代码、执行索引、14 个成功结果、1 个正式失败、所有相应日志、早期 15 次仿真前派发失败及工程修正记录。
- 原始综合核验 `reconciliation_v1.json` 与后续确定性报告扩充记录同时保留。本次不重跑仿真，不重新生成科学结果。
- [论文证据状态](../paper/RCAPS_V4_EVIDENCE_STATUS_CN.md)、[写作蓝图](../paper/RCAPS_WRITING_BLUEPRINT_CN.md)、[方法正文](../paper/RCAPS_THEORY_CN.md)与[中文汇报 Word](../paper/RCAPS_研究主线与实验进展汇报.docx)。汇报的[可编辑正文源文件](../ccfa-workfiles/writing/rcaps-storyline/source/RCAPS_REPORT_CN.md)一并保留。
- `v4_paper/` 和 `v4_validation/` 已在此前提交中发布，本次沿用其原始记录。

核心补证中的会话项窗口全部成功；成本窗口为8/9成功。100 ms、seed 1 的原生失败保留在实际执行目录中。目录根部 `index.json` 与 `runs/` 是更早的派发失败，实际仿真队列为 `execution/index.json`，两者不能混算。

## 发布完整性与边界

[发布字节核对](v4_core_validation/publication_byte_audit.json)检查已登记源文件、参照、成功与失败记录及 Git 暂存字节的一致性。复核命令为：

```powershell
python -m experiments.v4_core_validation.publication_audit
```

该命令只读取已有证据，不运行仿真或改写结果。需要重新保存发布核对记录时显式添加 `--write`。

本次上传限定为当前 RCAPS 主线的正式证据及其说明材料。未纳入当前完整方法的本地探索候选、待实现设计、无独立终态汇总的开发目录，以及环境缓存、检查点和本地渲染中间件，不纳入这次发布。

高负载 Swarm/SP 仍缺完整配对组，Parallax-inspired 仍为选路机制对照，分块成本仍为仿真假设。真实硬件校准和最大可持续容量结论均未完成。
