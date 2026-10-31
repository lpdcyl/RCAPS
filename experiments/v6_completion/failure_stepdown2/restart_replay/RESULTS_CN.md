# 电脑重启中断窗口的独立重放

相同正式 manifest 条件和 seed，独立保存；不覆盖正式索引中的首轮中断记录。

| 条件/方法/seed | 重放状态 | P95 TPOT (s) | P95 TTFT (s) | 完成率 | 原因 |
|---|---|---:|---:|---:|---|
| 30b_multi_rate525/HHplus/seed3 | completed | 0.6923 | 4.9777 | 0.9572 | 完成 |
| 30b_multi_rate525/V4/seed3 | failed | 未观测 | 未观测 | 未观测 | AssertionError('Exceed KV-cache capacity') |
