# E5a/E6 失败重放键有界第二轮

2026-11-03，用户明确要求失败键重新运行。E5a 第一轮独立重放仍在运行；E6 第一轮已 terminal 且审计通过，尚有 2 个失败键。本计划在第二轮结果产生前登记。

待 E5a 第一轮 terminal 且 `audit_e5a_failed` 审计通过后，从 E5a、E6 第一轮权威索引中只选 `failed` 键，冻结各第一轮失败工件 SHA、第一轮 manifest/index/audit SHA 和第二轮执行脚本 SHA。使用真正 `conda activate gllm`，新目录 `failed_replay_retry_v2`，单 worker，每键最多一次，沿用原方法、负载、种子、时长、部署和轨迹条件。两轮重放均仅作诊断，不修改正式结果，也不构成正式完整五种子组。

Windows 访问违规和确定性模拟器断言保留原日志及新失败工件；第二轮若仍复现，不再自动重试。软件修复需单独版本和完整受影响条件。第二轮 terminal 后由 `audit_failed_replay_retry` 独立核对来源、协议、部署、逐请求样本和工件 SHA。
