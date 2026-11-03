# E5a/E6/MILP 失败诊断记录（2026-11-03 至 11-04）

本记录只解释已保存的失败证据，不改变原正式批或任何独立重放的结果。E5a/E6 第二轮 24 键已 terminal 并通过[独立审计](failed_replay_retry_v2/FINAL_AUDIT.json)：4 成功、20 失败。下文仅讨论可由对应工件核对的故障。

## 已复现的边界

`E5a/load2150/RCAPS/seed0–4` 在新正式批五键全失败：seed0、2、3、4 为 `Exceed KV-cache capacity` 断言，seed1 为原生异常退出。第一轮独立重放仍五键失败，出现 KV token 数不匹配、推理请求不兼容、原生异常退出。第二轮有界独立重跑这五键也均失败：seed1、2、4 再次触发 KV 容量断言，seed3 触发 `Duplicate requests!`，seed0 为原生异常退出。逐键原始记录见相应 `index.json` 所列 `failure.json` 与 `worker.log`：

- [新正式索引](e5a/formal/index.json)
- [第一轮重放索引](e5a_failure_replay/index.json)
- [第二轮索引](failed_replay_retry_v2/index.json)

`E5a/load2150/RCAPS-KV/seed0–4` 的第二轮有界独立重跑也均失败：seed0–3 是 Windows 原生访问违规退出（十进制 `3221225477`，即 `0xC0000005`），seed4 是 `AttributeError("'int' object has no attribute 'node_uid'")`。同一键跨轮故障类型并不固定，不能将所有异常解释为单一已证实的软件原因。

随后 `E5a/load2150/Helix/seed1` 的第二轮重跑复现了原正式批相同的 `AttributeError("'int' object has no attribute 'node_uid'")`；第一轮重放因控制器中断未形成可比较的执行结果。第二轮调用栈显示，`network_link.py` 的传输完成调用 `request.py:add_routing_history` 时，`link.node_in` 实际为整数。该事实表明异常并非仅出现在 RCAPS 方法；其产生整数节点值的上游路径尚未定位。[该键 worker 日志](failed_replay_retry_v2/runs/E5a/load2150/Helix/seed1/worker.log)保留了完整调用栈。

`E5a/load2150/Helix/seed2` 的第二轮也在相同传输完成调用栈抛出 `link.node_in` 整数的异常；其原正式失败是另一种 `TypeError("'InferenceRequest' object is not subscriptable")`，第一轮重放因控制器中断终止。不能把跨轮所有故障合并成一个根因。

`E5a/load2150/Helix/seed3` 的第二轮同样在该调用栈失败，至此第二轮 Helix seed1–3 三键出现相同 `link.node_in` 类型异常。静态检索只在 `NetworkLink.__init__` 找到 `node_in` 的显式赋值，未找到后续直接赋值；这缩小了检查范围，但不足以证明是原生内存损坏，也不排除运行时动态修改。三键的正式或第一轮失败类型不同，仍按各自工件独立保留。

E6 的 `single/load350/S3/seed3` 在新正式批与第二轮独立重跑均以 `0xC0000005` 原生访问违规退出，第一轮重放则因控制器中断终止。这两次原生退出不构成成功结果，亦不能单凭退出码定位到特定 Python 或仿真器代码。

MILP 的 `single/load350/480/seed2` 与 `single/load350/480/seed4` 在新正式批和当前独立重放中均以 `0xC0000005` 退出。两次重放的 worker 日志由 `faulthandler` 留下传输路径的 Python 调用栈；Windows Application Error 事件 1000 的进程 ID、时间和异常码分别与对应 worker 唯一匹配，记录的故障模块均为 `python310.dll`。这些信息确认原生访问违规在两个键上再次出现，但调用栈和故障模块都不能单独确定最初的内存破坏来源。[seed2 证据](MILP_NATIVE_EXIT_EVIDENCE_20261104.json)与 [seed4 证据](MILP_NATIVE_EXIT_EVIDENCE_SEED4_20261104.json)分别记录正式与重放工件、worker 日志的 SHA256 以及系统事件编号。独立重放控制器已将两键记为失败并继续余下待运行键，未回填正式批。

MILP 的 `single/load700/official/seed0` 新正式批在 `finish_execution` 的批次句柄检查处抛出 `SystemError('error return without exception set')`；独立重放则在同一执行完成路径的 `mark_inferred` 中遇到 `AttributeError("'list' object has no attribute 'inference_history'")`。资源画像包装器在执行开始时会逐个读取批内请求的 `request_uid`，重放却在执行结束时看到列表对象；这提示执行期间的批内对象状态需要检查，但两次异常类型不同，现有证据不能确定是逻辑修改还是原生层破坏。[逐键证据](MILP_PYTHON_TYPE_FAILURE_EVIDENCE_20261104.json)保存正式和重放工件及 worker 日志的 SHA256。该键保持失败状态。

截至 2026-11-04 02:03 KST，MILP 单集群 `load700` 登记的 13 个正式失败键已全部完成独立重放，结果为 0 成功、13 失败，见[完整子组逐键快照](MILP_LOAD700_FAILURE_SNAPSHOT_20261104.json)。重放失败混有原生退出、Python 类型异常和在线调度断言，不能合并为一个已证实根因。其中 `480/seed4` 的正式与重放均在 `scheduler_core.py:276` 断言节点 2 无可行下一跳；该断言前的掩码可能由流量、长度或预期 KV 容量过滤，现有工件没有逐候选过滤原因，不能断定是哪项触发。01:50 的[运行中事件快照](MILP_NATIVE_EXIT_SNAPSHOT_20261104_PRETERMINAL.json)另将当时累计 6 个 MILP 原生退出与 Windows Application Error 事件按 PID、时间、异常码逐一匹配；它不代表最终原生退出总数。其余负载仍按预登记的一键一次运行。

2026-11-04 从 Windows Application Error 事件 1000 取得 [Python 进程崩溃快照](PYTHON_APP_CRASH_EVIDENCE_20261104.json)，并按 worker PID 与其运行时间窗匹配[第二轮原生退出](NATIVE_EXIT_EVENT_MATCH_20261104.json)：本轮 10 次 `0xC0000005` 原生退出均对应唯一的系统事件，其中 4 次事件把 `python310.dll` 列为故障模块，6 次模块为 `unknown`。故障模块是崩溃时观察到的位置，不足以判定最初破坏内存的代码。应用日志在同一时期记录的其他 Python 崩溃也未全部确认为本项目 worker。

## 代码路径与解释边界

RCAPS 的容量断言位于 `simulator/event_simulator/kv_cache.py` 的 `initialize_query_kv_cache` 和 `grow_query_kv_cache`，由 `compute_node.py` 完成执行后的 KV 更新触发。它证明当前仿真轨迹在该节点出现 KV 容量不足；现有日志尚不能区分是高负载下实际资源耗尽、准入估计不足，还是更早的路由／状态错误导致的容量计算异常。

RCAPS-KV 使用 `experiments/v5_kv_admission/scheduler.py` 的预期容量预留：以 `AVG_OUTPUT_LEN * 0.6` 估计输出，并以 90% 水位作准入检查。该文件本身明确说明这不是任意输出增长下的 KV 安全保证。已观察到的原生退出缺少可读转储，不能据此认定 KV 预留算法是原生崩溃根因。

同机 [Windows 蓝屏恢复事件](SYSTEM_CRASH_EVIDENCE_20261103.json) 已单独保存；事件只能证明运行环境也发生过系统级不稳定，不能替 Python 异常或模拟器断言作因果归因。

2026-11-04 02:06 KST，Windows 又记录一次 `0x0000003B` 检测错误后的重启。MILP 旧控制器与 worker 已消失，旧 PID 9224 被 `svchost.exe` 复用；看护任务保存原索引与工件 SHA 后，只启动一个续跑控制器。中断的 `multi/load160/official/seed2` 被明确记为 `controller_interrupted` 失败，未当作成功也未重跑；余下 pending 键继续。新转储文件存在，但当前用户无法读取其 SHA。[系统重启及续跑证据](SYSTEM_REBOOT_RECOVERY_EVIDENCE_20261104_0206.json)保留事件编号、原索引和恢复修订的哈希。这仍不能证明是实验程序引起系统蓝屏。

当前处理为保留每个失败工件、控制每键最多一次第二轮重跑，并将结果与正式批分列。任何软件修复须另立版本，冻结修改后的源与全部受影响条件，再运行完整新批；不能用零散成功重放拼出正式五种子组。

## 无人值守恢复边界

本机 `RCAPS-E5a-Replay-Watchdog` 每 10 分钟及用户登录时触发，任务主体为当前用户、`LogonType=Interactive`。2026-11-03 23:42 试图以该用户注册一项只写临时探针文件的 `S4U` 无登录任务，Windows 返回“拒绝访问”；探针任务未创建，临时脚本已删除，原看护任务未改动。因此正常登录会话中可自动检查与恢复；若再次蓝屏并重启到无人登录状态，不能声称看护仍会执行，需待用户登录后由登录触发器接续。该限制不改变已完成窗口或故障分类。
