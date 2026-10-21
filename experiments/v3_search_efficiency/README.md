# V3–Helix ILP 离线规划效率

验证轴：`optimization`；证据类型 `complexity`、`reproducibility`；主要风险 `unfair-comparison`；阶段 `result-writing`。

**研究问题**：在相同 C1 GPU 资源和同一运行主机上，冻结 V3 M2 与原 Helix ILP 生成合法 LLaMA-70B 部署各需要多少时间？这是规划实现的效率对照；两者优化目标和搜索空间不同，不据此声称某方法求得全局更优布局。

| 控制项 | 协议 |
| --- | --- |
| 拓扑 | C1 单集群、C1 三集群，物理文件与各自 V3 输入 SHA256 一致 |
| V3 | 冻结 `multi_any`，Beam 64，每阶段静态评分上限 500，使用冻结初始状态和参考布局 |
| Helix 原策略 | 原 `step2_gen_layout.py` 中的 LLaMA-70B ILP 入口、原 Gurobi 停机策略、原启发式初始布局 |
| Helix 预算检查 | 相同原始入口、模型与初始布局，额外给 Gurobi 120 秒和三集群 300 秒求解上限；单独标注可用与不可用 incumbent |
| 计时 | 单进程串行、每次新 Python 进程；记录完整规划到部署导出的时间与核心搜索/求解时间 |
| 复核 | 限时预算三次重复，原策略各拓扑一次 900 秒观察；记录 Gurobi 状态、gap、模型规模、V3 实际评分次数；检查导出布局的连续层段、容量、物理链路和完整路径 |

`runs/` 保存每次的原始 stdout、stderr、部署文件和 JSON 指标。Helix 原 `max_run_time=36000` 秒不改；`run.py` 的默认外部 900 秒仅是实验任务的超时保护，触发时标为 **timeout**，不填充完整规划时间。预算检查使用单独的 `helix_ilp_budgeted` 标签；有早期 incumbent 不代表原策略已经完成。

从仓库根目录运行：

```powershell
python -m experiments.v3_search_efficiency.run --cases C1_single C1_multi --helix-mode budgeted --solver-budget-s 120 --repeats 3 --timeout-s 300
python -m experiments.v3_search_efficiency.run --cases C1_multi --helix-mode budgeted --solver-budget-s 300 --repeats 3 --timeout-s 600
python -m experiments.v3_search_efficiency.run --helix-mode original --repeats 1 --timeout-s 900
python -m experiments.v3_search_efficiency.smoke
python -m experiments.v3_search_efficiency.report
```

`environment.json` 记录主机、Python、Gurobi 和源码哈希；`index.json` 记录逐次运行；`smoke_index.json` 只核对在线初始化和路径执行，不作为正式性能比较。`RESULTS_CN.md` 与 `analysis.json` 给出规划结果。
