# RCAPS V3 期刊版实现方案（交给代码代理执行）

本文件是 V3 投 IEEE Trans 期刊前的补实验与工程整理方案。每个任务卡写明目标、要改或新建的文件、协议、产出与验收标准。执行者按卡片顺序实现；任务之间的依赖在卡片里注明。

科学问题与三个挑战见论文工作区的单独文档。本方案中的任务编号与挑战的对应关系：

| 挑战 | 需要补的证据 | 任务 |
| --- | --- | --- |
| 挑战一：放置目标错位 | 泛化到更多资源池与模型 | T5、T6、T7、T9 |
| 挑战二：慢链路阶段间干扰 | 单集群是否存在同类干扰 | T1 |
| 挑战三：路径锁定 | 单集群完整 DAG 退化的原因与对策；M3 状态消融补齐 | T2、T3 |
| 全部 | 敏感性、开销 | T8、T10 |

## 执行环境

- 全部代码编写与实验运行都在本地仓库 `D:\PythonProject\Helix-GREEN` 完成，包括 1800 秒正式窗口。每张任务卡的实验全部跑完、报告生成后，再提交并推送到 GitHub。
- 命令在仓库根目录用 PowerShell 执行，形式为 `python -m experiments.<目录>.run --phase ...`；并行时用各实验已有的 `--workers` 参数，每个窗口是独立进程。
- **每次启动 Python 前必须固定哈希种子**：在同一个 PowerShell 会话里先执行 `$env:PYTHONHASHSEED="0"` 和 `$env:MPLBACKEND="Agg"`，再运行实验命令。只有 `benchmarks/run.py` 会自动设置 `PYTHONHASHSEED`；`m3_run.py` 等直接调用模拟器的实验入口**不会**自动设置，不设置会导致同一种子、同一代码的两次运行结果不同。每个正式结果 JSON 中须记录运行时的 `PYTHONHASHSEED` 取值（新建实验在写结果时加入 `"pythonhashseed": os.environ.get("PYTHONHASHSEED")` 字段）；已有实验不改代码，在报告中写明运行时的取值。
- **确定性抽查**：每张卡的正式窗口开始前，任选一个 60 秒窗口连续跑两次，确认两次结果除时间类字段外逐项相同；不同则停下报告，不进入正式运行。
- **代码身份比较一律先规范化换行**：Windows 检出的文件是 CRLF，git 中是 LF，字节哈希会不同但内容相同。判断适配器或方法代码"是否被改动"时，比较把 CRLF 统一为 LF 之后的内容；不要因为换行不同而重跑窗口。
- 推送前检查单个文件大小：超过 50 MB 的逐消息事件流（如 `*.jsonl.gz`）只保留在本地，不提交，与 `v3_phase_link_diagnosis` 的现有做法一致；汇总 JSON 与报告必须提交。
- 一张卡的实验没有全部跑完时，不提交该卡的报告；可以先提交代码，提交信息注明"结果待运行"。

## 全局规则（所有任务必须遵守）

1. **冻结内容不可改**：`rcaps/v3/`、`rcaps/v3_layouts/`、`rcaps/v3_method.py` 以及所有已发布实验的 `runs/` 原始结果，逐字节保持不变。新方法候选一律放在 `experiments/<新目录>/`，通过子类或适配器实现。T0.4 是唯一例外，且必须证明行为逐字节等价。
2. **目录规范**：每个新实验目录包含 `README.md`（协议与复现命令）、`run.py`（`--phase smoke|formal|report`）、`index.json`（逐窗口路径、SHA256、状态）、`RESULTS_CN.md`（结果表与判定）。
3. **窗口协议**：除非卡片另有说明，正式窗口为 1800 秒、零预热、窗口末不排空，通过 `benchmarks.fixed_window.run` 运行。环境变量 `PYTHONHASHSEED=0`、`MPLBACKEND=Agg`。
4. **种子**：正式种子固定为 0、1、2，所有任务一律只跑这三个，不增加种子。凡涉及选择（规则阈值、布局、参数），只用开发种子 100 的短窗口做选择，选择结果写入 `*_protocol.json` 并提交，之后才运行正式种子。开发种子不计入正式结果，正式种子不得参与调参。
5. **失败保留**：KV 断言、调度器断言、模拟器 `SystemError` 等失败写成 `.failure.json`，保留异常与日志，不折算为零吞吐，也不删除。
6. **复用规则**：只有方法、协议、布局哈希、物理配置哈希和请求轨迹哈希全部一致时，才复用已有窗口；`index.json` 中标记 `reused` 并记录来源路径。
7. **报告口径**：报告吞吐、P95 TTFT、P95 TPOT、完成率、末端积压，以及两方都完成的共同请求上的 P95。给出逐种子数值、三种子均值 ± 样本标准差和逐种子配对差值，不做显著性检验。
8. **提交粒度**：每张任务卡单独提交，提交信息写明任务编号。

---

## 阶段 0：工程准备（其余所有任务的前提）

### T0.1 合并诊断分支

- 把 `origin/codex/v3-phase-link-mechanism` 合并进 `main`，用 merge commit，不要 rebase。
- `benchmarks/fixed_window.py` 在该分支有改动。合并时逐行核对改动内容，并在提交说明中列出具体改了什么。

**验收**：`main` 包含六个诊断实验目录，合并前后已有实验的结果文件没有变化。

### T0.3 修复命令行入口

- 修复 `benchmarks/fixed_window.py` 的命令行入口：`--method graph` 目前不传 `scheduler_factory`，会直接报错。把 `graph` 改为 `rcaps_v3`，并传入 `GraphModeledQueueAwareDagScheduler`。只改 `main()`，不改 `run()`。

**验收**：`python -m benchmarks.fixed_window --scenario single --method rcaps_v3 --offered 350 --duration 60 --seed 100 --compact --solution rcaps/v3_layouts/single/solution.ini --sim-cluster rcaps/v3_layouts/single/simulator_cluster.ini` 可以跑完。

### T0.4 模型参数化（T6 的前提）

LLaMA-70B 被写死在以下位置：

- `rcaps/v3/topology.py:42`（`ModelManager(ModelName.LLaMa70B, ...)`）
- `benchmarks/fixed_window.py:76`、`:81`
- `experiments/m2_multistage_candidate/runtime_graph_audit.py:31`

做法：
- 给 `TopologyModel.__init__` 增加关键字参数 `model_name=ModelName.LLaMa70B`；给 `fixed_window.run` 增加 `model_name=ModelName.LLaMa70B`。默认值保持 70B。
- `rcaps/v3/topology.py` 属于冻结代码。允许这一处修改的前提是：默认参数下行为逐字节等价，且同步更新 `experiments/v3_release/manifest.json` 中的代码哈希（用 `verify --write-manifest`，并在提交说明里注明原因）。

**验收**：
1. `python -m experiments.v3_release.smoke_parity` 通过：60 秒窗口的轨迹、部署哈希、吞吐、P95、路径计数与改动前逐项一致。
2. `python -m rcaps.v3.plan C1_single --output <临时目录>` 导出的 `solution.ini` 与 `simulator_cluster.ini` 和冻结布局字节一致。

### T0.5 M3 实现说明与系数核实（只读诊断，不改冻结代码）

`rcaps/v3/online_scheduler.py:68-69` 的 `QueueAwareDagScheduler._decode_token_service` 把单 token Decode 服务时间乘以 2，注释写的是"与模拟器执行画像对齐"。论文需要说清这个系数从哪里来。

做法：新建 `experiments/v3_m3_calibration/`：
1. 在 C1 单集群冻结布局上，对每个 GPU 类型（A100/L4/T4），用模拟器实际执行 batch=1 的 Decode（开发种子 100 的短窗口即可，这一步不是正式窗口），记录 `FinishExecution` 的实际时长。
2. 与 `_layer_service(node, layer, Increment, 1)` 的逐层之和对比，报告实际时长与画像之和的比值。
3. 同时记录 `decode_typical_tokens` 和 `decode_max_tokens` 的取值。

**产出**：`RESULTS_CN.md` 写明比值是否接近 2，以及原因（例如模拟器是否对单请求 batch 有额外开销，或画像插值的偏差）。若比值不是 2，只报告，不改冻结代码。

另外：`rcaps/v3/routing.py` 文件头注释描述的是"最早完成时间"的递推，但 V3 实际生效的是 `queue_cost.py` 中 `WorkloadQueueDagScheduler._route` 的累加工作量代价。在 `RESULTS_CN.md` 中给出 M3 实际代价公式（逐项对应代码行号），供论文方法章节使用。

### T0.6 Prefill/Decode 链路干扰模型的离线检验（只做分析，不跑仿真）

**目的**：检验一个简单的排队模型，能否给出链路干扰的正确**方向与排序**，以决定是否把它作为方法升级的核心。本卡**不要求预测数值准确**：离线模型与在线结果本来就不同，标准是它能否选对方案、给对趋势。本卡不修改任何方法代码，也不跑新仿真。

**模型**：每条链路视为非抢占式优先级 M/G/1 队列，Decode 为高优先级（V3 调度器优先发送 Decode），已开始的 Prompt 传输不可抢占。链路 ℓ 上 Decode 消息的期望等待：

```latex
W_{d,\ell} = \frac{\lambda_{p,\ell}\,\mathbb{E}[S_{p,\ell}^2] + \lambda_{d,\ell}\,\mathbb{E}[S_{d,\ell}^2]}{2\,(1-\rho_{d,\ell})},\qquad \rho_{d,\ell}=\lambda_{d,\ell}\,\mathbb{E}[S_{d,\ell}]
```

- λp,ℓ、λd,ℓ：Prompt 与 Decode 消息到达该链路的速率（条/秒）
- Sp,ℓ、Sd,ℓ：单条消息的传输占用时间 = 消息字节数 ÷ 有效带宽，有效带宽为 `min(链路带宽, 发送端 NIC, 接收端 NIC)`，与 `rcaps/v3/routing.py` 的 `_transfer_time` 一致；不含传播延迟
- 若 ρd,ℓ ≥ 1，该链路记为饱和，W 记为无穷大，单独列出
- **模型没有任何可调参数**，不做拟合。不得根据结果修改公式；如需改动，作为新版本另行记录

一个请求的干扰代价 = 其路径上各计算节点间链路的 W 之和。

**新建目录**：`experiments/v3_interference_model/`
- `model.py`：纯函数实现上式，以及由流量份额计算各链路 λ、S 的函数
- `test_model.py`：单元测试。至少覆盖：ρd → 0 时退化为 λp E[Sp²]/2；带宽翻倍时 W 约降为 1/4；λp 减半时 Prompt 项减半
- `analyze.py`：检验 A、B、C，输出 `analysis.json` 与 `RESULTS_CN.md`

**检验 A：链路级排序**（数据：`experiments/v3_phase_link_diagnosis/`）
1. 输入取 `slow_links.csv` 中 baseline 的每一行（变体 k1/k3 × 负载 × 种子 × 链路）：
   - λp = `prompt_messages` ÷ 窗口秒数（600），λd = `decode_messages` ÷ 600
   - E[S] = 平均消息字节 ÷ 有效带宽（`capacity_MBps`）
   - E[S²] 优先从本地逐消息事件流 `runs/**/*.jsonl.gz` 中按消息字节精确计算；事件流不在时，退化为 (E[S])² × (1 + CV²)，CV 取该运行 `query_samples` 中输入 token 数的变异系数，并在报告中标注使用了退化估计
2. 预测值 W 与实测 `decode_wait_mean_s` 对比，计算 Spearman 秩相关：k1、k3 各自一个，合并一个。
3. 同时报告预测值与实测值之比的中位数和四分位距，仅作描述，不作判定依据。

**检验 B：干预方向**（只用 baseline 的输入，按模型推算干预后的 W）
1. **带宽翻倍**：S 减半、ρ 减半后重算 W。比较对象是 `experiments/v3_dynamic_bottleneck_counterfactuals/formal600_report.md` 中的 `k1_bw2` 与 `k3_bw2`。
2. **理想带宽**：S → 0。比较对象是 `v3_phase_link_diagnosis` 中的 `ideal_bandwidth`。
3. **Prompt 字节置零**：λp 项置零。比较对象是 `prompt_zero`。
4. **k1 → k3**：分别用 k1、k3 的 baseline 输入计算路径干扰代价，比较两者大小。

每个干预需判断两件事：
- 模型预测的改善方向，与实测 P95 TPOT 的变化方向是否一致
- k1 的改善是否大于 k3，与实测是否一致

**检验 C：布局排序**（模拟 M2 的用法，完全离线）
1. 布局集合：
   - `experiments/v3_search_sensitivity/` 中三集群的 6 个布局，负载 160、320
   - `experiments/v3_m2_linear_proxy/selection_manifest.json` 中候选池里已有正式在线结果的布局
   - 单集群同理，但单集群链路均为 1 Gbps，干扰很小，结果仅作参考，不参与判定
2. 对每个布局，**不用任何在线结果**估计各链路流量：
   - 请求到达率与输入、输出长度分布取开发种子 100 的轨迹（`OnlineRequestFeeder`，对应负载）
   - 流量在可达后继间均分，与 `rcaps/v3/placement.py` 中 `measure` 的假设一致
   - 每个请求在每条经过的链路上产生 1 条 Prompt 消息和"输出长度"条 Decode 消息，消息字节按 `_transfer_time` 中的 payload 计算
3. 计算布局级干扰代价（按流量加权的路径干扰代价均值），与该布局在线实测的三种子平均 P95 TPOT 求 Spearman 秩相关。
4. 用同一组布局，计算冻结 V3 静态目标 `objective(measure(...))` 与实测 P95 TPOT 的 Spearman，作为对照。

**判定规则（运行前写入 `protocol.json` 并提交，之后不得修改）**：

| 结果 | 结论与后续 |
| --- | --- |
| A 合并 Spearman ≥ 0.6，且 k1、k3 各自 > 0；B 的四项干预方向全部正确；C（三集群 320）的 Spearman > 0 且不低于冻结静态目标 | **全部通过**：干扰模型可以作为方法升级的核心，同时用于 M2 目标与 M3 代价，另开任务卡设计升级版本 |
| A、B 通过，C 不通过 | 模型能解释机制，但不足以替代 M2 目标。只用于 M3 的外部代价（新 Prompt 对已有会话的阻塞）和论文的机制解释 |
| A 或 B 不通过 | 单队列模型不能刻画该干扰（可能是 NIC 共享或多跳耦合的影响更大）。放弃模型驱动的升级，退回 T2 中的针对性修改 |

**产出**：`RESULTS_CN.md` 包含：模型与假设、每项检验的表格（逐行输入、预测、实测）、判定结果，以及模型的已知局限（泊松到达假设、Decode 合并发送、多跳耦合、NIC 共享）。

**验收**：
1. `python -m unittest experiments.v3_interference_model.test_model -v` 通过。
2. `python -m experiments.v3_interference_model.analyze` 可重复运行，输出逐字节相同。
3. `protocol.json` 的提交早于 `analysis.json`（以 git 提交顺序为证）。
4. 读取的每个已有结果文件，在 `analysis.json` 中记录路径与 SHA256。

---

## 阶段 1：补齐故事闭环

### T1 单集群的阶段间干扰诊断（挑战二）

**目的**：确认 Prefill/Decode 链路干扰在单集群（链路均为 1 Gbps）是否也存在、程度多大，从而决定科学问题是否加"跨集群带宽受限"的限定。

**背景**：`experiments/v3_phase_link_diagnosis/` 只在 C1 三集群做了 k1/k3。三集群跨集群链路为 10–15 Mbps，集群内约 1.1–1.4 Gbps；**单集群全部 324 条链路均为 1000 Mbps、1 ms**。原分析在 `run.py` 中用 `capacity_Bps <= 50_000_000` 划定慢链路，单集群没有链路满足，所以本卡改为对**全部计算节点间链路**统计。探针 `probe.py` 本身不含阈值，可直接导入复用。

**新建目录**：`experiments/v3_phase_link_single/`。导入 `experiments/v3_phase_link_diagnosis/probe.py` 的 `PhaseLinkProbe` 和该实验的干预实现（Prompt/Decode 字节置零、理想带宽），不复制代码，不修改原实验目录。

**布局**（3 个）：
- `experiments/v3_m2_branch_parallelism/layouts/C1_single/k1`
- `experiments/v3_m2_branch_parallelism/layouts/C1_single/k3`
- 冻结 V3 单集群布局 `rcaps/v3_layouts/single/`

**负载与窗口**：350、600、700 offered token/s；1800 秒、零预热、不排空；种子 0、1、2；`$env:PYTHONHASHSEED="0"`。

**干预与窗口清单**：

| 干预 | 布局 | 负载 | 种子 | 窗口数 |
| --- | --- | --- | --- | ---: |
| baseline | 3 个 | 350、600、700 | 0、1、2 | 27 |
| prompt_zero | 3 个 | 350、600、700 | 0、1、2 | 27 |
| decode_zero | 3 个 | 判定负载（见下） | 0、1、2 | 9 |
| ideal_bandwidth | 3 个 | 判定负载 | 0、1、2 | 9 |
| 合计 | | | | 72 |

**已知风险**：`v3_m2_branch_parallelism` 中，单集群 k1 在 700 负载下 3 个种子有 2 个触发 KV 容量断言。按全局规则保留 `.failure.json`，不折算、不重跑。

**判定负载**：取 600。若 k1 的 600 baseline 有任一种子失败，改取 350，并在报告中注明。先跑完全部 baseline，确定判定负载后，再运行 decode_zero 与 ideal_bandwidth。

**统计量**（对全部计算节点间链路，不用带宽阈值）：
1. 每条链路：Prompt/Decode 字节数、发送占用率、Decode 消息被同链路 Prompt 阻挡的比例、Decode 平均等待（与 `slow_links.csv` 同口径，输出为 `links.csv`）。
2. Decode 等待中与同链路 Prompt 传输重叠的时间占比。
3. 尾部 5% TPOT 查询与全体查询的阻挡率之差（与三集群报告同口径）。
4. 每个运行的吞吐、P95 TTFT、P95 TPOT、完成率、积压，以及与 baseline 共同完成请求上的 P95。

**判定规则**（写进 README 并单独提交 `protocol.json`，之后才运行正式窗口）：
- 主判定量：在判定负载下，k1 的 prompt_zero 相对 baseline 的 P95 TPOT 下降比例，取三种子均值。
- 若 < 10%：结论为"阶段间干扰主要出现在跨集群带宽受限场景"，科学问题加该限定。
- 若 ≥ 10%：结论为"单集群也存在同类干扰"，按实测比例报告，并与三集群的 39.1% 并列。
- 冻结 V3 布局的同一数值作为附加报告，不参与判定。

**产出**：`RESULTS_CN.md` 包含逐种子表格、与三集群诊断结果的并列对比表，以及判定结论。

### T2 完整 DAG 在单集群退化的原因诊断（挑战三）

**背景**：`experiments/v3_pathspace_ablation/` 显示，冻结 V3 布局上，单集群完整 DAG（62 边、4788 路径）比规范路径（36 边、12 路径）吞吐低 1.05 token/s、P95 TPOT 高 0.053 s；三集群方向相反，完整 DAG 的 P95 TPOT 低 0.125 s。

**步骤 A：诊断**（新建 `experiments/v3_pathspace_mechanism/`）

本步骤只诊断，不改方法。在**两种拓扑**上，用规范路径和完整 DAG 各重跑一遍并加装探针。三集群作为对照：同样的统计量在三集群上方向应当不同，否则解释不成立。

- 规范路径调度器：`experiments/v3_pathspace_ablation/run.py` 中的 `CanonicalGraphDagScheduler`（边集合由同文件 `canonical_edges` 生成），直接导入。
- 完整 DAG 调度器：冻结的 `GraphModeledQueueAwareDagScheduler`。
- 布局：冻结 V3 单集群与三集群布局；负载：单集群 700、三集群 320；1800 秒；种子 0、1、2；`$env:PYTHONHASHSEED="0"`。共 2 拓扑 × 2 路径集合 × 3 种子 = 12 个窗口。

**复现检查（先做）**：探针必须是被动的。12 个窗口的吞吐、P95 TTFT、P95 TPOT、完成率、积压、`route_counts`，必须与已有正式结果逐项相同：规范路径对照 `experiments/v3_pathspace_ablation/runs/formal/`，完整 DAG 对照 `benchmarks/runs/<single|multi>/seed<n>/rcaps_v3.json`。任一不同即停下报告，不进入分析。

**记录**：
1. 每个查询路径经过的计算节点数和计算节点间链路数（参考 `v3_phase_link_diagnosis/run.py` 的 `route_summary`，去掉带宽阈值）。
2. 每个 GPU 上存活的 KV 会话数，每 10 秒采样一次，取时间均值与最大值。
3. 每个 GPU 的 Decode 执行批大小，按 token 加权取均值。
4. 每条计算节点间链路的发送占用率，以及 Decode 被同链路 Prompt 阻挡的比例（与 T1 同口径）。
5. 每个 GPU 的忙碌比例；跨副本边（不在 `canonical_edges` 中的边）的使用次数，以及这些边两端 GPU 的忙碌比例。

**假设与确认标准**（写进 `protocol.json` 先行提交）。每个假设在单集群上"确认"的条件：完整 DAG 相对规范路径，三个种子方向一致，且三种子均值的相对差 ≥ 5%。

| 假设 | 统计量 | 退化方向 |
| --- | --- | --- |
| H1 路径变长 | 每查询计算节点间链路数均值 | 完整 DAG 更多 |
| H2 会话打散、Decode 批变小 | GPU 的 token 加权 Decode 批大小均值 | 完整 DAG 更小 |
| H3 切换点形成热点 | 忙碌比例最高的 3 个 GPU 的忙碌比例均值 | 完整 DAG 更高 |
| H4 链路干扰加重 | 全部计算节点间链路的 Decode 阻挡比例（按消息数加权） | 完整 DAG 更高 |

三集群上报告同样的统计量。若某假设在单集群确认、在三集群方向相反或不显著，记为"可解释拓扑差异"；若两种拓扑方向相同，记为"不能解释拓扑差异"。

**产出**：`RESULTS_CN.md` 含复现检查结果、四个假设的逐种子表格与判定，以及给 T12 的结论："跨副本切换代价"应当针对哪个机制，或者不应保留。

**步骤 B**：原步骤 B 已并入 T12，本卡只做步骤 A。

### T3 补齐 M3 状态消融（挑战三）

**现状**（以合并后的 `main` 为准）：`experiments/v3_method_validation/m3_formal_index.json` 共 20 项。
- 单集群种子 0、1：六个变体齐全（`static`、`full` 为复用，其余 4 个为新跑）。
- 单集群种子 2：只有 `static`、`full`。`runs/m3_formal/single/seed2/` 下有 4 个变体的 `.log`，但没有 `.json` 和 `.failure.json`，日志停在 `arrivals=800` 和 `arrivals=200` 附近，没有异常栈，判断为进程被中断，不是方法失败。
- 三集群种子 0–2：只有 `static`、`full`。

**协议**（全部沿用现有实现，不改任何参数）：
- 入口：`experiments/v3_method_validation/m3_run.py`，变体定义在同目录 `m3_state.py` 的 `VARIANTS`，**不修改这两个文件**。
- 布局：冻结 V3 布局（`rcaps.v3_method.layout`），即 `rcaps/v3_layouts/single/` 与 `rcaps/v3_layouts/multi/`。
- 负载：单集群 700、三集群 320 offered token/s（`m3_run.py` 中的 `LOADS`）。
- 窗口：1800 秒、零预热、不排空；种子 0、1、2；`compact=True`、`record_query_samples=True`。
- 每个变体只改变一项动态状态：

| 变体 | 含义 |
| --- | --- |
| `static` | 静态 DAG，不用实时状态（复用 `v3_core_ablations` 的 B 格） |
| `queue_only` | 只计 GPU 当前执行与排队工作；不计链路等待与 KV 会话 |
| `observed_eft` | 再加入链路等待；不计 KV 会话 |
| `full_no_session` | 完整状态，但去掉 KV 会话定价 |
| `full_no_link` | 完整状态，但去掉动态链路等待 |
| `full` | 冻结 V3 的完整 M3（复用主对照窗口） |

**16 个待跑窗口**：

| # | 拓扑 | 种子 | 变体 | 输出路径（相对 `experiments/v3_method_validation/`） |
| ---: | --- | ---: | --- | --- |
| 1–4 | single | 2 | queue_only、observed_eft、full_no_session、full_no_link | `runs/m3_formal/single/seed2/<变体>.json` |
| 5–8 | multi | 0 | 同上四个 | `runs/m3_formal/multi/seed0/<变体>.json` |
| 9–12 | multi | 1 | 同上四个 | `runs/m3_formal/multi/seed1/<变体>.json` |
| 13–16 | multi | 2 | 同上四个 | `runs/m3_formal/multi/seed2/<变体>.json` |

**执行步骤**：
1. 把 `runs/m3_formal/single/seed2/` 下 4 个残留的 `.log` 移到 `runs/m3_formal/single/seed2/interrupted/`，保留不删，并在 `RESULTS` 中注明。
2. 冒烟：`python -m experiments.v3_method_validation.m3_run --phase smoke --workers 4`（种子 100、60 秒），确认两种拓扑的 4 个变体都能运行。
3. 正式：`python -m experiments.v3_method_validation.m3_run --phase formal --workers 4`。该命令会复用 `static`、`full`，跳过已存在且身份一致的 8 个单集群窗口，只运行上表 16 个。
4. 报告：`python -m experiments.v3_method_validation.m3_run --phase report`，生成 `m3_formal_report.md` 与 `m3_formal_analysis.json`。

**确定性与失败处理**（T3 执行中出现过：未固定 `PYTHONHASHSEED` 的两轮运行中，`single/seed2/observed_eft` 一次通过、一次触发 KV 容量断言）：
- 所有 16 个正式窗口必须在 `PYTHONHASHSEED=0` 下运行。此前未固定哈希种子的各轮结果全部保留在 `runs/m3_formal_audit/<轮次>/` 下作为审计材料，不进入正式汇总；在报告中说明原因。这是按全局规则 3 修正协议，不属于重跑凑数。
- 先把 `single/seed2/observed_eft` 在 `PYTHONHASHSEED=0` 下连续跑两次：
  - 两次结果一致且都通过：正常纳入。
  - 两次一致且都触发 KV 断言：这是该变体的真实结果，保留 `.failure.json`，报告中列为"observed_eft 在单集群种子 2 触发 KV 容量断言"，不折算为零，不再重跑。该变体不含 KV 会话定价，这一失败本身可作为会话定价必要性的证据。
  - 两次结果不一致：停下报告，说明还存在 `PYTHONHASHSEED` 以外的非确定性来源，需要先定位再继续。

**验收**：
1. `m3_formal_index.json` 共 36 项（2 拓扑 × 3 种子 × 6 变体），状态为 `passed`、`reused`，或经上述确定性检查确认的 `failed`；`failed` 项保留 `.failure.json` 并在报告中列出，不重跑凑数。
2. 同一拓扑、同一种子下 6 个变体的 `trace_sha256` 相同（`report` 中的配对检查会自动校验，报错即不通过）。
3. 规范化换行（CRLF 统一为 LF）后，`m3_state.py` 的内容与 git 中已发布版本一致，证明适配器没有被改动。新旧窗口的 `adapter_sha256` 字节哈希可以因换行不同而不同，不作为不通过的理由。
4. 在 `m3_formal_report.md` 末尾追加一张表，列出每一项状态的贡献，按三种子均值与逐种子差值报告：
   - KV 会话定价的贡献 = `full` − `full_no_session`
   - 动态链路等待的贡献 = `full` − `full_no_link`
   - 链路等待在只看队列基础上的贡献 = `observed_eft` − `queue_only`
   - 实时状态整体的贡献 = `full` − `static`

   指标为吞吐、P95 TTFT、P95 TPOT、完成率、末端积压，以及两变体共同完成请求上的 P95 TTFT/TPOT。只陈述方向与数值，不写成显著性结论。

---

### T12 M3 的干扰外部代价与跨副本切换代价（挑战二、三）

**依赖**：T0.6（第二档：模型可作为 M3 外部代价的候选）、T1、T2 步骤 A 全部完成后才执行。T1、T2 步骤 A 结果出来前，可以先写代码和单元测试，但不得运行正式窗口。

**动机**：
- T3 显示，M3 现有的动态链路等待项在有 KV 会话定价时几乎没有增量作用：两种拓扑上 `full − full_no_link` 的 P95 TPOT 差都接近 0。它只看链路忙不忙，不区分是否有 Prompt 在阻塞 Decode。
- T0.6 显示，非抢占式优先级队列模型能给出链路干扰的正确方向与排序。

本卡把该模型推出的"外部代价"加入 M3，使 M3 直接针对挑战二。M2 不变。

**新建目录**：`experiments/v3_m3_interference/`
- `scheduler.py`：`GraphModeledQueueAwareDagScheduler` 的子类 `InterferenceAwareDagScheduler`。构造参数 `externality: bool`、`switch_cost: bool`。
- `test_scheduler.py`：单元测试。
- `run.py`：`--phase parity|dev|formal|report`。

**实现方式**：冻结代码不可改。`_route` 的代价循环在 `rcaps/v3/queue_cost.py` 的 `WorkloadQueueDagScheduler._route` 中，没有可挂接的钩子。因此在子类中**逐字复制**该方法，只在链路代价处加两个钩子调用：

```
score = cost + gpu_cost + link_wait + self._transfer_time(link, request) \
        + self._externality(link, request, decode_rate) + self._switch_penalty(last_uid, node.node_uid)
```

两个开关都关闭时，两个钩子返回 0.0。`test_scheduler.py` 必须包含一个测试：去掉这两个钩子调用后，复制的方法与冻结的 `_route` 源码逐行一致（用 `inspect.getsource` 比较）。

**项 E：干扰外部代价**（来自 T0.6 的模型，无可调参数）

新 Prompt 在计算节点间链路 ℓ 上传输时，给已在该链路上做 Decode 的会话带来的期望额外等待：

```latex
\Delta_\ell = \tfrac{1}{2}\,\lambda_{d,\ell}\,S_{p,\ell}^{2}
```

- Sp,ℓ：该请求 Prompt 在链路 ℓ 上的传输占用时间 = `self._transfer_time(link, request) - link.latency`。
- λd,ℓ：链路 ℓ 上的 Decode 消息速率，每次 `_route` 调用时计算一次：
  - 对每个活跃会话 s（`self.session_paths`，已在 `_active_session_counts` 中清理过期会话），其路径中相邻的两个计算节点 (u, v) 构成它使用的计算节点间链路。
  - 会话 s 的单 token 周期估计 τs = Σ 路径上各 GPU 的 `_decode_token_service(node, 首层, 末层+1, 0)`（按该 GPU 已加载的全部层计算） + Σ 路径上各计算节点间链路的 (latency + 单 token Decode 消息字节 ÷ 有效带宽)。单 token Decode 消息字节 = `token_size + activation_size`，与 `_transfer_time` 的 payload 规则一致。
  - λd,ℓ = Σ 使用链路 ℓ 的会话 1/τs。
- 只对计算节点间链路计入 Δ；source→首节点、末节点→sink 两类链路记 0，因为它们只传 token，不传激活。
- τs 用的是理想单 token 周期，会高估 Decode 速率、也就高估外部代价；这是保守的方向，在报告中写明。
- 外部代价的权重固定为 1，不调。

**项 X：跨副本切换代价**（是否启用由 T2 步骤 A 决定，运行前写入协议）

- T2 步骤 A 中 H1（路径变长）在单集群确认，且记为"可解释拓扑差异"：启用 X。对每条不在 `canonical_edges` 中的边 (u, v)，代价 = D_ref × (latency + 单 token Decode 消息字节 ÷ 有效带宽)。D_ref = 开发种子 100、对应负载轨迹的输出长度中位数，写入协议。
- 只有 H4（链路干扰）被确认：不启用 X，项 E 已覆盖这一机制。
- 只有 H2 或 H3 被确认：本卡不启用 X，在报告中写明需要另行设计，不在本卡内临时设计。
- 四个假设都不成立：不启用 X。

**实验组**：
- V3：冻结 V3，复用已有正式窗口 `benchmarks/runs/<single|multi>/seed<n>/rcaps_v3.json`
- E：只开项 E
- 若启用 X，增加 X（只开项 X）与 E+X（两项都开）

拓扑与负载：单集群 700、三集群 320；1800 秒；种子 0、1、2；`$env:PYTHONHASHSEED="0"`。只有 E 时新跑 6 个窗口，启用 X 时新跑 18 个窗口。

**执行步骤**：
1. **单元测试**：源码一致性测试；对一个手工构造的小场景（两条链路，已知会话数与带宽），验证 Δ 与手算一致；带宽翻倍时 Δ 降为 1/4。
2. **一致性窗口（parity）**：两个开关都关闭，两种拓扑各跑一个 60 秒窗口（开发种子 100）。结果必须与冻结 V3 同条件窗口逐项相同，包括 `route_counts`；不同即停下。
3. **确定性抽查**：项 E 开启的 60 秒窗口连续跑两次，结果逐项相同。
4. **开发窗口（dev）**：开发种子 100，300 秒，两种拓扑，各实验组各一个。只用于发现实现错误，例如外部代价数值异常大、路由全部集中到一条路径；不用于选择任何参数。同时记录 `_route` 调用耗时的 P50、P95。
5. **提交 `protocol.json`**：写明是否启用 X、D_ref 的值、下面的判定规则。单独提交后才能跑正式窗口。
6. **正式窗口与报告**。

**判定规则**（写入 `protocol.json`，提交后不得修改）。一个实验组"可采用"须同时满足：
1. **两种拓扑都不变差**（三种子均值，相对冻结 V3）：吞吐不低于 V3 的 99.5%；完成率不低于 V3 − 0.002；P95 TPOT 不高于 V3 的 101%；P95 TTFT 不高于 V3 的 102%。
2. **至少一种拓扑有改善**：P95 TPOT 在 3 个种子上都低于 V3，且均值降幅 ≥ 2%。

有多个组可采用时，选项数最少的组；只有当项数更多的组在两种拓扑上的 P95 TPOT 均值都更低时，才选它。没有组可采用时，作为负结果报告，冻结 V3 不变。

**机制检查**（报告，不参与判定）：对每个组，用 T1 的口径统计全部计算节点间链路的 Decode 阻挡比例，与 V3 比较。预期项 E 在三集群降低阻挡比例。若 P95 TPOT 改善了而阻挡比例没有下降，在报告中说明改善可能来自其他途径。

**产出**：`RESULTS_CN.md`：逐种子表、三种子均值与配对差、共同完成请求的 P95、阻挡比例、`_route` 开销、判定结论。

**采用后的后续**：若某组被采用，方法记为 V3.1，另开任务卡 T13，用 V3.1 重跑含 M3 的主对照：对 Helix ILP（单集群 700、三集群 320）、四方法共同负载（350、160）、M2 放置消融中的 M2 组，以及负载边界的关键负载点。T13 在 T12 结论出来后再写。

## 阶段 2：泛化与统计严谨性

### T5 42 节点高异构集群

背景：`artifact_evaluation/high_heterogeneity/` 是 Helix 原文的 42 节点集群（含 A100、V100、L4、L4x2、T4、T4x2、T4x4），链路全部 1000 Mbps、1 ms；现成的 Helix ILP、Swarm、Petals、SP 布局都在 `layout_llama70b/` 下。Helix artifact 的在线负载：MaxFlow 2150、Swarm 1450 offered token/s（见 `step3_simulation.py`）。

做法：新建 `experiments/v3_cluster42/`。
1. **V3 规划**：参照 `rcaps/v3/planning_inputs.json` 的结构，为 42 节点新增一个规划用例：物理文件为 `config/cluster42.ini`，模板为 Helix ILP 的 `simulator_cluster.ini`。`seed_state` 用 `search.initial_states` 产生的最优单边界候选；`reference_state` 用 Helix ILP 布局转换成的分段表示（若 Helix 布局不能表示成"共享前段 + 整链副本"的形式，则改用 `seed_state` 作参考，并在 README 写明）。在实验目录内写 `planning_inputs.json`，不修改冻结的那份。
2. 搜索参数与冻结 V3 相同（Beam 64、每阶段 500 次）。记录规划耗时和评分次数。若单次搜索超过 30 分钟，先报告耗时，暂停后续步骤。
3. **适配器**：`benchmarks/layout.py` 的 `MACHINES` 写死了 4 A100、8 L4、12 T4。给 `fixed_window.run` 传入 `machine_counts`（该参数已存在），从 `cluster42.ini` 统计。
4. **对照**：V3、Helix ILP、Swarm、SP。负载点 1450（共同负载）和 2150（Helix 原负载），种子 0、1、2。

**风险**：多卡节点（T4x2、T4x4、L4x2）在 V3 的 `TopologyModel` 中是否有画像需要先确认；`simulator/model_manager/llama2_70b/` 下有对应目录。

### T6 LLaMA-30B

依赖：T0.4。

做法：新建 `experiments/v3_llama30b/`。
1. 用 `model_name=ModelName.LLaMa30B` 在 C1 单集群和三集群上重新规划 V3 布局，规划输入结构同 T5 第 1 步。
2. Helix 的 30B 布局在 `artifact_evaluation/single_cluster/layout_llama30b/` 和 `artifact_evaluation/distributed_clusters/layout_llama30b/` 下。
3. 负载点取 Helix artifact 对 30B 的在线负载（从两个目录的 `step3_simulation.py` 中读出，写入 README），以及 Swarm 的负载作为共同负载点。
4. 对照：V3、Helix ILP、Swarm、SP；种子 0、1、2。

### T7 请求长度分布泛化

背景：`OnlineRequestFeeder` 写死了 `Dataset.AzureConversation` 和 `ArrivalRateSource.AzureConv`。仓库里还有 Azure Code、Alpaca、ShareGPT 的长度数据。

做法：
1. 给 `OnlineRequestFeeder.__init__` 增加关键字参数 `length_dataset=Dataset.AzureConversation` 和 `arrival_source=ArrivalRateSource.AzureConv`，默认值不变。**验收：默认参数下种子 0–2 的轨迹哈希与现有正式结果完全一致。**
2. 给 `fixed_window.run` 透传这两个参数，加入 `trace_sha256` 之外的 `length_dataset` 字段到结果 JSON。
3. 新建 `experiments/v3_workloads/`：在 C1 两拓扑上，用 Azure Code 和 ShareGPT 两种长度分布，比较 V3 与 Helix ILP。负载按"目标输出到达率与 AzureConv 主实验相当"换算（换算公式写入 README），种子 0–2。

### T8 敏感性实验

新建 `experiments/v3_sensitivity/`，三个子实验。所有变化都作用于物理配置文件的副本，副本放在实验目录内，并记录哈希。

1. **跨集群 RTT**（三集群）：把跨集群链路的 `latency` 乘以 {0.5, 1, 2, 4}，带宽不变。对每个倍数，V3 重新规划，Helix ILP 用原布局（Helix 重新求 ILP 太慢，README 中说明这一限制）。负载 320，种子 0–2。
2. **跨集群带宽**（三集群）：跨集群 `bandwidth` 乘以 {0.5, 1, 2, 4}，其余同上。这一项直接检验挑战二：带宽越低，V3 相对 Helix 的优势应越大。
3. **参考 Decode batch**：`TopologyModel(decode_batch=...)` 取 {4, 8, 16}，V3 重新规划；在线调度不变。报告布局是否改变、在线指标是否改变。两拓扑，种子 0–2。

### T9 C2/C3 资源池的 Helix 对照

背景：C2、C3 有 V3 正式窗口，但没有外部基线。

做法：新建 `experiments/v3_pools_baseline/`。
1. `experiments/v3_search_efficiency/run.py` 已实现 Helix ILP 限时求解（`--helix-mode budgeted`），但 `CASES` 只含 `C1_single`、`C1_multi`。在新目录中导入其 worker 逻辑，扩展到 C2、C3（物理文件见 `rcaps/v3/pools/C2|C3/physical.ini`），不改原实验文件。求解上限 300 秒，各重复 3 次，取第一个通过合法性检查（连续层段、容量、物理链路、完整路径）的布局。
2. 对照：V3（复用 C2/C3 已有正式窗口）与 Helix ILP 加原 MaxFlow 调度。负载与已有 C2/C3 窗口相同（C2 160、C3 400），种子 0–2。
3. README 写明：Helix 布局是限时 incumbent，不是原 36000 秒停机策略的结果。

### T10 在线调度开销

做法：新建 `experiments/v3_overhead/`。在单集群 700、三集群 320 的主对照设置下，对种子 0、1、2 各额外跑一次 `profile_scheduler=True`（`fixed_window.run` 已支持），记录 `_route`、`schedule_transmission`、`schedule_execution` 的调用次数、均值、P50、P95（微秒）。Helix 同样跑，记录 `update_scheduler` 等对应开销。开销测量窗口只用于计时，吞吐与延迟仍以主对照窗口为准。结果写入 `overhead.json` 与 `RESULTS_CN.md`。

---

## 阶段 3：理论部分的代码支撑（可选，优先级最低）

### T11 小规模实例上的最优性差距

目的：给 M2 有界搜索一个可量化的近似质量。

做法：新建 `experiments/v3_m2_optimality/`。
1. 从 C1 单集群中取 8 个 GPU 的子集（2 A100、2 L4、4 T4，ID 固定写入 README），构造缩小的物理配置。
2. 在"单边界、后段 1–3 条副本"的结构化空间中，对所有合法布局做穷举：边界取 4 的倍数，GPU 分组与链内顺序全部枚举，层分配用 `placement_utils.allocate`。对每个布局计算冻结目标 `objective(measure(...))`。
3. 用冻结 `search` 在同一子集上运行，报告其最优分数与穷举最优分数之差，以及评分次数之比。
4. 若穷举规模超过 10⁶ 个布局，减少 GPU 数直到可行，并在报告中写明规模。

---

## 建议执行顺序与工作量

| 顺序 | 任务 | 依赖 | 新跑窗口数（估计） | 状态 |
| --- | --- | --- | ---: | --- |
| 1 | T0.1、T0.3–T0.5 | 无 | 少量 60 秒窗口 | 已完成 |
| 1′ | T0.6 | T0.1 | 0（纯离线分析） | 已完成：第二档 |
| 2 | T3 | T0.1 | 16 | 已完成 |
| 3 | T1 | T0.1 | 72 | 待执行，可与 T2 步骤 A 并行 |
| 3′ | T2 步骤 A | T0.1 | 12 | 待执行，可与 T1 并行 |
| 4 | T12 | T0.6、T1、T2 步骤 A | 6（只有项 E）或 18（启用项 X） | 可先写代码与测试，正式窗口等依赖完成 |
| 5 | T13（若 T12 有组被采用） | T12 | 待定 | T12 结论后再写 |
| 6 | T7 | T0.1 | 约 24 | |
| 7 | T8 | T0.1 | 约 70 | |
| 8 | T5 | T0.4 | 约 24 | |
| 9 | T6 | T0.4 | 约 48 | |
| 10 | T9 | T0.1 | 约 6 + 规划 | |
| 11 | T10 | T0.1 | 12 | |
| 12 | T11 | 无 | 离线 | |

所有正式窗口只用种子 0、1、2。T1、T2 步骤 A、T12 决定科学问题的限定和方法是否升级为 V3.1，应在开始写论文正文的评测部分前完成。若 T12 采用了新组，阶段 2 的泛化实验（T5–T9）应使用 V3.1 运行，因此阶段 2 宜在 T12 结论之后开始。
