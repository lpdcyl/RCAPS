# 固定拓扑下的路径策略交叉实验

本实验检验工作三的动机：在同一个冻结的三集群异构 GPU 放置上，最优固定路径空间是否会随负载或跨集群链路容量变化。它只检验“是否需要切换路径空间”，不检验动态控制器本身。

## 因子

- 拓扑和放置固定为 C1_multi 的 24 GPU、三集群布局。
- offered token/s 为 50、160、320，分别作为低、中、高负载点。
- 比较规范路径、规范路径加固定四条跨副本慢链路绕行边、完整层兼容 DAG。
- 网络状态为原始跨集群 GPU-GPU 链路容量，以及将这些链路容量统一乘 4。只按名义容量不高于 50 MB/s 的计算节点间链路识别一次；两种网络状态使用完全相同的边集合。链路时延、NIC、GPU 放置、M3 代价和 KV 准入均不变。
- 三种策略都使用相同的全生命周期 KV 容量预约（prompt 长度加公开输出上限 1000 token），超容量请求延后到查询完成释放 KV 后重试。

实验完整矩阵和判定规则见 `protocol.json`。开发矩阵使用 seed 102、300 秒，每格一窗；正式矩阵使用 seed 0/1/2、1800 秒、零预热、窗口末不排空，共 54 窗口。正式种子不得以开发种子替换。

## 运行

在仓库根目录先显式激活 `gllm`。正式 PowerShell 驱动也会激活环境并校验解释器路径：

```powershell
(& 'D:\software\miniconda\Scripts\conda.exe' shell.powershell hook) | Out-String | Invoke-Expression
conda activate gllm
$env:PYTHONHASHSEED = '0'
python -m experiments.v3_path_crossover.run --phase audit
python -m experiments.v3_path_crossover.run --phase dev
./experiments/v3_path_crossover/run_formal_isolated.ps1
python -m experiments.v3_path_crossover.validate
python -m experiments.v3_path_crossover.report
```

正式窗口必须经 `run_formal_isolated.ps1` 执行，每格使用一个新 Python 进程。已有文件身份不匹配时不会覆盖。失败记录与日志保留在 `runs/`。报告在全部 54 个正式窗口齐全且轨迹哈希配对后才判定是否有交叉。

主要性能指标是 P95 TPOT，并同时检查吞吐、完成率、P95 TTFT 和末端积压；机制指标包括实际路径、部分层跳转、Decode 批大小和 KV 预约峰值。按条件输出逐种子及三种子描述值，不作显著性声明。

## 完整性校验

`python -m experiments.v3_path_crossover.validate --allow-incomplete` 可在运行期间检查已有格；`validation.json` 明确列出缺失格，未完成时 `complete` 为 false。最终报告必须通过不带该参数的完整校验。校验包括每格身份与源码哈希、逐请求重建轨迹及条件间配对、重算 P95 与完成率、积压守恒、KV 预约容量上限、实际路由合法性、网络带宽和时延干预。

`python -m unittest experiments.v3_path_crossover.test_integrity -v` 检查校验器能否拒绝错误种子、缺失请求、篡改的指标、KV 越界和错误网络干预，并检验胜者和 2/3 配对方向规则。单元测试只在内存中构造测试输入，不会写入正式结果。

本实验属于 `simulation_only`，不是 24 张实体 GPU 上的部署实测，也不验证 42 GPU 泛化或动态控制器本身。外部跨模型完整性评审工具当前不可用；本地校验不等同于已完成外部评审。
