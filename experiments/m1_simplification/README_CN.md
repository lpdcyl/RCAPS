# M1 静态资源代价候选：第一阶段复现

本目录验证仅替换离线放置评价器后的结果。`rcaps/placement/static_resource.py` 使用 GPU 性能画像、物理链路及各后缀等权资源负担计算确定性代价；等权是候选比较权重，不预测未来流量。评价器没有请求到达轨迹、队列状态或多请求事件 DAG。字段 `ttft_s`、`tpot_s` 是为了复用原搜索目标函数而保留的接口名，在本候选中分别代表孤立路径的 Prefill、Decode 代价代理，不是在线尾延迟预测。

新候选保留 V2 的 M2 搜索空间、初始化、邻域、16 轮上限、参考布局及 0.40／0.35／0.25 目标权重；在线使用同一个 `QueueAwareDagScheduler`。冻结 V2 布局与旧实验记录不被覆盖。

## 复现顺序

从仓库根目录运行：

```powershell
python -m unittest experiments.m1_simplification.test_static_resource -v
python -m experiments.m1_simplification.prepare
python -m experiments.m1_simplification.run --dry-run
python -m experiments.m1_simplification.run
python -m experiments.m1_simplification.report
```

`prepare` 将布局写入本目录 `layouts/`，用既有布局审计器核对显存、层覆盖、链路和 KV 容量，并计算层连续的源到汇路径数。`run` 先核验已有强静态模型与冻结 V2 窗口的部署文件 SHA256、在线方法、负载、种子、轨迹和请求身份；全部匹配即复用，只有缺失或不匹配的窗口才在本目录 `runs/` 重跑。每次新运行使用 1800 秒固定窗口、零预热、末端不排空；失败日志保留在相应 `.log` 文件。

`report` 输出 `summary.json` 与 `RESULTS_CN.md`。本次两个拓扑的布局文件均与旧强静态模型对照逐字节相同，六对正式窗口全部通过审计并复用，没有新跑 1800 秒仿真。

本阶段只检验“取消多请求预测后的静态放置评价”。统一的资源图接口、论文主表替换和最终方法命名尚未进行；三个种子不用于显著性或等效性结论。
