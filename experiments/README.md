# RCAPS 实验导航

本仓库保留论文统计所需 JSON、汇总表和图件；大型检查点及运行日志未上传，可用下述命令重跑生成。

当前默认主方法是 `rcaps_v3`，实现位于 [`rcaps/v3/`](../rcaps/v3/) 与 [`rcaps/v3_method.py`](../rcaps/v3_method.py)；V3 冻结记录见 [`v3_release/`](v3_release/)。Helix 基线适配器位于 [`baselines/`](../baselines/)，统一运行和比较入口位于 [`benchmarks/`](../benchmarks/)。V2 保留为 `rcaps_v2` 显式对照，V1 以历史名称 `rcaps` 保留。

| 目录 | 当前角色 | 先读哪个文件 |
| --- | --- | --- |
| `v3_release/` | 当前 V3 主方法的冻结清单、结果复用审计及 Helix 对照 | `README_CN.md` → `manifest.json` → `v3_vs_helix.json` |
| `v3_core_ablations/` | V3 在 C1 两种拓扑下的放置 × 调度递进消融与论文双栏表格 | `README.md` → `formal_report.md` → `v3_ablation_table.tex` |
| `m1_graph_candidate/` | V3 纯图 M1 的合法性、行为一致性与静态候选证据 | `README_CN.md` → `RESULTS_CN.md` |
| `m1_simplification/` | 纯图 M1 之前的强静态评价器来源与对照记录 | `README_CN.md` → `RESULTS_CN.md` |
| `m2_multistage_candidate/` | V3 多级 M2 来源实验与四格受控对照 | `RESULTS_CN.md` → `summary.json` |
| `adaptive_v2/` | 历史 V2 自适应共享复制结构及三种子配对证据 | `README.md` → `RESULTS.md` → `summary.json` |
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
- 当前 V3 主方法的已采纳放置：[`../rcaps/v3_layouts/single/`](../rcaps/v3_layouts/single/)、[`../rcaps/v3_layouts/multi/`](../rcaps/v3_layouts/multi/)。V2 和 V1 对照布局分别保留在 `../rcaps/v2_layouts/` 与 `../rcaps/layouts/`。
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

`rcaps/v3/search.py` 是 V3 多级 M2 的冻结搜索实现，布局和来源哈希见 [`v3_release/manifest.json`](v3_release/manifest.json)。不带 `--methods` 的 `benchmarks.run` 运行 V3 与 Helix，`benchmarks.compare` 默认以 V3 为主方法。V2 放置搜索仍在 `rcaps/placement/adaptive.py`，可显式指定 `rcaps_v2` 复验；`rcaps` 是 V1 对照。`queue_dag/evaluate.py` 的旧策略名仍可用于历史复验。

`graph_pipeline/` 保留早期分层 DAG 对照；当前固定窗口评测实现位于 `benchmarks/fixed_window.py`。历史 JSON 中的 `green` / `integrated` 指当时的 V1 方法，键名为保证已有统计脚本可重现而保留。

