"""
Does the prompt TEXT carry more signal than hand-built statistics?

Motivation
----------
Hand-built features (lengths, punctuation, intent flags) reached accuracy 0.6817 on the
output>256 task with AUC 0.7099. Threshold tuning gave nothing (0.5 was already optimal),
so accuracy is bounded by AUC. The remaining lever is the feature space: every existing
feature is an aggregate statistic, and none of them looks at WHAT the prompt says.

This script adds sparse text n-grams (word 1-2 grams + char 4-5 grams) on top of the
hand-built features and re-measures AUC/accuracy. If text n-grams do not move the number,
the ceiling is informational, not a modelling failure.

Note: the prompt text is re-read from the raw ShareGPT dump, because the parquet/pickle
feature table deliberately stores no text.
"""

import argparse
import json
import os
import re
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

HUMAN_ROLES = ("human", "user")
ASSISTANT_ROLES = ("gpt", "chatgpt", "bard", "bing")


def extract_prompts(path: str, limit: int = 0) -> Tuple[List[str], List[int], List[str]]:
    """
    Re-read the raw dump and return (prompt, output_len_tokens, id) triples.

    :param path: raw ShareGPT json
    :param limit: optional cap on conversations
    :return: prompts, output token lengths, ids
    """
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if limit:
        raw = raw[:limit]

    prompts: List[str] = []
    ids: List[str] = []
    for record in raw:
        turns = record.get("conversations") or []
        human_idx = None
        for idx, turn in enumerate(turns):
            if turn.get("from") in HUMAN_ROLES and (turn.get("value") or "").strip():
                human_idx = idx
                break
        if human_idx is None:
            continue
        if not any(t.get("from") in ASSISTANT_ROLES and (t.get("value") or "").strip()
                   for t in turns[human_idx + 1:]):
            continue
        prompts.append(turns[human_idx]["value"])
        ids.append(record.get("id", ""))
    return prompts, ids


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))

    parser = argparse.ArgumentParser(description="Text n-gram feature ablation")
    parser.add_argument("--pairs", default=os.path.join(here, "sharegpt_pairs.pkl"))
    parser.add_argument("--raw", default=os.path.join(here, "ShareGPT_V3_unfiltered_cleaned_split.json"))
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threshold", type=int, default=256)
    parser.add_argument("--max-rows", type=int, default=40000,
                        help="cap rows: sparse TF-IDF on 93k x 5 folds is slow")
    parser.add_argument("--out", default=os.path.join(here, "text_feature_ablation.json"))
    args = parser.parse_args()

    t0 = time.time()
    print("[1/4] rebuilding prompt text from raw dump")
    frame = pd.read_pickle(args.pairs)
    prompts, ids = extract_prompts(args.raw)
    text_map = dict(zip(ids, prompts))
    frame = frame[frame["id"].isin(text_map)].copy()
    if args.max_rows and len(frame) > args.max_rows:
        frame = frame.sample(n=args.max_rows, random_state=args.seed)
    frame["prompt_text"] = frame["id"].map(text_map)
    frame = frame.reset_index(drop=True)
    print(f"      {len(frame)} rows with text ({time.time() - t0:.0f}s)")

    y_len = frame["output_len"].to_numpy(dtype=float)
    y = (y_len > args.threshold).astype(int)

    # hand-built features only (no leaky column)
    import sys
    sys.path.insert(0, here)
    from bucket_classification import add_derived_features, ID_COLS, LEAKY_COLS, TARGET_COL
    rich = add_derived_features(frame)
    hand_cols = [c for c in rich.columns
                 if c not in ID_COLS + [TARGET_COL] + LEAKY_COLS + ["prompt_text"]]
    X_hand = rich[hand_cols].to_numpy(dtype=float)
    texts = frame["prompt_text"].tolist()
    print(f"      {len(hand_cols)} hand features")

    print(f"[2/4] cross-validated comparison ({args.folds} folds, task: output_len > {args.threshold})")
    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)

    results: Dict[str, Dict[str, float]] = {}
    oof_store: Dict[str, np.ndarray] = {k: np.zeros(len(y)) for k in
                                        ["hand_gbr", "hand_logreg", "text_logreg", "hand_text_logreg", "hand_text_gbr"]}

    for fold, (tr, te) in enumerate(skf.split(X_hand, y)):
        # ---- text n-grams fitted on the training fold only (no leakage) ----
        vec_word = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=200000,
                                   sublinear_tf=True, strip_accents="unicode")
        vec_char = TfidfVectorizer(analyzer="char_wb", ngram_range=(4, 5), min_df=5,
                                   max_features=200000, sublinear_tf=True)
        tr_texts = [texts[i] for i in tr]
        te_texts = [texts[i] for i in te]
        Xw_tr = vec_word.fit_transform(tr_texts)
        Xw_te = vec_word.transform(te_texts)
        Xc_tr = vec_char.fit_transform(tr_texts)
        Xc_te = vec_char.transform(te_texts)
        X_text_tr = sp.hstack([Xw_tr, Xc_tr]).tocsr()
        X_text_te = sp.hstack([Xw_te, Xc_te]).tocsr()

        scaler = StandardScaler().fit(X_hand[tr])
        Xh_tr = scaler.transform(X_hand[tr])
        Xh_te = scaler.transform(X_hand[te])

        Xall_tr = sp.hstack([sp.csr_matrix(Xh_tr), X_text_tr]).tocsr()
        Xall_te = sp.hstack([sp.csr_matrix(Xh_te), X_text_te]).tocsr()

        # hand only
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_depth=6,
                                           min_samples_leaf=40, random_state=args.seed)
        m.fit(Xh_tr, y[tr]); oof_store["hand_gbr"][te] = m.predict_proba(Xh_te)[:, 1]

        m = LogisticRegression(max_iter=1000, C=1.0)
        m.fit(Xh_tr, y[tr]); oof_store["hand_logreg"][te] = m.predict_proba(Xh_te)[:, 1]

        # text only
        m = LogisticRegression(max_iter=1000, C=4.0, solver="liblinear")
        m.fit(X_text_tr, y[tr]); oof_store["text_logreg"][te] = m.predict_proba(X_text_te)[:, 1]

        # hand + text (logistic regression handles sparse; HGB does not)
        m = LogisticRegression(max_iter=1000, C=4.0, solver="liblinear")
        m.fit(Xall_tr, y[tr]); oof_store["hand_text_logreg"][te] = m.predict_proba(Xall_te)[:, 1]

        print(f"      fold {fold + 1}/{args.folds} done ({time.time() - t0:.0f}s)", flush=True)

    print("[3/4] results")
    header = f"      {'feature set':<26} {'AUC':>8} {'acc@0.5':>9} {'best_acc':>9} {'best_t':>8}"
    print(header)
    print("      " + "-" * (len(header) - 6))
    for name, prob in oof_store.items():
        auc = roc_auc_score(y, prob)
        acc05 = float(np.mean((prob > 0.5).astype(int) == y))
        thresholds = np.arange(0.20, 0.81, 0.01)
        accs = [float(np.mean((prob > t).astype(int) == y)) for t in thresholds]
        best_idx = int(np.argmax(accs))
        results[name] = {"auc": auc, "acc_at_0.5": acc05,
                         "best_acc": accs[best_idx], "best_threshold": float(thresholds[best_idx])}
        print(f"      {name:<26} {auc:>8.4f} {acc05:>9.4f} {accs[best_idx]:>9.4f} {thresholds[best_idx]:>8.2f}")

    print()
    print(f"      majority-class baseline: {max(np.mean(y), 1 - np.mean(y)):.4f}")
    gain = results["hand_text_logreg"]["auc"] - results["hand_gbr"]["auc"]
    print(f"      AUC gain of text n-grams over hand features: {gain:+.4f}")

    print("[4/4] top text n-grams pushing toward LONG outputs (from a full-data fit)")
    vec_word = TfidfVectorizer(ngram_range=(1, 2), min_df=5, max_features=200000, sublinear_tf=True)
    vec_char = TfidfVectorizer(analyzer="char_wb", ngram_range=(4, 5), min_df=5,
                               max_features=200000, sublinear_tf=True)
    Xw = vec_word.fit_transform(texts)
    Xc = vec_char.fit_transform(texts)
    Xt = sp.hstack([Xw, Xc]).tocsr()
    lr = LogisticRegression(max_iter=1000, C=4.0, solver="liblinear").fit(Xt, y)
    names = vec_word.get_feature_names_out().tolist() + vec_char.get_feature_names_out().tolist()
    coefs = lr.coef_[0]
    order = np.argsort(coefs)
    print("      -> long:")
    for i in order[-12:][::-1]:
        print(f"         {names[i]!r:<28} {coefs[i]:+.3f}")
    print("      -> short:")
    for i in order[:12]:
        print(f"         {names[i]!r:<28} {coefs[i]:+.3f}")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"results": results, "n": int(len(y)), "threshold": args.threshold}, handle, indent=2)
    print()
    print(f"report -> {args.out}  (total {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
