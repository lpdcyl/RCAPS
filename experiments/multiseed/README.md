# 三种子可复现实验

本目录重跑论文当前使用的完整系统比较、挑战二与挑战三的控制变量实验、放置内部消融和挑战一的建模审计。种子为 0、1、2；每个种子、场景、实验各有独立的 `runs/seedN/{single,multi}/实验名.json` 和同名 `.log`。历史探索性调参和废弃策略不属于本批次。

## 实验集合

| 组 | 实验 | 固定参数与目的 |
| --- | --- | --- |
| `paper` | `paper_helix`, `paper_integrated` | 官方负载 700/320 token/s，1800 秒、无预热；原版 Helix 与整合系统 |
| `dev` | `dev_helix`, `dev_integrated` | 400/160 token/s，1980 秒、前 180 秒预热；完整系统对照 |
| `dev` | `dev_scheduler_helix` | 最终放置上运行 Helix 调度，和 `dev_integrated` 比较 |
| `dev` | `dev_placement_helix_layout`, `dev_placement_final_layout` | 同一早期 DAG 调度，比较 Helix 与最终图放置 |
| `dev` | `dev_ablation_before` | 典型路径或粗划分放置，对比 `dev_placement_final_layout` |
| `scheduler_ablation` | `dev_scheduler_serial`, `dev_scheduler_coalesced` | 最终放置上比较串行传输、合并传输及最终修正策略；`coalesced` 仅三集群 |
| `model` | `model_profile` | 300 秒、预热 60 秒，采集 GPU 忙碌占比，检验需求排名 |
| `model_refined` | `model_profile_refined` | 三集群最终细化放置的资源画像，复验原建模审计；仅三集群 |
| `model` | `model_before`, `model_after` | 600 秒、预热 180 秒，检验离线代理模型对局部改动方向的解释 |

每个种子包含单集群 12 次、三集群 14 次，总计 **78 次独立仿真**。固定窗口指标只统计测量窗口内完成的工作，不在结束后排空队列。各组内部同场景、同种子复用相同请求轨迹；完整系统比较同时改变放置和调度，控制变量实验分别隔离这两部分。`model` 的短窗口不能和 1800 秒性能表混用。

## 运行

在仓库根目录，使用安装了 `numpy`, `scipy`, `gurobipy==13.0.3`, `matplotlib`, `networkx` 的 Python：

```powershell
python -m experiments.multiseed.run --dry-run
python -u -m experiments.multiseed.run --workers 6
python -m experiments.multiseed.aggregate
```

`run.py` 支持 `--seeds 0 1 2`、`--scenarios single multi`、`--groups paper dev model model_refined scheduler_ablation` 和 `--python <解释器路径>`。成功的 JSON 会原子写入；再次运行会跳过已完成且协议字段一致的结果。若失败，请看对应 `.log` 并重跑同一命令。运行器只接受 Gurobi 13，并把精确版本写入每个 JSON；旧版本结果不会被复用。`aggregate.py` 必须看到全部 78 项才会产生 [RESULTS.md](RESULTS.md) 与 [summary.json](summary.json)；它核对成对轨迹哈希、请求到达数、Python/NumPy/Gurobi 版本和测量协议。

三个种子的平均值和样本标准差用于显示仿真轨迹波动。原最终放置与调度曾根据种子 1 的开发实验确定，种子 1 不是独立测试集；本实验也不代表真实 GPU 测量。
