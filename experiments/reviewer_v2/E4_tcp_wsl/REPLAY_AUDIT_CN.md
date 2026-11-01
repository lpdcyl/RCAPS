# E4 中断键独立复测审计

- 原正式批次：150 次登记，149 次成功、1 次中断失败；原件为 `runs/12p5MBps/priority/repeat0/failure.json`，未覆盖。
- 独立复测：`interrupted_replay_20261101/manifest.json` 固定同一流量和 12.5 MB/s、priority、repeat0；`index.json` 为 completed，结果 SHA256 `4490fc76ce5080ee041814c0d8519b66493d8b40b84f96ae24873163c66b732d`。
- 源码校验：复测入口先核对冻结 bench.py、traffic.py 和 traffic.json 的 SHA256，再调用原 `bench.run_one`；结果仍单列，不回填正式批次。接收消息 1159 条小消息、3 条大消息，结果中的总接收字节数为 55,889,056，与冻结流量逐条校验一致。
- 因原 12.5 MB/s priority 组仅 9/10，本次复测不用于把正式组改称 10/10，也不重算原组配对置信区间。
- 范围：WSL2 的 netns/veth/netem 虚拟 Linux TCP 链路，不代表物理 NIC 或跨机网络。
