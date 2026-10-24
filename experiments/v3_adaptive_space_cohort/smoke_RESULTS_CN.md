# 工作三：自适应空间生命周期复核

阶段：smoke。有效完整矩阵：True。结果：9/9。

仿真结果，三种子描述性比较；确定性复算不等于独立跨模型审核。

| 状态 | 策略 | 全生命周期 P95 TPOT 均值（秒） | 固定前缀 P95 TPOT 均值（秒） | 原窗口吞吐 | 唯一胜者 |
| --- | --- | ---: | ---: | ---: | --- |
| middle/nominal | canonical | 0.537671 | 0.535110 | 2.866667 | 无 |
| middle/nominal | partial | 0.603005 | 0.613648 | 3.400000 | 无 |
| middle/nominal | full | 0.610038 | 0.619713 | 3.366667 | 无 |
| high/nominal | canonical | 0.584335 | 0.591214 | 3.533333 | full |
| high/nominal | partial | 0.557191 | 0.562044 | 4.200000 | full |
| high/nominal | full | 0.548966 | 0.549430 | 4.500000 | full |
| high/crosslink_4x | canonical | 0.567795 | 0.574407 | 6.033333 | partial |
| high/crosslink_4x | partial | 0.539277 | 0.548563 | 6.133333 | partial |
| high/crosslink_4x | full | 0.543189 | 0.543890 | 6.000000 | partial |

## 配对交叉检查

- middle/nominal → high/nominal：{"conditions": ["middle/nominal", "high/nominal"], "confirmed": false, "reason": "No different unique primary winners"}
- high/nominal → high/crosslink_4x：{"conditions": ["high/nominal", "high/crosslink_4x"], "confirmed": false, "winners": ["full", "partial"], "all_request_matching_seeds": 1, "prefix_matching_seeds": 0, "prefix_mean_direction_preserved": false}

测试范围内自适应空间通过预注册复核：False。
事后按状态选固定策略相对最佳全局固定策略的混合 P95 改善：0.00%。
该事后参照使用评价结果且不包含真实切换/瞬态代价，只用于估计候选空间，不能视为控制器收益。
若未通过，只能说当前范围未确认，不能推出不存在任何动态路径控制机会。

排空期停止新到达，会改变尾段资源状态。固定到达前缀是预注册敏感性检查，也不能替代后续持续负载下的动态闭环实验。
本复核不验证 42 GPU 泛化、KV 高压收益或少 GPU 相比全 GPU Helix 的优势。
