# T3 确定性与复跑审计

## 当前可用证据

- 首轮在 PowerShell 中显式设置 `PYTHONHASHSEED=0`、`MPLBACKEND=Agg` 后运行
  `python -m experiments.v3_method_validation.m3_run --phase formal --workers 4`。
  新增 16 个窗口全部完成；当前正式索引共 36 项：24 `passed`、12 `reused`。
- 首轮适配器在 Windows 工作树中为 CRLF，原始 SHA256 为
  `459f45032e8dba9779c4f7daab3426a19bedd1b3fdbd09fad41e2adab0ad69f6`。
  Git 中的 LF 文件 SHA256 为
  `626ad10a9030b6ba167a23bfd4fec83645cf67de8c9e543cd6966dfcdf74bee5`。
  将前者的 CRLF 规范化为 LF 后与 Git 文件逐字节相同，符合修订后的 T3 验收口径。
- 为排查哈希差异发起的第二轮也在启动命令中显式设置上述两个环境变量。
  第二轮索引保存在 `runs/m3_formal_second_attempt_audit/m3_formal_index.json`：
  12 `reused`、9 `passed`、1 `failed`、14 `runner_failed`。
  `single/seed2/observed_eft` 在约 435 秒于模拟器
  `KVCache.grow_query_kv_cache` 抛出 `TypeError: 'int' object is not subscriptable`；
  随后一名子进程异常退出，进程池将 14 个任务标为 `runner_failed`。
  该异常不折算为零性能，也没有用结果填补第二轮缺格。异常和进程日志原样保留。

前两轮的启动命令设置了哈希种子，但原有 `m3_run.py` 没有在每个子进程中
记录环境。因此这两轮的“实际取值”只能由启动命令与进程继承规则佐证，
不能用窗口 JSON 单独复核。我们未修改 `m3_run.py` 或 `m3_state.py`。

## 可比较窗口

第二轮在 16 个新窗口中仅 `multi/seed0/queue_only` 独立成功。
它与首轮同名窗口的吞吐、P95 TTFT、P95 TPOT、完成率、
`trace_sha256`、`route_counts` 全部逐项相同；去除仅反映 CRLF/LF 的
`adapter_sha256` 字段后，完整结果 JSON 相同。
第二轮其他 15 个新窗口没有成功 JSON，因而无法做“15 个共同成功窗口”的比较。

## 隔离诊断

按固定哈希种子、相同布局、负载、种子和 1800 秒窗口，单独运行一次
`single/seed2/observed_eft`。其
`runs/m3_determinism/attempt1/environment.json` 在进程内记录了
`PYTHONHASHSEED=0`、`MPLBACKEND=Agg`、代码及布局哈希。
窗口成功，结果 SHA256 为
`09aa3c73b55d12e9fa087425c4dcfe3083ee8375cbe1c15315aa52079ac7682b`。
它与首轮同名窗口的上述六项指标逐项相同；去除适配器原始换行哈希字段后，
完整 JSON 也相同。用户随后明确要求不再运行第二次独立窗口，故未运行 attempt 2。

## 判定边界

代码核查还发现 `observed_eft` 与 `full_no_session` 在当前继承链中等价：
`rcaps/v3/queue_cost.py:19–20` 已关闭 `include_committed` 和
`include_session_round`，两变体都返回空的活动会话计数。六个拓扑×种子
窗口的主要指标、路径计数与逐请求样本完全相同。因此不能将这两个变体的
差值解释为“已承诺路径工作量”的贡献。

首轮完整结果可用于查看三种子描述性差值，不能据此宣称 T3 的状态贡献已
通过重复性验证。两轮均在启动时设置了 `PYTHONHASHSEED=0`；因此没有证据把
故障归因于未固定该变量。第二轮的 KV 异常和进程池异常的根因尚未定位，
隔离运行成功说明 KV 异常并非每次都在该配置下必现。按照当前审核节点，
先停下 T3 机制结论，不启动 T1。
