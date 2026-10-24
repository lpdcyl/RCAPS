# 工作三：自适应空间生命周期复核

阶段：formal。有效完整矩阵：True。结果：27/27。

仿真结果，三种子描述性比较；确定性复算不等于独立跨模型审核。

| 状态 | 策略 | 全生命周期 P95 TPOT 均值（秒） | 固定前缀 P95 TPOT 均值（秒） | 原窗口吞吐 | 唯一胜者 |
| --- | --- | ---: | ---: | ---: | --- |
| middle/nominal | canonical | 0.612073 | 0.613943 | 35.747963 | partial |
| middle/nominal | partial | 0.567361 | 0.569320 | 35.908333 | partial |
| middle/nominal | full | 0.579838 | 0.582497 | 35.898519 | partial |
| high/nominal | canonical | 0.820176 | 0.813862 | 69.822963 | 无 |
| high/nominal | partial | 0.703408 | 0.701273 | 70.557037 | 无 |
| high/nominal | full | 0.696712 | 0.697546 | 70.575926 | 无 |
| high/crosslink_4x | canonical | 0.645967 | 0.646287 | 70.819259 | partial |
| high/crosslink_4x | partial | 0.601637 | 0.602601 | 71.102407 | partial |
| high/crosslink_4x | full | 0.633817 | 0.636098 | 71.072037 | partial |

## 配对交叉检查

- middle/nominal → high/nominal：{"conditions": ["middle/nominal", "high/nominal"], "confirmed": false, "reason": "No different unique primary winners"}
- high/nominal → high/crosslink_4x：{"conditions": ["high/nominal", "high/crosslink_4x"], "confirmed": false, "reason": "No different unique primary winners"}

测试范围内自适应空间通过预注册复核：False。
事后按状态选固定策略相对最佳全局固定策略的混合 P95 改善：-0.02%。
该事后参照使用评价结果且不包含真实切换/瞬态代价，只用于估计候选空间，不能视为控制器收益。
若未通过，只能说当前范围未确认，不能推出不存在任何动态路径控制机会。

排空期停止新到达，会改变尾段资源状态。固定到达前缀是预注册敏感性检查，也不能替代后续持续负载下的动态闭环实验。
本复核不验证 42 GPU 泛化、KV 高压收益或少 GPU 相比全 GPU Helix 的优势。
