"""
build_augmented_humaneval_csv.py
=================================
Builds the augmented stratified_human_eval_full_factorial.csv with:
  - Original 30 Cochran-sampled pairwise items
  - 11 new Two-Step vs Two-Step items (for independent plan quality Cochran sample, n=22/N=74)
  - 3 sentinel items (hidden reliability checks — same pair as an existing item, A/B swapped)
  - conditions_a / conditions_b columns for Two-Step items

Run from repo root:
    python step4_evaluation/build_augmented_humaneval_csv.py
"""
import json
import random
import re
from pathlib import Path

import pandas as pd

REPO        = Path(r"c:\Repos\slm_test_generation")
PRED_DIR    = REPO / "TestEval/predictions_realworld_1/run_1"
SRC_CSV     = REPO / "TestEval/predictions_judgellm/stratified_human_eval_full_factorial.csv"
FULL_JSONL  = REPO / "TestEval/predictions_judgellm/pairwise_judgements_full_factorial.jsonl"
UNIFIED_CSV = REPO / "TestEval/predictions_judgellm/unified_human_eval.csv"
OUT_CSV     = REPO / "TestEval/predictions_judgellm/stratified_human_eval_full_factorial.csv"
SURVEY_CSV  = Path(r"C:\Repos\code-evaluation-survey\stratified_human_eval_full_factorial.csv")

RANDOM_SEED = 42

# Map display model name fragment → linecov2 JSONL filename
MODEL_FILE = {
    "Qwen3-4B-Instruct":        "linecov2_Qwen3-4B-Instruct-2507_temp_0.0.jsonl",
    "Ministral-3-3B-Reasoning": "linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0.jsonl",
    "Ministral-3-8B-Instruct":  "linecov2_Ministral-3-8B-Instruct-2512-AWQ-8bit_temp_0.0.jsonl",
    "gemma-3-4b-it":            "linecov2_gemma-3-4b-it_temp_0.0.jsonl",
    "granite-4.0-micro":        "linecov2_granite-4.0-micro_temp_0.0.jsonl",
}


def model_file(display_name: str):
    for key, fname in MODEL_FILE.items():
        if key in display_name:
            return PRED_DIR / fname
    return None


def load_pred_index():
    """Load all Two-Step predictions into {(model_key, task_num): conditions_text}."""
    idx = {}
    for model_key, fname in MODEL_FILE.items():
        fpath = PRED_DIR / fname
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                task_num = int(rec["task_num"])
                conds = rec.get("conditions", {})
                if conds:
                    parts = []
                    for line_num, info in sorted(conds.items(), key=lambda x: int(x[0])):
                        text = info.get("condition_text", "").strip()
                        # Strip <cond>…</cond> XML wrapper if present
                        text = re.sub(r"</?cond>", "", text).strip()
                        parts.append(f"**Line {line_num}:** {text}")
                    idx[(model_key, task_num)] = "\n\n".join(parts)
                else:
                    idx[(model_key, task_num)] = ""
    return idx


def get_conditions(display_name: str, task_id: int, pred_idx: dict) -> str:
    """Return formatted condition text for a model+task, or '' if not Two-Step / not found."""
    if "Two-S" not in display_name:
        return ""
    for key in MODEL_FILE:
        if key in display_name:
            return pred_idx.get((key, task_id), "")
    return ""


def assign_stratum(score_diff: float, final_winner: str) -> str:
    if final_winner == "Tie" or abs(score_diff) <= 2:
        return "Tie"
    if abs(score_diff) >= 6:
        return "Clear"
    return "Marginal"


def load_full_jsonl():
    records = []
    with open(FULL_JSONL, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def main():
    rng = random.Random(RANDOM_SEED)

    print("Loading prediction index...")
    pred_idx = load_pred_index()
    print(f"  {len(pred_idx)} (model, task) entries loaded")

    print("Loading full JSONL...")
    all_pairs = load_full_jsonl()
    print(f"  {len(all_pairs)} pairs total")

    print("Loading existing stratified CSV...")
    src_df = pd.read_csv(SRC_CSV)
    existing_keys = set(zip(src_df["task_id"].astype(int), src_df["model_a"], src_df["model_b"]))
    print(f"  {len(src_df)} existing rows")

    # --- Step 1: Add conditions columns to existing 30 rows ---
    src_df["conditions_a"] = [
        get_conditions(row["model_a"], int(row["task_id"]), pred_idx)
        for _, row in src_df.iterrows()
    ]
    src_df["conditions_b"] = [
        get_conditions(row["model_b"], int(row["task_id"]), pred_idx)
        for _, row in src_df.iterrows()
    ]
    src_df["is_sentinel"] = False
    src_df["sentinel_of_task_id"] = None

    two_step_existing = src_df[
        src_df["model_a"].str.contains("Two-S") & src_df["model_b"].str.contains("Two-S")
    ]
    print(f"  {len(two_step_existing)} existing Two-Step vs Two-Step items with conditions joined")

    # --- Step 2: Sample 11 new Two-Step vs Two-Step items ---
    candidates = [
        r for r in all_pairs
        if "Two-S" in r.get("model_a", "") and "Two-S" in r.get("model_b", "")
        and (int(r["task_id"]), r["model_a"], r["model_b"]) not in existing_keys
    ]
    print(f"  {len(candidates)} Two-Step candidate pairs not already sampled")

    # Assign strata and stratify sample
    for r in candidates:
        r["_stratum"] = assign_stratum(
            float(r.get("score_diff", 0)),
            r.get("final_winner_model", "Tie")
        )

    by_stratum = {"Clear": [], "Marginal": [], "Tie": []}
    for r in candidates:
        by_stratum[r["_stratum"]].append(r)

    # Try 2 Clear + 2 Marginal + 1 Tie (fallback to available)
    # Plan quality sub-sample: original 30 already contains ~11 Two-Step pairs;
    # 5 extras bring total to ~16, satisfying Cochran n=16 at e=0.25, 95% CI.
    targets = {"Clear": 2, "Marginal": 2, "Tie": 1}
    new_pairs = []
    for stratum, want in targets.items():
        pool = by_stratum[stratum]
        rng.shuffle(pool)
        new_pairs.extend(pool[:want])

    # Top up to 5 if any stratum ran short
    added_keys = {(int(r["task_id"]), r["model_a"], r["model_b"]) for r in new_pairs}
    leftover = [r for r in candidates if (int(r["task_id"]), r["model_a"], r["model_b"]) not in added_keys]
    rng.shuffle(leftover)
    while len(new_pairs) < 5 and leftover:
        new_pairs.append(leftover.pop())

    print(f"  Selected {len(new_pairs)} new Two-Step pairs:")
    stratum_counts = {}
    for r in new_pairs:
        s = r["_stratum"]
        stratum_counts[s] = stratum_counts.get(s, 0) + 1
    for s, c in stratum_counts.items():
        print(f"    {s}: {c}")

    # Build new rows
    new_rows = []
    for r in new_pairs:
        task_id = int(r["task_id"])
        model_a = r["model_a"]
        model_b = r["model_b"]
        cond_a = get_conditions(model_a, task_id, pred_idx)
        cond_b = get_conditions(model_b, task_id, pred_idx)

        new_rows.append({
            "task_id":              task_id,
            "stratum":              r["_stratum"],
            "score_diff":           float(r.get("score_diff", 0)),
            "model_a":              model_a,
            "model_b":              model_b,
            "model_a_total_score":  float(r.get("model_a_total_score", 0)),
            "model_b_total_score":  float(r.get("model_b_total_score", 0)),
            "docstring":            r.get("docstring", "No docstring."),
            "focal_code":           r.get("focal_code", ""),
            "code_a":               r.get("code_a", ""),
            "code_b":               r.get("code_b", ""),
            "reasoning_pass_full":  r.get("reasoning_pass_full", ""),
            "conditions_a":         cond_a,
            "conditions_b":         cond_b,
            "is_sentinel":          False,
            "sentinel_of_task_id":  None,
        })

    new_df = pd.DataFrame(new_rows)

    # --- Step 3: Combine existing + new ---
    combined = pd.concat([src_df, new_df], ignore_index=True)
    print(f"\nCombined: {len(combined)} rows (30 original + {len(new_rows)} new Two-Step, plan-quality e=0.25)")

    # --- Step 4: Pick 3 sentinel items from existing 30 ---
    # Use unified_human_eval.csv to find items with strongest annotator consensus
    unified = pd.read_csv(UNIFIED_CSV)
    agreed = unified[unified["human_consensus"].isin(["A", "B", "Tie"])].copy()

    # Count how many annotator columns agree with consensus
    ann_winner_cols = [c for c in unified.columns if re.match(r"ann\d+_winner$", c)]
    def agreement_count(row):
        consensus = row["human_consensus"]
        if consensus == "Disagreement":
            return 0
        return sum(1 for c in ann_winner_cols if row[c] == consensus)

    agreed = agreed.copy()
    agreed["_agree_count"] = agreed.apply(agreement_count, axis=1)
    agreed = agreed.sort_values("_agree_count", ascending=False)

    # Pick top 3 with different strata if possible
    sentinel_source = []
    used_strata = set()
    for _, row in agreed.iterrows():
        stratum = row["stratum"]
        if stratum not in used_strata and len(sentinel_source) < 3:
            sentinel_source.append(row)
            used_strata.add(stratum)
    # Fallback if strata aren't fully covered
    for _, row in agreed.iterrows():
        if len(sentinel_source) >= 3:
            break
        if int(row["task_id"]) not in {int(r["task_id"]) for r in sentinel_source}:
            sentinel_source.append(row)

    sentinel_source = sentinel_source[:3]
    print(f"\nSentinel sources (task_ids: {[int(r['task_id']) for r in sentinel_source]}):")

    sentinel_rows = []
    for src_row in sentinel_source:
        orig_task_id = int(src_row["task_id"])
        # Find the matching row in combined
        orig = combined[combined["task_id"] == orig_task_id].iloc[0]

        # Unique sentinel task_id: original + 100000
        sentinel_task_id = orig_task_id + 100000

        print(f"  task {orig_task_id} -> sentinel {sentinel_task_id} "
              f"(stratum={orig['stratum']}, consensus={src_row['human_consensus']})")

        sentinel_rows.append({
            "task_id":              sentinel_task_id,
            "stratum":              orig["stratum"],
            "score_diff":           -float(orig["score_diff"]),  # inverted because A/B swapped
            "model_a":              orig["model_b"],  # swapped
            "model_b":              orig["model_a"],  # swapped
            "model_a_total_score":  float(orig["model_b_total_score"]),
            "model_b_total_score":  float(orig["model_a_total_score"]),
            "docstring":            orig["docstring"],
            "focal_code":           orig["focal_code"],
            "code_a":               orig["code_b"],   # swapped
            "code_b":               orig["code_a"],   # swapped
            "reasoning_pass_full":  orig["reasoning_pass_full"],
            "conditions_a":         orig.get("conditions_b", ""),  # swapped
            "conditions_b":         orig.get("conditions_a", ""),  # swapped
            "is_sentinel":          True,
            "sentinel_of_task_id":  orig_task_id,
        })

    sentinel_df = pd.DataFrame(sentinel_rows)
    final_df = pd.concat([combined, sentinel_df], ignore_index=True)
    print(f"\nFinal CSV: {len(final_df)} rows "
          f"(30 original + {len(new_rows)} new Two-Step + 3 sentinels)")

    # Ensure column order is consistent
    base_cols = ["task_id", "stratum", "score_diff", "model_a", "model_b",
                 "model_a_total_score", "model_b_total_score",
                 "docstring", "focal_code", "code_a", "code_b", "reasoning_pass_full",
                 "conditions_a", "conditions_b", "is_sentinel", "sentinel_of_task_id"]
    final_df = final_df[base_cols]

    final_df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved: {OUT_CSV}")

    final_df.to_csv(SURVEY_CSV, index=False)
    print(f"Synced: {SURVEY_CSV}")

    # Summary
    print("\n--- Summary ---")
    real = final_df[~final_df["is_sentinel"]]
    both_ts = real[real["model_a"].str.contains("Two-S") & real["model_b"].str.contains("Two-S")]
    print(f"Real items: {len(real)} ({len(src_df)} original Cochran + {len(new_rows)} new Two-Step)")
    print(f"Two-Step vs Two-Step total: {len(both_ts)} (Cochran n=16 from N=74 for plan quality, e=0.25)")
    print(f"Sentinels: {len(final_df) - len(real)}")
    print(f"Two-Step pairs with conditions_a non-empty: "
          f"{(both_ts['conditions_a'].str.len() > 0).sum()}")
    print(f"Two-Step pairs with conditions_b non-empty: "
          f"{(both_ts['conditions_b'].str.len() > 0).sum()}")


if __name__ == "__main__":
    main()
