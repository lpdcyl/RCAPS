# V4 正式三种子执行批次

2026-10-26：主队列因 `single/load700/static/seed1` 原生访问冲突中止；
70 格成功、1 格失败、22 格未启动，没有自动重试。
外部批次 27 格完成。[阶段结果与诊断](../v4_paper/EXECUTION_AUDIT_CN.md)。

正式运行：seed **0/1/2**，1800 秒、零预热、不排空。没有开发种子或正式结果驱动的参数重选。

`protocol.json` 固定方法、指标、既有锚点护栏和失败处理规则；`manifest.json` 在开始前冻结完整输入与源码身份；`index.json` 记录每个进程和状态。新旧实现工程等价性结果见 `preflight.json`。历史偶发类型异常的根因仍未定位，任何新异常将停止派发后续任务，失败不能自动重试或替换。

已实现的队列顺序：

1. 三集群 320/160 的 V3、仅准入、仅分块、完整 V4 四格，24 个窗口。
2. V4 两拓扑六负载主曲线，36 个窗口，扣除与第一组重复的 6 格后新增 30 格。
3. 三集群 320 的规范图、全链路分块、1/2/8 MiB，新增 15 格。
4. 两拓扑锚点的静态路由和单边界放置条件消融，新增 12 格。
5. C2/C3 的 V3 与 V4，新增 12 格。

合计 **93 个去重后的新窗口**。第一组重新运行四个条件，保持同批计量；主曲线的其他 V3/Helix 对照另做历史复用审计。外部五方法资源计量、网络/画像/窗口稳健性尚未纳入本次 93 格，不能把本批完成写成全部论文实验已完成。

使用 `ENVIRONMENT_CN.md` 中的环境变量和 Python 路径，从仓库根目录运行：

```powershell
python -u -m experiments.v4_formal.run --phase freeze
python -u -m experiments.v4_formal.run --phase queue --group mandatory
```

仅执行首批 24 格时将 `--group mandatory` 改为 `--group factorial`。每格独立 Python 进程，最多同时 2 格。队列启动前检查源码、物理配置、布局、模型画像及请求数据哈希；运行结束再检查一次。不能在运行中修改冻结执行源码。

`runs/<scenario>/load<load>/<cell>/seed<seed>/` 内保存 worker.log、result.json 或 failure.json。完成窗口与数值护栏通过是两个不同状态。`--phase report` 可随时整理已有结果，只有齐全 0/1/2 的组才生成三种子均值；初步效果不能用于改参数。

新的分块感知探针覆盖初次发送和每次续传，按实际最终发送结束记录传播阶段；其 `corrected_network_accounting` 替换旧探针不完整的网络服务字段。GPU 忙碌保持旧指标，Prompt-only、Decode-only、mixed 批次工作分开列出；不把混合批次工作按请求数任意分摊。

同链路、发送 NIC、接收 NIC 的 Prompt 占用重叠可能互相重合，不得相加作总阻塞时间；它们是占用重叠证据，不等于全部等待的因果归属。
