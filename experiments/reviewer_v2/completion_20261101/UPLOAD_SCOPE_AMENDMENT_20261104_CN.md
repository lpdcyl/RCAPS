# 上传范围修订：保留已取消窗口的索引来源

2026-11-04 终态汇总后，初版 `UPLOAD_MANIFEST.json` 登记 3413 个文件，SHA256 为 `04d6948ede3be22e62d1d204c2f0d4d5c1b60672bc6d4e18166e95c10b3e53c2`。上传前的逐索引核对发现，`experiments/v5_model30b/formal/index.json` 中 29 个 `cancelled_baseline_adaptation` 条目各自引用一个取消记录，但初版清单既未包含这些记录，Git 也未跟踪它们。

29 个取消记录均存在，并与索引保存的 `artifact_sha256` 逐项匹配。构建器现将它们作为**取消证据**纳入上传范围，绝不计作成功结果，也不改变任何正式批或重放结果。其他终态索引的来源路径均已在初版清单或现有 Git 跟踪文件中。初版清单保留在本地 `UPLOAD_MANIFEST_PRE_TRACEABILITY_FIX.bak`，最终上传以重新生成的 `UPLOAD_MANIFEST.json` 为准。

第二次上传前核对发现系统 Git 配置 `core.autocrlf=true` 将暂存的文本内容转换为 LF，导致 3444 个暂存路径中 3182 个 Git blob 的 SHA256 与工作区清单不一致。使用 `core.autocrlf=false` 对清单路径执行 `git add --renormalize` 后，3444 个暂存 blob 与清单逐字节一致。上传辅助脚本现自动执行这一步并再次逐 blob 核对。修复脚本前的第二版清单 SHA256 为 `cef33a93b0041ee4c7233373a3f745fef1e6b90eaf48b81fe84d2e1ed6d5c001`，保留在本地 `UPLOAD_MANIFEST_PRE_BLOB_FIX.bak`；最终清单重新生成后才用于提交。
