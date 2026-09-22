"""
Build a (prompt -> real output length) dataset from the raw ShareGPT dump.

Input : data/sharegpt_raw/ShareGPT_V3_unfiltered_cleaned_split.json
Output: data/sharegpt_raw/sharegpt_pairs.pkl

Design notes
------------
1. Prompt/target split follows the vLLM-style ShareGPT preprocessing rule used by the
   upstream Helix artifact: take the FIRST non-empty `human` turn as the prompt and the
   FIRST non-empty `gpt` turn after it as the target response. The raw dump has 94145
   conversations but only 58827 start with a `human` turn (others open with `system`),
   so we search for the first human turn instead of assuming index 0.
2. Token lengths are measured with the LLaMA tokenizer that already ships with this
   repo (artifact_evaluation/single_cluster/models/llama70b), so the lengths are on
   exactly the same scale as the existing length_data/*.pkl files. That makes the new
   dataset directly comparable with `Dataset.SharedGPT`.
3. We keep raw text out of the feature table to stay small; only derived features are
   stored. Set --dump-prompts to also write a prompts.jsonl for inspection.
4. Output is pickle rather than parquet so the pipeline has no extra binary dependency
   (the feature table is only ~94k rows).
5. Length caps (`--max-input-tokens` / `--max-output-tokens`) drop a handful of genuine
   but pathological rows (e.g. id 6E4LLxD_12 pastes a 394k-char CSV, giving 241402 prompt
   tokens). They are real data, not corruption, but they carry virtually no signal for
   output-length prediction while dominating squared-error metrics. The retained count
   is reported so the filtering cost is always visible.
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# --------------------------------------------------------------------------------------
# Prompt extraction
# --------------------------------------------------------------------------------------

HUMAN_ROLES = ("human", "user")
ASSISTANT_ROLES = ("gpt", "chatgpt", "bard", "bing")


def extract_prompt_target(conversation: Dict[str, Any]) -> Optional[Tuple[str, str, int]]:
    """
    Pull the first (human, assistant) exchange out of one ShareGPT conversation.

    :param conversation: one raw record with a "conversations" list
    :return: (prompt, target, num_total_turns) or None when no usable exchange exists
    """
    turns: List[Dict[str, Any]] = conversation.get("conversations") or []
    total_turns = len(turns)

    human_idx: Optional[int] = None
    for idx, turn in enumerate(turns):
        if turn.get("from") in HUMAN_ROLES and (turn.get("value") or "").strip():
            human_idx = idx
            break
    if human_idx is None:
        return None

    assistant_idx: Optional[int] = None
    for idx in range(human_idx + 1, total_turns):
        if turns[idx].get("from") in ASSISTANT_ROLES and (turns[idx].get("value") or "").strip():
            assistant_idx = idx
            break
    if assistant_idx is None:
        return None

    return turns[human_idx]["value"], turns[assistant_idx]["value"], total_turns


# --------------------------------------------------------------------------------------
# Cheap, tokenizer-free features (computed from the raw prompt string)
# --------------------------------------------------------------------------------------

_RE_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_RE_CODE_FENCE = re.compile(r"```")
_RE_INLINE_CODE = re.compile(r"`[^`\n]+`")
_RE_CODE_KW = re.compile(
    r"\b(def|class|import|function|return|console\.log|printf|public static|"
    r"#include|SELECT|FROM|WHERE|npm |pip install|git |docker )\b"
)
_RE_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.MULTILINE)
_RE_BULLET_WORDS = re.compile(r"\b(bullet points?|list|steps?|enumerate|outline)\b", re.IGNORECASE)
_RE_JSON = re.compile(r"^\s*[\[{]")
_RE_TRANSLATE = re.compile(r"\b(translate|translation|in (?:chinese|spanish|french|german|japanese))\b", re.IGNORECASE)
_RE_SUMMARIZE = re.compile(r"\b(summari[sz]e|summary|tl;?dr|condense)\b", re.IGNORECASE)
_RE_EXPLAIN = re.compile(r"\b(explain|why|how does|what is|what are|describe)\b", re.IGNORECASE)
_RE_WRITE = re.compile(r"\b(write|draft|compose|generate|create)\b", re.IGNORECASE)
_RE_CODE_REQUEST = re.compile(r"\b(code|program|script|function|implement|debug|refactor|regex)\b", re.IGNORECASE)
_RE_ESSAY = re.compile(r"\b(essay|article|blog|story|poem|letter|email)\b", re.IGNORECASE)

_WORD_RE = re.compile(r"\S+")
_SENT_RE = re.compile(r"[.!?]+")


def cheap_features(prompt: str) -> Dict[str, float]:
    """
    Extract string-level statistics and crude intent flags from a prompt.

    :param prompt: raw prompt text
    :return: dict of feature name -> value
    """
    stripped = prompt.strip()
    lines = prompt.splitlines()
    words = _WORD_RE.findall(prompt)
    n_chars = len(prompt)

    return {
        # ---- size ----
        "n_chars": n_chars,
        "n_chars_nospace": len(re.sub(r"\s", "", prompt)),
        "n_words": len(words),
        "n_lines": len(lines),
        "n_nonempty_lines": sum(1 for line in lines if line.strip()),
        "n_sentences": max(1, len([s for s in _SENT_RE.split(prompt) if s.strip()])),
        "avg_word_len": (sum(len(w) for w in words) / len(words)) if words else 0.0,
        # ---- lexical shape ----
        "n_question_marks": prompt.count("?"),
        "n_exclamations": prompt.count("!"),
        "n_newlines": prompt.count("\n"),
        "n_digits": sum(c.isdigit() for c in prompt),
        "n_upper": sum(c.isupper() for c in prompt),
        "n_punct": sum((not c.isalnum()) and (not c.isspace()) for c in prompt),
        # ---- structural markers ----
        "n_code_fence": len(_RE_CODE_FENCE.findall(prompt)),
        "n_inline_code": len(_RE_INLINE_CODE.findall(prompt)),
        "has_code_kw": float(bool(_RE_CODE_KW.search(prompt))),
        "n_list_items": len(_RE_LIST.findall(prompt)),
        "starts_with_json": float(bool(_RE_JSON.match(stripped))),
        "has_url": float(bool(_RE_URL.search(prompt))),
        # ---- intent flags ----
        "is_bullet_req": float(bool(_RE_BULLET_WORDS.search(prompt))),
        "is_translate": float(bool(_RE_TRANSLATE.search(prompt))),
        "is_summarize": float(bool(_RE_SUMMARIZE.search(prompt))),
        "is_explain": float(bool(_RE_EXPLAIN.search(prompt))),
        "is_write": float(bool(_RE_WRITE.search(prompt))),
        "is_code_req": float(bool(_RE_CODE_REQUEST.search(prompt))),
        "is_essay_req": float(bool(_RE_ESSAY.search(prompt))),
        # ---- misc ----
        "starts_with_question_word": float(
            bool(re.match(r"\s*(what|why|how|when|where|who|which|can|could|should|is|are|do|does)\b",
                          prompt, re.IGNORECASE))
        ),
        "n_instruction_verbs": len(re.findall(
            r"\b(write|explain|list|describe|give|provide|create|make|analyze|compare|summarize|"
            r"translate|generate|help|show|tell|find|calculate)\b", prompt, re.IGNORECASE)),
    }


# --------------------------------------------------------------------------------------
# Parallel worker
# --------------------------------------------------------------------------------------

_WORKER_TOKENIZER = None
_WORKER_TOKENIZER_PATH = None


def _init_worker(tokenizer_path: str) -> None:
    """Load the tokenizer once per process."""
    global _WORKER_TOKENIZER, _WORKER_TOKENIZER_PATH
    from transformers import AutoTokenizer
    _WORKER_TOKENIZER = AutoTokenizer.from_pretrained(tokenizer_path)
    _WORKER_TOKENIZER_PATH = tokenizer_path


def _process_batch(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Turn a batch of raw conversations into feature rows."""
    prompts: List[str] = []
    targets: List[str] = []
    turn_counts: List[int] = []
    ids: List[str] = []

    for record in batch:
        parsed = extract_prompt_target(record)
        if parsed is None:
            continue
        prompt, target, total_turns = parsed
        prompts.append(prompt)
        targets.append(target)
        turn_counts.append(total_turns)
        ids.append(record.get("id", ""))

    if not prompts:
        return []

    tok = _WORKER_TOKENIZER
    prompt_encodings = tok(prompts, add_special_tokens=True)["input_ids"]
    target_encodings = tok(targets, add_special_tokens=True)["input_ids"]

    rows: List[Dict[str, Any]] = []
    for i, prompt in enumerate(prompts):
        row: Dict[str, Any] = {
            "id": ids[i],
            "input_len": len(prompt_encodings[i]),
            "output_len": len(target_encodings[i]),
            "raw_num_turns": turn_counts[i],
        }
        row.update(cheap_features(prompt))
        rows.append(row)
    return rows


def chunked(items: List[Any], size: int):
    """Yield successive chunks of `size`."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------

def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))

    parser = argparse.ArgumentParser(description="Build ShareGPT prompt->output-length dataset")
    parser.add_argument("--input", default=os.path.join(here, "ShareGPT_V3_unfiltered_cleaned_split.json"),
                        help="raw ShareGPT json")
    parser.add_argument("--output", default=os.path.join(here, "sharegpt_pairs.pkl"),
                        help="output pickle path")
    parser.add_argument("--tokenizer",
                        default=os.path.join(repo_root, "artifact_evaluation", "single_cluster", "models", "llama70b"),
                        help="tokenizer directory")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4)),
                        help="number of parallel processes")
    parser.add_argument("--limit", type=int, default=0, help="only process the first N conversations (0 = all)")
    parser.add_argument("--max-input-tokens", type=int, default=8192,
                        help="drop pairs whose prompt exceeds this many tokens (0 = no cap)")
    parser.add_argument("--max-output-tokens", type=int, default=2048,
                        help="drop pairs whose target exceeds this many tokens (0 = no cap)")
    parser.add_argument("--dump-prompts", action="store_true",
                        help="also write prompts.jsonl with the raw prompt/target text")
    args = parser.parse_args()

    t_start = time.time()
    print(f"[1/4] loading {args.input}")
    with open(args.input, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if args.limit:
        raw = raw[:args.limit]
    print(f"      {len(raw)} conversations")

    print(f"[2/4] tokenizing + featurizing with {args.workers} workers")
    batches = list(chunked(raw, 500))
    rows: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                            initargs=(args.tokenizer,)) as pool:
        for idx, part in enumerate(pool.map(_process_batch, batches)):
            rows.extend(part)
            if (idx + 1) % 20 == 0 or idx + 1 == len(batches):
                done = min((idx + 1) * 500, len(raw))
                print(f"      {done}/{len(raw)} conversations -> {len(rows)} pairs "
                      f"({time.time() - t_start:.0f}s)", flush=True)

    if not rows:
        print("ERROR: no usable prompt/target pairs produced", file=sys.stderr)
        sys.exit(1)

    print("[3/4] writing feature table")
    frame = pd.DataFrame(rows)

    # apply length caps (see module docstring note 5)
    n_before = len(frame)
    if args.max_input_tokens > 0:
        frame = frame[frame["input_len"] <= args.max_input_tokens]
    if args.max_output_tokens > 0:
        frame = frame[frame["output_len"] <= args.max_output_tokens]
    frame = frame.reset_index(drop=True)
    n_dropped = n_before - len(frame)

    if frame.empty:
        print("ERROR: all rows were removed by the length caps", file=sys.stderr)
        sys.exit(1)

    frame.to_pickle(args.output)

    if args.dump_prompts:
        prompt_path = os.path.join(os.path.dirname(args.output), "prompts.jsonl")
        with open(prompt_path, "w", encoding="utf-8") as handle:
            for record in raw:
                parsed = extract_prompt_target(record)
                if parsed is None:
                    continue
                prompt, target, _ = parsed
                handle.write(json.dumps({"id": record.get("id", ""), "prompt": prompt, "target": target},
                                        ensure_ascii=False) + "\n")
        print(f"      wrote {prompt_path}")

    print("[4/4] summary")
    print(f"      pairs            : {len(frame)}")
    print(f"      dropped by caps  : {n_dropped} ({n_dropped / n_before * 100:.2f}%)")
    print(f"      input_len  mean  : {frame['input_len'].mean():.1f}")
    print(f"      input_len  median: {frame['input_len'].median():.0f}")
    print(f"      output_len mean  : {frame['output_len'].mean():.1f}")
    print(f"      output_len median: {frame['output_len'].median():.0f}")
    print(f"      output_len p90   : {frame['output_len'].quantile(0.90):.0f}")
    print(f"      output_len max   : {frame['output_len'].max()}")
    print(f"      elapsed          : {time.time() - t_start:.1f}s")
    print()
    print("compare with the shipped Dataset.SharedGPT length_data:")
    print("      shipped avg_input=74.1 avg_output=228.6 max_input=1023 max_output=1046")


if __name__ == "__main__":
    main()
