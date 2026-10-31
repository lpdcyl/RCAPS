# V6 实验持续运行交接

日期：2026-10-29（韩国时间）。所有命令使用 Windows 的 D:/software/miniconda/envs/gllm/python.exe，仓库根目录 D:/PythonProject/Helix-GREEN。用户要求完成 P0/P1/P2 中可用 CPU 离散事件模拟完成的项目；真机网络微基准 P1-2 与 Sarathi 式计算侧 chunked-prefill P2-3 跳过，不伪称为模拟结果。

## 已结案

- 30B 原正式主批次仍为 69/80 成功，11 个失败键独立重放仍 11/11 失败（6 个 Helix 准入、5 个实际 KV 分配溢出）。
- 原 V5 失败共 99 键独立重放，31 成功、68 失败，原正式结果不替换。
- P1-6 放置权重离线搜索 12/12 完成，FINAL_AUDIT.json 为 passed=true。
- P2-1 的 48/96 GPU 离线搜索已完成；原搜索源码保存在 scalability/search_source_v1.py。首次在线 smoke 是 CLI 参数解析错误，原失败保留；修正版 smoke_v2 通过。

## 正在运行

以下各 formal/index.json 是权威状态；不要因为看到 running 而重新启动。正式批次分别为 generalization 180、session_cost 80、robustness 270、weight_online 60、session_capacity 160、bandwidth_threshold 140、scalability 10 窗口。均已登记不可变 manifest 和 frozen_runtime_inputs.zip；不要在各批次终结前修改对应的 .py 运行脚本。

后台控制会话先前已存在：generalization 1797、session_cost 27746；本轮新启动 robustness 86830、weight_online 63220、session_capacity 91098、bandwidth_threshold 82063、scalability 13232。会话号仅是诊断提示，不能据此判定仍在运行；以 index 与 worker PID/原始产物为准。

watchdog 每分钟汇总各批次进度到 watchdog/status.json。最初会话 48385 因匿名材料输出顺序修正而主动停止，记录保留在 watchdog/intentional_restart_amendment.json；随后会话 63322 在 2026-10-29 约 02:34（韩国时间）因 Windows 状态文件替换遇 WinError 5 退出。已给 watchdog.py 的状态写入增加短退避重试，并于约 02:39 以 PID 48368 恢复，详见 watchdog/RECOVERY_20261029_CN.md。旧 error.json 保留事故记录，不能仅凭它判断当前状态。全部批次 terminal 后，watchdog 会逐批重建报告、生成 Decode 批量统计、独立重放 V6 失败键、冻结重放输入、执行统一重建脚本、生成六组图表与匿名衍生证据包，并写 STATUS_CN.md。当前失败时看最新 watchdog/status.json、error.json 与 steps.log；不覆盖任何原始窗口。

长 Prompt 条件现有失败包括 Helix 无可接纳下游、真实 KV 容量溢出，以及 prompt4 下 RCAPS 的请求超过已有 0..7500 token 的 Prompt 性能画像范围；最后一类是画像外推边界，不应混作 KV 失败。首次正式失败不填零。新失败键在全部批次终结后由 failure_replay.py 每键只独立重放一次；重放成功不是新种子。

## 验证完成

只有 watchdog/status.json 的 state=complete、各 formal/index.json 与 failure_replay/formal/index.json 均 terminal、所有 FINAL_AUDIT.json passed=true、REBUILD_AUDIT.json 与 PUBLIC_BUNDLE_AUDIT.json passed=true 时，才可报告本轮可行实验完成。P2-1 的 48/96 物理池只部署了 8/11 张 GPU，路由耗时不代表全部 48/96 张同时活跃；见 scalability/INTERPRETATION_CN.md。

## 用户追加的失败边界补测（2026-10-29）

用户要求部分种子失败按原条件重跑、全部种子失败时降低 token 数找边界，并指定 PowerShell conda activate gllm。已验证激活后的解释器是 D:/software/miniconda/envs/gllm/python.exe。V5 的 99 个失败键已按原条件独立重放；V6 原失败键仍由主 watchdog 在七批 terminal 后统一独立重放，不能重复启动。

另建 failure_stepdown.py 与 failure_stepdown/README_CN.md，登记 70B 长 Prompt 的半提供负载/较短 Prompt 条件，以及 30B multi/630 条件；原正式失败不动。15 个 60 秒冒烟 7 成功、8 失败：70B 的 HH/HHplus 在长 Prompt 降载后仍复现准入断言，四个 V4 冒烟成功；30B multi/630 三方法成功。75 个 1800 秒五种子正式补测于约 11:27（韩国时间）以 gllm 后台启动，控制 PID 31280，以 failure_stepdown/formal/index.json 为准；不要重复启动。此新批次不在原 watchdog 的七批名单中，rcaps 心跳监控已更新为同时检查它。最终需另核对 failure_stepdown/FINAL_AUDIT.json 和原条件/新条件的分开表述。

第一轮降 token 补测已 terminal，FINAL_AUDIT passed=true：20/75 成功、55/75 失败。30B multi/630 原 RCAPS 仍 5/5 KV 溢出；70B Prompt×2/×3 在两个拓扑的 Helix/Helix+ 均 0/5，单集群 RCAPS 也均 0/5。三集群 RCAPS 两点均 5/5 成功，但完成率仅约 58%/44%，不能只报可观测 TPOT。基于这一边界，在看新结果前登记第二轮 70B Prompt×1.5（350/160 token/s）与 30B multi/525；60 秒冒烟 7/9 成功，45 个正式五种子窗口于约 12:55（韩国时间）使用 gllm 启动，控制 PID 39740。以 failure_stepdown2/formal/index.json 为准，不要重复启动；结果与原点、第一轮各自独立。
