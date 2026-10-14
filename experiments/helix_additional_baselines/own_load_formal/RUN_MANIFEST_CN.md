# 各自请求压力正式窗口执行记录

所有运行采用 `benchmarks.run`、70B、对应 24-GPU 拓扑、种子 0/1/2、1800 秒、零预热、窗口尾不排空。各方法负载由 `../own_load_development/{single,multi}/selection.json` 在开发种子 100/101 上确定；每份结果 JSON 保存布局哈希、物理拓扑哈希、轨迹哈希和请求身份。

三集群由 `python -u -m experiments.helix_additional_baselines.own_load_formal --scenario multi` 顺序运行 Helix 30、SP 30、RCAPS V2 300 token/s，各方法内部并行度为 2。Swarm 在扩展网格最低 20 token/s 未通过预定 L90 门槛，因此没有正式窗口。SP 的种子 1 在 30 token/s 触发 KV 容量断言，失败日志位于 `multi/separate/results/multi/seed1/separate.log`，不补算指标。

单集群三个已确定的运行点为 Helix 112.5、Swarm 75、SP 300 token/s；RCAPS V2 在开发搜索达到网格上限 900 后，按协议取 675 token/s。它们分别使用 `python -u -m benchmarks.run --methods <method> --scenarios single --seeds 0 1 2 --offered-single <load> --offered-multi <load> --duration 1800 --warmup 0 --workers 2 --results-dir experiments/helix_additional_baselines/own_load_formal/single/<method>/results`。四种方法的窗口彼此独立，负载不同的结果不做同负载改善计算。
