# T0.6 Prefill/Decode 链路干扰模型离线检验

本目录只读取既有实验，不启动仿真窗口。模型是无拟合参数的 Decode 高优先级、非抢占式 M/G/1 链路等待代理；传输占用不含传播延迟。`protocol.json` 在分析前单独提交并锁定。

## 复现

在仓库根目录的同一个 PowerShell 会话中运行：

```powershell
$env:PYTHONHASHSEED="0"
$env:MPLBACKEND="Agg"
python -m unittest experiments.v3_interference_model.test_model -v
python -m experiments.v3_interference_model.analyze
```

通用入口也支持 `python -m experiments.v3_interference_model.run --phase smoke|formal|report`。`formal` 与 `report` 都执行相同的纯离线分析。`index.json` 记录读取文件路径、SHA256 和状态；本卡没有新窗口，故 `simulation_windows` 为空。输出为 `analysis.json` 与 `RESULTS_CN.md`。

检验 A 使用慢链路诊断原有的种子 1–3、600 秒数据；检验 B 读取已有带宽和消息字节反事实；检验 C 使用开发种子 100 的 1800 秒生成轨迹估算流量，在线结果仅在最后一步用于 Spearman。旧数据的种子不会更换或重跑。
