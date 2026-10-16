# M1 纯图建模候选：复现说明

> 2026-10-16 更新：纯图 M1 已纳入 RCAPS V3，冻结接口与结果来源见 [V3 冻结记录](../v3_release/README_CN.md)。本目录保留原始独立候选证据。

此候选将 M1 限定为异构资源图和布局导出的层兼容 DAG。M1 没有请求到达、排队、事件 DAG 或布局评分。M2 使用第一阶段验证过的强静态代价，保留原搜索空间、初始化、邻域、16 轮上限、评分参考及目标权重。M3 的路径代价、Decode 固定路径和传输合并语义不变；候选调度器只通过 M1 图接口检查已部署的合法边。

从仓库根目录依次运行：

```powershell
python -m experiments.m1_graph_candidate.prepare
python -m unittest experiments.m1_graph_candidate.test_graph experiments.m1_simplification.test_static_resource -v
python -m experiments.m1_graph_candidate.route_parity
python -m experiments.m1_graph_candidate.stress_route_parity
python -m experiments.m1_graph_candidate.run --dry-run
python -m experiments.m1_graph_candidate.run
python -m experiments.m1_graph_candidate.path_analysis
python -m experiments.m1_graph_candidate.report
```

`prepare` 将部署文件写入本目录 `layouts/`，核对新旧静态候选评分、参考值、布局及部署文件 SHA256，并执行层覆盖、显存、KV 和链路审计。`route_parity` 在固定请求轨迹上逐请求比对原 M3 与图接口候选的路由，检查运行时 DAG 与部署边集。`stress_route_parity` 在正式 offered load 下用开发种子 100／101 做 300 秒行为回归，不纳入正式性能表。`run` 仅处理正式种子 0／1／2、1800 秒、单集群 700／三集群 320 offered token/s；只有布局与调度语义一致且旧窗口通过轨迹、协议及请求身份审计时才复用。否则只在本目录 `runs/` 运行受影响窗口并保留日志。`path_analysis` 对复用的每条正式执行路径逐边、逐层验证，并统计规范后缀外的实际路径和跨后缀使用。

`layout_audit.json`、`route_parity.json`、`stress_route_parity.json`、`run_index.json`、`path_analysis.json`、`summary.json` 提供机器可读证据、逐种子原始路径和 SHA256。[结果报告](RESULTS_CN.md)解释结构、执行路径和在线指标。现有种子 0／1／2 的六对正式窗口全部通过复用审计，未重新运行正式仿真。冻结 V2 只作为改造前后的迁移参考，不是论文性能基线；M1 用图合法性与接口一致性验收，M2、M3 的收益需分别由受控对照验证。三个种子不支持显著性或等效性结论。
