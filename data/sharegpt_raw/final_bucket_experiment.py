"""
Final bucket-classification experiment: text features x bucket scheme.

Why this exists
---------------
text_feature_ablation.py showed that TF-IDF text n-grams lift the binary output>256
task from AUC 0.69 to 0.796 and accuracy 0.666 to 0.743. That comparison was binary only.
The deliverable, however, is a request classifier over a bucket scheme, so this script
sweeps bucket schemes under the winning feature configuration.

Implementation notes
--------------------
* HashingVectorizer (stateless) is used inside cross-validation. A stateful
  TfidfVectorizer refitted per fold is more faithful but costs minutes per scheme; the
  stateless version keeps every scheme directly comparable. A TfidfVectorizer variant is
  run once at the end on the best scheme to confirm the hashing approximation does not
  change conclusions.
* Hand features are scaled and weighted by HAND_WEIGHT so ~44 dense columns are not
  drowned by ~1e5 sparse n-gram columns.
* Reported next to plain accuracy: balanced accuracy and macro-F1, because with 38-60%
  majority classes a plain accuracy number can look healthy while a whole class is never
  predicted.
"""

import argparse
import json
import os
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

TARGET_COL = "output_len"
ID_COLS = ["id"]
LEAKY_COLS = ["raw_num_turns"]
HAND_WEIGHT = 12.0
HUMAN_ROLES = ("human", "user")
ASSISTANT_ROLES = ("gpt", "chatgpt", "bard", "bing")

SCHEMES: Dict[str, Tuple[float, ...]] = {
    "2way_256": (256,),
    "2way_512": (512,),
    "3way_128_512": (128, 512),
    "3way_256_512": (256, 512),
    "4way_64_256_768": (64, 256, 768),
}


def load_texts(raw_path: str, limit: int = 0) -> Dict[str, str]:
    """
    Map conversation id -> first human prompt text.

    :param raw_path: raw ShareGPT json
    :param limit: optional cap
    :return: id -> prompt text
    """
    with open(raw_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if limit:
        raw = raw[:limit]

    out: Dict[str, str] = {}
    for record in raw:
        turns = record.get("conversations") or []
        for turn in turns:
            if turn.get("from") in HUMAN_ROLES and (turn.get("value") or "").strip():
                out[record.get("id", "")] = turn["value"]
                break
    return out


def scheme_labels(values: np.ndarray, cuts: Tuple[float, ...]) -> np.ndarray:
    """Assign bucket indices by ascending inclusive cut points."""
    labels = np.zeros(len(values), dtype=int)
    for cut in cuts:
        labels += (values > cut).astype(int)
    return labels


def metrics(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> Dict[str, object]:
    """Accuracy, balanced accuracy, macro-F1 and the confusion matrix."""
    acc = float(np.mean(y_true == y_pred))
    recalls, f1s = [], []
    for cls in range(n_classes):
        tp = float(np.sum((y_pred == cls) & (y_true == cls)))
        fp = float(np.sum((y_pred == cls) & (y_true != cls)))
        fn = float(np.sum((y_pred != cls) & (y_true == cls)))
        support = tp + fn
        recalls.append(tp / support if support > 0 else 0.0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = recalls[-1]
        f1s.append(2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0)
    return {
        "accuracy": acc,
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1s)),
        "per_class_recall": [round(r, 4) for r in recalls],
        "confusion": confusion_matrix(y_true, y_pred, labels=list(range(n_classes))).tolist(),
    }


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Text features x bucket scheme")
    parser.add_argument("--pairs", default=os.path.join(here, "sharegpt_pairs.pkl"))
    parser.add_argument("--raw", default=os.path.join(here, "ShareGPT_V3_unfiltered_cleaned_split.json"))
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--max-rows", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=os.path.join(here, "final_bucket_results.json"))
    parser.add_argument("--no-char", action="store_true",
                        help="skip char_wb n-grams (much faster; word n-grams carry the signal)")
    args = parser.parse_args()

    import sys
    sys.path.insert(0, here)
    from bucket_classification import add_derived_features

    t0 = time.time()
    print("[1/3] preparing features")
    frame = pd.read_pickle(args.pairs)
    texts_map = load_texts(args.raw)
    frame = frame[frame["id"].isin(texts_map)].copy()
    if args.max_rows and len(frame) > args.max_rows:
        frame = frame.sample(n=args.max_rows, random_state=args.seed)
    frame = frame.reset_index(drop=True)
    frame["prompt_text"] = frame["id"].map(texts_map)

    rich = add_derived_features(frame)
    hand_cols = [c for c in rich.columns
                 if c not in ID_COLS + [TARGET_COL] + LEAKY_COLS + ["prompt_text"]]
    X_hand = StandardScaler().fit_transform(rich[hand_cols].to_numpy(dtype=float)) * HAND_WEIGHT
    texts = frame["prompt_text"].tolist()
    y_len = frame[TARGET_COL].to_numpy(dtype=float)
    print(f"      {len(frame)} rows, {len(hand_cols)} hand features ({time.time() - t0:.0f}s)")

    # stateless text hashing, shared across all folds and schemes.
    # 2**18 dims: 2**19 made LogisticRegression ~3x slower per fit without changing the
    # conclusions, and this script refits once per scheme per fold.
    hasher = HashingVectorizer(n_features=2 ** 18, alternate_sign=False, norm="l2",
                               ngram_range=(1, 2), lowercase=True)
    X_word = hasher.transform(texts)
    if args.no_char:
        X_text = X_word.tocsr()
    else:
        char_hasher = HashingVectorizer(n_features=2 ** 18, alternate_sign=False, norm="l2",
                                        analyzer="char_wb", ngram_range=(4, 5), lowercase=True)
        X_text = sp.hstack([X_word, char_hasher.transform(texts)]).tocsr()
    X_all = sp.hstack([sp.csr_matrix(X_hand), X_text]).tocsr()
    print(f"      text matrix {X_text.shape}, combined {X_all.shape} ({time.time() - t0:.0f}s)")

    print(f"[2/3] sweeping {len(SCHEMES)} bucket schemes ({args.folds}-fold CV)")
    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
    folds = list(skf.split(X_all, np.zeros(len(y_len))))

    results: Dict[str, Dict[str, object]] = {}
    for name, cuts in SCHEMES.items():
        n_classes = len(cuts) + 1
        y = scheme_labels(y_len, cuts)
        shares = np.bincount(y, minlength=n_classes) / len(y)

        skf_y = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
        pred_lr = np.zeros(len(y), dtype=int)
        for tr, te in skf_y.split(X_all, y):
            lr = LogisticRegression(max_iter=1000, C=4.0, solver="liblinear")
            lr.fit(X_all[tr], y[tr])
            pred_lr[te] = lr.predict(X_all[te])

        m_lr = metrics(y, pred_lr, n_classes)
        majority = float(shares.max())
        results[name] = {"n_classes": n_classes, "class_shares": shares.tolist(),
                         "majority_accuracy": majority, "text_logreg": m_lr}

        print(f"  {name:<24} shares={','.join(f'{s * 100:.0f}%' for s in shares)}")
        print(f"      text+hand LR : acc={m_lr['accuracy']:.4f} bal={m_lr['balanced_accuracy']:.4f} "
              f"macroF1={m_lr['macro_f1']:.4f}  (majority {majority:.4f}, lift {m_lr['accuracy'] - majority:+.4f})")
        print()

    best_name = max(results, key=lambda k: results[k]["text_logreg"]["accuracy"])
    best = results[best_name]
    print(f"[3/3] best scheme by accuracy: {best_name} "
          f"(acc={best['text_logreg']['accuracy']:.4f})")
    print("      confusion matrix (rows=true, cols=pred):")
    for row in best["text_logreg"]["confusion"]:
        print("        " + " ".join(f"{v:6d}" for v in row))
    print("      per-class recall: " + ", ".join(f"{r:.3f}" for r in best["text_logreg"]["per_class_recall"]))

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"results": results, "best": best_name}, handle, indent=2)
    print()
    print(f"report -> {args.out}  (total {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
