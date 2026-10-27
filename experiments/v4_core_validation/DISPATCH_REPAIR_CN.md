# 派发适配器工程修正

2026-10-27。首次启动兼容适配器遗漏了 `subprocess.STDOUT` 常量，15 个条件均在 `Popen` 调用之前发生 `AttributeError`。这些属于派发失败：没有仿真 worker PID，没有 `worker_started.json`，没有运行任何正式窗口。旧 `index.json`、全部 `dispatch_failure.json`、日志、适配器及其登记文件原样保留。

使用独立 `run_execution.py` 补齐常量，并在 `execution_amendment.json` 登记源码、原 manifest、原失败 index 和失败文件校验值。先做一次真实隐藏子进程派发检查，然后在独立 `execution/` 路径执行原来 15 个条件。未改变配置、种子、成本取值、仿真代码或结果筛选规则。该修正不是因性能结果不理想而重跑；仍须在最终报告单独列明此前 15 次派发失败。

后续自动监控使用 `execution/index.json` 和 `execution/runs/`，不是旧失败 index。任何实际进入仿真的失败依旧保留并继续后续条件，不自动重试。
