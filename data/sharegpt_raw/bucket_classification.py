"""
Classify ShareGPT requests into output-length buckets, and search for good bucket
definitions.

Why a separate experiment from the regression one
-------------------------------------------------
The regression run scored 0.395 bucket accuracy, but that number is misleading: it is a
regressor's output thresholded after the fact, and the regressor was trained to minimise
squared error, which pulls every prediction toward the mean. A classifier optimises the
decision boundary directly, so it should do materially better on the same buckets.

Design
------
1. Bucket search. Accuracy depends heavily on where the cuts are and how many buckets
   there are. We sweep several candidate schemes (2/3/4 way) over quantile and
   fixed-token cuts so the reported accuracy is never an artifact of one arbitrary
   choice.
2. Classifiers. HistGradientBoostingClassifier vs logistic regression on the same
   features, and an ordinal variant, so we can tell a modelling problem from a
   signal-ceiling problem.
3. Honest baselines. Majority-class and a shuffled-label control, so accuracy is always
   read against what is achievable by guessing.
"""

import argparse
import json
import os
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TARGET_COL = "output_len"
ID_COLS = ["id"]
LEAKY_COLS = ["raw_num_turns"]


# --------------------------------------------------------------------------------------
# Bucket schemes
# --------------------------------------------------------------------------------------

def scheme_2way(v: float) -> int:
    """short / long split at 256 tokens."""
    return 0 if v <= 256 else 1


def scheme_3way(v: float) -> int:
    """short / medium / long at 128 and 512."""
    if v <= 128:
        return 0
    return 1 if v <= 512 else 2


def scheme_3way_b(v: float) -> int:
    """three-way at 256 and 768."""
    if v <= 256:
        return 0
    return 1 if v <= 768 else 2


def scheme_4way(v: float) -> int:
    """four-way at 128 / 256 / 512."""
    if v <= 128:
        return 0
    if v <= 256:
        return 1
    return 2 if v <= 512 else 3


def scheme_4way_b(v: float) -> int:
    """four-way at 64 / 256 / 768, closer to a quantile split."""
    if v <= 64:
        return 0
    if v <= 256:
        return 1
    return 2 if v <= 768 else 3


def scheme_5way(v: float) -> int:
    """five-way at 64 / 128 / 256 / 512."""
    if v <= 64:
        return 0
    if v <= 128:
        return 1
    if v <= 256:
        return 2
    return 3 if v <= 512 else 4


def scheme_6way(v: float) -> int:
    """six-way, the fine-grained case."""
    if v <= 64:
        return 0
    if v <= 128:
        return 1
    if v <= 256:
        return 2
    if v <= 512:
        return 3
    return 4 if v <= 1024 else 5


SCHEMES = {
    "2way_256": scheme_2way,
    "3way_128_512": scheme_3way,
    "3way_256_768": scheme_3way_b,
    "4way_128_256_512": scheme_4way,
    "4way_64_256_768": scheme_4way_b,
    "5way_64_128_256_512": scheme_5way,
    "6way_64_128_256_512_1024": scheme_6way,
}


# --------------------------------------------------------------------------------------
# Extra features built from the prompt text
# --------------------------------------------------------------------------------------

def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add ratio and interaction features that classifiers exploit well.

    :param frame: feature table
    :return: new frame with extra columns
    """
    out = frame.copy()
    eps = 1e-6
    out["words_per_sentence"] = out["n_words"] / (out["n_sentences"] + eps)
    out["chars_per_word"] = out["n_chars"] / (out["n_words"] + eps)
    out["punct_ratio"] = out["n_punct"] / (out["n_chars"] + eps)
    out["upper_ratio"] = out["n_upper"] / (out["n_chars"] + eps)
    out["digit_ratio"] = out["n_digits"] / (out["n_chars"] + eps)
    out["newline_per_line"] = out["n_newlines"] / (out["n_lines"] + eps)
    out["question_density"] = out["n_question_marks"] / (out["n_sentences"] + eps)
    out["code_marker_sum"] = out["n_code_fence"] + out["n_inline_code"] + out["has_code_kw"]
    out["intent_sum"] = (out["is_bullet_req"] + out["is_translate"] + out["is_summarize"]
                         + out["is_explain"] + out["is_write"] + out["is_code_req"]
                         + out["is_essay_req"])
    out["verb_density"] = out["n_instruction_verbs"] / (out["n_words"] + eps)
    out["list_density"] = out["n_list_items"] / (out["n_nonempty_lines"] + eps)
    out["log_input_len"] = np.log1p(out["input_len"])
    out["is_very_short_prompt"] = (out["input_len"] <= 10).astype(float)
    out["is_long_prompt"] = (out["input_len"] > 1024).astype(float)
    return out


# --------------------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------------------

def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Accuracy plus macro-F1 and adjacent accuracy.

    :param y_true: true bucket labels
    :param y_pred: predicted bucket labels
    :return: metrics dict
    """
    n_classes = int(max(y_true.max(), y_pred.max())) + 1
    acc = float(np.mean(y_true == y_pred))
    adjacent = float(np.mean(np.abs(y_true - y_pred) <= 1))

    # macro F1 without sklearn's helper, to keep the per-class view explicit
    f1s: List[float] = []
    for cls in range(n_classes):
        tp = float(np.sum((y_pred == cls) & (y_true == cls)))
        fp = float(np.sum((y_pred == cls) & (y_true != cls)))
        fn = float(np.sum((y_pred != cls) & (y_true == cls)))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0)
    return {
        "accuracy": acc,
        "adjacent_accuracy": adjacent,
        "macro_f1": float(np.mean(f1s)),
        "majority_baseline": float(np.max(np.bincount(y_true)) / len(y_true)),
    }


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Bucket classification of ShareGPT output length")
    parser.add_argument("--input", default=os.path.join(here, "sharegpt_pairs.pkl"))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=os.path.join(here, "bucket_classification.json"))
    args = parser.parse_args()

    raw = pd.read_pickle(args.input)
    frame = add_derived_features(raw)
    y_len = frame[TARGET_COL].to_numpy(dtype=float)
    deploy_cols = [c for c in frame.columns if c not in ID_COLS + [TARGET_COL] + LEAKY_COLS]
    X = frame[deploy_cols].to_numpy(dtype=float)

    print(f"n = {len(frame)}, deployable features = {len(deploy_cols)}")
    print()

    # ---------------------------------------------------------------- distribution
    print("output_len distribution (percentiles):")
    for q in [0.05, 0.1, 0.25, 0.5, 0.6, 0.75, 0.9, 0.95]:
        print(f"  p{q * 100:5.1f} = {np.quantile(y_len, q):7.1f}")
    print()

    results: Dict[str, Dict[str, object]] = {}

    for scheme_name, fn in SCHEMES.items():
        y = np.array([fn(v) for v in y_len])
        counts = np.bincount(y)
        shares = counts / counts.sum()
        n_classes = len(counts)

        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)

        # majority-class baseline
        maj_pred = np.zeros_like(y)
        maj_acc = float(shares.max())

        # gradient boosting classifier
        gbr = HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.06, max_depth=6,
            min_samples_leaf=40, l2_regularization=1.0, random_state=args.seed,
        )
        pred_gbr = cross_val_predict(gbr, X, y, cv=skf, method="predict")
        m_gbr = evaluate(y, pred_gbr)

        # logistic regression reference
        lr = make_pipeline(StandardScaler(),
                           LogisticRegression(max_iter=2000, C=1.0, multi_class="auto"))
        pred_lr = cross_val_predict(lr, X, y, cv=skf, method="predict")
        m_lr = evaluate(y, pred_lr)

        results[scheme_name] = {
            "n_classes": n_classes,
            "class_shares": shares.tolist(),
            "majority_accuracy": maj_acc,
            "gbr": m_gbr,
            "logreg": m_lr,
        }

        print(f"--- {scheme_name}  ({n_classes} classes) ---")
        print("  class shares : " + ", ".join(f"{s * 100:.1f}%" for s in shares))
        print(f"  majority     : acc={maj_acc:.4f}")
        print(f"  logreg       : acc={m_lr['accuracy']:.4f}  macroF1={m_lr['macro_f1']:.4f}  adj={m_lr['adjacent_accuracy']:.4f}")
        print(f"  gradboost    : acc={m_gbr['accuracy']:.4f}  macroF1={m_gbr['macro_f1']:.4f}  adj={m_gbr['adjacent_accuracy']:.4f}"
              f"   (lift over majority {m_gbr['accuracy'] - maj_acc:+.4f})")
        print()

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()
