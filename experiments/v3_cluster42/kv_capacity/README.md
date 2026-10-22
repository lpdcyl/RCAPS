# 并发 KV 容量约束的少卡实验

在仓库根目录用现有 Python 环境执行。该工作是 CPU 事件模拟，不需要真实 GPU 部署。

```powershell
$env:PYTHONHASHSEED='0'
python -m experiments.v3_cluster42.test_kv_admission
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_capacity --phase smoke --candidate c400k_w3_b1
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_capacity --phase screening --candidate c400k_w3_b1
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_capacity --phase screening --candidate helix
python -m experiments.v3_cluster42.capacity_report
```

选型后，先在 protocol.json 中冻结正式候选，再提交协议，之后执行：

```powershell
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_capacity --phase formal --seed 0
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_capacity --phase formal --seed 1
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_capacity --phase formal --seed 2
python -m experiments.v3_cluster42.capacity_report
```

每次调用保存 JSON 和同名日志。已有 JSON 会复用，并校验候选、种子、负载和时长；不同源码/布局的实验应使用新候选名或新目录，不能覆盖旧结果。失败保存 failure.json，CLI 返回非零。正式 Helix 基线复用原始 42 节点完整窗口并逐项核对输入与轨迹哈希；screening 使用新运行的 600 秒配对 Helix。

布局已经保存，通常无需重新生成。重生成命令如下，只应输出到新目录以保留历史布局：

```powershell
python -m experiments.v3_cluster42.memory_plan --min-kv-tokens 400000 --destination experiments/v3_cluster42/kv_capacity_new
```

400000 token/驻留层是并发余量设计约束，不是物理显存扩容，也不保证在线性能。在线准入仍按每请求输入长度与公开输出长度上限做全生命周期预约，等待时间计入 TTFT。协议、原始结果、analysis.json 和 RESULTS_CN.md 共同构成证据。
