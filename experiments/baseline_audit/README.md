# 离线实验目录

正式结果从 [RESULTS_OFFLINE.md](RESULTS_OFFLINE.md) 开始阅读。

| 文件或目录 | 用途 |
| --- | --- |
| `offline_compare.py` | 单次运行：Helix 官方动态准入或新方法的分层 KV 动态准入 |
| `run_batch.py` | 运行单集群/三集群、种子 0/1/2，共 12 项完整窗口实验 |
| `aggregate_offline.py` | 校验 12 项输出并生成结果文档和汇总 JSON |
| `runs_dynamic/seed*/` | 正式实验的逐种子 JSON 与日志 |
| `single_offline_helix_gurobi13.log`、`multi_offline_helix_gurobi13.log` | 直接运行官方脚本的独立复现日志 |

`runs/`、`sweep/`、`smoke_dynamic/` 和 `smoke_multi_*.json` 是早期固定并发或短窗口诊断，不参与任何正式统计。

在仓库根目录复现正式实验：

```powershell
.venv_multiseed\Scripts\python.exe -m experiments.baseline_audit.run_batch --seeds 0 1 2 --workers 4 --python .venv_multiseed\Scripts\python.exe
.venv_multiseed\Scripts\python.exe -m experiments.baseline_audit.aggregate_offline
```
