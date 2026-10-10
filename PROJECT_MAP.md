# 项目文件导航与清理清单

当前代码与结果的阅读顺序见 [`experiments/README.md`](experiments/README.md)。以下是经代码引用核对的**删除候选清单**；本次只列清单，没有删除文件。

## 当前论文主线（保留）

| 位置 | 用途 |
| --- | --- |
| `simulator/`、`examples/`、`artifact_evaluation/` | Helix 仿真器、配置、官方评测脚本及原始布局；复现对照依赖它们。 |
| `experiments/critical_graph/` | 资源事件 DAG、路径分析、容量约束放置、归因和审计。`runs/single_final/` 与 `runs/multi_final/` 是最终布局。 |
| `experiments/queue_dag/` | 分层 DAG 调度、批量传输和成对比较。`runs/paperload_*` 是官方负载的 1800 秒结果及日志。 |
| `experiments/multiseed/`、`experiments/ccfa_validation/`、`experiments/baseline_audit/` | 三种子正式结果、补充负载/RTT/开销/共同准入实验及其原始日志；论文结论依赖这些记录。 |
| `experiments/graph_pipeline/` | 早期分层 DAG 基础实现。当前 `critical_graph/fixed_window.py` 和 `queue_dag/routing_dag.py` 仍引用其中的 `evaluate.py`、`scheduler.py`、`model.py`，不能整目录删除。`runs/long/{single,multi}_helix_seed1_1800.json` 也是放置归因的基线输入。 |
| `experiments/RESULTS.md` | 指标、实验口径、结果来源与限制。 |
| `experiments/METHOD_FRAMEWORK.md` | 三项方法的统一框架。 |
| `experiments/paper_figures/` | 论文图的生成代码、PDF、PNG、SVG 及图源说明；主图为 `ccf_integrated_framework.*`。 |

## A. 可直接删除

这些对象不被当前代码、正式结果比较或论文图读取。虚拟环境删除后需重新安装依赖；检查点删除后不能从中断点继续。

| 对象 | 目前大小 | 原因 |
| --- | ---: | --- |
| `.venv_queue_dag/`、`.venv-helix312/` | 556.04 MiB | 本机安装副本，不是源码或实验记录。 |
| `experiments/queue_dag/runs/*.pkl.gz`、`*.pkl.gz.tmp`（共 5 个） | 1058.86 MiB | 中断运行检查点；论文数据取自 JSON，原始运行日志为 `.log`。 |
| 虚拟环境以外的所有 `__pycache__/`、`*.pyc` | 1.62 MiB | Python 自动生成的缓存。 |
| `experiments/queue_dag_single_pilot.log` | 0 | 空文件。 |
| `experiments/paper_figures/ccf_method_framework.py/.pdf/.png/.svg` | 约 0.24 MiB | 已由 `ccf_integrated_framework.*` 替代，正文、图索引和出图入口均不引用。 |

表中的大小来自原清单编制时的快照；补充实验新增结果后，工作区总大小需重新测量。

5 个检查点的确切名称是：

- `single_helix_fresh_compact_seed1_1800.pkl.gz`
- `single_helix_gllm_seed1_1800.pkl.gz`
- `single_helix_hash0_seed1_1800_checkpoint.pkl.gz`
- `single_queue_dag_gllm_seed1_1800.pkl.gz`
- `single_queue_dag_gllm_seed1_1800.pkl.gz.tmp`

## B. 同步改引用后再删

| 对象 | 需要一起修改的地方 |
| --- | --- |
| `experiments/paper_figures/fig00_method_overview.py/.pdf/.png` | 这是旧的分离式方法图。删去 `FIGURE_GUIDE.md` 对它的条目，并同步调整 `verify_figures.py` 的图数；`build_all.py` 会自动跳过已不存在的 `fig00` 脚本。 |
| `experiments/archive/slo_placement/` 与 `experiments/graph_pipeline/compare.py` | 早期 SLO 放置分支与唯一读取其结果的旧比较脚本；一起删除，并更新 `archive/README.md`、`graph_pipeline/README.md` 和导航。当前正式结果不依赖它们。 |
| `experiments/queue_dag/experimental/`、`runs/*seed1_420*.json`、`runs/*seed1_240*.json`、`runs/*seed1_60*.json` | 17 个探索策略与 49 个短窗口开发 JSON，约 0.20 MiB；删除时收紧 `evaluate.py` 的旧策略分支，移除 `scheduler_queue_cost.py` 和 `routing_dag.py` 中仅供这些策略使用的类。**保留** `single_paper_smoke*_seed0_60.json/.log`，它们支撑 `RESULTS.md` 中 compact/noncompact 一致性的说明。 |
| `experiments/critical_graph/runs/{single_v2,single_v3,multi_v2,multi_v3,multi_ensemble}/` | 未进入最终比较的候选布局；当前 Python 脚本不读取。删后更新 `critical_graph/README.md` 与 `runs/README.md` 中的历史记录说明。 |
| `experiments/graph_pipeline/` 中的 `placement.py`、`refine.py`、`explain.py`、`compare_long.py`，以及 `runs/` 内除 `long/single_helix_seed1_1800.json` 和 `long/multi_helix_seed1_1800.json` 以外的早期结果 | 先把 `graph_pipeline/README.md` 缩成兼容模块说明。当前方法仍依赖该目录的 `model.py`、`scheduler.py`、`evaluate.py`，以及上述两个 Helix 基线 JSON；这些必须留下。 |
| `experiments/` 根目录中的 Helix 论文 PDF | 约 2.57 MiB，本地文献副本不被代码引用；若无需离线阅读，可删除。 |
| 本清单 `PROJECT_MAP.md` | 完成清理后，若 `experiments/README.md` 已覆盖最终目录结构，可删掉这份临时清单，避免两份导航长期并存。 |

## 必须保留

`simulator/`、`examples/`、`artifact_evaluation/`；`critical_graph/` 的建模、放置与最终归因输入；`queue_dag/` 的最终调度实现；`multiseed/`、`baseline_audit/runs_dynamic/`、`ccfa_validation/` 的正式结果及日志；两个 `*_final/` 布局；`RESULTS.md`、`METHOD_FRAMEWORK.md`；`ccf_integrated_framework.*` 与 `fig01` 至 `fig14` 的源码和图件。特别不要整目录删除 `graph_pipeline/` 或 `critical_graph/runs/single_ensemble/`、`multi_coarse/`、`single_sharedpush/`，它们仍被当前导入、归因或审计读取。
