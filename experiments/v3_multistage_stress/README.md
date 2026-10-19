# 多级复制合成层热点压力验证

本目录只用于独立压力实验，不修改冻结 V3，也不把逐层知情适配器视为冻结 V3 的组成部分。新资源池从 C1 单集群确定性移除原编号 21、23 的两张 L4，得到 4 A100、6 L4、12 T4。计算画像与链路参数由 C1 原文件继承；所有层热点均为**合成成本**，不是 LLaMA 的逐层实测画像。

## 对照

- 中段 `[32,48)` 的 Prompt/Decode 成本倍率：1、2、4。倍率 4 为主场景，150、300、450 offered token/s；倍率 1 和 2 在 300 点。
- 前段 `[0,16)` 成本倍率 4，在 300 点。
- 每场景比较单边界和最多双边界，以及统一画像与逐层知情两种放置评分信息。两者的在线模拟都使用相同的合成成本和冻结 M3。
- 固定见证布局 `1→4→1`、边界 32/48、128 层副本，作为结构潜力诊断；它不参与搜索选优。
- 主场景 300 点增加时间突发：600–900 秒为均匀到达强度 2 倍，其他时段为 0.8 倍。它保持请求数、长度与顺序，仅改变到达时间。此项检验时间突发鲁棒性，不是请求类别偏斜。

每点使用相同种子 0、1、2，1800 秒、零预热且不排空。先使用种子 100 的 60 秒窗口检查合法性与运行路径。相同部署文件和执行语义的窗口根据哈希复用。失效与不可行保留原记录，不补指标。

## 复现

从仓库根目录运行：

```powershell
python -m experiments.v3_multistage_stress.plan
python -m experiments.v3_multistage_stress.audit_layouts
python -m experiments.v3_multistage_stress.run smoke --workers 4
python -m experiments.v3_multistage_stress.run formal --workers 12
python -m experiments.v3_multistage_stress.report
```

`plan_index.json` 记录结构与规划代价；`layout_audit.json` 逐一核验部署文件的层覆盖、显存/KV 容量和 M1 DAG 边；`smoke_index.json`、`formal_index.json` 给出逐窗口来源和哈希；`runs/` 保存请求样本、执行路径与日志；`analysis.json` 保存逐种子、配对差值、未完成等待分布与共同完成请求尾延迟。`RESULTS_CN.md` 是简表，`mid_hotspot_curve.png` 是主场景曲线。

只有逐层知情的多级放置在同场景、同负载下优于逐层知情的单边界放置，才能说明多级结构在该**合成热点**下有在线价值。若统一画像放置不能识别热点，必须说明冻结 V3 当前不具备逐层热点自适应能力。三个种子只描述波动。
