"""
Ablation: how much of the output-length signal is actually available at request time?

Motivation
----------
The first training run reported R2=0.316 with `raw_num_turns` as the single most
important feature (delta-MAE +41). But `raw_num_turns` is the TOTAL number of messages
in the whole ShareGPT conversation. At the moment a first-turn request arrives, that
number is unknowable -- a serving system sees only the prompt. So a model that leans on
it cannot be deployed, and reporting its R2 would overstate what is achievable.

This script therefore compares three feature sets under identical CV:

    A. all features            (includes raw_num_turns; LEAKY, upper bound only)
    B. deployable features     (everything knowable from the prompt text alone)
    C. prompt length only      (single-feature reference)

and additionally reports bucketed accuracy, because a serving simulator mostly needs the
right ORDER OF MAGNITUDE rather than an exact token count.
"""

import argparse
import json
import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

TARGET_COL = "output_len"
ID_COLS = ["id"]
# Features that are NOT observable when the first request arrives.
LEAKY_COLS = ["raw_num_turns"]


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Token-space regression metrics."""
    residual = y_pred - y_true
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    denom = np.maximum(y_true, 1.0)
    return {
        "MAE": float(np.mean(np.abs(residual))),
        "RMSE": float(np.sqrt(np.mean(residual ** 2))),
        "R2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "MedAE": float(np.median(np.abs(residual))),
        "within_50pct": float(np.mean(np.abs(residual) / denom <= 0.5)),
        "spearman": _spearman(y_true, y_pred),
    }


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Rank correlation, computed directly to avoid a scipy dependency."""
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else float("nan")


def bucket_of(value: float, edges: List[float]) -> int:
    """Map a length to a bucket index."""
    for idx, edge in enumerate(edges):
        if value <= edge:
            return idx
    return len(edges)


def cv_predict(X: np.ndarray, y: np.ndarray, folds: int, seed: int) -> np.ndarray:
    """Out-of-fold gradient boosting predictions."""
    kf = KFold(n_splits=folds, shuffle=True, random_state=seed)
    out = np.zeros_like(y, dtype=float)
    for train_idx, test_idx in kf.split(X):
        model = HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.06, max_depth=6,
            min_samples_leaf=40, l2_regularization=1.0, random_state=seed,
        )
        model.fit(X[train_idx], y[train_idx])
        out[test_idx] = model.predict(X[test_idx])
    return np.clip(out, 0.0, None)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Deployable-signal ablation for output-length prediction")
    parser.add_argument("--input", default=os.path.join(here, "sharegpt_pairs.pkl"))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=os.path.join(here, "output_len_ablation.json"))
    args = parser.parse_args()

    frame = pd.read_pickle(args.input)
    y = frame[TARGET_COL].to_numpy(dtype=float)
    all_cols = [c for c in frame.columns if c not in ID_COLS + [TARGET_COL]]
    deploy_cols = [c for c in all_cols if c not in LEAKY_COLS]

    feature_sets: List[Tuple[str, List[str]]] = [
        ("A_all_with_leak", all_cols),
        ("B_deployable", deploy_cols),
        ("C_input_len_only", ["input_len"]),
    ]

    print(f"n = {len(frame)} pairs, folds = {args.folds}")
    print(f"leaky columns removed from B: {LEAKY_COLS}")
    print()

    # ---------------------------------------------------------------- length buckets
    edges = [64, 128, 256, 512, 1024]
    print("output_len buckets used for accuracy:")
    bucket_names = []
    prev = 0
    for edge in edges:
        name = f"{prev + 1}-{edge}"
        bucket_names.append(name)
        share = np.mean((y > prev) & (y <= edge))
        print(f"  {name:>9} tokens : {share * 100:5.1f}%")
        prev = edge
    top_share = np.mean(y > prev)
    bucket_names.append(f">{prev}")
    print(f"  {'>' + str(prev):>9} tokens : {top_share * 100:5.1f}%")
    print()

    y_bucket = np.array([bucket_of(v, edges) for v in y])

    # ---------------------------------------------------------------- evaluation
    header = (f"{'feature set':<20} {'MAE':>7} {'RMSE':>8} {'R2':>7} {'MedAE':>7} "
              f"{'<=50%':>7} {'rho':>7} {'bkt_acc':>8} {'bkt+-1':>7}")
    print(header)
    print("-" * len(header))

    report: Dict[str, Dict[str, float]] = {}
    for name, cols in feature_sets:
        X = frame[cols].to_numpy(dtype=float)
        pred = cv_predict(X, y, args.folds, args.seed)
        m = metrics(y, pred)
        pred_bucket = np.array([bucket_of(v, edges) for v in pred])
        exact = float(np.mean(pred_bucket == y_bucket))
        adjacent = float(np.mean(np.abs(pred_bucket - y_bucket) <= 1))
        m["bucket_acc"] = exact
        m["bucket_acc_adjacent"] = adjacent
        m["n_features"] = len(cols)
        report[name] = m
        print(f"{name:<20} {m['MAE']:>7.1f} {m['RMSE']:>8.1f} {m['R2']:>7.4f} {m['MedAE']:>7.1f} "
              f"{m['within_50pct']:>7.3f} {m['spearman']:>7.4f} {exact:>8.3f} {adjacent:>7.3f}")

    print()
    print("Reading of the numbers:")
    print("  rho        = Spearman correlation between prediction and truth")
    print("  bkt_acc    = exact bucket hit rate (7 buckets, random baseline ~ largest bucket share)")
    print("  bkt+-1     = hit rate allowing one bucket of error")
    print()

    leak_gain = report["A_all_with_leak"]["MAE"] - report["B_deployable"]["MAE"]
    base_gain = report["C_input_len_only"]["MAE"] - report["B_deployable"]["MAE"]
    print(f"removing the leaky feature costs {leak_gain:+.1f} MAE tokens "
          f"(A {report['A_all_with_leak']['MAE']:.1f} -> B {report['B_deployable']['MAE']:.1f})")
    print(f"prompt features beat input_len-only by {base_gain:+.1f} MAE tokens "
          f"(C {report['C_input_len_only']['MAE']:.1f} -> B {report['B_deployable']['MAE']:.1f})")

    # ---------------------------------------------------------------- per-bucket error
    print()
    print("B_deployable error by true bucket (does it fail systematically on long outputs?):")
    X = frame[deploy_cols].to_numpy(dtype=float)
    pred = cv_predict(X, y, args.folds, args.seed)
    print(f"  {'true bucket':>12} {'n':>7} {'mean_true':>10} {'mean_pred':>10} {'MAE':>8} {'bias':>8}")
    for bidx, bname in enumerate(bucket_names):
        sel = y_bucket == bidx
        if not sel.any():
            continue
        print(f"  {bname:>12} {sel.sum():>7} {y[sel].mean():>10.1f} {pred[sel].mean():>10.1f} "
              f"{np.mean(np.abs(pred[sel] - y[sel])):>8.1f} {np.mean(pred[sel] - y[sel]):>+8.1f}")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"results": report, "bucket_names": bucket_names, "n": int(len(frame))},
                  handle, indent=2)
    print()
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()
