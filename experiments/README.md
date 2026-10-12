# RCAPS 实验导航

本仓库保留论文统计所需 JSON、汇总表和图件；大型检查点及运行日志未上传，可用下述命令重跑生成。

当前默认主方法是 `rcaps_v2`，实现位于仓库顶层 [`rcaps/`](../rcaps/)；Helix 基线适配器位于 [`baselines/`](../baselines/)，统一运行和比较入口位于 [`benchmarks/`](../benchmarks/)。V1 双后缀方法以历史名称 `rcaps` 保留为显式对照。本目录保存 V2 结果、历史实验、论文数据和旧命令兼容入口。

| 目录 | 当前角色 | 先读哪个文件 |
| --- | --- | --- |
| `adaptive_v2/` | 当前 V2 自适应共享复制结构及三种子配对证据 | `README.md` → `RESULTS.md` → `summary.json` |
| `critical_graph/` | V1 放置实验与双后缀布局的历史记录 | `runs/single_final/`、`runs/multi_final/` |
| `queue_dag/` | V1 调度实验的历史结果与兼容入口；在线调度实现位于 `rcaps/scheduling/` | `evaluate.py`、`runs/` |
| `multiseed/` | 种子 0、1、2 的 78 项正式复验、逐种子日志与统计 | `RESULTS.md` → `summary.json` → `run.py` |
| `baseline_audit/` | 官方离线基线复现与三种子离线对照 | `RESULTS_OFFLINE.md` → `offline_compare.py` → `run_batch.py` |
| `ccfa_validation/` | 统一协议负载扫描、三集群 RTT 敏感性、方法开销和共同准入离线对照 | `README.md` → `run.py` / `run_common_offline.py` → `aggregate.py` |
| `validation_2026/` | 三种子搜索消融、瓶颈归因、去事件图及放置×调度交叉实验 | `RESULTS.md` → `CROSS_RESULTS.md` |
| `structure_ablation_2026/` | 单路径、双后缀与共享前缀长度的结构消融；含原负载失败和共同安全负载 | `RESULTS.md` → `README.md` → `summary.json` |
| `queue_predictor_2026/` | 在线队列感知资源预测的探索性放置实验；排序改善但未带来在线收益 | `RESULTS.md` → `summary.json` → `README.md` |
| `paper_figures/` | 论文图源码和已生成图件 | `FIGURE_GUIDE.md` |
| `graph_pipeline/` | 早期分层 DAG 实现及放置归因的对照输入；当前仿真入口仍引用其三个基础模块 | `model.py`、`scheduler.py`、`evaluate.py` |
| `archive/` | 已停用的探索分支和原始结果 | `README.md` |

## 正式结果在哪

- 论文方法与结果说明：[`METHOD_FRAMEWORK.md`](METHOD_FRAMEWORK.md)、[三种子结果](multiseed/RESULTS.md)、[官方高负载三方案归因](multiseed/PAPER_PLACEMENT.md)。旧版单种子分析保留在 [`RESULTS.md`](RESULTS.md)。
- 补充证据：[负载扫描、RTT 敏感性、共同准入离线对照与开销](ccfa_validation/RESULTS.md)；40 次正式在线补充运行及 12 次共同准入离线运行的 JSON 和日志见 `ccfa_validation/runs/`。
- 新的三种子结构证据：[单路径与双后缀及前缀长度](structure_ablation_2026/RESULTS.md)，[放置与在线调度交叉](validation_2026/CROSS_RESULTS.md)。原始 JSON、哈希核验、图和可复现脚本分别在对应目录。
- 预测代理探索：[队列感知资源预测与放置](queue_predictor_2026/RESULTS.md)。三集群排队排序改善但在线性能没有稳定提升，主 RCAPS 放置保持不变。
- 离线负载正式对照：[三种子离线结果](baseline_audit/RESULTS_OFFLINE.md)；12 次完整窗口 JSON 与日志在 `baseline_audit/runs_dynamic/seed*/`。Helix 种子 0 的 252.1/98.0 token/s 与官方 artifact 一致。
- 当前 V2 主方法的已采纳放置：[`../rcaps/v2_layouts/single_adaptive/`](../rcaps/v2_layouts/single_adaptive/)、[`../rcaps/v2_layouts/multi_adaptive/`](../rcaps/v2_layouts/multi_adaptive/)。V1 对照布局保留在 `../rcaps/layouts/`。
- 官方负载、1800 秒端到端对照：`queue_dag/runs/paperload_{single,multi}_{helix,integrated}_seed0_1800.json`；同名 `.log` 是运行日志，`paperload_*_comparison_seed0_1800.json` 是成对核对报告。
- 开发负载及归因：`critical_graph/runs/*final*seed1_1800.json` 和 `queue_dag/runs/*seed1_1800.json`。文件名中的 `seed` 是随机种子，`1800` 是测量窗口秒数；`hash0` 表示运行时固定 `PYTHONHASHSEED=0`。
- `queue_dag/runs/` 中的 `*.pkl.gz` 是中断运行的检查点，**不是论文指标的来源**；大型检查点未上传。

## 当前主入口

在仓库根目录运行：

```powershell
python -m benchmarks.run --dry-run
python -m benchmarks.run
python -m benchmarks.compare --baselines helix
python -m benchmarks.compare --baselines rcaps
```

`rcaps/placement/adaptive.py` 是 V2 放置搜索实现，已采纳布局随仓库提供；重算命令见 [`adaptive_v2/README.md`](adaptive_v2/README.md)。不带 `--methods` 的 `benchmarks.run` 运行 V2 与 Helix，`benchmarks.compare` 默认以 V2 为主方法。`rcaps` 仅在显式指定时用于 V1 双后缀对照。`queue_dag/evaluate.py` 的旧策略名仍可用于历史复验；完整的 V1 旧负载参数见 [`RESULTS.md`](RESULTS.md)。

`graph_pipeline/` 保留早期分层 DAG 对照；当前固定窗口评测实现位于 `benchmarks/fixed_window.py`。历史 JSON 中的 `green` / `integrated` 指当时的 V1 方法，键名为保证已有统计脚本可重现而保留。

