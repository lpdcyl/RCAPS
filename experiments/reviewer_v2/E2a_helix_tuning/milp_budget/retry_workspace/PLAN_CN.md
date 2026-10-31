# MILP 工作目录修正后的独立重放

登记于 2026-10-30、重放结果产生前。原 formal 四个键均因运行器预先写入 stdout/stderr，导致 Helix `LayoutSynthesizer` 的空工作目录断言；原 failure.json、日志、manifest 与 index 保留。此处每键在独立目录重放一次，参数仍为 C1_single/C1_multi 各 120/480 s，保持原 ILP 源码、拓扑、画像、初始解、回调和外层保护时限。

修正仅限目录布局：Gurobi 输出专用空目录 `layout/`，进程日志写在同级而非该目录内。结果只作为独立重放记录，不将原四个失败改写为成功。
