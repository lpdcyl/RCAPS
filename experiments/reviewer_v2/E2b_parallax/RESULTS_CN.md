# E2b Parallax（模拟器复现）

70B 画像驱动 CPU 仿真；1800 s 固定窗口、零预热、不排空。
该物理池总容量 152 层，小于两条 80 层流水线所需 160 层；DP 仅能选 k=1。
计算能力以 batch=8 Decode 单层画像耗时倒数近似，不等于原版 TFLOPS。
无真实 Parallax 执行后端、动态成员协议和分布式遥测。

| 拓扑/负载 | 执行器 | 成功 | P95 TPOT s | P95 TTFT s | 吞吐 token/s | 完成率 | GPU s/token | 相对 V4 TPOT 配对变化 |
|---|---|---:|---:|---:|---:|---:|---:|
| single/350 | fifo | 4/5 | — | — | — | — | — | — |
| single/350 | shared | 5/5 | 0.5723 | 3.6478 | 76.38 | 0.935 | 0.0244 | +44.22% ± 1.99pp |
| single/700 | fifo | 2/5 | — | — | — | — | — | — |
| single/700 | shared | 2/5 | — | — | — | — | — | — |
| multi/160 | fifo | 5/5 | 0.9210 | 5.3322 | 34.56 | 0.892 | 0.1240 | +74.78% ± 4.32pp |
| multi/160 | shared | 5/5 | 0.8083 | 5.3284 | 34.94 | 0.911 | 0.0312 | +53.38% ± 2.63pp |
| multi/320 | fifo | 4/5 | — | — | — | — | — | — |
| multi/320 | shared | 2/5 | — | — | — | — | — | — |

仅完整五种子组报告均值与 t(4) 配对 95% CI；失败单列，不填零。
相对 V4 的数字为整体方法差异，不能归因于单独放置、路由或执行器。

## 原失败与独立重放
正式批次 29/40 成功、11 个原失败；独立重放 5/11 成功，6 仍失败。
原失败按 Windows native access violation、Python 异常、KV 容量断言和重启中断分列；重放不替换正式值。
原失败分类：{'windows_native_access_violation': 5, 'python_exception': 3, 'kv_capacity_assertion': 1, 'reboot_interruption': 2}；重放分类：{'success': 5, 'python_exception': 4, 'kv_capacity_assertion': 1, 'windows_native_access_violation': 1}。
逐键来源、错误和 SHA256 见 failure_replay/FINAL_AUDIT.json。
