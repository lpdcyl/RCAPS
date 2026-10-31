# 第二轮补测控制器恢复记录

2026-10-29：正式队列控制器进程已退出，但 index 中仍有两个 `running` 条目，且对应 worker 没有 `result.json` 或 `failure.json`。两条 worker.log 被保留；条目按 `controller_or_worker_abnormal_exit` 结案，随后由原冻结 manifest 重新排队未完成的 pending 条目。
