# E5：42 节点规模与 KV / 长上下文边界预注册

登记日期：2026-10-30，E5 新正式结果产生前。来源：仓库根目录 RCAPS_审稿补充实验清单_v2.md E5 与 experiments/reviewer_v2/PLAN_CN.md。E2b 正式窗口运行期间不另起并行 CPU 批次，避免资源竞争。

## 旧失败来源核对

- experiments/v3_cluster42/analysis.json 登记 2150 token/s 下 V3、gated 及关单请求 Decode 双倍计时反事实共 12 个失败。当前本地工作树未找到其 runs/formal 原始 failure.json，因此 **不能从现有报告断定每个失败的具体异常**；E5a 的正式报告须把这条证据缺口显式标出，不把报告文字当作原始 traceback。
- experiments/v5_kv_stress/formal/runs/ 中 27 份原失败：15 份 KV cache 容量断言，12 份控制器和 worker 中断。它们来自原 1/2、1/4、1/8 容量压力批次，失败原件保留，重放必须独立索引。

## E5a 冻结设计

物理资源池固定 artifact_evaluation/high_heterogeneity/config/cluster42.ini，70B；42 个计算节点按设备配置折算 64 张物理 GPU，报告同时给出两种计数。比较当前 RCAPS（V4 机制）、RCAPS-KV、Helix 与 Helix+。负载 1450、1800、2150 token/s；seed0–4；1800 s、零预热、不排空。共 4×3×5=60 个新窗口，仅在代码、42 节点部署与模拟器校验完成、冒烟通过后冻结并运行。不得直接复用旧 V3 作为当前 V4。记录部署层跨度、活跃节点/物理 GPU 数、规划墙钟、单次路由均值/P95、P95 TPOT/TTFT、吞吐、完成率及失败原因。同种子跨方法轨迹哈希必须一致；只在五个成功配对种子上给均值和 t(4) 95% CI。

## E5b 冻结设计

首先在原物理池与轨迹下按 1/2 KV 容量单独比较 RCAPS-KV 与 Helix+，单集群 700、三集群 320 token/s，seed0–4。若复用旧成功结果，必须校验环境/轨迹/布局/执行器相同；旧失败重放另列，不能补零。长 Prompt 设原分布的 ×1.5 与 ×2，负载对应减半；RCAPS、RCAPS-KV、Helix+，seed0–4。请求或配置超出 0–7500 token 剖析范围时直接记录边界失败，不外推或截断伪装；独立说明 KV 溢出与画像越界。所有新正式窗口在看到结果前冻结清单、Python 环境、代码、部署、画像和轨迹生成器 SHA256，先冒烟再运行；原失败与独立重放分列。

E5a/E5b 是 CPU 画像仿真，不是物理 GPU 集群验证。E4 WSL2 虚拟网络由用户自行运行。
