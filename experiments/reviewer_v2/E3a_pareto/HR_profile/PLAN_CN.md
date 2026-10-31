# HR GPU 工作量十窗口补测

登记日期：2026-10-29。补测 single/700 与 multi/320、seed0–4、cell=HR；1800 s、零预热、不排空。使用 experiments/v5_core_supplement/run.py 的统一执行器和原 V5 核心 formal/manifest.json 冻结源码、部署、画像。所有正式运行使用 Windows conda gllm 解释器，PYTHONHASHSEED=0、PYTHONIOENCODING=utf-8、MPLBACKEND=Agg、OMP/OPENBLAS/MKL 线程数均为 1。

每窗口记录 P95 TPOT、P95 TTFT、输出吞吐、完成率、GPU 秒/token、轨迹及部署哈希；与旧 HR 同种子轨迹、部署哈希必须相同。原始五种子文件保留。失败不填零，批次全部 terminal 后只在五种子齐全时给 E3a HR 均值和 CI。
