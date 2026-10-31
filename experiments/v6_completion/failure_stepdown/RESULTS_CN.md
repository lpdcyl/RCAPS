# 降 token 边界补测

原失败条件保持不变；下表是事先登记的不同负载/Prompt 长度条件，不能替代原失败。
每个方法五种子，1800 s 固定窗口、零预热、不排空。失败不填零。

| 条件 | 方法 | 成功 | P95 TPOT s | P95 TTFT s | 输出 token/s | 完成率 | GPU 秒/token |
|---|---|---:|---:|---:|---:|---:|---:|
| 70b_single_prompt2_rate350 | HH | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_single_prompt2_rate350 | HHplus | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_single_prompt2_rate350 | V4 | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt2_rate160 | HH | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt2_rate160 | HHplus | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt2_rate160 | V4 | 5/5 | 0.5618 ± 0.0040 | 8.0415 ± 0.1035 | 8.7150 ± 1.2403 | 0.5806 ± 0.0559 | 0.2167 ± 0.0103 |
| 70b_single_prompt3_rate350 | HH | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_single_prompt3_rate350 | HHplus | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_single_prompt3_rate350 | V4 | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt3_rate160 | HH | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt3_rate160 | HHplus | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |
| 70b_multi_prompt3_rate160 | V4 | 5/5 | 0.5623 ± 0.0140 | 6.4936 ± 0.2868 | 3.1663 ± 0.1807 | 0.4438 ± 0.0346 | 0.2813 ± 0.0119 |
| 30b_multi_rate630 | HH | 5/5 | 0.6609 ± 0.0078 | 4.8787 ± 0.0212 | 144.4157 ± 2.1628 | 0.9537 ± 0.0022 | 0.1033 ± 0.0019 |
| 30b_multi_rate630 | HHplus | 5/5 | 0.8339 ± 0.0255 | 4.8667 ± 0.0186 | 143.9690 ± 2.1078 | 0.9488 ± 0.0020 | 0.0223 ± 0.0006 |
| 30b_multi_rate630 | V4 | 0/5 | 未汇总 | 未汇总 | 未汇总 | 未汇总 | 未汇总 |

## 失败原因

- 30b_multi_rate630/V4: actual_kv_allocation_overflow × 5
- 70b_multi_prompt2_rate160/HH: helix_admission_no_eligible_next_node × 5
- 70b_multi_prompt2_rate160/HHplus: helix_admission_no_eligible_next_node × 5
- 70b_multi_prompt3_rate160/HH: helix_admission_no_eligible_next_node × 5
- 70b_multi_prompt3_rate160/HHplus: helix_admission_no_eligible_next_node × 5
- 70b_single_prompt2_rate350/HH: helix_admission_no_eligible_next_node × 5
- 70b_single_prompt2_rate350/HHplus: helix_admission_no_eligible_next_node × 5
- 70b_single_prompt2_rate350/V4: actual_kv_allocation_overflow × 5
- 70b_single_prompt3_rate350/HH: helix_admission_no_eligible_next_node × 5
- 70b_single_prompt3_rate350/HHplus: helix_admission_no_eligible_next_node × 5
- 70b_single_prompt3_rate350/V4: actual_kv_allocation_overflow × 5

结果仅为模拟器条件边界。完成与否本身是结果；没有五种子成功组时不计算配对 CI。
