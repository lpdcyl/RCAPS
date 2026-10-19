# V3–Helix ILP 负载边界

本目录独立于冻结 V3。`offered_tokens_per_s` 是输入与目标输出 token 的总到达强度；`output_throughput_tokens_per_s` 只统计窗口内实际产生的输出 token。因此两者不能直接相除作为完成率。完成率使用请求数计算。

## 固定协议

| 拓扑 | 预设负载（offered token/s） |
| --- | --- |
| C1 单集群 | 100、200、350、500、700、900 |
| C1 三集群 | 50、100、160、240、320、400 |

各点比较冻结 V3 与 Helix ILP，种子为 0、1、2。每窗 1800 秒，零预热，到窗口末停止且不排空。同拓扑、负载、种子的两方法使用相同到达轨迹。

## 复现

从仓库根目录运行：

```powershell
python -m experiments.v3_load_boundary.run audit
python -m experiments.v3_load_boundary.audit_history
python -m experiments.v3_load_boundary.run run --workers 12
python -m experiments.v3_load_boundary.run report
```

`audit.json` 固定代码、部署与物理配置哈希；`historical_audit.json` 逐项说明旧窗口复用判定；`index.json` 记录逐窗口来源和哈希；`runs/` 保存完整请求样本及日志。`analysis.json` 保留逐种子的输入到达率、目标输出到达率、尾延迟、完成率、积压、未完成请求等待分布，以及共同完成请求的配对尾延迟。`RESULTS_CN.md`、`load_curve.png`、`completion_backlog.png` 是汇总表和曲线。旧窗口只有全部身份字段及 V3 发布清单哈希通过时才复用；未通过则原样保留旧结果并在本目录重跑。

只能根据测试点描述吞吐与延迟转折所在区间，不从离散测试点外推精确容量。三个种子用于描述波动，不用于统计显著性声明。
