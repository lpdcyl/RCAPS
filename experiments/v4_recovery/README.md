# 用户授权恢复批次

2026-10-26 用户明确要求“继续 失败的重新运行就行了”。据此登记一次第二尝试，成功后继续 22 个从未启动的窗口。原始主批次 index、失败日志和成功结果均不覆盖。

先单独执行 `single/load700/static/seed1` 的第二尝试；成功后按原 manifest 顺序、最多两个独立进程继续剩余窗口。正式种子 0/1/2，1800 秒、零预热、不排空，所有算法、输入、依赖环境和默认参数沿用原冻结协议。新批次任何失败仍停止派发，不循环重试、不择优保留。环境稳定性和历史 TypeError 根因仍未知。

本目录 `manifest.json` 固定本次授权、原始 index/失败日志哈希、23 个窗口及恢复控制器代码。控制器直接调用冻结的 `run_one`，仅将结果写入本目录，追加尝试编号和恢复 manifest 身份。不存在重新实现算法或替换种子。

使用原 `v4_formal/ENVIRONMENT_CN.md` 环境变量与解释器，依次执行：

```powershell
python -m experiments.v4_recovery.run register
python -m experiments.v4_recovery.run validate
python -u -X faulthandler -m experiments.v4_recovery.run queue
```

恢复前的 70+27 个成功窗口与恢复批次结果联合形成有效窗口集合；原始失败必须单列。最终即使 120 个窗口齐全，也应报告至少 121 次尝试、至少 1 次失败，不能写成 120/120 首次运行成功。
