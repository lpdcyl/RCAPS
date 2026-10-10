# 历史调度候选

这里保存开发阶段的路径选择变体，用于复现已有短测和消融结果；论文最终方法在上一层的 [`scheduler_final.py`](../scheduler_final.py)。

| 文件 | 尝试的规则 |
| --- | --- |
| `scheduler_decode.py` | 先比较解码服务需求，再比较提示完成时间。 |
| `scheduler_pareto.py` | 保留吞吐代理与延迟代理的非支配标签。 |
| `scheduler_corridor.py` | 将在线路径限制在放置产生的分支内。 |
| `scheduler_bottleneck.py` | 用瓶颈代价和提示代价组成两维标签。 |
| `policies.py` | 旧实验的策略名称到类的映射。 |

其他服务代价与优先级的早期变体仍定义在 [`../scheduler_queue_cost.py`](../scheduler_queue_cost.py)，因为最终调度器继承其中的单 token 队列代价实现。正常运行使用 `python -m experiments.queue_dag.evaluate --policy final ...`。
