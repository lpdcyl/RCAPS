# E4 WSL2 执行说明

代码和流量代理已经冻结：manifest.json 与 traffic.json。使用本机 WSL2 Ubuntu 的 Python3 标准库；不需要在 WSL 安装 Windows 的 gllm conda 环境。其他 CPU 模拟实验仍用 Windows gllm。

建议等 experiments/v4_paper_seed45/retry_env/FINAL_AUDIT.json 产生、补种子批次结案后再启动 E4。进入 WSL 终端，依次运行：

    cd /mnt/d/PythonProject/Helix-GREEN
    python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --prepare
    sudo python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --preflight
    sudo python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --run | tee experiments/reviewer_v2/E4_tcp_wsl/console.log
    python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --report

需要 WSL2 已有 python3、ip、tc，且 sudo 能创建 network namespace/veth/netem。preflight 只创建、检查并清理临时命名空间；成功应显示 PREFLIGHT_OK。run 会在三个速率、五个发送模式、十轮重复上顺序执行共 150 次测量，至少约 75 分钟，实际受系统速度影响。每次测量单独写 runs/速率/模式/repeatN/result.json 或 failure.json；重启后再次执行 --run 会跳过既有结果和失败，不覆盖原件。失败请保留 receiver.log、failure.json 和 console.log 供诊断；若需要独立重放，由本任务另建重放批次。

最终查看 RESULTS_CN.md、individual.csv 和 FINAL_AUDIT.json。只有每组 10/10 成功时，报告才会给该组均值与配对区间。指标是 WSL2 虚拟链路上 Linux TCP 栈的端到端测量，不是物理网卡或真实广域网测量。Prompt 时间戳来自原全局到达轨迹的确定性抽样，Decode 速率来自所选慢链路的已审计计数；这两者不是原链路逐包抓包。详细口径见 PLAN_CN.md。
