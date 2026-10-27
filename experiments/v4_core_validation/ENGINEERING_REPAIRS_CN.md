# 工程启动修正记录

## 2026-10-27：后台启动编码与 Windows 版本检测

工程预检与登记已通过。第一次 PowerShell `Start-Process` 启动的控制器在旧冻结环境的严格字典比较处退出，报 `Worker environment drift`。没有生成正式 index，没有派发仿真窗口。

最初怀疑解释器路径表示不同；独立探测否定了该猜测。`engineering/launch_environment.json` 显示只有 `platform` 不同：前台返回 Windows build 26200，隐藏后台返回 26100。随后 `engineering/launch_encoding_diagnosis.json` 隔离了原因：隐藏后台使用 `-X utf8` 时系统版本探测返回 26100，不加此参数时环境字典与原冻结环境完全相同。原先批次的 worker 也没有使用 `-X utf8`。

修正仅移除后台控制器与 worker 命令行中的 `-X utf8`，恢复原批次的系统命令解码行为；仍设置 `PYTHONIOENCODING=utf-8`，文件 I/O 显式使用 UTF-8。修正由独立 `run_compatible.py` 与 `launch.py` 实现，登记在 `launch_amendment.json`。环境字典检查没有放宽，也没有伪造 OS 版本。冻结的 `run.py`、`core.py`、协议与 manifest 均保持原样。

首次 `queue.log`、`queue.err`、`launcher.json` 及第二次 `queue_20261027_113032.log/err` 均保留；后续启动使用带时间戳的新日志。两次均没有 index 或仿真派发，属于正式窗口开始前的启动工程问题，不计作正式实验窗口或算法失败。
