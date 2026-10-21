# V3 M3 全周期会话定价（候选，不是冻结 V3）

## 要检验的痛点

路径空间消融显示：冻结 V3 布局上，完整 DAG 在单集群比规范路径 P95 TPOT 高约
0.053 s、吞吐低约 1.05 token/s，三集群则相反。已发布窗口的 `route_counts`
显示完整 DAG 使每个请求平均多经过 0.48（单集群）/ 0.94（三集群）个 GPU。

M3 路由代价 `queue_cost.py:53–68` 对每个经过的 GPU 收取
`活跃会话数 × 本请求在该 GPU 上执行的层片的 Decode 服务`。但 Decode 路径在
Prompt 选路时就被锁定（`online_scheduler.py:36–38`），而模拟器的 GPU 按全部驻留层
循环执行（`compute_node.py:595–618`）：从段中间进入一个 GPU 的请求，每个 Decode
token 仍要等这个 GPU 的完整一轮。冻结代价因此低估跨副本的部分段跳。

## 候选改动（无新参数）

`scheduler.py` 的 `FullCycleSessionScheduler` 只覆盖 `_decode_token_service`：
会话项改用该 GPU 全部驻留层的 Decode 服务。规范路径上的每个 GPU 都执行完整段，
代价与冻结 V3 完全相同；只有部分段跳变贵。`RouteRecorder` 被动记录每个请求的
GPU 跳数与部分段跳数，不改变选路。

## 协议

判定规则写在 `protocol.json`，先于正式窗口提交。开发种子 100（300 秒）只用于运行器
检查与机制描述；正式种子 0/1/2，1800 秒，零预热、不排空，单集群 700、三集群
320 offered token/s，冻结 V3 布局。对照为已发布的 V3 窗口与路径空间消融的规范路径
窗口；本目录另在同环境重跑冻结 V3，用于逐项一致性核对和跳数记录。

## 复现

```bash
export PYTHONHASHSEED=0 MPLBACKEND=Agg
python -m experiments.v3_cycle_pricing.run --phase dev --workers 4
python -m experiments.v3_cycle_pricing.run --phase formal --workers 4
python -m experiments.v3_cycle_pricing.run --phase report
```

已存在的结果文件不会被覆盖；失败窗口保留 `.failure.json` 与日志。
