# E1 R-uniform 退化情况修订

2026-10-29，在 R-uniform 正式布局生成及任何正式评估窗口前：原预诊断错误地将其与 R-pipelines 一并标作不可行。R-uniform 的原定义是“最大可行同宽度”，其宽度 1 是合法退化，应实际生成并评估。原规划 manifest 保留为 planning_manifest_v1.json；最初的 INFEASIBLE_v1.json 保留供追溯。R-pipelines 的两条完整无共享流水线仍有容量硬下界 160 > 152，不可行。未修改任何正式测量结果；本修订之后冻结新 manifest。
