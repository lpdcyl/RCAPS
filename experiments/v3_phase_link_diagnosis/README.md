# V3 Prefill/Decode 慢链路机制验证

本实验检查 V3 复制分支是否减轻已开始的 Prompt 激活传输对 Decode 的等待。V3 调度器会优先发送已经就绪的 Decode；链路没有 FIFO 队列，已开始的传输在现有模拟器中不可抢占。

## 复现

从仓库根目录按顺序执行，正式任务串行运行：

```powershell
python -m experiments.v3_phase_link_diagnosis.run --phase smoke
python -m experiments.v3_phase_link_diagnosis.run --phase formal --section high
python -m experiments.v3_phase_link_diagnosis.run --phase formal --section baseline
python -m experiments.v3_phase_link_diagnosis.run --phase formal --section intervention
python -m experiments.v3_phase_link_diagnosis.run --phase formal --section ideal
python -m experiments.v3_phase_link_diagnosis.run --phase formal --section kv
python -m experiments.v3_phase_link_diagnosis.run --phase analyze
python -m experiments.v3_phase_link_diagnosis.chunk_run --phase smoke
python -m experiments.v3_phase_link_diagnosis.chunk_run --phase formal
python -m experiments.v3_phase_link_diagnosis.run --phase confirm
python -m experiments.v3_phase_link_diagnosis.chunk_run --phase confirm
```

`formal` 使用固定 600 秒、不排空窗口，负载 160、320、350，种子 1–3。高负载按 350、340、330 顺序选择 k1/k3 全部种子都可执行的第一个值；失效窗口保留为 `.failure.json`，不折算为零吞吐。`confirm` 只在预注册的尾部富集和 Prompt 置零门槛通过后运行 1800 秒。各结果带有布局、资源配置及运行代码哈希，匹配的结果可复用；修改代码后应另开结果目录重新运行。

## 输出

- `formal_report.md`、`analysis.json`：逐种子结果与解释。
- `slow_links.csv`：逐慢速计算节点间链路的 Prompt/Decode 字节、占用率和等待；阻挡比例由原始发送事件重算，以该链路全部 Decode 消息为分母。
- `interference_components.csv`：Decode 消息等待中同链路 Prompt、共享 NIC Prompt 及两者交叠的时间；并集只计一次。
- `interventions.csv`：置零及理想带宽干预的配对变化。
- `confirm_interventions.csv`：1800 秒窗口的字节干预及共同完成查询配对结果。
- `tail_query_bootstrap.json`：以查询为单位抽样的尾部阻挡率差值区间。
- `blocking_vs_utilization.png`：逐慢链路发送占用率和 Decode 阻挡比例。
- `load_vs_interference.png`：随负载变化的最忙慢链路占用率与其 Decode 阻挡比例，细点为各随机种子。
- `runs/**/**/*.json`：每窗口原始汇总指标和查询样本；同名 `.jsonl.gz` 是逐消息事件流，因体积大只在本地保留，可用脚本重跑生成。

从 GitHub 克隆后，汇总 JSON 与表格可直接查看。若要重新生成逐消息分析，先备份并移走本实验的 `runs/` 结果目录，再按上述顺序运行；运行器会复用已有的同身份 JSON，因此仅缺少 `.jsonl.gz` 时不会自动重跑。完整正式窗口会重新生成本地逐消息事件流。

Prompt/Decode 置零仅移除计算节点间激活字节，保留 token 字节、传播延迟、计算、KV、布局和到达轨迹。理想带宽把链路和 NIC 带宽同比放大一百万倍，传播延迟保持不变。分块对照仅把计算节点间的 Prompt 传输切成固定 1 MiB 块，在块间调用现有 Decode 优先调度；请求在全部块传完并经过一次传播延迟后才能进入下一计算节点。它是与 [MoLink](https://aclanthology.org/2025.findings-emnlp.957/) 相关的机制对照，不是新颖性主张。

尾部查询依据现有基准的每查询平均 TPOT 取最高 5%，仅包含窗口内至少两个输出 token 的查询；阻挡步骤只计第二个及以后已完成的 Decode。请求级等待分量不直接相加为查询级 TPOT。KV 断言表示仿真窗口失效；本实验不据此推断真实系统会崩溃。
