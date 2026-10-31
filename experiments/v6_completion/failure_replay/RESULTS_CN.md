# V6 失败窗口独立重放

每个首次正式失败键只重放一次，原结果与失败记录不覆盖；重放成功不计为新种子。

| 批次 | 原因 | 重放状态 | 重放原因 | 窗口数 |
|---|---|---|---|---:|
| generalization | actual_kv_allocation_overflow | failed | actual_kv_allocation_overflow | 16 |
| generalization | helix_admission_no_eligible_next_node | failed | helix_admission_no_eligible_next_node | 40 |
| generalization | profiling_range_exceeded | failed | profiling_range_exceeded | 9 |
| robustness | AttributeError("'InferenceRequest' object has no attribute 'Initialization'") | completed | completed | 2 |
| robustness | AttributeError("'generator' object has no attribute 'link_uid'") | completed | completed | 1 |
| robustness | AttributeError("'int' object has no attribute 'phase'") | completed | completed | 1 |
| robustness | AttributeError("'str' object has no attribute 'entity_name'") | completed | completed | 1 |
| robustness | KeyError('end_time') | completed | completed | 1 |
| robustness | TypeError("'NetworkLink' object is not subscriptable") | completed | completed | 1 |
| robustness | TypeError("'list_iterator' object is not callable") | completed | completed | 1 |
| robustness | TypeError("unhashable type: 'dict'") | completed | completed | 1 |
| robustness | abnormal_exit | completed | completed | 5 |
| robustness | actual_kv_allocation_overflow | failed | actual_kv_allocation_overflow | 1 |

逐键来源与 SHA256 见 individual.csv。容量不足可复现时属于有效的容量边界，不填零。
