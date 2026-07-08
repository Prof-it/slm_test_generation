"""
build_second_exp_humaneval_csv.py
==================================
Builds a human evaluation CSV for the second experiment from raw predictions.
Can run BEFORE the LLM-as-judge runs — no judge output required.

Sampling strategy:
  - Per tier (A/B/C): 10 pairs where both models pass
  - Priority 1: Two-Step (linecov2) vs One-Step (linecov) of the SAME model
    (directly tests whether the planning step helps)
  - Priority 2: Two-Step vs Two-Step cross-model, or One-Step vs One-Step cross-model
  - 3 sentinel items (A/B swapped duplicates of 3 selected pairs)

Output:
  C:\\Repos\\code-evaluation-survey\\second_exp_human_eval.csv

Run from repo root:
    python step4_evaluation/build_second_exp_humaneval_csv.py
"""
import json
import random
import re
import os
from pathlib import Path
from itertools import combinations
from collections import defaultdict

import pandas as pd

REPO         = Path(r"c:\Repos\slm_test_generation")
PRED_BASE    = REPO / "downloaded_predictions/second_experiment/run_1"
EVAL_BASE    = REPO / "evaluation_results/second_experiment/run_1"
SURVEY_CSV   = Path(r"C:\Repos\code-evaluation-survey\second_exp_human_eval.csv")

TIERS        = ["tier_A", "tier_B", "tier_C"]
PAIRS_PER_TIER = 10
RANDOM_SEED  = 42

# Judge stratification thresholds (must match llm_as_judge.py)
TIE_THRESHOLD   = 2.0
CLEAR_THRESHOLD = 6.0
# Per-tier stratum targets: 3 Tie / 3 Marginal / 4 Clear
STRATUM_TARGETS = {"Tie": 3, "Marginal": 3, "Clear": 4}

JUDGE_DIR = REPO / "TestEval/predictions_judgellm"

# Models present in each tier (without temp suffix)
MODEL_STEMS = [
    "linecov2_Ministral-3-3B-Reasoning-2512",
    "linecov2_Qwen3-4B-Thinking-2507",
    "linecov2_Qwen3.5-4B",
    "linecov2_gemma-4-E4B-it",
    "linecov2_granite-4.0-micro",
    "linecov_Ministral-3-3B-Reasoning-2512",
    "linecov_Qwen3-4B-Thinking-2507",
    "linecov_Qwen3.5-4B",
    "linecov_gemma-4-E4B-it",
    "linecov_granite-4.0-micro",
]


def _strip_thinking(raw: str) -> str:
    """Remove <think>…</think> blocks that thinking models emit before the answer."""
    # Remove complete think blocks
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Remove an unclosed think block that ran to end of string
    cleaned = re.sub(r"<think>.*\Z", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def extract_test_code(raw: str) -> str:
    """
    Extract the last Python code block that looks like a pytest test.

    Thinking models wrap reasoning in <think>…</think>; strip that first.
    Some models also mention 'def test_' inside prose — Priority 4 handles
    that by finding only structurally-valid function definitions (proper
    indented body with assert) and preferring the last one.

    Strategy (in priority order):
      1. Fenced blocks (``` ```python) that contain 'def test_'
      2. Fenced blocks with a conventional starter
      3. Unclosed fenced block (truncated output)
      4. Last well-formed 'def test_' block in plain text
      5. Last fenced block, or cleaned text as final fallback
    """
    cleaned = _strip_thinking(raw)

    # Fenced blocks — lenient: allow spaces/optional language tag
    closed = re.findall(r"```[ \t]*(?:python)?[ \t]*\n(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)

    # Priority 1: fenced blocks with a def test_
    test_blocks = [b.strip() for b in closed if "def test_" in b]
    if test_blocks:
        return test_blocks[-1]

    # Priority 2: conventional starter
    starter_blocks = [
        b.strip()
        for b in closed
        if b.strip().startswith(("import ", "from ", "def test", "class Test"))
    ]
    if starter_blocks:
        return starter_blocks[-1]

    # Priority 3: unclosed fenced block (truncated output)
    unclosed = re.search(r"```[ \t]*(?:python)?[ \t]*\n(.*)\Z", cleaned, re.DOTALL | re.IGNORECASE)
    if unclosed:
        body = unclosed.group(1).strip()
        if "def test_" in body or body.startswith(("import ", "from ")):
            return body

    # Priority 4: last structurally-valid 'def test_' block in plain text.
    # Require: function def line ends with ":\n", body is indented, has assert.
    # Use finditer and take the LAST match so we skip prose-embedded fragments.
    best = None
    for m in re.finditer(
        r"^(def test_\w+\([^)]*\)\s*:\n(?:[ \t]+[^\n]+\n?)+)",
        cleaned,
        re.MULTILINE,
    ):
        candidate = m.group(1).strip()
        if "assert" in candidate or "assertEqual" in candidate:
            best = candidate
    if best:
        return best

    # Priority 5: last closed block, or cleaned text
    if closed:
        return closed[-1].strip()
    return cleaned if cleaned else raw.strip()


def _extract_conditions_text(conditions: dict) -> str:
    """
    Pull the human-readable condition statements from a conditions dict.

    For thinking models the condition_text is a long chain-of-thought.  We
    extract only the final concluded conditions by looking for structured
    sentences after key phrases, or fall back to a short excerpt.
    """
    if not conditions:
        return ""

    parts = []
    for line_num, info in sorted(conditions.items(), key=lambda x: int(x[0])):
        raw_text = info.get("condition_text", "").strip()
        raw_text = re.sub(r"</?cond>", "", raw_text).strip()
        # Strip thinking wrapper — use post-think text if available
        raw_text = _strip_thinking(raw_text) or raw_text

        # Try to extract the concluded condition from thinking-model output.
        # Thinking models often end with a short summary sentence after all
        # the deliberation.  Heuristics (in order):
        #   a) Last non-empty line that starts with a capital letter
        #   b) Last sentence after "So," / "Therefore," / "In summary,"
        #   c) Truncated excerpt

        # (a) find a clean conclusion line
        conclusion = ""
        for keyword in ("In summary,", "Therefore,", "So,", "In conclusion,",
                        "The condition is", "The condition for", "To summarize,"):
            idx = raw_text.rfind(keyword)
            if idx != -1:
                tail = raw_text[idx:].split("\n")[0].strip()
                if len(tail) > 20:
                    conclusion = tail
                    break

        if not conclusion:
            # Last non-empty, non-trivial line
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            for line in reversed(lines):
                if len(line) > 30 and not line.startswith(("Wait", "Hmm", "Actually",
                                                            "Let me", "I think", "OK,", "Okay,")):
                    conclusion = line
                    break

        if conclusion and len(conclusion) < 300:
            parts.append(f"**Line {line_num}:** {conclusion}")
        else:
            # Fall back to a short excerpt (first 300 chars of raw text)
            excerpt = raw_text[:297] + "…" if len(raw_text) > 300 else raw_text
            parts.append(f"**Line {line_num}:** {excerpt}")

    return "\n\n".join(parts)


def format_conditions(conditions: dict) -> str:
    """Format conditions dict into readable markdown for the survey."""
    return _extract_conditions_text(conditions)


def load_tier(tier: str):
    """
    Load predictions and evaluation results for a tier.

    Returns:
        preds: dict {(stem, task_num): record}  — prediction records with extracted test_code
        passing: dict {stem: set of task_nums that passed}
    """
    pred_dir = PRED_BASE / tier
    eval_dir = EVAL_BASE / tier

    preds = {}
    passing = defaultdict(set)

    for stem in MODEL_STEMS:
        pred_file = pred_dir / f"{stem}_temp_0.0.jsonl"
        eval_file = eval_dir / f"{stem}_temp_0.0_evaluated.jsonl"

        if not pred_file.exists():
            print(f"  [warn] missing pred: {pred_file.name}")
            continue
        if not eval_file.exists():
            print(f"  [warn] missing eval: {eval_file.name}")
            continue

        # Load predictions
        with open(pred_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                task_num = int(rec["task_num"])
                # Extract the test code from the last passing target line
                tests = rec.get("tests", {})
                if not tests:
                    continue
                # Use the last line key's test_code
                last_line = max(tests.keys(), key=lambda k: int(k))
                raw_code = tests[last_line].get("test_code", "")
                extracted = extract_test_code(raw_code)
                # Only accept records where the extracted code is a real test
                if "def test_" not in extracted or (
                    "assert" not in extracted and "assertEqual" not in extracted
                ):
                    continue
                rec["_extracted_code"] = extracted
                rec["_conditions_md"] = format_conditions(rec.get("conditions", {}))
                preds[(stem, task_num)] = rec

        # Load evaluation status
        with open(eval_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("status") == "Pass":
                    passing[stem].add(int(rec["task_num"]))

    return preds, passing


def base_model(stem: str) -> str:
    """Return the model name without linecov/linecov2 prefix."""
    return stem.replace("linecov2_", "").replace("linecov_", "")


def _stem_to_friendly(stem: str, tier: str) -> str:
    """Convert a model stem to the friendly name used in judge output.

    e.g. "linecov2_Qwen3.5-4B" + "tier_B" -> "Qwen3.5-4B Two-Step Tier-B"
    """
    step = "Two-Step" if stem.startswith("linecov2_") else "One-Step"
    model = base_model(stem)
    tier_label = tier.replace("tier_", "Tier-")   # "tier_B" -> "Tier-B"
    return f"{model} {step} {tier_label}"


def load_judge_scores(tier: str) -> dict:
    """Load judge results for a tier.

    Returns dict keyed by frozenset({friendly_a, friendly_b, task_id}) ->
        {"score_diff": float, "bias_status": str, "final_winner": str}
    Uses frozenset so lookup is order-independent.
    """
    judge_file = JUDGE_DIR / f"pairwise_judgements_second_experiment_{tier}.jsonl"
    scores = {}
    if not judge_file.exists():
        print(f"  [warn] judge file missing: {judge_file.name}")
        return scores

    with open(judge_file, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            key = (frozenset([r["model_a"], r["model_b"]]), int(r["task_id"]))
            scores[key] = {
                "score_diff":    float(r.get("score_diff", 0.0)),
                "bias_status":   r.get("bias_status", "None"),
                "final_winner":  r.get("final_winner_model", ""),
                "model_a":       r["model_a"],
            }
    print(f"  Loaded {len(scores)} judge results for {tier}")
    return scores


def _score_stratum(score_diff: float) -> str:
    if score_diff <= TIE_THRESHOLD:
        return "Tie"
    if score_diff < CLEAR_THRESHOLD:
        return "Marginal"
    return "Clear"


def build_pairs(preds, passing, tier: str, rng: random.Random,
                judge_scores: dict) -> list:
    """
    Build candidate pairs for a tier using judge-score-stratified sampling.

    Stratification: 3 Tie / 3 Marginal / 4 Clear (STRATUM_TARGETS).
    Pairs without a judge score (judge didn't evaluate them) are placed in
    a fallback pool and only used when a stratum is short.
    """
    # Collect all valid pairs with their judge scores
    strata: dict[str, list] = {"Tie": [], "Marginal": [], "Clear": [], "Unknown": []}

    for stem_a, stem_b in combinations(MODEL_STEMS, 2):
        common_tasks = passing[stem_a] & passing[stem_b]
        for task_num in common_tasks:
            if (stem_a, task_num) not in preds or (stem_b, task_num) not in preds:
                continue
            fa = _stem_to_friendly(stem_a, tier)
            fb = _stem_to_friendly(stem_b, tier)
            key = (frozenset([fa, fb]), task_num)
            info = judge_scores.get(key)

            if info is None or info["bias_status"] != "None":
                strata["Unknown"].append((stem_a, stem_b, task_num, 0.0, "Unknown"))
            else:
                sd = info["score_diff"]
                s  = _score_stratum(sd)
                strata[s].append((stem_a, stem_b, task_num, sd, s))

    # Shuffle each stratum
    for s in strata:
        rng.shuffle(strata[s])

    # Sample according to targets; fill shortfalls from Unknown pool
    selected = []
    for s, target in STRATUM_TARGETS.items():
        pool = strata[s]
        take = min(target, len(pool))
        selected.extend(pool[:take])
        shortfall = target - take
        if shortfall > 0:
            fill = strata["Unknown"][:shortfall]
            selected.extend(fill)
            strata["Unknown"] = strata["Unknown"][shortfall:]
            print(f"  [warn] {tier} {s}: only {take}/{target}, filled {shortfall} from Unknown")

    rng.shuffle(selected)

    counts = {s: sum(1 for _, _, _, _, st in selected if st == s) for s in STRATUM_TARGETS}
    print(f"  {tier}: selected {len(selected)} pairs — " +
          " / ".join(f"{s}={n}" for s, n in counts.items()))

    # Convert to rows
    rows = []
    for stem_a, stem_b, task_num, score_diff, stratum in selected:
        rec_a = preds[(stem_a, task_num)]
        rec_b = preds[(stem_b, task_num)]
        rows.append({
            "task_id":             task_num,
            "tier":                tier,
            "stratum":             stratum,
            "score_diff":          score_diff,
            "model_a":             stem_a,
            "model_b":             stem_b,
            "focal_code":          rec_a.get("python_solution", ""),
            "docstring":           rec_a.get("docstring", "No docstring."),
            "code_a":              rec_a["_extracted_code"],
            "code_b":              rec_b["_extracted_code"],
            "conditions_a":        rec_a["_conditions_md"],
            "conditions_b":        rec_b["_conditions_md"],
            "is_sentinel":         False,
            "sentinel_of_task_id": None,
        })

    return rows


def build_sentinels(rows: list, rng: random.Random, n: int = 3) -> list:
    """
    Pick n pairs at random and create A/B-swapped duplicates as sentinels.
    Sentinels use task_id + 100_000 to avoid collision.
    """
    real_rows = [r for r in rows if not r["is_sentinel"]]
    # Prefer P1 (Two-Step vs One-Step) rows for sentinels — identifiable by approach prefix mix
    p1 = [r for r in real_rows
          if r["model_a"].startswith("linecov2_") and r["model_b"].startswith("linecov_")]
    pool = p1 if len(p1) >= n else real_rows
    rng.shuffle(pool)
    sources = pool[:n]

    sentinels = []
    for src in sources:
        sentinels.append({
            "task_id":             src["task_id"] + 100_000,
            "tier":                src["tier"],
            "stratum":             src["stratum"],
            "score_diff":          -src["score_diff"],
            "model_a":             src["model_b"],   # swapped
            "model_b":             src["model_a"],   # swapped
            "focal_code":          src["focal_code"],
            "docstring":           src["docstring"],
            "code_a":              src["code_b"],    # swapped
            "code_b":              src["code_a"],    # swapped
            "conditions_a":        src["conditions_b"],  # swapped
            "conditions_b":        src["conditions_a"],  # swapped
            "is_sentinel":         True,
            "sentinel_of_task_id": src["task_id"],
        })
        print(f"  sentinel: task {src['task_id']} -> {src['task_id'] + 100_000}  "
              f"({src['tier']}, {base_model(src['model_a'])} vs {base_model(src['model_b'])})")

    return sentinels


def main():
    rng = random.Random(RANDOM_SEED)
    all_rows = []

    for tier in TIERS:
        print(f"\nLoading {tier}...")
        preds, passing = load_tier(tier)
        judge_scores = load_judge_scores(tier)
        rows = build_pairs(preds, passing, tier, rng, judge_scores)
        all_rows.extend(rows)

    print(f"\nTotal real rows: {len(all_rows)}")

    print("\nBuilding sentinels...")
    sentinels = build_sentinels(all_rows, rng, n=3)
    all_rows.extend(sentinels)

    COLS = [
        "task_id", "tier", "stratum", "score_diff",
        "model_a", "model_b",
        "focal_code", "docstring",
        "code_a", "code_b",
        "conditions_a", "conditions_b",
        "is_sentinel", "sentinel_of_task_id",
    ]
    df = pd.DataFrame(all_rows, columns=COLS)

    os.makedirs(SURVEY_CSV.parent, exist_ok=True)
    df.to_csv(SURVEY_CSV, index=False)
    print(f"\nSaved: {SURVEY_CSV}")

    # Summary
    real = df[~df["is_sentinel"]]
    ts_vs_os = real[real["model_a"].str.startswith("linecov2_") != real["model_b"].str.startswith("linecov2_")]
    ts_vs_ts = real[real["model_a"].str.startswith("linecov2_") & real["model_b"].str.startswith("linecov2_")]
    os_vs_os = real[~real["model_a"].str.startswith("linecov2_") & ~real["model_b"].str.startswith("linecov2_")]
    has_both_conds = real[(real["conditions_a"].str.len() > 0) & (real["conditions_b"].str.len() > 0)]
    print("\n--- Summary ---")
    print(f"Real items: {len(real)}  ({PAIRS_PER_TIER} per tier x {len(TIERS)} tiers)")
    print(f"  Stratum breakdown: " + " / ".join(
        f"{s}={len(real[real['stratum']==s])}" for s in ["Tie","Marginal","Clear","Unknown"]))
    print(f"  Two-Step vs One-Step: {len(ts_vs_os)}")
    print(f"  Two-Step vs Two-Step: {len(ts_vs_ts)}  (plan comparison shown in survey)")
    print(f"  One-Step vs One-Step: {len(os_vs_os)}")
    print(f"  Items where plan comparison will appear: {len(has_both_conds)}")
    print(f"  Avg score_diff: {real['score_diff'].mean():.1f}")
    print(f"Sentinels: {len(df) - len(real)}")


if __name__ == "__main__":
    main()
