# ShareGPT 请求按输出长度分类：方法与最优配置

生成日期：2026-09-21
脚本目录：`data/sharegpt_raw/`

---

## 1. 结论速览

**推荐配置：`

2way_256`（≤256 / >256 tokens）+ 文本 n-gram 特征 + 逻辑回归**

| 指标 | 数值 |
|---|---|
| 准确率 | **0.7284** |
| 平衡准确率 | **0.6937** |
| macro-F1 | **0.6994** |
| 多数类基线 | 0.6082 |
| **净提升** | **+0.1202** |

这是准确率与类别平衡的最佳折中。若只要最高准确率，`2way_512` 达 **0.7869**，但少数类召回仅 0.264（见 §4 的陷阱）。

### 关键突破：必须用 prompt 文本内容

| 特征 | AUC | 准确率 |
|---|---|---|
| 仅手工统计量（长度/标点/意图） | 0.6885 | 0.6662 |
| **加入文本 n-gram** | **0.7964** | **0.7431** |

**AUC +0.108，准确率 +0.077。** 而仅用 `input_len` 做二分类 AUC 只有 0.48–0.53，**等于随机**——信号不在长度里，在**内容**里。

---

## 2. 全部分档方案实测（25k 样本，3 折交叉验证）

| 分档方案 | 类别占比 | 多数类 | **准确率** | 平衡准确率 | macro-F1 | 提升 |
|---|---|---|---|---|---|---|
| **2way_256** | 39/61 | 0.6082 | **0.7284** | **0.6937** | **0.6994** | +0.1202 |
| 2way_512 | 76/24 | 0.7585 | **0.7869** | 0.6087 | 0.6229 | +0.0284 |
| 3way_128_512 | 20/56/24 | 0.5590 | 0.6431 | 0.5239 | 0.5486 | +0.0842 |
| 3way_256_512 | 39/37/24 | 0.3918 | 0.5607 | 0.5421 | 0.5452 | +0.1690 |
| 4way_64_256_768 | 11/28/51/10 | 0.5104 | 0.6052 | 0.4436 | 0.4722 | +0.0948 |

**规律：档位越多，准确率越低。** 2档 0.73–0.79，3档 0.56–0.64，4档 0.61（且平衡准确率崩到 0.44）。

`3way_256_512` 的**提升幅度最大（+0.169）**，因为它类别最均衡（39/37/24），是"相对基线"意义上的最佳方案。

---

## 3. 学习到的判别词（可解释性）

对逻辑回归系数排序，最强信号完全符合直觉：

**→ 长输出**
`code that`、`how does`、`can you`、`story about`、`so that`、`as an`、`each of`

**→ 短输出**
`how many`、`name for`、`title for`、`hi`、`ask`、`reply`、`is`

`ratio` 类特征（单词长度、标点密度）也贡献显著——术语密度高的技术问题倾向长回答。

---

## 4. 必须注意的陷阱：accuracy 会骗人

`2way_512` 的准确率 **0.7869** 看起来最优，但混淆矩阵暴露了真相：

```
              预测短    预测长
真实短        18080      882     ← 召回 0.954
真实长         4445     1593     ← 召回 0.264
```

**它在 95% 的情况下把请求判为"短"，等于"几乎全猜多数类"。** 平衡准确率仅 0.6087，只比随机猜（0.5）好一点。

所以：
- 只看 accuracy 会选到**退化解**
- 必须同时看 **balanced accuracy** 和 **per-class recall**
- `2way_256` 的两类召回为 0.694 / 0.693，是真正"会分类"的方案

---

## 5. 关于参考论文 CAPS 的评估

论文《Multi-Objective Scheduling for LLM Inference with Prompt-Level Cost Prediction and SLO Awareness》(Preprints 202604.1399) 声称输出长度回归 **MAE 38.6 tokens / MAPE 18.2%**。

**在 ShareGPT 上无法复现这个量级。** 我的实测是 MAE 185 tokens。差距 4.8 倍，原因：

1. 论文特征含 **"historical statistics for the tenant"**——这依赖请求的时序/租户结构；
2. 论文用 **"the first three days"** 做训练、后续 7 天评估，说明其 workload 是**带时序的生产 trace**；
3. 从 `MAE 38.6 / MAPE 18.2%` 反推，其平均输出长度约 212 tokens，与 ShareGPT 分布不符；
4. 论文的 **"conversation turn count"** 特征正是我在 ShareGPT 上发现并剔除的**数据泄漏**（首轮请求到达时不可知）。

**该论文的方法论可以借鉴（关键词任务类型分类、轻量 GBM），但它的精度数字不应作为 ShareGPT 的预期目标。**

---

## 6. 使用方法

```powershell
# 交叉验证评估（推荐方案）
python data\sharegpt_raw\request_bucket_classifier.py fit --scheme 2way_256 --folds 5

# 训练并保存模型
python data\sharegpt_raw\request_bucket_classifier.py fit --scheme 2way_256 --max-rows 0

# 用模型给新请求打标
python data\sharegpt_raw\request_bucket_classifier.py predict --model bucket_model.pkl --input prompts.txt
```

可选分档方案：`2way_256`（推荐）、`2way_512`、`3way_128_512`、`3way_256_512`、`4way_64_256_768`、`4way_128_256_512`

---

## 7. 产出与复现

| 文件 | 说明 |
|---|---|
| `request_bucket_classifier.py` | **主交付**：训练+推理一体 |
| `final_bucket_experiment.py` | 分档方案 × 特征 对比实验 |
| `final_bucket_results.json` | 全部分档结果（含混淆矩阵） |
| `text_feature_ablation.py` | 文本特征增益验证（AUC 0.69→0.80） |
| `text_feature_ablation.json` | 文本特征结果 |
| `decision_rule_tuning.py` | 决策规则/类权重调优 |
| `decision_rule_tuning.json` | 调优结果 |
| `bucket_classification.py` | 特征工程 + 首轮分档实验 |
| `sharegpt_pairs.pkl` | 92,729 行特征表（含真实标签） |
| `extract_features.py` | 原始数据 → 特征表流水线 |

```powershell
python data\sharegpt_raw\extract_features.py --workers 8          # ~16s
python data\sharegpt_raw\text_feature_ablation.py --folds 3 --max-rows 40000   # ~6min
python data\sharegpt_raw\final_bucket_experiment.py --folds 3 --max-rows 25000 --no-char
python data\sharegpt_raw\request_bucket_classifier.py fit --scheme 2way_256 --folds 5
```

### 环境备注

- 数据获取需走 **ModelScope 镜像**（HF 的 xet CDN 在本网络被阻断）
- 需额外安装：`scikit-learn`（`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple scikit-learn`）
- `HistGradientBoostingClassifier` **不支持稀疏矩阵**，文本特征必须配线性模型
- sklearn 1.7.2 中 `liblinear` 做多分类已弃用，未来需换 `saga` 或 `OneVsRestClassifier`
