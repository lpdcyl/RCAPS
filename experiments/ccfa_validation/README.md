# CCFA 补充实验

这里集中存放统一协议负载扫描、三集群网络敏感性、调度/放置开销，以及双方使用相同准入规则的离线对照。已有三种子官方负载结果保留在 `../multiseed/`，作为负载和 RTT 曲线的中间档，不复制原始 JSON。

## 协议

- 在线：LLaMA-70B、24 GPU、种子 0/1/2、Gurobi 13；1800 s 固定窗口、无预热。同场景/负载/种子，Helix 与本方法的请求轨迹哈希必须一致。
- 负载：官方 offered load 的 0.7、1.0、1.1 倍。单集群为 490/700/770 token/s；三集群为 224/320/352 token/s。先前 1.3 倍试验在三集群 Helix 中发生不可路由失败，其原始日志保留在 `runs/load/high/`，不作为完整 1800 s 比较点。
- 网络：三集群官方 offered load 320 token/s；仅缩放跨物理分区链路 RTT 为 0.5、1.0、2.0 倍。本方法按每档拓扑重新生成放置；Helix 使用官方层放置，在修改后的物理拓扑和执行链路上运行。其余网络和 GPU 配置保持原值。
- 开销：官方负载种子 0 的两场景成对运行，在完整窗口对调度入口计进程内耗时。另用 `planner_overhead.py` 测完整本方法放置生成时间。Helix 的官方 ILP 不重求解，故不计算放置加速比。
- 离线：初始 20 请求，双方使用相同的逐层 KV 容量利用率准入规则与 0.8 阈值；预热 60 s、测量 600 s、种子 0/1/2。它与 `../baseline_audit/` 中双方各用原生准入策略的结果分开报告。

## 运行与复核

在仓库根目录，使用 Gurobi 13 的环境：

```powershell
.venv_multiseed\Scripts\python.exe -m experiments.ccfa_validation.run --dry-run --python .venv_multiseed\Scripts\python.exe
.venv_multiseed\Scripts\python.exe -u -m experiments.ccfa_validation.run --workers 4 --python .venv_multiseed\Scripts\python.exe
.venv_multiseed\Scripts\python.exe -u -m experiments.ccfa_validation.run_common_offline --workers 2 --python .venv_multiseed\Scripts\python.exe
.venv_multiseed\Scripts\python.exe -m experiments.ccfa_validation.mechanism_audit
.venv_multiseed\Scripts\python.exe -m experiments.ccfa_validation.planner_overhead
.venv_multiseed\Scripts\python.exe -m experiments.ccfa_validation.aggregate
```

运行器对已完成且协议字段匹配的 JSON 跳过执行；原始 JSON 和同名 `.log` 位于 `runs/`。`aggregate.py` 要求全部结果存在，校验运行环境、成对轨迹、窗口与网络配置，然后生成 `summary.json` 和 `RESULTS.md`。短窗口冒烟检查只检验代码路径，不纳入统计。

正式在线补充批次为 40/40 次完成；共同准入离线批次为 12/12 次完成。`runs/load/high/` 另保留 1.3 倍负载的探索性应力试验（9 次完成、3 次 Helix 不可路由），不属于正式三档负载曲线。
