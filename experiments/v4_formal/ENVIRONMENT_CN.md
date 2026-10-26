# V4 本地执行环境

沿用现有 CPU 离散事件仿真环境，不租用资源，不需要 GPU/模型权重。
声明见 `env-spec.json`；Python 3.10.16，使用已有 Miniconda，未安装或升级依赖。

在 PowerShell 中从仓库根目录执行下面整段命令。工程检查只用 seed 0，60 秒固定窗口，对比新旧实现，既不选择参数，也不计入正式结果。正式实验另用 0/1/2、1800 秒。

```powershell
$env:PYTHONHASHSEED='0'
$env:MPLBACKEND='Agg'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'D:/software/miniconda/python.exe' -u -m experiments.v4_formal.preflight
```

成功标志是 `V4_PREFLIGHT_PASSED` 和新生成的 `preflight.json`。仅导入成功不足以判定可运行。若检查失败，保留输出，停止正式队列，不自行修改参数或跳过断言。

历史 seed 2 偶发类型异常根因尚未定位。正式运行将逐格独立进程执行并保存故障栈和关键局部状态；遇到异常停止新任务派发，不自动重试。新入口通过行为等价检查也不意味着历史异常根因已解决。
