# RCAPS 实验导航

本仓库保留论文统计所需 JSON、汇总表和图件；大型检查点及运行日志未上传，可用下述命令重跑生成。

从这里读代码即可。当前论文方法有三步：**解释资源瓶颈 → 生成模型放置 → 在线选择请求路径**。运行使用原仓库的 `simulator/`、`examples/` 和 `artifact_evaluation/` 配置。

| 目录 | 当前角色 | 先读哪个文件 |
| --- | --- | --- |
| `critical_graph/` | 挑战一：资源事件 DAG；挑战二：拓扑与容量约束放置 | `event_graph.py` → `path_ensemble.py` → `topology.py` → `partition.py` |
| `queue_dag/` | 挑战三：队列感知分层 DAG 路由与解码传输合并 | `routing_dag.py` → `scheduler_queue_cost.py` → `scheduler_final.py` → `evaluate.py` |
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
- 最终单集群和三集群放置：`critical_graph/runs/single_final/`、`critical_graph/runs/multi_final/`，每处保留 `placement.json`、`solution.ini` 和 `simulator_cluster.ini`。
- 官方负载、1800 秒端到端对照：`queue_dag/runs/paperload_{single,multi}_{helix,integrated}_seed0_1800.json`；同名 `.log` 是运行日志，`paperload_*_comparison_seed0_1800.json` 是成对核对报告。
- 开发负载及归因：`critical_graph/runs/*final*seed1_1800.json` 和 `queue_dag/runs/*seed1_1800.json`。文件名中的 `seed` 是随机种子，`1800` 是测量窗口秒数；`hash0` 表示运行时固定 `PYTHONHASHSEED=0`。
- `queue_dag/runs/` 中的 `*.pkl.gz` 是中断运行的检查点，**不是论文指标的来源**。它们暂未删除。

## 两个主入口

在仓库根目录运行：

```powershell
python -m experiments.critical_graph.partition --scenario single --output-dir experiments/critical_graph/runs/single_final
python -m experiments.critical_graph.partition --scenario multi --output-dir experiments/critical_graph/runs/multi_final
```

`partition.py` 生成布局。`queue_dag/evaluate.py` 用 `--policy final` 运行最终调度器；历史结果的同一实现记录名是 `coalesced_corrected`，旧命令仍可执行。完整的负载参数和成对比较命令见 [`RESULTS.md`](RESULTS.md)。`queue_dag/experimental/` 保留早期策略供归因复验，正常阅读与运行无需进入该目录。

不要把 `graph_pipeline/` 当作当前最终放置。它保留是因为 `critical_graph/fixed_window.py`、`queue_dag/routing_dag.py` 及部分放置对照仍依赖其基础代码或基线结果。

