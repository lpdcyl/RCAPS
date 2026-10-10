# 自适应共享与复制结构：V2 实验

本实验从冻结的 `v1.0.0-research` 标签出发，仅改变离线放置。`rcaps_v2` 自动选择 A100 共享前缀设备数、前缀层数及两条或三条完整后缀；`rcaps_v2_fixed_structure` 使用同一 V2 搜索和代理，但限制为单 GPU、12 层共享前缀及两条后缀。两者与 V1 `rcaps` 均使用相同的 `QueueAwareDagScheduler`。

## 生成布局

在仓库根目录运行：

```bash
python -m rcaps.placement.adaptive --scenario single --variant adaptive --output-dir rcaps/v2_layouts/single_adaptive
python -m rcaps.placement.adaptive --scenario multi --variant adaptive --output-dir rcaps/v2_layouts/multi_adaptive
python -m rcaps.placement.adaptive --scenario single --variant fixed --output-dir rcaps/v2_layouts/single_fixed
python -m rcaps.placement.adaptive --scenario multi --variant fixed --output-dir rcaps/v2_layouts/multi_fixed
```

搜索使用固定六请求事件图代理，前缀只使用 A100，全部 24 张 GPU 各承载至少一层；不读取待测请求轨迹。`placement.json` 保存所选结构、代理分数、候选评估次数和放置耗时。

## 完整窗口对照

```bash
python -m benchmarks.run --methods rcaps_v2 rcaps_v2_fixed_structure --scenarios single multi --seeds 0 1 2 --duration 1800 --workers 4 --results-dir benchmarks/runs
python -m experiments.adaptive_v2.aggregate
```

共最多 12 次新增完整运行；V1 结果仅在同拓扑、种子、负载、窗口和请求轨迹哈希一致时复用。V2 两组完整运行启用相同的资源画像；V1 的旧结果未启用该画像，因此逐 GPU 排队只在两组 V2 之间直接比较。短时画像开关校验记录于聚合报告。所有结论只针对当前仿真与三个开发种子，不据此宣称统计显著。
