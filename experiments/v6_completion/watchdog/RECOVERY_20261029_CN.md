# 自动收尾进程恢复记录（2026-10-29 韩国时间）

- 约 02:34，原 watchdog 在写入 status.json.part 并替换 status.json 时遇到 Windows WinError 5，异常记录保留在 error.json；此时六个未终结正式批次的控制器仍继续运行，正式窗口和 manifest 未改动。
- 仅修改 watchdog.py 的状态文件写入：遇到 PermissionError 时最多重试 20 次，每次短暂退避；未修改正式批次或 frozen_runtime_inputs.zip。
- gllm Python 语法检查通过。02:39 以隐藏后台进程重新启动 watchdog，PID 48368；status.json 时间戳已更新到 02:39，state=waiting_for_registered_campaigns。
- failure_replay.py 的原因分类新增 profiling_range_exceeded，用于区分四倍 Prompt 下超过既有 Prompt 性能画像 0..7500 token 的窗口与真实 KV 溢出。分类不改变原结果，仍按每个失败键独立重放一次。
- 原 error.json 保留为历史事故记录；后续以当前 watchdog/status.json、各 formal/index.json 和最终审计为准。
