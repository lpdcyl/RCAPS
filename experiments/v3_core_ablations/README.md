# V3 核心递进消融（C1）

本目录只比较 C1 单集群与三集群的放置 × 调度四格，不修改已冻结的 V3 布局。

| 格 | 冻结布局 | 调度 |
| --- | --- | --- |
| A | `single_any` | V3 层兼容 DAG，静态资源代价 |
| B | `multi_any` | V3 层兼容 DAG，静态资源代价 |
| C | `single_any` | V3 实时 M3 |
| D | `multi_any` | V3 实时 M3 |

静态调度器只把 GPU/链路排队等待及活跃 KV 会话价格置零。M1 边检查、基础计算/通信代价、平局顺序、Decode 固定路径和传输合并继承 V3。`multi_any` 在 C1 三集群实际仍是单边界，因此该拓扑的 B−A 反映微观放置差异。

## 复现

在仓库根目录运行：

```powershell
python -m experiments.v3_core_ablations.run --phase audit
python -m experiments.v3_core_ablations.run --phase smoke --workers 4
python -m experiments.v3_core_ablations.run --phase formal --workers 4
python -m experiments.v3_core_ablations.report --phase formal
```

`formal` 新跑 A/B 的种子 0/1/2、1800 秒窗口。C/D 在哈希、布局、协议及 C 的短窗口行为检查通过时复用已存在的逐种子记录。若高负载静态格因 KV 容量或无法路由失败，保留其失败日志后，对全部四格运行预先固定的共同低负载：

```powershell
python -m experiments.v3_core_ablations.run --phase low --workers 4
python -m experiments.v3_core_ablations.report --phase low
```

单集群高/低负载为 700/350 offered token/s，三集群为 320/160；均零预热、窗口末不排空。原始窗口在 `runs/`，各索引记录 SHA256；`audit.json` 保存物理与布局哈希、结构和搜索开销。`formal_analysis.json` 和 `formal_report.md` 给出逐种子指标、配对差值、共同完成请求及未完成请求驻留时长。三个种子只作波动描述，不作显著性推断。

## 论文双栏表格

运行 `python -m experiments.v3_core_ablations.make_paper_table`，从审计后的
`formal_analysis.json` 生成 `v3_ablation_table.tex`。在双栏 LaTeX 论文导言区加入
`\usepackage{booktabs}`，正文使用
`\input{experiments/v3_core_ablations/v3_ablation_table.tex}`。表格使用 `table*`
跨双栏，单集群与三集群并列；`v3_ablation_preview.tex` 是独立编译预览文件。
