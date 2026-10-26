# 第二次用户授权的恢复批次

2026-10-26，恢复批次在 C2/load160/v4/seed1 首次尝试发生原生访问冲突后，用户再次明确要求“重新运行就是”。本批仅对该窗口登记一次第二尝试，成功后继续剩余 7 个未启动窗口。此前主批次和第一次恢复批次的 index、成功结果及两次失败均不覆盖。

仍使用种子 0/1/2、1800 秒、零预热、不排空、原算法、原输入、原环境和原参数。先单独重跑 C2/V4/seed1；成功后最多两个进程续跑。任何新失败停止派发，不循环重试。本次成功不代表原生崩溃或历史 TypeError 根因已解决。

控制器调用原冻结 `run_one`，仅将输出重定向到本目录，增加尝试编号与恢复 manifest 身份。额外固定上一恢复批次 index 哈希，以保证选择的确实是一个失败窗口和七个未启动窗口。

沿用 `v4_formal/ENVIRONMENT_CN.md` 中环境变量与解释器：

```powershell
python -m experiments.v4_recovery2.run register
python -m experiments.v4_recovery2.run validate
python -u -X faulthandler -m experiments.v4_recovery2.run queue
```

若全部补齐，总计为 120 个成功窗口、122 次尝试、2 次保留失败；不能称作 120 次首次运行全成功。
