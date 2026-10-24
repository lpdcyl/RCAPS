# 工作三完整路径门控：开发结果

环境：显式激活 gllm；每格独立解释器；离散事件仿真。历史冻结源码未修改。

指标采用全部到达请求完整生命周期；吞吐仅使用到达窗口输出 token。GPU 秒/token 为全部实际执行工作量/实际输出，不是实体 GPU 测量。

| 种子 | 方法 | P95 TPOT s | P95 TTFT s | 窗口输出 token/s | GPU 秒/token | 平均 Decode 批 | 新增选路 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 104 | canonical | 0.705779 | 6.343747 | 33.423 | 0.068202 | 4.797 | 0 |
| 104 | partial | 0.640380 | 5.304766 | 34.105 | 0.105017 | 3.007 | 0 |
| 104 | full | 0.626722 | 5.168945 | 34.160 | 0.135199 | 2.280 | 0 |
| 104 | adaptive_link | 0.640380 | 5.304766 | 34.105 | 0.105017 | 3.007 | 0 |
| 104 | route_control | 0.646485 | 5.154102 | 34.168 | 0.133228 | 2.325 | 40 |
| 105 | canonical | 0.659295 | 6.700198 | 30.288 | 0.076455 | 4.246 | 0 |
| 105 | partial | 0.628351 | 4.782308 | 30.822 | 0.112233 | 2.786 | 0 |
| 105 | full | 0.626916 | 4.668949 | 30.810 | 0.139136 | 2.227 | 0 |
| 105 | adaptive_link | 0.628351 | 4.782308 | 30.822 | 0.112233 | 2.786 | 0 |
| 105 | route_control | 0.627393 | 4.991316 | 30.830 | 0.143805 | 2.144 | 43 |

## 预定判定

```json
{
  "paired": [
    {
      "seed": 104,
      "best_latency_fixed": "full",
      "latency_gain": -0.0315330749359759,
      "latency_guardrails_pass": false,
      "best_eligible_efficiency_fixed": "full",
      "efficiency_gain": 0.014580383254741314,
      "efficiency_guardrails_pass": false,
      "actual_control_action": true
    },
    {
      "seed": 105,
      "best_latency_fixed": "full",
      "latency_gain": -0.0007608408146295709,
      "latency_guardrails_pass": false,
      "best_eligible_efficiency_fixed": "partial",
      "efficiency_gain": -0.2813155992777838,
      "efficiency_guardrails_pass": false,
      "actual_control_action": true
    }
  ],
  "latency_branch_pass": false,
  "efficiency_branch_pass": false,
  "performance_gate_pass": false,
  "formal_authorized_by_this_report": false,
  "next": "STOP current candidate; preserve negative evidence; no expanded sweep or formal matrix"
}
```

性能门槛通过也不自动等于正式闭环；还需机制、消融、开销与正式 0/1/2。门槛未通过时停止当前候选，不代表所有动态控制均不可能。

完整性：10/10 个结果通过逐请求事件、执行工作量、路径覆盖、KV、轨迹与哈希复算。
