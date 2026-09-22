"""
Confidence-stratified classification: turn prediction uncertainty into a routing policy.

Why this is the right framing for a scheduler
---------------------------------------------
The earlier experiments established that prompt-level text features predict output length
with AUC ~0.80 (binary) but that ~26% of requests are still misclassified, and the errors
are not uniform: the classifier is confident on some requests and near-random on others.

A carbon-aware scheduler does not need one hard label per request. It needs to know which
requests it can safely route on a prediction and which must be handled conservatively
(pessimistic cost estimate, or defer to the delay-tolerant pool). So this script measures
the relationship between the classifier's own confidence and its correctness:

    for each confidence band, what fraction of predictions are actually right?

If high confidence really is reliable, the scheduler can route on predictions where
confidence is high and fall back elsewhere -- and the effective accuracy on the
"act-on-it" subset is what matters, not the global number.

Outputs a reliability table plus the accuracy/coverage trade-off curve.
"""

import argparse
import json
import os
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

TARGET_COL = "output_len"
ID_COLS = ["id"]
LEAKY_COLS = ["raw_num_turns"]
HAND_WEIGHT = 12.0
HUMAN_ROLES = ("human", "user")
TEXT_ONLY = False


def load_texts(raw_path: str) -> Dict[str, str]:
    """Map conversation id -> first human prompt text."""
    with open(raw_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    out: Dict[str, str] = {}
    for record in raw:
        for turn in (record.get("conversations") or []):
            if turn.get("from") in HUMAN_ROLES and (turn.get("value") or "").strip():
                out[record.get("id", "")] = turn["value"]
                break
    return out


def scheme_labels(values: np.ndarray, cuts: Tuple[float, ...]) -> np.ndarray:
    """Bucket indices by ascending inclusive cut points."""
    labels = np.zeros(len(values), dtype=int)
    for cut in cuts:
        labels += (values > cut).astype(int)
    return labels


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Confidence-stratified routing analysis")
    parser.add_argument("--pairs", default=os.path.join(here, "sharegpt_pairs.pkl"))
    parser.add_argument("--raw", default=os.path.join(here, "ShareGPT_V3_unfiltered_cleaned_split.json"))
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--max-rows", type=int, default=40000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=os.path.join(here, "confidence_routing.json"))
    args = parser.parse_args()

    import sys
    sys.path.insert(0, here)
    from bucket_classification import add_derived_features

    t0 = time.time()
    print("[1/3] preparing data")
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

    hasher = HashingVectorizer(n_features=2 ** 19, alternate_sign=False, norm="l2", ngram_range=(1, 2))
    char_hasher = HashingVectorizer(n_features=2 ** 19, alternate_sign=False, norm="l2",
                                    analyzer="char_wb", ngram_range=(4, 5))
    X_all = sp.hstack([sp.csr_matrix(X_hand), hasher.transform(texts), char_hasher.transform(texts)]).tocsr()
    print(f"      {len(frame)} rows, matrix {X_all.shape} ({time.time() - t0:.0f}s)")

    # three schemes that matter for routing: short/other, 3-tier, 4-tier
    schemes = {
        "2way_256": (256,),
        "3way_128_512": (128, 512),
        "4way_128_256_512": (128, 256, 512),
    }

    report: Dict[str, object] = {}
    print("[2/3] fitting and collecting out-of-fold probabilities")
    for name, cuts in schemes.items():
        y = scheme_labels(y_len, cuts)
        n_classes = len(cuts) + 1
        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
        proba = np.zeros((len(y), n_classes))
        for tr, te in skf.split(X_all, y):
            lr = LogisticRegression(max_iter=1000, C=4.0, solver="liblinear")
            lr.fit(X_all[tr], y[tr])
            proba[te] = lr.predict_proba(X_all[te])
        pred = np.argmax(proba, axis=1)
        conf = proba.max(axis=1)
        correct = (pred == y).astype(float)
        print(f"      {name}: overall acc={correct.mean():.4f}")

        # ---- reliability table ----
        bands = [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]
        reliability: List[Dict[str, float]] = []
        print(f"        {'confidence':>14} {'coverage':>9} {'accuracy':>9}")
        for lo, hi in bands:
            sel = (conf >= lo) & (conf < hi)
            if sel.sum() == 0:
                continue
            cov = float(sel.mean())
            acc = float(correct[sel].mean())
            reliability.append({"lo": lo, "hi": hi, "coverage": cov, "accuracy": acc,
                                "n": int(sel.sum())})
            print(f"        [{lo:.2f},{hi:.2f})   {cov:>8.3f} {acc:>9.3f}")

        # ---- coverage/accuracy trade-off: act only on the most confident ----
        order = np.argsort(-conf)
        curve: List[Dict[str, float]] = []
        print("        act-on-top-k:")
        for frac in [0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            k = int(len(order) * frac)
            idx = order[:k]
            acc = float(correct[idx].mean())
            curve.append({"coverage": frac, "accuracy": acc})
            print(f"          top {frac * 100:5.0f}%  acc={acc:.4f}")

        report[name] = {
            "n_classes": int(n_classes),
            "overall_accuracy": float(correct.mean()),
            "reliability": reliability,
            "coverage_curve": curve,
        }

    print("[3/3] summarising the actionable rule")
    print("      A scheduler can act on prediction when confidence >= 0.7:")
    for name, cuts in schemes.items():
        data = report[name]
        rel = data["reliability"]
        high = [r for r in rel if r["lo"] >= 0.7]
        if not high:
            continue
        n_high = sum(int(r["n"]) for r in high)
        acc_high = sum(r["accuracy"] * r["n"] for r in high) / max(1, n_high)
        n_all = sum(int(r["n"]) for r in rel)
        print(f"        {name:<20} coverage={n_high / n_all:.3f}  "
              f"accuracy-on-acted={acc_high:.4f}  (overall {data['overall_accuracy']:.4f})")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print()
    print(f"report -> {args.out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
