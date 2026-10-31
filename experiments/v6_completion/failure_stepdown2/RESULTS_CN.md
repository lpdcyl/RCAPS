# 降 token 边界补测

原失败条件保持不变；下表是事先登记的不同负载/Prompt 长度条件，不能替代原失败。
每个方法五种子，1800 s 固定窗口、零预热、不排空。失败不填零。

| 条件 | 方法 | 成功 | P95 TPOT s | P95 TTFT s | 输出 token/s | 完成率 | GPU 秒/token |
|---|---|---:|---:|---:|---:|---:|---:|
| 70b_single_prompt1p5_rate350 | HH | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_single_prompt1p5_rate350 | HHplus | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_single_prompt1p5_rate350 | V4 | 5/5 | 0.4318 ± 0.0100 | 4.3976 ± 0.0392 | 56.4594 ± 1.4667 | 0.9090 ± 0.0135 | 0.1224 ± 0.0055 |
| 70b_multi_prompt1p5_rate160 | HH | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt1p5_rate160 | HHplus | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt1p5_rate160 | V4 | 5/5 | 0.5800 ± 0.0229 | 7.1507 ± 0.5865 | 25.0660 ± 1.1975 | 0.8832 ± 0.0179 | 0.1280 ± 0.0157 |
| 30b_multi_rate525 | HH | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 30b_multi_rate525 | HHplus | 4/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 30b_multi_rate525 | V4 | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |

## 失败原因

- 30b_multi_rate525/HH: AttributeError("'RequestLocation' object has no attribute 'location_history'") × 1
- 30b_multi_rate525/HH: abnormal_exit × 4
- 30b_multi_rate525/HHplus: controller_or_worker_abnormal_exit × 1
- 30b_multi_rate525/V4: abnormal_exit × 1
- 30b_multi_rate525/V4: actual_kv_allocation_overflow × 3
- 30b_multi_rate525/V4: controller_or_worker_abnormal_exit × 1
- 70b_multi_prompt1p5_rate160/HH: helix_admission_no_eligible_next_node × 5
- 70b_multi_prompt1p5_rate160/HHplus: helix_admission_no_eligible_next_node × 5
- 70b_single_prompt1p5_rate350/HH: helix_admission_no_eligible_next_node × 5
- 70b_single_prompt1p5_rate350/HHplus: helix_admission_no_eligible_next_node × 5

结果仅为模拟器条件边界。完成与否本身是结果；没有五种子成功组时不计算配对 CI。
