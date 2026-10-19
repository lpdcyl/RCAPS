# V3 多级复制合成层热点压力验证

此实验的逐层热点为合成画像；逐层知情适配器不属于冻结 V3。
下表均为种子 0/1/2 的完整 1800 秒窗口，未完成窗口留空。

## 离线结构

| 信息条件/场景/结构 | 边界 | 各段副本数 | 层副本量 | 启用 GPU | 瓶颈资源 | 评分次数 | 规划秒数 |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| uniform/mid_x1/single | [48] | [1, 2] | 112 | 16 | gpu:0 | 728 | 25.69 |
| uniform/mid_x1/multi | [48, 77] | [1, 2, 3] | 115 | 17 | gpu:0 | 772 | 25.69 |
| layer_aware/mid_x1/single | [48] | [1, 2] | 112 | 16 | gpu:0 | 728 | 27.44 |
| layer_aware/mid_x1/multi | [48, 77] | [1, 2, 3] | 115 | 17 | gpu:0 | 772 | 27.44 |
| layer_aware/mid_x2/single | [77] | [1, 3] | 86 | 13 | gpu:0 | 728 | 27.80 |
| layer_aware/mid_x2/multi | [77] | [1, 3] | 86 | 13 | gpu:0 | 896 | 27.80 |
| layer_aware/mid_x4/single | [79] | [1, 3] | 82 | 12 | gpu:10 | 690 | 27.58 |
| layer_aware/mid_x4/multi | [20, 26] | [1, 2, 1] | 86 | 11 | gpu:6 | 946 | 27.58 |
| layer_aware/front_x4/single | [76] | [1, 3] | 88 | 11 | gpu:6 | 578 | 27.39 |
| layer_aware/front_x4/multi | [24, 28] | [1, 2, 1] | 84 | 10 | gpu:6 | 742 | 27.39 |

## 在线结果

| 场景 | 负载 | 到达 | 布局 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | 实际路径数 | 跨副本请求比 |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mid_x1 | 300 | uniform | uniform_single | 66.059 | 3.325 | 0.459 | 0.945 | 29.7 | 57.7 | 0.918 |
| mid_x1 | 300 | uniform | uniform_multi | 66.026 | 3.194 | 0.459 | 0.945 | 29.7 | 77.3 | 0.852 |
| mid_x1 | 300 | uniform | aware_single | 66.059 | 3.325 | 0.459 | 0.945 | 29.7 | 57.7 | 0.918 |
| mid_x1 | 300 | uniform | aware_multi | 66.026 | 3.194 | 0.459 | 0.945 | 29.7 | 77.3 | 0.852 |
| mid_x1 | 300 | uniform | witness | 65.894 | 3.616 | 0.498 | 0.943 | 30.7 | 141.7 | 0.903 |
| mid_x2 | 300 | uniform | uniform_single | 65.745 | 3.511 | 0.514 | 0.941 | 31.7 | 58.3 | 0.935 |
| mid_x2 | 300 | uniform | uniform_multi | 65.733 | 3.471 | 0.514 | 0.941 | 32.0 | 75.7 | 0.846 |
| mid_x2 | 300 | uniform | aware_single | 65.763 | 3.600 | 0.533 | 0.941 | 32.0 | 3.0 | 0.000 |
| mid_x2 | 300 | uniform | aware_multi | 65.763 | 3.600 | 0.533 | 0.941 | 32.0 | 3.0 | 0.000 |
| mid_x2 | 300 | uniform | witness | 64.688 | 4.971 | 0.740 | 0.917 | 44.7 | 154.0 | 0.935 |
| mid_x4 | 150 | uniform | uniform_single | 33.129 | 3.604 | 0.503 | 0.931 | 18.7 | 47.7 | 0.935 |
| mid_x4 | 150 | uniform | uniform_multi | 33.142 | 3.618 | 0.498 | 0.931 | 18.7 | 64.7 | 0.873 |
| mid_x4 | 150 | uniform | aware_single | 33.215 | 3.433 | 0.494 | 0.937 | 17.0 | 3.0 | 0.000 |
| mid_x4 | 150 | uniform | aware_multi | 33.257 | 3.276 | 0.479 | 0.938 | 16.7 | 2.0 | 0.000 |
| mid_x4 | 300 | uniform | uniform_single | 65.296 | 3.914 | 0.610 | 0.933 | 36.3 | 55.7 | 0.920 |
| mid_x4 | 300 | uniform | uniform_multi | 65.272 | 3.917 | 0.608 | 0.932 | 37.0 | 71.7 | 0.848 |
| mid_x4 | 300 | uniform | aware_single | 65.152 | 4.214 | 0.674 | 0.930 | 37.7 | 3.0 | 0.000 |
| mid_x4 | 300 | uniform | aware_multi | 65.264 | 3.791 | 0.632 | 0.931 | 37.3 | 2.0 | 0.000 |
| mid_x4 | 300 | uniform | witness | 61.827 | 7.603 | 1.255 | 0.859 | 76.0 | 155.3 | 0.932 |
| mid_x4 | 450 | uniform | uniform_single | 100.856 | 4.318 | 0.708 | 0.914 | 71.3 | 61.3 | 0.917 |
| mid_x4 | 450 | uniform | uniform_multi | 100.877 | 4.316 | 0.700 | 0.913 | 72.0 | 81.3 | 0.839 |
| mid_x4 | 450 | uniform | aware_single | 99.355 | 4.701 | 0.887 | 0.897 | 85.3 | 3.0 | 0.000 |
| mid_x4 | 450 | uniform | aware_multi | 100.018 | 4.389 | 0.801 | 0.903 | 80.3 | 2.0 | 0.000 |
| front_x4 | 300 | uniform | uniform_single | 65.383 | 4.102 | 0.594 | 0.935 | 35.3 | 55.3 | 0.922 |
| front_x4 | 300 | uniform | uniform_multi | 65.397 | 4.008 | 0.589 | 0.934 | 35.7 | 77.0 | 0.875 |
| front_x4 | 300 | uniform | aware_single | 65.313 | 4.036 | 0.633 | 0.933 | 36.3 | 3.0 | 0.000 |
| front_x4 | 300 | uniform | aware_multi | 65.305 | 3.744 | 0.630 | 0.933 | 36.3 | 2.0 | 0.000 |
| front_x4 | 300 | uniform | witness | 64.968 | 4.474 | 0.689 | 0.924 | 41.3 | 146.0 | 0.903 |
| mid_x4 | 300 | burst | uniform_single | 66.055 | 4.032 | 0.742 | 0.945 | 29.7 | 54.7 | 0.926 |
| mid_x4 | 300 | burst | uniform_multi | 66.074 | 4.170 | 0.738 | 0.946 | 29.3 | 75.0 | 0.850 |
| mid_x4 | 300 | burst | aware_single | 66.066 | 4.608 | 0.952 | 0.945 | 29.7 | 3.0 | 0.000 |
| mid_x4 | 300 | burst | aware_multi | 66.165 | 4.140 | 0.851 | 0.948 | 28.3 | 2.0 | 0.000 |
| mid_x4 | 300 | burst | witness | 63.569 | 7.872 | 1.429 | 0.890 | 59.3 | 152.3 | 0.932 |

## 同场景配对差值

正值表示左侧布局高于右侧；TTFT/TPOT 的负值表示左侧更快。
仅三种子齐全时汇总。

| 场景/负载/到达 | 对比 | 吞吐差 | P95 TTFT 差 | P95 TPOT 差 | 完成率差 |
| --- | --- | ---: | ---: | ---: | ---: |
| mid_x1/300/False | aware_multi-aware_single | -0.032 | -0.131 | +0.000 | +0.000 |
| mid_x1/300/False | uniform_multi-uniform_single | -0.032 | -0.131 | +0.000 | +0.000 |
| mid_x1/300/False | aware_multi-uniform_multi | +0.000 | +0.000 | +0.000 | +0.000 |
| mid_x1/300/False | witness-aware_single | -0.164 | +0.291 | +0.040 | -0.002 |
| mid_x2/300/False | aware_multi-aware_single | +0.000 | +0.000 | +0.000 | +0.000 |
| mid_x2/300/False | uniform_multi-uniform_single | -0.012 | -0.040 | +0.000 | -0.001 |
| mid_x2/300/False | aware_multi-uniform_multi | +0.030 | +0.129 | +0.019 | +0.000 |
| mid_x2/300/False | witness-aware_single | -1.075 | +1.371 | +0.207 | -0.023 |
| mid_x4/150/False | aware_multi-aware_single | +0.042 | -0.156 | -0.016 | +0.001 |
| mid_x4/150/False | uniform_multi-uniform_single | +0.013 | +0.014 | -0.005 | +0.000 |
| mid_x4/150/False | aware_multi-uniform_multi | +0.114 | -0.342 | -0.020 | +0.007 |
| mid_x4/300/False | aware_multi-aware_single | +0.111 | -0.423 | -0.042 | +0.001 |
| mid_x4/300/False | uniform_multi-uniform_single | -0.024 | +0.002 | -0.003 | -0.001 |
| mid_x4/300/False | aware_multi-uniform_multi | -0.008 | -0.126 | +0.025 | -0.001 |
| mid_x4/300/False | witness-aware_single | -3.326 | +3.389 | +0.581 | -0.071 |
| mid_x4/300/True | aware_multi-aware_single | +0.099 | -0.468 | -0.101 | +0.002 |
| mid_x4/300/True | uniform_multi-uniform_single | +0.019 | +0.139 | -0.004 | +0.001 |
| mid_x4/300/True | aware_multi-uniform_multi | +0.091 | -0.031 | +0.113 | +0.002 |
| mid_x4/300/True | witness-aware_single | -2.497 | +3.263 | +0.477 | -0.055 |
| mid_x4/450/False | aware_multi-aware_single | +0.663 | -0.312 | -0.086 | +0.006 |
| mid_x4/450/False | uniform_multi-uniform_single | +0.021 | -0.003 | -0.008 | -0.001 |
| mid_x4/450/False | aware_multi-uniform_multi | -0.859 | +0.073 | +0.101 | -0.010 |
| front_x4/300/False | aware_multi-aware_single | -0.008 | -0.292 | -0.003 | -0.000 |
| front_x4/300/False | uniform_multi-uniform_single | +0.014 | -0.094 | -0.005 | -0.001 |
| front_x4/300/False | aware_multi-uniform_multi | -0.092 | -0.264 | +0.040 | -0.001 |
| front_x4/300/False | witness-aware_single | -0.344 | +0.438 | +0.056 | -0.009 |
