# 工作三：入场时链路干扰价格

在已通过正式非劣效检验的慢链路门控稀疏 DAG 上，加入 T12 无拟合系数的
`0.5 × λ_decode × S_prompt²` 价格。对照为完全相同边集和原 V3 路由价格的 gated；
另跑完整 V3 作为参照。Prompt 入场时选路；Decode 路径继续绑定，不改变传输调度。

协议在开发结果之前锁定于 `protocol.json`。此实验不改动既有冻结方法或历史结果。

运行：

```powershell
$env:PYTHONHASHSEED = '0'
$env:MPLBACKEND = 'Agg'
python -m unittest work3_link_price.test_scheduler
python -m work3_link_price.run --phase development
python -m work3_link_price.run --phase report
```
