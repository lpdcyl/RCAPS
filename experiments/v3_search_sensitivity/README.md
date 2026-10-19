# V3 M2 搜索参数敏感性

本实验独立于冻结的 V3。只改变 `multi_any` 搜索中的 GPU 分组 Beam 宽度和每阶段静态评分预算，保持布局空间、种子布局、参考布局、M2 静态目标及 M3 不变。

| 扫描 | Beam | 每阶段评分预算 |
| --- | --- | --- |
| 默认 | 64 | 500 |
| Beam 单因素 | 32、128 | 500 |
| 预算单因素 | 64 | 250、1000 |
| 高资源检查 | 128 | 1000 |

每个设置在独立 Python 进程中运行，避免参数覆盖跨设置泄漏。默认设置必须复现 V3 发布版分数与两个部署文件哈希。`planning_index.json` 记录搜索结果；其中规划耗时覆盖共享搜索和单边界、多级两个扩展分支，不能解释为单独的 `multi_any` 耗时。`audit.json` 记录正式运行的输入与部署哈希。相同 `solution.ini` 与 `simulator_cluster.ini` 哈希的设置共用在线窗口。

正式窗口：C1 单集群 350／700、三集群 160／320 offered token/s；种子 0／1／2；1800 秒；零预热；窗口末不排空。每个不同布局先经过种子 100 的 60 秒运行与合法路径检查。通过严格身份审计的发布版窗口从 `v3_load_boundary` 复用，其余布局重新运行。

从仓库根目录运行：

```powershell
python -m experiments.v3_search_sensitivity.plan sweep
python -m experiments.v3_search_sensitivity.run smoke --workers 4
python -m experiments.v3_search_sensitivity.run formal --workers 4
python -m experiments.v3_search_sensitivity.report
```

`FINDINGS_CN.md` 给出解释边界，`RESULTS_CN.md` 为离线与在线结果表，`analysis.json` 包含逐种子来源和配对差值，`paired_seed_deltas.csv` 可用于论文绘图，`offline_sensitivity.png` 与 `online_sensitivity.png` 展示参数敏感性。最低静态分数仅是本次扫描中的已测最好结果，不能解释为全局最优值。三个种子只用于描述波动。
