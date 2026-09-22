# Helix_waterwise / carbon-helix-sim 窗口交接文档

## 1. 当前状态

项目已经完成 **Final Validation & Reality-Gap Closure**，当前工作已经停止，
没有进入 Phase 1，也没有继续增加新算法。

- 项目目录：`D:\PythonProject\Helix_waterwise\carbon-helix-sim`
- 当前分支：`final-validation`
- 工作区：clean
- 起始 commit：`858541a`
- 起始 tag：`prototype-before-final-validation`
- Final Validation implementation/results commit：`7273564fec33826bea30dcce038a50804b6c9a4c`
- 本交接文档会形成一个位于其后的独立 commit；新窗口应以 `git log` 显示的 HEAD 为准。
- 最终 tag：`final-validation-complete`

新窗口开始工作前，先执行：

```powershell
Set-Location D:\PythonProject\Helix_waterwise\carbon-helix-sim
git status --short
git log --oneline --decorate -5
```

## 2. 最终环境

正式验证使用的是用户指定的 `gllm` 环境：

```text
D:\software\miniconda\envs\gllm\python.exe
Python 3.10.20
```

最终测试命令：

```powershell
& D:\software\miniconda\envs\gllm\python.exe -m pytest -q
```

最终结果：

```text
81 passed
0 failed
0 skipped
```

`pip check` 发现的是旧版 `xuance` 与当前 NumPy/SciPy/OpenCV 的依赖冲突。
用户已经明确说“xuance 不要了不管”，所以没有处理它；本项目测试不依赖 xuance。

## 3. 已完成的工作

### 3.1 原始模拟器审计

报告：

`results/final_validation/helix_simulator_audit.md`

结论：原始模拟器是 aggregate serving-graph simulator，不是 request-level
discrete-event simulator。它没有 request arrival、queue、service time、completion
event、TTFT、TBT、end-to-end latency 或 SLO evaluator。

因此 request-level 集成状态必须保持：

```text
PARTIAL/BLOCKED
```

不能把 aggregate throughput 结果表述成真实延迟或 SLO 结果。

### 3.2 Stage-aware carbon model

新增：

- `src/carbon/stage.py`
- prefill/decode workload accounting
- prefill/decode 能耗 profile
- legacy scalar energy 配置兼容

修改：

- `src/carbon/config.py`
- `configs/energy_profiles.yaml`

验证：

- 9 个 stage-aware rows
- prefill-heavy / balanced / decode-heavy
- 3 个 GPU/network 场景
- stage-weighted routing 路径变化为 0%
- bounded joint placement 平均降低 stage carbon 1.8413%
- stage energy 是参数化 simulator assumption，不是硬件 profiling 数据

### 3.3 历史 CI 支持

新增：

- `experiments/import_historical_ci.py`
- `src/carbon/trace.py` 中的 `HistoricalCITraceLoader`
- `RegionMappedCIProvider`
- `data/carbon/raw/`
- `data/carbon/processed/`
- `data/carbon/metadata/`

数据来源：英国 National Grid Carbon Intensity API，日期 `2025-01-01`，真实
30 分钟采样，共 48 个实际 GB intensity values。

注意：同一个 GB trace 被映射到两个合成区域 A/B，只能证明 temporal ingestion，
不能证明 multi-region spatial carbon arbitrage。

历史实验覆盖完整 86,400 秒：

- low：相对 static Helix 降碳 25.4056%
- medium：相对 static Helix 降碳 4.3958%
- high：相对 static Helix 降碳 0.8446%
- 平均：10.2153%
- served fraction：100%

### 3.4 Legacy regression

所有 legacy regression 输出都写入新的：

`results/final_validation/`

没有覆盖原正式结果。

- Phase 3.5：930 points，PASS
- Challenge 2：930 points，PASS；科学结果列与正式结果一致，runtime 允许机器差异
- Challenge 3：135 points，核心 carbon/throughput/violation/flow/slow-CBGP/accepted-placement
  指标一致

Challenge 3 仍然是 bounded MILP comparator，不是 exact joint oracle。单次重跑中
`always_replace_placement_changes` 诊断值差 6，已记录为 time-limited solver
nondeterminism，没有覆盖或隐藏。

## 4. 重要报告和结果

- `results/final_validation/final_validation_report.md`
- `results/final_validation/final_validation_implementation_report.md`
- `results/final_validation/EXPERIMENT_AUDIT.md`
- `results/final_validation/EXPERIMENT_AUDIT.json`
- `results/final_validation/final_validation_summary.csv`
- `results/final_validation/request_level_results.csv`
- `results/final_validation/stage_aware_results.csv`
- `results/final_validation/historical_ci_results.csv`
- `results/final_validation/historical_ci_timeseries.csv`
- `results/final_validation/phase35_regression/`
- `results/final_validation/challenge2_regression/`
- `results/final_validation/challenge3_legacy_regression/`

图表：

- `final_validation_fig1_trace_flow.{pdf,png}`
- `final_validation_fig2_cumulative_carbon.{pdf,png}`
- `final_validation_fig3_stage_workloads.{pdf,png}`
- `final_validation_fig4_summary.{pdf,png}`

## 5. 最终验证结论

可以确认：

1. aggregate placement-aware carbon-flow 主线在现有 simulator 范围内成立。
2. Challenge 2 与 Challenge 3 的既有聚合结果已回归验证。
3. prefill/decode stage-aware accounting 已实现并保持 legacy compatibility。
4. 历史 CI temporal ingestion 已实现并使用真实 GB trace 验证。

不能确认：

1. 真实 request-level TTFT/TBT/端到端 latency。
2. queueing 或 service-time 影响。
3. production SLO violation。
4. multi-region historical spatial generalization。
5. exact joint MILP oracle 结论。

## 6. 明确不要做的事情

除非用户明确改变研究范围，否则新窗口不要：

- 创建 Challenge 4
- 添加新的 scheduler family
- 添加 RL 方法
- 添加 migration/hysteresis
- 添加伪造的 request latency/SLO
- 修改 Phase 3、Phase 3.5、Challenge 2、Challenge 3 正式历史结果
- 为了让测试通过而修改测试或旧业务逻辑
- 重新处理 xuance 依赖

## 7. 建议的新窗口开场指令

可以直接把下面这段复制到新窗口：

> 继续 `D:\PythonProject\Helix_waterwise\carbon-helix-sim` 项目。请先阅读
> `HANDOFF_FINAL_VALIDATION.md`、`results/final_validation/final_validation_report.md`
> 和 `results/final_validation/helix_simulator_audit.md`，确认当前分支是
> `final-validation`，并确认 Final Validation commit `7273564fec33826bea30dcce038a50804b6c9a4c`
> 已在当前 HEAD 历史中，不要重复已经完成的
> Final Validation。当前 request-level integration 必须保持 PARTIAL/BLOCKED，不能伪造
> TTFT/TBT/latency/SLO。先检查 git status 和 81 个测试，再等待我给出下一步具体任务。
