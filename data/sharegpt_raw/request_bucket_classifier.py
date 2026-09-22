"""
Deliverable: a request classifier that buckets ShareGPT requests by output length.

Pipeline
--------
    prompt text
      -> hand-built statistics (length / punctuation / intent flags)
      -> TF-IDF word 1-2 grams + char_wb 4-5 grams
      -> LogisticRegression
      -> bucket label (short / medium / long ...)

The text n-grams are what make this work: on the output>256 task they lift AUC from 0.69
(hand statistics only) to ~0.80 and accuracy from 0.666 to ~0.74, against a 0.609
majority-class baseline. Prompt length alone is nearly useless (AUC ~0.48-0.53, i.e.
chance) -- the signal lives in WHAT the prompt asks for, not how long it is.

Usage
-----
    # fit and report cross-validated accuracy
    python request_bucket_classifier.py fit --scheme 2way_256

    # fit on everything and save the model
    python request_bucket_classifier.py fit --scheme 2way_256 --save bucket_model.pkl

    # label a new prompt (one per line, or a json/jsonl with a "prompt" field)
    python request_bucket_classifier.py predict --model bucket_model.pkl --input prompts.txt

Buckets are defined by inclusive upper bounds in tokens; the default 2way_256 scheme is
the best-measured configuration (accuracy ~0.74 at 61% majority baseline).
"""

import argparse
import json
import os
import pickle
import sys
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

TARGET_COL = "output_len"
ID_COLS = ["id"]
LEAKY_COLS = ["raw_num_turns"]
HAND_WEIGHT = 12.0

SCHEMES: Dict[str, Tuple[float, ...]] = {
    "2way_256": (256,),
    "2way_512": (512,),
    "3way_128_512": (128, 512),
    "3way_256_512": (256, 512),
    "4way_64_256_768": (64, 256, 768),
    "4way_128_256_512": (128, 256, 512),
}


def bucket_labels(values: Sequence[float], cuts: Sequence[float]) -> np.ndarray:
    """
    Map lengths to bucket indices using ascending inclusive cut points.

    :param values: output lengths in tokens
    :param cuts: e.g. (128, 512) means <=128, <=512, >512
    :return: integer labels
    """
    labels = np.zeros(len(values), dtype=int)
    arr = np.asarray(values, dtype=float)
    for cut in cuts:
        labels += (arr > cut).astype(int)
    return labels


def bucket_names(cuts: Sequence[float]) -> List[str]:
    """Human-readable names for each bucket."""
    names, prev = [], 0
    for cut in cuts:
        names.append(f"{prev + 1}-{int(cut)}")
        prev = int(cut)
    names.append(f">{prev}")
    return names


# --------------------------------------------------------------------------------------
# Feature building
# --------------------------------------------------------------------------------------

class BucketFeatureBuilder:
    """
    Turn raw prompts into the sparse feature matrix the classifier consumes.

    Holds the fitted text vectorizers and the hand-feature scaler so that inference and
    training use byte-identical transformations.
    """

    def __init__(self, hand_weight: float = HAND_WEIGHT, max_word_features: int = 200000,
                 max_char_features: int = 200000) -> None:
        self.hand_weight = hand_weight
        self.vec_word = TfidfVectorizer(ngram_range=(1, 2), min_df=3,
                                        max_features=max_word_features, sublinear_tf=True,
                                        strip_accents="unicode")
        self.vec_char = TfidfVectorizer(analyzer="char_wb", ngram_range=(4, 5), min_df=5,
                                        max_features=max_char_features, sublinear_tf=True)
        self.scaler: StandardScaler or None = None

    @staticmethod
    def hand_features(prompts: Sequence[str]) -> np.ndarray:
        """Compute the dense statistical features for a list of prompts."""
        from extract_features import cheap_features  # reuse the audited implementation

        rows = [cheap_features(p) for p in prompts]
        frame = pd.DataFrame(rows)
        # ratio features, kept in sync with add_derived_features
        eps = 1e-6
        frame["words_per_sentence"] = frame["n_words"] / (frame["n_sentences"] + eps)
        frame["chars_per_word"] = frame["n_chars"] / (frame["n_words"] + eps)
        frame["punct_ratio"] = frame["n_punct"] / (frame["n_chars"] + eps)
        frame["upper_ratio"] = frame["n_upper"] / (frame["n_chars"] + eps)
        frame["digit_ratio"] = frame["n_digits"] / (frame["n_chars"] + eps)
        frame["newline_per_line"] = frame["n_newlines"] / (frame["n_lines"] + eps)
        frame["question_density"] = frame["n_question_marks"] / (frame["n_sentences"] + eps)
        frame["code_marker_sum"] = frame["n_code_fence"] + frame["n_inline_code"] + frame["has_code_kw"]
        frame["intent_sum"] = (frame["is_bullet_req"] + frame["is_translate"] + frame["is_summarize"]
                               + frame["is_explain"] + frame["is_write"] + frame["is_code_req"]
                               + frame["is_essay_req"])
        frame["verb_density"] = frame["n_instruction_verbs"] / (frame["n_words"] + eps)
        frame["list_density"] = frame["n_list_items"] / (frame["n_nonempty_lines"] + eps)
        frame["log_input_len"] = np.log1p(frame["n_chars"])
        frame["is_very_short_prompt"] = (frame["n_words"] <= 3).astype(float)
        frame["is_long_prompt"] = (frame["n_chars"] > 4000).astype(float)
        return frame.to_numpy(dtype=float)

    def fit_transform(self, prompts: Sequence[str]) -> sp.csr_matrix:
        """Fit all vectorizers and return the training matrix."""
        hand = self.hand_features(prompts)
        self.scaler = StandardScaler().fit(hand)
        hand_scaled = sp.csr_matrix(self.scaler.transform(hand) * self.hand_weight)
        text = sp.hstack([self.vec_word.fit_transform(prompts),
                          self.vec_char.fit_transform(prompts)]).tocsr()
        return sp.hstack([hand_scaled, text]).tocsr()

    def transform(self, prompts: Sequence[str]) -> sp.csr_matrix:
        """Apply the fitted transformations to new prompts."""
        assert self.scaler is not None, "Feature builder must be fitted first"
        hand = self.hand_features(prompts)
        hand_scaled = sp.csr_matrix(self.scaler.transform(hand) * self.hand_weight)
        text = sp.hstack([self.vec_word.transform(prompts),
                          self.vec_char.transform(prompts)]).tocsr()
        return sp.hstack([hand_scaled, text]).tocsr()


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------

def report(y_true: np.ndarray, y_pred: np.ndarray, names: List[str]) -> Dict[str, float]:
    """Print and return accuracy, balanced accuracy and macro-F1."""
    n_classes = len(names)
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

    print(f"    accuracy          : {acc:.4f}")
    print(f"    balanced accuracy : {np.mean(recalls):.4f}")
    print(f"    macro F1          : {np.mean(f1s):.4f}")
    print(f"    per-class recall  : " + ", ".join(f"{n}={r:.3f}" for n, r in zip(names, recalls)))
    print("    confusion (rows=true, cols=pred):")
    matrix = confusion_matrix(y_true, y_pred, labels=list(range(n_classes)))
    for row in matrix:
        print("      " + " ".join(f"{v:6d}" for v in row))
    return {"accuracy": acc, "balanced_accuracy": float(np.mean(recalls)),
            "macro_f1": float(np.mean(f1s)), "per_class_recall": recalls}


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------

def load_pairs(path: str) -> pd.DataFrame:
    """Load the feature table that carries the real output-length labels."""
    frame = pd.read_pickle(path)
    for col in (ID_COLS + [TARGET_COL]):
        assert col in frame.columns, f"missing column {col} in {path}"
    return frame


def load_prompts(here: str, raw_path: str) -> Dict[str, str]:
    """Map id -> prompt text from the raw ShareGPT dump."""
    with open(raw_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    out: Dict[str, str] = {}
    for record in raw:
        for turn in (record.get("conversations") or []):
            if turn.get("from") in ("human", "user") and (turn.get("value") or "").strip():
                out[record.get("id", "")] = turn["value"]
                break
    return out


def cmd_fit(args: argparse.Namespace, here: str) -> None:
    """Fit the classifier and report cross-validated accuracy."""
    assert args.scheme in SCHEMES, f"unknown scheme {args.scheme}; choose from {list(SCHEMES)}"
    cuts = SCHEMES[args.scheme]
    names = bucket_names(cuts)

    frame = load_pairs(args.pairs)
    prompts_by_id = load_prompts(here, args.raw)
    frame = frame[frame["id"].isin(prompts_by_id)].copy()
    if args.max_rows and len(frame) > args.max_rows:
        frame = frame.sample(n=args.max_rows, random_state=args.seed)
    frame = frame.reset_index(drop=True)
    prompts = frame["id"].map(prompts_by_id).tolist()
    y = bucket_labels(frame[TARGET_COL].to_numpy(dtype=float), cuts)

    print(f"scheme      : {args.scheme}  buckets={names}")
    print(f"rows        : {len(frame)}")
    shares = np.bincount(y, minlength=len(names)) / len(y)
    print(f"class shares: " + ", ".join(f"{n}={s * 100:.1f}%" for n, s in zip(names, shares)))
    print(f"majority    : {shares.max():.4f}")
    print()

    if args.folds > 1:
        print(f"--- {args.folds}-fold cross-validated performance ---")
        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
        oof = np.zeros(len(y), dtype=int)
        for fold, (tr, te) in enumerate(skf.split(np.zeros(len(y)), y), start=1):
            builder = BucketFeatureBuilder()
            X_tr = builder.fit_transform([prompts[i] for i in tr])
            X_te = builder.transform([prompts[i] for i in te])
            clf = LogisticRegression(max_iter=1000, C=args.C, solver="liblinear")
            clf.fit(X_tr, y[tr])
            oof[te] = clf.predict(X_te)
            print(f"    fold {fold} done")
        report(y, oof, names)
        print()

    print("--- final fit on all data ---")
    builder = BucketFeatureBuilder()
    X = builder.fit_transform(prompts)
    clf = LogisticRegression(max_iter=1000, C=args.C, solver="liblinear")
    clf.fit(X, y)
    print(f"    fitted on {X.shape[0]} rows x {X.shape[1]} features")

    if args.save:
        with open(args.save, "wb") as handle:
            pickle.dump({"builder": builder, "classifier": clf, "scheme": args.scheme,
                         "cuts": cuts, "names": names, "C": args.C}, handle)
        print(f"    saved -> {args.save}")


def cmd_predict(args: argparse.Namespace, here: str) -> None:
    """Label new prompts."""
    with open(args.model, "rb") as handle:
        bundle = pickle.load(handle)
    builder: BucketFeatureBuilder = bundle["builder"]
    clf = bundle["classifier"]
    names: List[str] = bundle["names"]

    if args.input.endswith(".jsonl") or args.input.endswith(".json"):
        with open(args.input, "r", encoding="utf-8") as handle:
            if args.input.endswith(".jsonl"):
                records = [json.loads(line) for line in handle if line.strip()]
            else:
                records = json.load(handle)
        prompts = [r.get("prompt", "") for r in records]
    else:
        with open(args.input, "r", encoding="utf-8") as handle:
            prompts = [line.rstrip("\n") for line in handle if line.strip()]

    X = builder.transform(prompts)
    proba = clf.predict_proba(X)
    pred = proba.argmax(axis=1)

    print(f"scheme: {bundle['scheme']}  buckets={names}")
    for text, label, row in zip(prompts, pred, proba):
        conf = float(row[label])
        print(f"  [{names[label]:>12}] conf={conf:.3f}  {text[:70]!r}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            for text, label, row in zip(prompts, pred, proba):
                handle.write(json.dumps({"prompt": text, "bucket": names[label],
                                         "label": int(label),
                                         "confidence": float(row[label]),
                                         "proba": [float(p) for p in row]}, ensure_ascii=False) + "\n")
        print(f"wrote -> {args.output}")


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)

    parser = argparse.ArgumentParser(description="Bucket ShareGPT requests by output length")
    sub = parser.add_subparsers(dest="command", required=True)

    fit = sub.add_parser("fit", help="fit and evaluate the classifier")
    fit.add_argument("--scheme", default="2way_256", choices=list(SCHEMES))
    fit.add_argument("--pairs", default=os.path.join(here, "sharegpt_pairs.pkl"))
    fit.add_argument("--raw", default=os.path.join(here, "ShareGPT_V3_unfiltered_cleaned_split.json"))
    fit.add_argument("--folds", type=int, default=5)
    fit.add_argument("--max-rows", type=int, default=0, help="0 = all rows")
    fit.add_argument("--C", type=float, default=4.0)
    fit.add_argument("--seed", type=int, default=0)
    fit.add_argument("--save", default=os.path.join(here, "bucket_model.pkl"))

    pred = sub.add_parser("predict", help="label new prompts")
    pred.add_argument("--model", default=os.path.join(here, "bucket_model.pkl"))
    pred.add_argument("--input", required=True, help="txt (one prompt per line) or json/jsonl with 'prompt'")
    pred.add_argument("--output", default="")

    args = parser.parse_args()
    if args.command == "fit":
        cmd_fit(args, here)
    else:
        cmd_predict(args, here)


if __name__ == "__main__":
    main()
