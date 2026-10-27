# RCAPS 主线核心补证

本轮新增 15 个正式条件，均已前瞻登记，不根据结果改变参数：

1. 会话持续服务代价：单集群 700、三集群 320，种子 0/1/2，共 6 个 `no_session` 窗口。
2. 分块边界占用成本：三集群 320，1/10/100 ms 每中间块边界，种子 0/1/2，共 9 个窗口。

相同 1800 秒到达前缀，观察至 5400 秒。复用 9 个已冻结且哈希登记的完整系统/无分块参照。成本值为仿真假设，并非硬件测量。

## 当前有效路径

- 科学协议：`PROTOCOL_CN.md`、`manifest.json`。
- 执行入口：`run_execution.py`；有效队列：`execution/index.json`。
- 实际仿真记录：`execution/runs/`；日志：`execution/queue.log`、`execution/queue.err`。
- 启动修正：`ENGINEERING_REPAIRS_CN.md`、`DISPATCH_REPAIR_CN.md` 及两个 amendment JSON。
- 根目录 `index.json` 和 `runs/` 留存仿真启动前的 15 次派发工程失败；不得将其当作有效队列或删除。

正式队列已结束：14个窗口成功，100ms成本seed1发生原生访问冲突并留档；没有缺失窗口，14个成功结果已通过最终核验。早期15次仿真前派发失败另行留档，不并入正式计数。

## 查看及恢复

PowerShell 中从仓库根目录设置与原批次相同的环境：

```powershell
$spec = Get-Content -LiteralPath 'experiments/v4_formal/env-spec.json' -Raw | ConvertFrom-Json
$spec.env.PSObject.Properties | ForEach-Object {
    [Environment]::SetEnvironmentVariable($_.Name, [string]$_.Value, 'Process')
}
& 'D:/software/miniconda/python.exe' -m experiments.v4_core_validation.run_execution --phase status
```

控制器意外退出后，可以用同一入口 `--phase queue` 恢复；先检查 PID 与创建时间，保留既有 worker 和全部记录。恢复日志使用新时间戳，禁止覆盖原日志。隐藏后台启动不加 `-X utf8`，原因与探测结果见修正记录；文件与输出流仍显式 UTF-8。

## 终态核验

当有效 index 为 completed 且无 pending/running/starting 时，在相同环境执行一次：

```powershell
& 'D:/software/miniconda/python.exe' -m experiments.v4_core_validation.report
```

首次综合生成 `results.json`、`individual.csv`、`RESULTS_CN.md`。随后只对已核验配对结果作确定性报告扩充，原件保存在 `reconciliation_v1.json`，哈希见 `report_enrichment.json`。已有原始源与输入、逐种子请求身份、百分位、完成量、工作量与成本计数逐项核查；不完整种子组不输出完整三种子均值。

真实异构硬件校准仍未完成。已完成逐种子结果核对，并更新 `paper/RCAPS_V4_EVIDENCE_STATUS_CN.md` 和 `paper/RCAPS_WRITING_BLUEPRINT_CN.md`。结论限定为画像驱动仿真：会话项有延迟—GPU工作取舍；低成本分块假设下相对无分块有TPOT收益，100ms组三种子不完整；真实硬件/协议校准未完成。原始结果和失败样本均保留。用户此前选择暂不制图，本轮未新增方法示意图。
