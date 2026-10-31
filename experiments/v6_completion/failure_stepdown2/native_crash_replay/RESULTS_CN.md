# 30B 早期异常窗口诊断重放

与正式窗口同条件、同种子；重放不覆盖正式失败，也不产生新种子。

| 键 | 状态 | 原因 | P95 TPOT s | P95 TTFT s | 完成率 |
|---|---|---|---:|---:|---:|
| 30b_multi_rate525/HH/seed0 | failed | TypeError("'list_iterator' object is not callable") | 未观测 | 未观测 | 未观测 |
| 30b_multi_rate525/HH/seed1 | completed | completed | 0.6005 | 4.8548 | 0.9655 |
| 30b_multi_rate525/HH/seed2 | completed | completed | 0.5905 | 4.8910 | 0.9632 |
| 30b_multi_rate525/HH/seed3 | completed | completed | 0.6127 | 4.9767 | 0.9583 |
| 30b_multi_rate525/HH/seed4 | completed | completed | 0.6054 | 4.8861 | 0.9664 |
| 30b_multi_rate525/V4/seed0 | failed | AssertionError('Exceed KV-cache capacity!') | 未观测 | 未观测 | 未观测 |
