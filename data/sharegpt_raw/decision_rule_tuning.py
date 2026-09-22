"""
Push classification accuracy up: tune the decision rule, not just the model.

What actually limits accuracy here
----------------------------------
Three separate things, and they need different fixes:

1. Feature space. Covered by text_feature_ablation.py (hand stats vs text n-grams).
2. Decision rule. A classifier trained with log-loss predicts calibrated P(class|x),
   and argmax is NOT the accuracy-maximising rule under class imbalance -- it silently
   sacrifices rare classes. Re-weighting the predicted probabilities before argmax can
   recover a lot of macro-F1 and balanced accuracy, and sometimes outright accuracy.
3. Bucket definition. Accuracy on a 6-way split is mechanically lower than on a 2-way
   split even with identical discriminative power, so the choice of buckets must be
   reported alongside the number rather than hidden.

This script attacks (2) and (3) explicitly, and reports balanced accuracy and macro-F1
next to plain accuracy so an imbalanced win is never mistaken for a real one.

Decision rule fitted here:  y_hat = argmax_k  w_k * P(k|x)
with w learned on out-of-fold predictions by coordinate ascent. w is fitted on OOF
probabilities from the training folds only, then applied to the held-out fold, so the
reported numbers stay honest.
"""

import argparse
import json
import os
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold

TARGET_COL = "output_len"
ID_COLS = ["id"]
LEAKY_COLS = ["raw_num_turns"]


# --------------------------------------------------------------------------------------
# Bucket schemes
# --------------------------------------------------------------------------------------

def make_scheme(cuts: Sequence[float]):
    """
    Build a bucket function from ascending cut points (inclusive upper bounds).

    :param cuts: e.g. (128, 512) gives 3 buckets
    :return: function value -> bucket index
    """
    cuts = tuple(cuts)

    def scheme(v: float) -> int:
        for idx, cut in enumerate(cuts):
            if v <= cut:
                return idx
        return len(cuts)

    return scheme


SCHEMES: Dict[str, Tuple] = {
    "2way_256": (256,),
    "2way_512": (512,),
    "3way_128_512": (128, 512),
    "3way_256_512": (256, 512),
    "3way_256_768": (256, 768),
    "4way_128_256_512": (128, 256, 512),
    "4way_64_256_768": (64, 256, 768),
    "5way_64_128_256_512": (64, 128, 256, 512),
}


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------

def full_metrics(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> Dict[str, float]:
    """Accuracy, balanced accuracy, macro-F1, and per-class recall."""
    acc = float(np.mean(y_true == y_pred))
    recalls = []
    f1s = []
    for cls in range(n_classes):
        tp = float(np.sum((y_pred == cls) & (y_true == cls)))
        fp = float(np.sum((y_pred == cls) & (y_true != cls)))
        fn = float(np.sum((y_pred != cls) & (y_true == cls)))
        support = tp + fn
        recalls.append(tp / support if support > 0 else 0.0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / support if support > 0 else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0)
    return {
        "accuracy": acc,
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1s)),
        "per_class_recall": [float(r) for r in recalls],
    }


def fit_weights(proba: np.ndarray, y_true: np.ndarray, n_classes: int,
                objective: str, rounds: int = 4) -> np.ndarray:
    """
    Coordinate-ascent search over per-class multipliers of the predicted probabilities.

    :param proba: OOF class probabilities, shape (n, n_classes)
    :param y_true: true labels
    :param n_classes: number of classes
    :param objective: "accuracy" or "balanced_accuracy"
    :param rounds: number of coordinate-ascent sweeps
    :return: weight vector of length n_classes
    """
    grid = np.concatenate([np.linspace(0.4, 3.0, 27), np.linspace(3.5, 12.0, 18)])
    weights = np.ones(n_classes, dtype=float)

    def score(w: np.ndarray) -> float:
        pred = np.argmax(proba * w, axis=1)
        m = full_metrics(y_true, pred, n_classes)
        return m[objective]

    best = score(weights)
    for _ in range(rounds):
        improved = False
        for cls in range(n_classes):
            current = weights[cls]
            for candidate in grid:
                weights[cls] = candidate
                value = score(weights)
                if value > best + 1e-9:
                    best = value
                    current = candidate
                    improved = True
            weights[cls] = current
        if not improved:
            break
    return weights


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------

def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Tune decision rule and bucket definition")
    parser.add_argument("--input", default=os.path.join(here, "sharegpt_pairs.pkl"))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=os.path.join(here, "decision_rule_tuning.json"))
    args = parser.parse_args()

    import sys
    sys.path.insert(0, here)
    from bucket_classification import add_derived_features

    raw = pd.read_pickle(args.input)
    frame = add_derived_features(raw)
    y_len = frame[TARGET_COL].to_numpy(dtype=float)
    cols = [c for c in frame.columns if c not in ID_COLS + [TARGET_COL] + LEAKY_COLS]
    X = frame[cols].to_numpy(dtype=float)
    print(f"n = {len(frame)}, features = {len(cols)}")
    print()

    results: Dict[str, object] = {}

    for scheme_name, cuts in SCHEMES.items():
        scheme = make_scheme(cuts)
        y = np.array([scheme(v) for v in y_len])
        n_classes = len(cuts) + 1
        shares = np.bincount(y, minlength=n_classes) / len(y)

        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
        proba_oof = np.zeros((len(y), n_classes))

        # ---- honest nested evaluation: fit the weight vector per fold on inner OOF ----
        pred_argmax = np.zeros(len(y), dtype=int)
        pred_tuned_acc = np.zeros(len(y), dtype=int)
        pred_tuned_bal = np.zeros(len(y), dtype=int)
        inner_folds = min(3, args.folds)

        for tr, te in skf.split(X, y):
            inner = StratifiedKFold(n_splits=inner_folds, shuffle=True, random_state=args.seed + 1)
            inner_proba = np.zeros((len(tr), n_classes))
            for itr, ite in inner.split(X[tr], y[tr]):
                clf = HistGradientBoostingClassifier(
                    max_iter=400, learning_rate=0.06, max_depth=6,
                    min_samples_leaf=40, l2_regularization=1.0, random_state=args.seed,
                )
                clf.fit(X[tr][itr], y[tr][itr])
                inner_proba[ite] = clf.predict_proba(X[tr][ite])

            w_acc = fit_weights(inner_proba, y[tr], n_classes, "accuracy")
            w_bal = fit_weights(inner_proba, y[tr], n_classes, "balanced_accuracy")

            clf = HistGradientBoostingClassifier(
                max_iter=400, learning_rate=0.06, max_depth=6,
                min_samples_leaf=40, l2_regularization=1.0, random_state=args.seed,
            )
            clf.fit(X[tr], y[tr])
            proba = clf.predict_proba(X[te])
            proba_oof[te] = proba
            pred_argmax[te] = np.argmax(proba, axis=1)
            pred_tuned_acc[te] = np.argmax(proba * w_acc, axis=1)
            pred_tuned_bal[te] = np.argmax(proba * w_bal, axis=1)

        m_argmax = full_metrics(y, pred_argmax, n_classes)
        m_tuned_acc = full_metrics(y, pred_tuned_acc, n_classes)
        m_tuned_bal = full_metrics(y, pred_tuned_bal, n_classes)
        majority = float(shares.max())

        results[scheme_name] = {
            "n_classes": int(n_classes),
            "class_shares": shares.tolist(),
            "majority_accuracy": majority,
            "argmax": m_argmax,
            "tuned_accuracy": m_tuned_acc,
            "tuned_balanced": m_tuned_bal,
        }

        print(f"--- {scheme_name} ({n_classes} classes) ---")
        print("  shares : " + ", ".join(f"{s * 100:.1f}%" for s in shares))
        print(f"  argmax            : acc={m_argmax['accuracy']:.4f}  bal={m_argmax['balanced_accuracy']:.4f}  "
              f"macroF1={m_argmax['macro_f1']:.4f}   (majority {majority:.4f})")
        print(f"  tuned(accuracy)   : acc={m_tuned_acc['accuracy']:.4f}  bal={m_tuned_acc['balanced_accuracy']:.4f}  "
              f"macroF1={m_tuned_acc['macro_f1']:.4f}")
        print(f"  tuned(balanced)   : acc={m_tuned_bal['accuracy']:.4f}  bal={m_tuned_bal['balanced_accuracy']:.4f}  "
              f"macroF1={m_tuned_bal['macro_f1']:.4f}")
        print("  per-class recall (argmax) : " + ", ".join(f"{r:.3f}" for r in m_argmax["per_class_recall"]))
        print("  per-class recall (balanced): " + ", ".join(f"{r:.3f}" for r in m_tuned_bal["per_class_recall"]))
        print()

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()
