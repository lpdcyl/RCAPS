# T0.5：M3 Decode 系数与实际代价核实

## 协议与完整性

C1 单集群冻结布局；V3 完整 M3；开发种子 100；350 offered token/s；
60 秒固定窗口；零预热；窗口末不排空。这里只诊断单请求 Decode batch，
不作为正式种子 0/1/2 的性能证据。被动包装执行起止函数，不改变模拟时间或调度。

轨迹 SHA256：`71a5b013329e0652e6b13c7a7790a7f812ad96f6d1180969ea30e8aaf5dbb2f1`；结果 SHA256：`0e91a049fc70dc5012a74afe3fc5e21454646db3d78c990a443278264d49f036`。
校准窗口成功数：1；最终失败数：0；窗口末尚未完成的被观察 batch：5。

## 单请求 Decode：实际执行与逐层画像

每条记录是一个 GPU 上某一层完成的单请求 Decode batch。实际时长取
`FinishExecution` 时间减 `start_execution` 时间；预测时长取
`_layer_service(node, layer, Increment, 1)`。同 GPU 类型先求时长总和，再取比值。

| GPU | batch 数 | 实际总时长 (s) | 画像总时长 (s) | 实际/画像 |
| --- | ---: | ---: | ---: | ---: |
| A100 | 48612 | 68.086667 | 34.028400 | 2.0009 |
| L4 | 21779 | 150.336228 | 75.137550 | 2.0008 |
| T4 | 14035 | 99.677121 | 49.824250 | 2.0006 |

### 首层与其他层

| GPU | 层位置 | batch 数 | 实际/画像 | 执行事件时长核对最大误差 (s) |
| --- | --- | ---: | ---: | ---: |
| A100 | first | 4051 | 2.0105 | 2.804e-15 |
| A100 | other | 44561 | 2.0000 | 3.843e-15 |
| L4 | first | 2785 | 2.0064 | 6.866e-15 |
| L4 | other | 18994 | 2.0000 | 1.871e-15 |
| T4 | first | 3882 | 2.0021 | 6.927e-15 |
| T4 | other | 10153 | 2.0000 | 5.889e-15 |

## 节点 Decode batch 设置

| GPU | 节点 ID | 层段 | decode_typical_tokens | decode_max_tokens |
| --- | ---: | --- | ---: | ---: |
| L4 | 2 | 51–57 | 7 | 280 |
| T4 | 3 | 65–67 | 9 | 300 |
| T4 | 4 | 68–71 | 6 | 300 |
| L4 | 5 | 58–64 | 7 | 280 |
| T4 | 6 | 51–54 | 6 | 300 |
| L4 | 7 | 55–61 | 7 | 280 |
| A100 | 8 | 0–11 | 4 | 300 |
| T4 | 9 | 51–54 | 6 | 300 |
| T4 | 10 | 72–75 | 6 | 300 |
| A100 | 11 | 12–23 | 4 | 300 |
| A100 | 12 | 24–35 | 4 | 300 |
| L4 | 13 | 62–68 | 7 | 280 |
| T4 | 14 | 48–50 | 9 | 300 |
| T4 | 15 | 48–50 | 9 | 300 |
| L4 | 16 | 55–61 | 7 | 280 |
| T4 | 17 | 48–50 | 9 | 300 |
| T4 | 18 | 48–50 | 9 | 300 |
| A100 | 19 | 36–47 | 4 | 300 |
| L4 | 20 | 62–68 | 7 | 280 |
| T4 | 21 | 76–79 | 6 | 300 |
| T4 | 22 | 76–79 | 6 | 300 |
| L4 | 23 | 69–75 | 7 | 280 |
| T4 | 24 | 76–79 | 6 | 300 |
| L4 | 25 | 69–75 | 7 | 280 |

## 系数解释

`QueueAwareDagScheduler._decode_token_service` 将单 token Decode 画像和乘 2
（`rcaps/v3/online_scheduler.py:68–69`），用于路由时的 KV 会话定价。
该系数与模拟器的实现直接对应：`ModelLayer.get_inference_statistics` 在
`decode_phase_tokens == 1` 时明确把 Decode 时间乘 2
（`simulator/event_simulator/model.py:131–134`）。因此非首层的实测比值
精确为 2；首层另有 activation 拼接和传输开销
（`simulator/event_simulator/compute_node.py:460–479`），实测略高于 2。
这个系数是模拟器单请求执行时间与原始画像之间的确定性修正，
不是根据正式窗口调出的自由权重。

## V3 M3 实际生效的路径代价

V3 的 `_route` 来自 `WorkloadQueueDagScheduler`，而不是
`routing.py` 文件头所述的 earliest-finish 递推。对于合法分段路径 P，
选择使以下累加代价最小的路径（单位秒）：

`C(P)=Σ_{v∈P}[prompt_service(v)+max(0,gpu_release(v)-now)+
active_sessions(v)·2·Σ_{l∈segment(v)}decode_profile(v,l,batch=1)]
+Σ_{e∈P}[max(0,link_release(e)-now)+transfer_time(e,request)]`。

Prompt service、GPU 等待、KV 会话项见 `rcaps/v3/queue_cost.py:53–68`；
终点链路同样加等待和传输时间，见 `queue_cost.py:79–91`。
GPU/链路释放时间来自当前 batch 与队列快照，见 `routing.py:85–174`；
由于 `queue_cost.py:19–20` 将 `include_committed` 与
`include_session_round` 设为 False，该快照不计已承诺路线和额外批次预留。
传输时间见 `routing.py:75–83`。合法边由 `rcaps/v3/scheduler.py` 限制。

这不是在线完成时间的无偏预测，也不是将各资源等待时间按串行时间轴递推；
它是用当前状态排序合法路径的工作量代理。

开发期间一次探针调用签名错误已修复，失败记录保留于 `runs/dev_seed100.attempt1.failure.json`（SHA256 `eba703243350dfaad5de2537cc8c4a2d698b0ede211d3fda49bb490352d520e3`）；该失败发生在首个模拟事件，未计入校准窗口。
