# 全种子失败条件的降 token 边界补测

原正式失败与独立重放结果均不修改。此处新建**不同条件**，不能把成功结果倒填成原负载或原 Prompt 长度的结果。五个固定条件在看本批结果前已登记于 failure_stepdown.py：

| 条件 | 原失败点 | 新条件 |
|---|---|---|
| 70B 单集群 Prompt×2 | single/700、三方法 0/5 | Prompt 仍×2，提供负载减至 350 token/s |
| 70B 三集群 Prompt×2 | multi/320、三方法 0/5 | Prompt 仍×2，提供负载减至 160 token/s |
| 70B 单集群 Prompt×4 | single/700、三方法 0/5；部分 RCAPS 请求超出 7500-token 画像 | Prompt 降至×3，提供负载减至 350 token/s |
| 70B 三集群 Prompt×4 | multi/320、三方法 0/5；部分 RCAPS 请求超出 7500-token 画像 | Prompt 降至×3，提供负载减至 160 token/s |
| 30B 三集群 840 token/s | 原版 RCAPS 5/5 KV 溢出 | 相同模型、拓扑与部署，提供负载减至 630 token/s；Helix/Helix+ 保留原分池部署 |

每点三方法 HH、HHplus、V4；正式窗口种子 0–4、1800 秒、零预热不排空；先以 seed100/60 秒冒烟。所有方法在同一点共用请求轨迹。旧失败、冒烟、正式窗口各自保存；不足五种子成功的组不汇总均值或配对 CI。

运行环境经 PowerShell 真实执行 conda activate gllm 验证，解释器为 D:/software/miniconda/envs/gllm/python.exe。冒烟 15 格中 7 成功、8 失败：四个 70B 条件的 V4 成功，而 HH/HHplus 均再次出现上游“无可接纳下游”断言；30B/630 的三方法均成功。60 秒短窗口完成率不是正式 1800 秒结果。

部分种子失败的原条件：V5 的 99 个失败键已独立重放一次，分类见 ../../v5_failure_replay/CAUSES_CN.md；V6 的失败键由主 watchdog 在全部原批次终结后独立重放，不能从新降载条件代替。若重放仍为实际 KV 或无可接纳下游，则属当前预设条件的容量/准入边界，不能归因于 Python 环境。
