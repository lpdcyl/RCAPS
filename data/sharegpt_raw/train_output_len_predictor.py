"""
Train and evaluate a point predictor for ShareGPT output length.

Input : data/sharegpt_raw/sharegpt_pairs.pkl  (built by extract_features.py)
Output: printed evaluation report + data/sharegpt_raw/output_len_model.pkl

What this answers
-----------------
The scientific question here is NOT "can we fit the target" but "is output length
predictable from the prompt at all, and how much do prompt features buy us over the
trivial baseline". So the report always reports four baselines next to the model:

    global mean      : predict train-set mean for everything (the floor)
    input_len only   : single-feature linear fit on prompt token count
    features + ridge : all cheap features, linear model
    features + GBR   : all cheap features, gradient boosting (the main model)

Metrics are reported in TOKEN units (MAE / RMSE / R2), plus median AE and the
fraction of predictions within +/-50% of the true length, which matters more than R2
for a serving simulator that only needs the right order of magnitude.
"""

import argparse
import json
import os
import time
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

ID_COLS = ["id"]
TARGET_COL = "output_len"


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Compute token-space regression metrics.

    :param y_true: ground-truth output lengths
    :param y_pred: predicted output lengths
    :return: dict of metric name -> value
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    residual = y_pred - y_true

    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    denom = np.maximum(y_true, 1.0)
    return {
        "MAE": float(np.mean(np.abs(residual))),
        "RMSE": float(np.sqrt(np.mean(residual ** 2))),
        "R2": r2,
        "MedAE": float(np.median(np.abs(residual))),
        "within_50pct": float(np.mean(np.abs(residual) / denom <= 0.5)),
        "within_100pct": float(np.mean(np.abs(residual) / denom <= 1.0)),
        "bias": float(np.mean(residual)),
    }


def spearman_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation without pulling in scipy.stats."""
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else float("nan")


def cross_val_predict(make_model, X: np.ndarray, y: np.ndarray, folds: int, seed: int) -> np.ndarray:
    """
    Out-of-fold predictions.

    :param make_model: zero-arg callable returning a fresh estimator
    :param X: feature matrix
    :param y: target vector
    :param folds: number of CV folds
    :param seed: shuffle seed
    :return: out-of-fold prediction vector aligned with y
    """
    kf = KFold(n_splits=folds, shuffle=True, random_state=seed)
    out = np.zeros_like(y, dtype=float)
    for train_idx, test_idx in kf.split(X):
        model = make_model()
        model.fit(X[train_idx], y[train_idx])
        out[test_idx] = model.predict(X[test_idx])
    return out


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Train/evaluate ShareGPT output-length predictor")
    parser.add_argument("--input", default=os.path.join(here, "sharegpt_pairs.pkl"))
    parser.add_argument("--model-out", default=os.path.join(here, "output_len_model.pkl"))
    parser.add_argument("--report-out", default=os.path.join(here, "output_len_report.json"))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-rows", type=int, default=0, help="subsample rows for a fast run (0 = all)")
    parser.add_argument("--log-target", action="store_true",
                        help="train on log1p(target) instead of the raw count")
    args = parser.parse_args()

    print(f"[1/5] loading {args.input}")
    frame = pd.read_pickle(args.input)
    if args.max_rows and args.max_rows < len(frame):
        frame = frame.sample(n=args.max_rows, random_state=args.seed).reset_index(drop=True)
    print(f"      {len(frame)} pairs, {frame.shape[1]} columns")

    feature_cols: List[str] = [c for c in frame.columns if c not in ID_COLS + [TARGET_COL]]
    X = frame[feature_cols].to_numpy(dtype=float)
    y = frame[TARGET_COL].to_numpy(dtype=float)
    input_len = frame["input_len"].to_numpy(dtype=float)

    # ---------------------------------------------------------------- data sanity
    print("[2/5] target distribution")
    quantiles = [0.01, 0.05, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0]
    for q in quantiles:
        print(f"      p{q * 100:5.1f} = {np.quantile(y, q):8.1f}")
    print(f"      mean   = {y.mean():8.1f}   std = {y.std():8.1f}")
    print(f"      frac(output_len == 0): {np.mean(y == 0):.4f}")
    print(f"      spearman(input_len, output_len) = {spearman_corr(input_len, y):+.4f}")
    print(f"      pearson (input_len, output_len) = {np.corrcoef(input_len, y)[0, 1]:+.4f}")

    # ---------------------------------------------------------------- baselines
    print(f"[3/5] cross-validated evaluation ({args.folds} folds, out-of-fold predictions)")
    y_sq = np.log1p(y) if args.log_target else y

    def unwrap(pred_log_space: np.ndarray) -> np.ndarray:
        """Map predictions back to token space when training on log1p."""
        pred = np.expm1(pred_log_space) if args.log_target else pred_log_space
        return np.clip(pred, 0.0, None)

    results: Dict[str, Dict[str, float]] = {}

    # baseline 0: global mean
    pred_mean = cross_val_predict(lambda: _MeanRegressor(), X[:, :1], y_sq, args.folds, args.seed)
    results["global_mean"] = regression_metrics(y, unwrap(pred_mean))

    # baseline 1: input_len only, linear
    pred_lin_in = cross_val_predict(lambda: _ScaledRidge(alpha=1.0), input_len.reshape(-1, 1), y_sq,
                                    args.folds, args.seed)
    results["input_len_linear"] = regression_metrics(y, unwrap(pred_lin_in))

    # baseline 2: all features, ridge
    pred_ridge = cross_val_predict(lambda: _ScaledRidge(alpha=1.0), X, y_sq, args.folds, args.seed)
    results["features_ridge"] = regression_metrics(y, unwrap(pred_ridge))

    # main model: all features, gradient boosting
    def make_gbr():
        return HistGradientBoostingRegressor(
            max_iter=400,
            learning_rate=0.06,
            max_depth=6,
            min_samples_leaf=40,
            l2_regularization=1.0,
            random_state=args.seed,
        )

    pred_gbr = cross_val_predict(make_gbr, X, y_sq, args.folds, args.seed)
    results["features_gbr"] = regression_metrics(y, unwrap(pred_gbr))

    # ---------------------------------------------------------------- report
    print(f"[4/5] results (token space, target={'log1p' if args.log_target else 'raw'})")
    header = f"      {'model':<18} {'MAE':>8} {'RMSE':>9} {'R2':>8} {'MedAE':>8} {'<=50%':>7} {'<=100%':>7} {'bias':>8}"
    print(header)
    print("      " + "-" * (len(header) - 6))
    for name, metrics in results.items():
        print(f"      {name:<18} {metrics['MAE']:>8.1f} {metrics['RMSE']:>9.1f} {metrics['R2']:>8.4f} "
              f"{metrics['MedAE']:>8.1f} {metrics['within_50pct']:>7.3f} {metrics['within_100pct']:>7.3f} "
              f"{metrics['bias']:>+8.1f}")

    gain = results["input_len_linear"]["MAE"] - results["features_gbr"]["MAE"]
    rel = gain / results["input_len_linear"]["MAE"] * 100
    print()
    print(f"      MAE improvement of features_gbr over input_len_linear: {gain:+.1f} tokens ({rel:+.1f}%)")

    # ---------------------------------------------------------------- feature importance
    print("[5/5] permutation importance on a holdout split (top 15)")
    rng = np.random.default_rng(args.seed)
    order = rng.permutation(len(X))
    split = int(len(X) * 0.8)
    train_idx, test_idx = order[:split], order[split:]
    final_model = make_gbr()
    final_model.fit(X[train_idx], y_sq[train_idx])
    base_mae = regression_metrics(y[test_idx], unwrap(final_model.predict(X[test_idx])))["MAE"]

    importances = []
    for col_idx, col_name in enumerate(feature_cols):
        X_perm = X[test_idx].copy()
        X_perm[:, col_idx] = rng.permutation(X_perm[:, col_idx])
        perm_mae = regression_metrics(y[test_idx], unwrap(final_model.predict(X_perm)))["MAE"]
        importances.append((col_name, perm_mae - base_mae))
    importances.sort(key=lambda item: item[1], reverse=True)
    print(f"      holdout MAE = {base_mae:.1f}; delta MAE when a feature is shuffled")
    for name, delta in importances[:15]:
        print(f"        {name:<26} {delta:+8.2f}")

    # ---------------------------------------------------------------- persist
    final_model.fit(X, y_sq)
    with open(args.model_out, "wb") as handle:
        import pickle
        pickle.dump({
            "model": final_model,
            "feature_cols": feature_cols,
            "log_target": args.log_target,
            "metrics": results,
        }, handle)
    with open(args.report_out, "w", encoding="utf-8") as handle:
        json.dump({"results": results, "n_pairs": int(len(frame)),
                   "importances": [{"feature": n, "delta_mae": float(d)} for n, d in importances]},
                  handle, indent=2)
    print()
    print(f"      model  -> {args.model_out}")
    print(f"      report -> {args.report_out}")


# --------------------------------------------------------------------------------------
# Small helper estimators (kept here to avoid extra imports at module scope)
# --------------------------------------------------------------------------------------

class _MeanRegressor:
    """Predict the training mean."""

    def fit(self, X, y):
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(X.shape[0], self.mean_)


class _ScaledRidge:
    """Standardize features then ridge-regress."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, X, y):
        self.scaler_ = StandardScaler().fit(X)
        self.model_ = Ridge(alpha=self.alpha).fit(self.scaler_.transform(X), y)
        return self

    def predict(self, X):
        return self.model_.predict(self.scaler_.transform(X))


if __name__ == "__main__":
    main()
