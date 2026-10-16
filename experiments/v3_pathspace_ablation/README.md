# V3 路径空间核心消融

IEEE 证据检查轴：`hardware-system / ablation / weak-ablation / planning`。
本轮只补一项机制实验：

| 主张 | 已有证据 | 本轮补足的证据 | 判定范围 |
| --- | --- | --- | --- |
| M1 定义合法执行关系 | 部署图逐边核验 | 规范路径为完整合法图的子图 | 图正确性，不主张性能增益 |
| M2 选择共享复制结构 | 同预算单边界与多级四格对照 | 固定 V3 布局 | 不再改变放置 |
| M3 可利用层兼容路径 | 静态与实时 M3 四格对照 | 同一实时评分下规范路径与完整 DAG 配对 | 若在线指标改善，才归因于路径空间 |

固定 V3 `multi_any` 部署与实时 M3，仅限制 Prompt 可选边，比较规范层段路径和完整层兼容 DAG。Decode 路径、KV 状态计价、实时 GPU/链路等待及传输合并相同。C1 单集群和三集群均使用原负载、种子 0/1/2、1800 秒零预热不排空窗口；V3 正式结果经哈希核验后复用。

在仓库根目录运行：

```powershell
python -m experiments.v3_pathspace_ablation.run --phase audit
python -m experiments.v3_pathspace_ablation.run --phase smoke --workers 2
python -m experiments.v3_pathspace_ablation.run --phase formal --workers 2
python -m experiments.v3_pathspace_ablation.report
```

`audit.json` 保存允许的边、理论路径数与冻结输入哈希；`formal_index.json` 保存各原始窗口路径和 SHA256；`formal_analysis.json` 与 `formal_report.md` 提供逐种子配对指标、共同完成请求尾延迟及未完成请求驻留时长。若规范路径容量不足，保留失败记录，不补造指标。

本次 6 个正式窗口全部完成。完整结果与结论见 [`formal_report.md`](formal_report.md)：单集群限制为规范路径的指标更好；三集群开放完整 DAG 的指标更好。两种拓扑呈相反方向，因此不把更多合法路径写成普遍性能收益。
