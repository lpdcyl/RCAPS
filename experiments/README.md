# RCAPS 实验导航

本仓库保留论文统计所需 JSON、汇总表和图件；大型检查点及运行日志未上传，可用下述命令重跑生成。

当前主方法代码位于仓库顶层 [`rcaps/`](../rcaps/)，Helix 基线适配器位于 [`baselines/`](../baselines/)，统一运行和比较入口位于 [`benchmarks/`](../benchmarks/)。本目录保存历史实验、论文数据、图件和旧命令兼容入口。方法有三步：**解释资源瓶颈 → 生成模型放置 → 在线选择请求路径**。

| 目录 | 当前角色 | 先读哪个文件 |
| --- | --- | --- |
| `critical_graph/` | 放置实验与最终布局的历史记录；主要实现已移至 `rcaps/placement/` | `runs/single_final/`、`runs/multi_final/` |
| `queue_dag/` | 调度实验的历史结果与兼容入口；主要实现已移至 `rcaps/scheduling/` | `evaluate.py`、`runs/` |
| `multiseed/` | 种子 0、1、2 的 78 项正式复验、逐种子日志与统计 | `RESULTS.md` → `summary.json` → `run.py` |
| `baseline_audit/` | 官方离线基线复现与三种子离线对照 | `RESULTS_OFFLINE.md` → `offline_compare.py` → `run_batch.py` |
| `ccfa_validation/` | 统一协议负载扫描、三集群 RTT 敏感性、方法开销和共同准入离线对照 | `README.md` → `run.py` / `run_common_offline.py` → `aggregate.py` |
| `paper_figures/` | 论文图源码和已生成图件 | `FIGURE_GUIDE.md` |
| `graph_pipeline/` | 早期分层 DAG 实现及放置归因的对照输入；当前仿真入口仍引用其三个基础模块 | `model.py`、`scheduler.py`、`evaluate.py` |
| `archive/` | 已停用的探索分支和原始结果 | `README.md` |

## 正式结果在哪

- 论文方法与结果说明：[`METHOD_FRAMEWORK.md`](METHOD_FRAMEWORK.md)、[三种子结果](multiseed/RESULTS.md)、[官方高负载三方案归因](multiseed/PAPER_PLACEMENT.md)。旧版单种子分析保留在 [`RESULTS.md`](RESULTS.md)。
- 补充证据：[负载扫描、RTT 敏感性、共同准入离线对照与开销](ccfa_validation/RESULTS.md)；40 次正式在线补充运行及 12 次共同准入离线运行的 JSON 和日志见 `ccfa_validation/runs/`。
- 离线负载正式对照：[三种子离线结果](baseline_audit/RESULTS_OFFLINE.md)；12 次完整窗口 JSON 与日志在 `baseline_audit/runs_dynamic/seed*/`。Helix 种子 0 的 252.1/98.0 token/s 与官方 artifact 一致。
- 当前主方法的可部署放置：[`../rcaps/layouts/single/`](../rcaps/layouts/single/)、[`../rcaps/layouts/multi/`](../rcaps/layouts/multi/)。历史实验使用的原始副本保留在 `critical_graph/runs/*_final/`。
- 官方负载、1800 秒端到端对照：`queue_dag/runs/paperload_{single,multi}_{helix,integrated}_seed0_1800.json`；同名 `.log` 是运行日志，`paperload_*_comparison_seed0_1800.json` 是成对核对报告。
- 开发负载及归因：`critical_graph/runs/*final*seed1_1800.json` 和 `queue_dag/runs/*seed1_1800.json`。文件名中的 `seed` 是随机种子，`1800` 是测量窗口秒数；`hash0` 表示运行时固定 `PYTHONHASHSEED=0`。
- `queue_dag/runs/` 中的 `*.pkl.gz` 是中断运行的检查点，**不是论文指标的来源**；大型检查点未上传。

## 当前主入口

在仓库根目录运行：

```powershell
python -m rcaps.placement.partition --scenario single --output-dir rcaps/layouts/single
python -m rcaps.placement.partition --scenario multi --output-dir rcaps/layouts/multi
python -m benchmarks.run --dry-run
python -m benchmarks.run --methods rcaps helix
python -m benchmarks.compare --baselines helix
```

`rcaps/placement/partition.py` 生成布局；`benchmarks.run` 在统一协议下运行 RCAPS 与 Helix。`queue_dag/evaluate.py` 的 `--policy final` 和旧记录名 `coalesced_corrected` 仍可用于历史复验。完整的旧负载参数见 [`RESULTS.md`](RESULTS.md)。新增 baseline 时在 `baselines/` 添加适配器并登记到 `benchmarks/registry.py`。

`graph_pipeline/` 保留早期分层 DAG 对照；当前固定窗口评测实现位于 `benchmarks/fixed_window.py`。历史 JSON 中的 `green` / `integrated` 指当前 RCAPS 方法，键名为保证已有统计脚本可重现而保留。

