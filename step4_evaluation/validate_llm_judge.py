"""
validate_llm_judge.py
=====================
One-shot validation of the LLM-as-Judge against human expert evaluations.

Reads:
  C:\\Repos\\code-evaluation-survey\\human_evaluations_export.json   (Firestore download)
  C:\\Repos\\code-evaluation-survey\\second_exp_human_eval.csv       (evaluation sample)
  TestEval/predictions_judgellm/pairwise_judgements_second_experiment_tier_{A,B,C}.jsonl

Outputs (all in step4_evaluation/human_validation/):
  unified_human_eval.csv    -- merged 30-row dataset
  kappa_results.json        -- all statistics (machine-readable)
  figures/
    fig1_kappa_summary.png
    fig2_criterion_correlation.png
    fig3_confusion_matrices.png
    fig4_stratum_breakdown.png
    fig5_score_scatter.png

Usage (from repo root):
    python step4_evaluation/validate_llm_judge.py
"""

import hashlib
import json
import math
import random
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import cohen_kappa_score, confusion_matrix

# Paths
SURVEY_REPO  = Path(r"C:\Repos\code-evaluation-survey")
JSON_EXPORT  = SURVEY_REPO / "human_evaluations_export.json"
SAMPLE_CSV   = SURVEY_REPO / "second_exp_human_eval.csv"

JUDGE_DIR    = Path("TestEval/predictions_judgellm")
JUDGE_TIERS  = ["tier_A", "tier_B", "tier_C"]

OUT_DIR      = Path("step4_evaluation/human_validation")
FIGURES_DIR  = OUT_DIR / "figures"

CRITERIA = ["robustness", "assertions", "readability", "conciseness"]
CRITERIA_LABELS = {
    "robustness": "Robustness",
    "assertions": "Assertion Strength",
    "readability": "Readability",
    "conciseness": "Conciseness",
}

# Plot style (matches rest of project)
sns.set_style("whitegrid")
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "figure.dpi": 150,
})
PALETTE = {
    "pass":    "#2ca02c",   # green
    "warn":    "#ff7f0e",   # orange
    "fail":    "#d62728",   # red
    "neutral": "#1f77b4",   # blue
    "light":   "#aec7e8",
}
STRATUM_COLORS = {"Clear": "#2ca02c", "Marginal": "#ff7f0e", "Tie": "#9467bd"}



# SECTION 1 — Data loading

# Strips date-version suffixes that the judge strips from model display names.
# e.g. "Qwen3-4B-Thinking-2507" → "Qwen3-4B-Thinking"
_DATE_SUFFIX = re.compile(r"-\d{4}$")


def _stem_to_friendly(stem: str, tier: str) -> str:
    """Convert a CSV model stem to the friendly name stored in judge JSONL files.

    CSV stem: "linecov2_Qwen3-4B-Thinking-2507"
    JSONL name: "Qwen3-4B-Thinking Two-Step Tier-B"
    """
    step = "Two-Step" if stem.startswith("linecov2_") else "One-Step"
    base = stem.replace("linecov2_", "").replace("linecov_", "")
    base = _DATE_SUFFIX.sub("", base)
    tier_label = tier.replace("tier_", "Tier-")
    return f"{base} {step} {tier_label}"


def _stable_hash(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def get_case_order(annotator_id: str, n: int) -> list:
    """Deterministic shuffle — identical to the Streamlit app."""
    seed = _stable_hash(f"case_order_{annotator_id}") % (2 ** 31)
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    return order


def load_inputs():
    for p in (JSON_EXPORT, SAMPLE_CSV):
        if not p.exists():
            sys.exit(f"ERROR: required file not found: {p}")

    with open(JSON_EXPORT, encoding="utf-8") as f:
        ann_data = json.load(f)

    csv_df = pd.read_csv(SAMPLE_CSV)
    csv_df["task_id"] = csv_df["task_id"].astype(int)

    # Merge all tier JSONL files. Key by (task_id, frozenset({model_a, model_b}))
    # so the lookup is order-independent regardless of which model was "A" in the judge.
    jlookup: dict = {}
    for tier in JUDGE_TIERS:
        jpath = JUDGE_DIR / f"pairwise_judgements_second_experiment_{tier}.jsonl"
        if not jpath.exists():
            print(f"  [warn] judge file not found: {jpath}")
            continue
        with open(jpath, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                key = (int(rec["task_id"]), frozenset([rec["model_a"], rec["model_b"]]))
                jlookup[key] = rec

    print(f"  Loaded {len(jlookup)} judge records from {len(JUDGE_TIERS)} tiers")
    return ann_data, csv_df, jlookup



# SECTION 2 — Merge / integrate
def deswap(resp: dict) -> tuple:
    """Return (model_a_scores, model_b_scores) in canonical order.

    Prefers scores_actual_a/b (stored de-swapped by new app version).
    Falls back to manual de-swap of scores_display_a/b for old submissions.
    """
    if "scores_actual_a" in resp and "scores_actual_b" in resp:
        return resp["scores_actual_a"], resp["scores_actual_b"]
    sa, sb = resp["scores_display_a"], resp["scores_display_b"]
    return (sb, sa) if resp["ab_swapped"] else (sa, sb)


def llm_criterion_avgs(jrec: dict) -> tuple:
    """Average pass-1 and pass-2 per-criterion scores for model_a and model_b."""
    def avg(p1, p2):
        return [(a + b) / 2 if a is not None and b is not None else None
                for a, b in zip(p1, p2)]
    p1a = jrec.get("model_a_scores_pass1", [None] * 4)
    p2a = jrec.get("model_a_scores_pass2", [None] * 4)
    p1b = jrec.get("model_b_scores_pass1", [None] * 4)
    p2b = jrec.get("model_b_scores_pass2", [None] * 4)
    return avg(p1a, p2a), avg(p1b, p2b)


def build_unified(ann_data: list, csv_df: pd.DataFrame, jlookup: dict) -> pd.DataFrame:
    if len(ann_data) < 3:
        sys.exit("ERROR: need at least 3 annotators in the JSON export.")

    def make_map(ann):
        aid = ann["annotator_id"]
        # Use n_cases stored at session-start (present for annotators after the fix).
        # Fall back to len(responses) which equals the CSV size for fully completed sessions.
        n = int(ann.get("n_cases", len(ann["responses"])))
        order = get_case_order(aid, n)
        display_to_csv = {(i + 1): order[i] for i in range(n)}
        mapping = {}
        for resp in ann["responses"]:
            dp = resp["display_order"]
            if dp not in display_to_csv:
                continue  # response from a session with a different CSV size — skip
            csv_idx = display_to_csv[dp]
            actual_tid = int(csv_df.iloc[csv_idx]["task_id"])
            if actual_tid != resp["task_id"]:
                sys.exit(
                    f"case_order mismatch for annotator {aid} "
                    f"display_order={dp}: expected {actual_tid}, got {resp['task_id']}"
                )
            mapping[csv_idx] = resp
        return mapping

    maps = [make_map(ann) for ann in ann_data]

    rows = []
    for csv_idx, csv_row in csv_df.iterrows():
        task_id  = int(csv_row["task_id"])
        model_a  = csv_row["model_a"]
        model_b  = csv_row["model_b"]
        stratum  = csv_row["stratum"]

        tier      = str(csv_row.get("tier", ""))
        fa        = _stem_to_friendly(model_a, tier)
        fb        = _stem_to_friendly(model_b, tier)
        jkey      = (task_id, frozenset([fa, fb]))
        jrec      = jlookup.get(jkey, {})

        # Detect if the JSONL stored the pair with A/B swapped relative to the CSV.
        # If so, flip winner labels and swap per-model scores so they match CSV's A/B.
        j_flipped = bool(jrec) and jrec.get("model_a", "") == fb

        def _flip(w):
            return {"A": "B", "B": "A"}.get(w, w) if j_flipped else w

        llm_winner   = _flip(jrec.get("final_winner_model"))
        bias_status  = jrec.get("bias_status", "")
        pass1_winner = _flip(jrec.get("pass1_winner", ""))
        _sa = "model_b_total_score" if j_flipped else "model_a_total_score"
        _sb = "model_a_total_score" if j_flipped else "model_b_total_score"
        llm_score_a = float(jrec.get(_sa) or csv_row.get("model_a_total_score") or 0)
        llm_score_b = float(jrec.get(_sb) or csv_row.get("model_b_total_score") or 0)
        crit_a, crit_b = llm_criterion_avgs(jrec)
        if j_flipped:
            crit_a, crit_b = crit_b, crit_a
        _ca = "code_b" if j_flipped else "code_a"
        _cb = "code_a" if j_flipped else "code_b"
        code_a = str(jrec.get(_ca, csv_row.get("code_a", "")))
        code_b = str(jrec.get(_cb, csv_row.get("code_b", "")))

        is_sentinel = bool(csv_row.get("is_sentinel", False))
        row = {
            "csv_row_idx":  csv_idx,
            "task_id":      task_id,
            "model_a":      model_a,
            "model_b":      model_b,
            "stratum":      stratum,
            "is_sentinel":  is_sentinel,
            "llm_winner":   llm_winner,
            "bias_status":  bias_status,
            "pass1_winner": pass1_winner,
            "llm_score_a":  llm_score_a,
            "llm_score_b":  llm_score_b,
            "code_a_len":   len(code_a.split()),
            "code_b_len":   len(code_b.split()),
        }
        for i, c in enumerate(CRITERIA):
            row[f"llm_{c}_a"] = crit_a[i]
            row[f"llm_{c}_b"] = crit_b[i]

        votes = []
        for ann_idx, (ann, m) in enumerate(zip(ann_data, maps), start=1):
            r = m.get(csv_idx)
            if r is None:
                # This annotator did not see this item (e.g. old 30-item session)
                row[f"ann{ann_idx}_id"]     = ann["annotator_id"]
                row[f"ann{ann_idx}_winner"] = None
                row[f"ann{ann_idx}_notes_comparison"] = ""
                row[f"ann{ann_idx}_notes_plan"]       = ""
                for c in CRITERIA:
                    row[f"ann{ann_idx}_{c}_a"] = None
                    row[f"ann{ann_idx}_{c}_b"] = None
                continue
            sa, sb = deswap(r)
            row[f"ann{ann_idx}_id"]     = ann["annotator_id"]
            row[f"ann{ann_idx}_winner"] = r["winner_actual"]
            row[f"ann{ann_idx}_notes_comparison"] = r.get("notes_comparison", r.get("notes", ""))
            row[f"ann{ann_idx}_notes_plan"]       = r.get("notes_plan", "")
            for c in CRITERIA:
                row[f"ann{ann_idx}_{c}_a"] = sa.get(c)
                row[f"ann{ann_idx}_{c}_b"] = sb.get(c)
            votes.append(r["winner_actual"])

        threshold = math.ceil(len(ann_data) / 2)
        top = Counter(votes).most_common(1)[0]
        row["human_consensus"] = top[0] if top[1] >= threshold else "Disagreement"
        rows.append(row)

    return pd.DataFrame(rows)


# SECTION 3 — Statistics
def safe_kappa(y1, y2):
    try:
        return float(cohen_kappa_score(y1, y2, labels=["A", "B", "Tie"]))
    except ValueError:
        return float("nan")


def bootstrap_kappa_ci(y1, y2, n_resamples=2000, confidence_level=0.95, seed=42):
    """Bootstrap percentile 95% CI for Cohen's kappa."""
    y1, y2 = list(y1), list(y2)
    rng = random.Random(seed)
    n = len(y1)
    kappas = []
    for _ in range(n_resamples):
        idx = [rng.randint(0, n - 1) for _ in range(n)]
        k = safe_kappa([y1[i] for i in idx], [y2[i] for i in idx])
        if not math.isnan(k):
            kappas.append(k)
    if not kappas:
        return float("nan"), float("nan")
    lo = float(np.percentile(kappas, (1 - confidence_level) / 2 * 100))
    hi = float(np.percentile(kappas, (1 + confidence_level) / 2 * 100))
    return lo, hi


def interpret_kappa(k: float) -> str:
    if np.isnan(k) or k < 0:   return "Poor"
    if k < 0.20:                return "Slight"
    if k < 0.40:                return "Fair"
    if k < 0.60:                return "Moderate"
    if k < 0.80:                return "Substantial"
    return "Almost Perfect"


def interpret_r(r: float) -> str:
    a = abs(r)
    if a < 0.20: return "Negligible"
    if a < 0.40: return "Weak"
    if a < 0.60: return "Moderate"
    if a < 0.80: return "Strong"
    return "Very Strong"


def compute_statistics(df: pd.DataFrame, ann_data: list) -> dict:
    n_ann = len(ann_data)

    def expertise_label(ann):
        return ann.get("demographics", {}).get("testing_expertise", "?")

    lbl_map = {f"ann{i+1}": f"Ann{i+1} ({expertise_label(ann_data[i])})"
               for i in range(n_ann)}

    # --- Inter-Annotator Agreement ---
    # Exclude sentinel rows: they present the same focal code twice (A/B swapped),
    # so including them would double-count observations and inflate IAA.
    df_iaa = df[~df["is_sentinel"].fillna(False).astype(bool)].copy()

    # Only keep rows where every annotator has a response (handles cross-CSV-version annotators)
    ann_winner_cols = [f"ann{i}_winner" for i in range(1, n_ann + 1)]
    df_iaa = df_iaa.dropna(subset=ann_winner_cols)

    def _fleiss_kappa(cols, categories=("A", "B", "Tie")):
        n = len(cols[0])
        r = len(cols)
        cat_idx = {c: i for i, c in enumerate(categories)}
        mat = np.zeros((n, len(categories)), dtype=float)
        for col in cols:
            for i, val in enumerate(col):
                if val in cat_idx:
                    mat[i, cat_idx[val]] += 1
        P_i = (np.sum(mat ** 2, axis=1) - r) / (r * (r - 1))
        P_bar = P_i.mean()
        p_j = mat.sum(axis=0) / (n * r)
        P_e = float(np.sum(p_j ** 2))
        if P_e >= 1.0:
            return float("nan")
        return float((P_bar - P_e) / (1 - P_e))

    pairwise_kappas = {}
    pairwise_agree  = {}
    for i, j in combinations(range(1, n_ann + 1), 2):
        k = safe_kappa(df_iaa[f"ann{i}_winner"], df_iaa[f"ann{j}_winner"])
        pairwise_kappas[f"kappa_ann{i}_ann{j}"] = k
        pairwise_agree[f"agree_ann{i}_ann{j}"] = int(
            (df_iaa[f"ann{i}_winner"] == df_iaa[f"ann{j}_winner"]).sum()
        )

    fleiss_k = _fleiss_kappa([list(df_iaa[f"ann{i}_winner"]) for i in range(1, n_ann + 1)])

    # Average pairwise observed agreement
    if pairwise_agree:
        avg_agree_n = sum(pairwise_agree.values()) / len(pairwise_agree)
    else:
        avg_agree_n = 0.0

    # --- LLM vs Human ---
    # Exclude sentinels AND Invalid_Bias items — the latter should not be silently treated
    # as Ties, as that would artificially inflate κ on Tie cases.
    df_v = df[
        ~df["is_sentinel"].fillna(False).astype(bool) &
        df["llm_winner"].notna() &
        (df["llm_winner"] != "Invalid_Bias")
    ].copy()
    df_v = df_v.dropna(subset=ann_winner_cols)

    n_invalid_bias = int(
        df[~df["is_sentinel"].fillna(False).astype(bool) &
           (df["llm_winner"] == "Invalid_Bias")].shape[0]
    )

    llm_kappas = {}
    llm_agrees = {}
    for i in range(1, n_ann + 1):
        llm_kappas[f"kappa_ann{i}"] = safe_kappa(df_v["llm_winner"], df_v[f"ann{i}_winner"])
        lo, hi = bootstrap_kappa_ci(df_v["llm_winner"], df_v[f"ann{i}_winner"])
        llm_kappas[f"kappa_ann{i}_ci"] = [lo, hi]
        llm_agrees[f"pct_agree_ann{i}"] = float(
            (df_v["llm_winner"] == df_v[f"ann{i}_winner"]).sum() / len(df_v)) if len(df_v) else 0.0

    cons_df = df_v[df_v["human_consensus"] != "Disagreement"]
    k_cons = safe_kappa(cons_df["llm_winner"], cons_df["human_consensus"])
    k_cons_lo, k_cons_hi = bootstrap_kappa_ci(cons_df["llm_winner"], cons_df["human_consensus"])
    agree_c = (cons_df["llm_winner"] == cons_df["human_consensus"]).sum()

    # --- Per-criterion correlation (Spearman — ordinal 1-5 scale) ---
    crit_stats = {}
    for crit in CRITERIA:
        hv, lv = [], []
        for _, row in df_v.iterrows():
            for side in ("a", "b"):
                h_vals = [row.get(f"ann{i}_{crit}_{side}") for i in range(1, n_ann + 1)]
                h_vals = [h for h in h_vals if h is not None]
                ll = row.get(f"llm_{crit}_{side}")
                if ll is not None and h_vals:
                    hv.append(sum(h_vals) / len(h_vals))
                    lv.append(ll)
        rho, p = spearmanr(hv, lv)
        crit_stats[crit] = {"rho": float(rho), "p": float(p), "n": len(hv)}

    # Total score correlation (Spearman)
    ht, lt = [], []
    for _, row in df_v.iterrows():
        for side in ("a", "b"):
            h_totals = [sum(row.get(f"ann{i}_{c}_{side}") or 0 for c in CRITERIA)
                        for i in range(1, n_ann + 1)]
            ht.append(sum(h_totals) / len(h_totals))
            lt.append(sum(row.get(f"llm_{c}_{side}") or 0 for c in CRITERIA))
    rho_tot, p_tot = spearmanr(ht, lt)

    # --- Stratum breakdown (non-sentinel, non-invalid-bias) ---
    stratum_stats = {}
    for st in ["Clear", "Marginal", "Tie"]:
        sub = df_v[df_v["stratum"] == st]
        n_s = len(sub)
        if n_s == 0:
            continue
        entry = {"n": n_s}
        for i in range(1, n_ann + 1):
            entry[f"llm_ann{i}"] = int((sub["llm_winner"] == sub[f"ann{i}_winner"]).sum())
        # Average pairwise human agreement per stratum
        pair_agree_counts = []
        for i, j in combinations(range(1, n_ann + 1), 2):
            pair_agree_counts.append(int((sub[f"ann{i}_winner"] == sub[f"ann{j}_winner"]).sum()))
        entry["avg_human_agree"] = round(sum(pair_agree_counts) / len(pair_agree_counts), 1) if pair_agree_counts else 0
        stratum_stats[st] = entry

    # --- Verbosity bias check ---
    # If LLM scores correlate strongly with test code word-count, verbosity bias is present.
    # Using df_v (non-sentinel, non-invalid-bias items with LLM scores).
    vb_rho, vb_p = float("nan"), float("nan")
    if "code_a_len" in df_v.columns and len(df_v) >= 5:
        lengths, scores = [], []
        for _, row in df_v.iterrows():
            lengths.extend([row["code_a_len"], row["code_b_len"]])
            scores.extend([row["llm_score_a"], row["llm_score_b"]])
        if len(lengths) >= 5:
            vb_rho, vb_p = spearmanr(lengths, scores)
            vb_rho, vb_p = float(vb_rho), float(vb_p)

    # --- Position bias direction check ---
    # Across all clean (bias_status=None) judgments, what fraction did A (position 1) win
    # in pass 1? If meaningfully different from 0.5, residual positional preference exists.
    pb_stats = {"n": 0, "pass1_A_wins": 0, "pass1_B_wins": 0,
                "pass1_Tie": 0, "pass1_A_fraction": float("nan")}
    clean_items = df_v[df_v["bias_status"] == "None"]
    if len(clean_items) > 0:
        p1w = clean_items["pass1_winner"]
        pb_stats["n"]             = len(clean_items)
        pb_stats["pass1_A_wins"]  = int((p1w == "A").sum())
        pb_stats["pass1_B_wins"]  = int((p1w == "B").sum())
        pb_stats["pass1_Tie"]     = int((p1w == "Tie").sum())
        decisive = pb_stats["pass1_A_wins"] + pb_stats["pass1_B_wins"]
        if decisive > 0:
            pb_stats["pass1_A_fraction"] = round(
                pb_stats["pass1_A_wins"] / decisive, 3
            )

    return {
        "labels":  lbl_map,
        "n_ann":   n_ann,
        "n_total": len(df),
        "n_real":  len(df_iaa),
        "n_invalid_bias": n_invalid_bias,
        "verbosity_bias": {
            "spearman_rho_length_vs_score": vb_rho,
            "p": vb_p,
            "flag": abs(vb_rho) > 0.5 if not math.isnan(vb_rho) else False,
        },
        "position_bias_direction": pb_stats,
        "iaa": {
            **pairwise_kappas,
            **pairwise_agree,
            "fleiss_kappa":      fleiss_k,
            "n_way":             n_ann,
            "interpretation":    interpret_kappa(fleiss_k),
            "avg_agree_n":       avg_agree_n,
            "pct_avg_agree":     avg_agree_n / len(df_iaa) if len(df_iaa) else 0.0,
        },
        "llm_vs_human": {
            "n": len(df_v),
            "n_excluded_invalid_bias": n_invalid_bias,
            **llm_kappas,
            **llm_agrees,
            "kappa_consensus":    k_cons,
            "kappa_consensus_ci": [k_cons_lo, k_cons_hi],
            "n_consensus":        len(cons_df),
            "pct_agree_cons":     float(agree_c / len(cons_df)) if len(cons_df) else None,
        },
        "criterion_correlation": crit_stats,
        "total_score_correlation": {
            "rho": float(rho_tot), "p": float(p_tot), "n": len(ht),
            "human_scores": ht, "llm_scores": lt,
        },
        "stratum_breakdown": stratum_stats,
    }


# SECTION 4 — Console report
def _sig(p):
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "ns"


def print_report(df: pd.DataFrame, stats: dict):
    n_ann = stats["n_ann"]
    iaa   = stats["iaa"]
    llm   = stats["llm_vs_human"]
    tsc   = stats["total_score_correlation"]

    sep = "=" * 72

    # Build dynamic stratum summary
    strata_summary = "  ".join(
        f"{st}:{stats['stratum_breakdown'].get(st, {}).get('n', 0)}"
        for st in ["Clear", "Marginal", "Tie"]
    )

    print(sep)
    print("LLM-AS-JUDGE HUMAN VALIDATION REPORT")
    print(sep)
    print(f"  Total rows     : {stats['n_total']}  "
          f"(real: {stats['n_real']}, sentinels excluded from IAA)")
    print(f"  LLM eval items : {llm['n']}  "
          f"({llm['n_excluded_invalid_bias']} Invalid_Bias excluded)")
    print(f"  Strata         : {strata_summary}")
    for i in range(1, n_ann + 1):
        print(f"  Annotator {i}    : {stats['labels'][f'ann{i}']}")

    print(f"\n{sep}")
    print("1. INTER-ANNOTATOR AGREEMENT  (Pairwise Cohen's Kappa + Fleiss' Kappa)")
    print(f"   (computed on {stats['n_real']} real items, sentinels excluded)")
    print(sep)
    for key, k in iaa.items():
        if key.startswith("kappa_ann"):
            parts = key.replace("kappa_", "").split("_")
            label = f"{parts[0].capitalize()} vs {parts[1].capitalize()}"
            print(f"  {label} : k = {k:.3f}  ({interpret_kappa(k)})")
    print(f"  Fleiss' k ({n_ann}-way) : {iaa['fleiss_kappa']:.3f}  ({iaa['interpretation']})")
    avg_agree = iaa["avg_agree_n"]
    pct_avg   = iaa["pct_avg_agree"]
    print(f"  Avg pairwise observed agreement : {avg_agree:.1f}/{stats['n_real']} = {pct_avg:.1%}")

    ann_hdrs = "  ".join(f"Ann{i:>1d}" for i in range(1, n_ann + 1))
    df_real = df[~df["is_sentinel"].fillna(False).astype(bool)]
    print(f"\n  {'Label':8s}  {ann_hdrs}   LLM")
    print(f"  {'-'*(10 + 7*n_ann + 6)}")
    for lbl in ["A", "B", "Tie"]:
        counts = "  ".join(
            f"{(df_real[f'ann{i}_winner'] == lbl).sum():5d}"
            for i in range(1, n_ann + 1)
        )
        ll = (df_real["llm_winner"] == lbl).sum()
        print(f"  {lbl:8s}  {counts}  {ll:5d}")

    print(f"\n{sep}")
    print("2. LLM vs HUMAN AGREEMENT  (Cohen's Kappa, Invalid_Bias excluded)")
    print(sep)
    THRESH = 0.60
    for i in range(1, n_ann + 1):
        lbl = stats["labels"][f"ann{i}"]
        k   = llm[f"kappa_ann{i}"]
        ci  = llm.get(f"kappa_ann{i}_ci", [float("nan"), float("nan")])
        pct = llm[f"pct_agree_ann{i}"]
        obs = f"{int(pct*llm['n'])}/{llm['n']} = {pct:.1%}"
        status = "[PASS]" if k >= THRESH else "[FAIL]"
        print(f"  {status}  LLM vs {lbl}")
        print(f"         k = {k:.3f}  95%CI [{ci[0]:.3f}, {ci[1]:.3f}]  ({interpret_kappa(k)})  |  {obs}")
    k_cons = llm["kappa_consensus"]
    ci_cons = llm.get("kappa_consensus_ci", [float("nan"), float("nan")])
    obs_cons = (f"{int(llm['pct_agree_cons']*llm['n_consensus'])}/{llm['n_consensus']} = "
                f"{llm['pct_agree_cons']:.1%}" if llm["pct_agree_cons"] else "n/a")
    status = "[PASS]" if k_cons >= THRESH else "[FAIL]"
    print(f"  {status}  LLM vs Consensus ({llm['n_consensus']} cases)")
    print(f"         k = {k_cons:.3f}  95%CI [{ci_cons[0]:.3f}, {ci_cons[1]:.3f}]  ({interpret_kappa(k_cons)})  |  {obs_cons}")
    print(f"\n  Threshold: k >= {THRESH}  (Siddiq et al., 2024 — Substantial)")

    print(f"\n{sep}")
    print("3. BIAS DIAGNOSTICS")
    print(sep)

    vb = stats["verbosity_bias"]
    flag = " *** VERBOSITY BIAS LIKELY ***" if vb["flag"] else ""
    vb_rho_str = f"{vb['spearman_rho_length_vs_score']:.3f}" if not math.isnan(vb["spearman_rho_length_vs_score"]) else "n/a"
    vb_p_str   = f"{vb['p']:.4f}" if not math.isnan(vb["p"]) else "n/a"
    print(f"  Verbosity bias (word-count vs LLM score Spearman rho) : {vb_rho_str}  (p={vb_p_str}){flag}")
    print(f"  Threshold: |rho| > 0.50 → flag. Scores should be driven by quality, not length.")

    pb = stats["position_bias_direction"]
    if pb["n"] > 0:
        frac = pb["pass1_A_fraction"]
        frac_str = f"{frac:.3f}" if not math.isnan(frac) else "n/a"
        flag_pb = " *** DIRECTIONAL POSITION BIAS LIKELY ***" if not math.isnan(frac) and abs(frac - 0.5) > 0.10 else ""
        print(f"  Position bias direction ({pb['n']} clean judgments) :")
        print(f"    Pass-1 A wins: {pb['pass1_A_wins']}  B wins: {pb['pass1_B_wins']}  Tie: {pb['pass1_Tie']}")
        print(f"    A-fraction of decisive pass-1 outcomes: {frac_str}{flag_pb}")
        print(f"  Expected ~0.50 if no position preference. >0.60 or <0.40 indicates bias.")
    else:
        print("  Position bias direction: no clean judgments available.")

    print(f"\n{sep}")
    n_pairs = stats["criterion_correlation"][CRITERIA[0]]["n"]
    print(f"4. PER-CRITERION SCORE CORRELATION  (Spearman rho — ordinal 1-5 scale)")
    print(sep)
    print(f"  Human avg = mean of {n_ann} annotators   |   n = {n_pairs} score pairs per criterion")
    print(f"\n  {'Criterion':20s}  {'rho':>6s}  {'p':>7s}  {'Interp.'}")
    print(f"  {'-'*55}")
    for crit in CRITERIA:
        cs  = stats["criterion_correlation"][crit]
        sig = _sig(cs["p"])
        print(f"  {CRITERIA_LABELS[crit]:20s}  {cs['rho']:6.3f}  "
              f"{cs['p']:7.4f}{sig}  {interpret_r(cs['rho'])}")
    sig = _sig(tsc["p"])
    print(f"  {'Total score':20s}  {tsc['rho']:6.3f}  {tsc['p']:7.4f}{sig}  "
          f"{interpret_r(tsc['rho'])}")

    print(f"\n{sep}")
    print("5. STRATUM BREAKDOWN")
    print(sep)
    ann_cols = "   ".join(f"LLM=Ann{i}" for i in range(1, n_ann + 1))
    print(f"\n  {'Stratum':10s}  n   {ann_cols}  Avg Human")
    print(f"  {'-'*70}")
    for st, sv in stats["stratum_breakdown"].items():
        n = sv["n"]
        parts = "   ".join(f"{sv[f'llm_ann{i}']}/{n} ({sv[f'llm_ann{i}']/n:.0%})"
                            for i in range(1, n_ann + 1))
        ah = sv["avg_human_agree"]
        print(f"  {st:10s}  {n:2d}  {parts}  {ah:.1f}/{n} ({ah/n:.0%})")

    print(f"\n{sep}")
    print("SUMMARY")
    print(sep)
    print(f"  Fleiss' Kappa ({n_ann}-way IAA) = {iaa['fleiss_kappa']:.3f}  ({iaa['interpretation']})")
    for key, k in iaa.items():
        if key.startswith("kappa_ann"):
            parts = key.replace("kappa_", "").split("_")
            print(f"  {parts[0].capitalize()} vs {parts[1].capitalize()} k = {k:.3f}")
    for i in range(1, n_ann + 1):
        lbl = stats["labels"][f"ann{i}"]
        print(f"  LLM vs {lbl}: k = {llm[f'kappa_ann{i}']:.3f}")
    print(f"  LLM vs Consensus:    k = {llm['kappa_consensus']:.3f}  "
          f"(on {llm['n_consensus']} agreed cases)")
    print(f"  Total score Spearman rho = {tsc['rho']:.3f}  (p = {tsc['p']:.4f})")
    print(f"\n  Bias diagnostics:")
    vb_rho = stats["verbosity_bias"]["spearman_rho_length_vs_score"]
    vb_rho_str = f"{vb_rho:.3f}" if not math.isnan(vb_rho) else "n/a"
    print(f"    Verbosity rho = {vb_rho_str}  "
          f"({'FLAGGED' if stats['verbosity_bias']['flag'] else 'OK'})")
    pb = stats["position_bias_direction"]
    frac = pb.get("pass1_A_fraction", float("nan"))
    frac_str = f"{frac:.3f}" if not math.isnan(frac) else "n/a"
    flag_pb = "FLAGGED" if not math.isnan(frac) and abs(frac - 0.5) > 0.10 else "OK"
    print(f"    Position bias A-fraction = {frac_str}  ({flag_pb}, expected ~0.50)")
    print(f"\n  Survivorship note: only Pass-status tests enter the judge.")
    print(f"  Check pass-rate stats in llm_as_judge logs — large inter-model")
    print(f"  pass-rate gaps mean the judge compares selected subsets, not typical output.")
    print(sep)


# SECTION 5 — Figures
THRESHOLD = 0.60


def _kappa_color(k: float) -> str:
    if k >= 0.60: return PALETTE["pass"]
    if k >= 0.40: return PALETTE["warn"]
    return PALETTE["fail"]


def fig1_kappa_summary(stats: dict, out: Path):
    """Horizontal bar chart of all Kappa values with validation threshold."""
    n_ann = stats["n_ann"]
    llm   = stats["llm_vs_human"]
    iaa   = stats["iaa"]

    labels = [f"Fleiss' Kappa\n({n_ann}-way IAA)"]
    kappas = [iaa["fleiss_kappa"]]
    for i in range(1, n_ann + 1):
        labels.append(f"LLM vs {stats['labels'][f'ann{i}']}")
        kappas.append(llm[f"kappa_ann{i}"])
    labels.append("LLM vs Human\nConsensus")
    kappas.append(llm["kappa_consensus"])

    colors = [_kappa_color(k) for k in kappas]

    fig, ax = plt.subplots(figsize=(9, max(6, 1.2 * len(labels))))
    bars = ax.barh(labels, kappas, color=colors, height=0.5, edgecolor="white", linewidth=0.8)

    # Threshold line
    ax.axvline(THRESHOLD, color="black", linestyle="--", linewidth=1.2,
               label=f"Validation threshold k = {THRESHOLD}")

    # Value labels
    for bar, k in zip(bars, kappas):
        interp = interpret_kappa(k)
        ax.text(k + 0.01, bar.get_y() + bar.get_height() / 2,
                f"k = {k:.3f}  ({interp})",
                va="center", ha="left", fontsize=10)

    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Cohen's Kappa (k)")
    ax.set_title("LLM-as-Judge Validation: Inter-Rater Agreement (Kappa)")

    legend_patches = [
        mpatches.Patch(color=PALETTE["pass"], label="Substantial (k >= 0.60)"),
        mpatches.Patch(color=PALETTE["warn"], label="Moderate (0.40 <= k < 0.60)"),
        mpatches.Patch(color=PALETTE["fail"], label="Fair (k < 0.40)"),
    ]
    ax.legend(handles=legend_patches + [
        plt.Line2D([0], [0], color="black", linestyle="--", label=f"Threshold k = {THRESHOLD}")
    ], loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0, fontsize=8, frameon=True)

    # Interpretation band shading
    ax.axvspan(0.60, 0.80, alpha=0.06, color=PALETTE["pass"])
    ax.axvspan(0.40, 0.60, alpha=0.06, color=PALETTE["warn"])

    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def fig2_criterion_correlation(stats: dict, out: Path):
    """Horizontal bar chart of per-criterion Spearman rho values."""
    crits  = CRITERIA + ["total"]
    labels = [CRITERIA_LABELS[c] for c in CRITERIA] + ["Total Score"]
    rs     = [stats["criterion_correlation"][c]["rho"] for c in CRITERIA]
    ps     = [stats["criterion_correlation"][c]["p"] for c in CRITERIA]
    rs.append(stats["total_score_correlation"]["rho"])
    ps.append(stats["total_score_correlation"]["p"])

    colors = [sns.color_palette("Blues_d", len(rs))[i] for i in range(len(rs))]
    # sort by r for coloring (keep label order intact)
    sorted_rs = sorted(rs)
    colors = [sns.color_palette("Blues_d", len(rs))[sorted_rs.index(r)] for r in rs]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(labels, rs, color=colors, height=0.5, edgecolor="white")

    for bar, r, p in zip(bars, rs, ps):
        sig = _sig(p)
        ax.text(r + 0.01, bar.get_y() + bar.get_height() / 2,
                f"r = {r:.3f} {sig}", va="center", ha="left", fontsize=10)

    ax.set_xlim(0, 1.15)
    ax.set_xlabel("Spearman rho (ordinal 1-5 scale)")
    n_ann   = stats["n_ann"]
    n_pairs = stats["criterion_correlation"][CRITERIA[0]]["n"]
    ax.set_title("Human vs LLM Per-Criterion Score Correlation\n"
                 f"(Spearman rho, human avg of all {n_ann} annotators vs LLM avg of both passes, "
                 f"n = {n_pairs} pairs)")
    ax.axvline(0, color="grey", linewidth=0.7)
    ax.text(0.01, -0.6, "*** p<0.001  ** p<0.01  * p<0.05",
            transform=ax.transAxes, fontsize=8, color="grey")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def fig3_confusion_matrices(df: pd.DataFrame, stats: dict, out: Path):
    """Side-by-side normalised confusion matrices: LLM vs each annotator."""
    n_ann = stats["n_ann"]
    cats  = ["A", "B", "Tie"]

    df_v   = df[df["llm_winner"].notna()]
    cms    = [confusion_matrix(df_v[f"ann{i}_winner"], df_v["llm_winner"], labels=cats)
              for i in range(1, n_ann + 1)]
    titles = [f"LLM vs {stats['labels'][f'ann{i}']}\n"
              f"(k = {stats['llm_vs_human'][f'kappa_ann{i}']:.3f})"
              for i in range(1, n_ann + 1)]

    fig, axes = plt.subplots(1, n_ann, figsize=(6 * n_ann, 5))
    if n_ann == 1:
        axes = [axes]
    for ax, cm, title in zip(axes, cms, titles):
        annot = np.array([
            [f"{cm[i,j]}\n({cm[i,j]/cm[i].sum():.0%})" if cm[i].sum() > 0 else "0"
             for j in range(3)] for i in range(3)
        ])
        sns.heatmap(
            cm, annot=annot, fmt="s", cmap="Blues",
            xticklabels=cats, yticklabels=cats,
            linewidths=0.5, linecolor="grey",
            cbar=False, ax=ax, vmin=0,
        )
        ax.set_xlabel("LLM Prediction")
        ax.set_ylabel("Human Label")
        ax.set_title(title)

    fig.suptitle("Confusion Matrices: LLM-as-Judge vs Human Annotators",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def fig4_stratum_breakdown(stats: dict, out: Path):
    """Grouped bar chart: agreement rates per stratum."""
    n_ann  = stats["n_ann"]
    strata = list(stats["stratum_breakdown"].keys())

    group_labels  = [f"LLM vs {stats['labels'][f'ann{i}']}" for i in range(1, n_ann + 1)]
    group_labels += ["Avg Human Agreement"]
    keys  = [f"llm_ann{i}" for i in range(1, n_ann + 1)] + ["avg_human_agree"]
    _base = [PALETTE["neutral"], PALETTE["warn"], PALETTE["pass"], PALETTE["light"]]
    extra = list(sns.color_palette("Set2", max(0, len(keys) - len(_base))))
    bar_colors = (_base + extra)[:len(keys)]

    x = np.arange(len(strata))
    width = 0.20
    fig, ax = plt.subplots(figsize=(10, 5))

    for i, (grp_lbl, key, color) in enumerate(zip(group_labels, keys, bar_colors)):
        rates = [
            stats["stratum_breakdown"][st][key] / stats["stratum_breakdown"][st]["n"]
            for st in strata
        ]
        offset = (i - (len(group_labels) - 1) / 2) * width
        bars = ax.bar(x + offset, rates, width, label=grp_lbl,
                      color=color, edgecolor="white")
        for bar, rate in zip(bars, rates):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    f"{rate:.0%}", ha="center", va="bottom", fontsize=9)

    ax.axhline(THRESHOLD, color="black", linestyle="--", linewidth=1,
               label=f"Threshold {THRESHOLD:.0%}")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{st}\n(n={stats['stratum_breakdown'][st]['n']})" for st in strata])
    ax.set_ylabel("Observed Agreement Rate")
    ax.set_ylim(0, 1.12)
    ax.set_title("Agreement Rates by Difficulty Stratum")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def fig5_score_scatter(df: pd.DataFrame, stats: dict, out: Path):
    """Scatter plot: human avg total score vs LLM total score, coloured by stratum."""
    tsc = stats["total_score_correlation"]
    human = np.array(tsc["human_scores"])
    llm   = np.array(tsc["llm_scores"])

    # Build stratum labels from the same filtered subset used in compute_statistics
    # (non-sentinel, non-Invalid_Bias) — 2 points per row (model_a and model_b).
    n_ann = stats["n_ann"]
    ann_winner_cols = [f"ann{i}_winner" for i in range(1, n_ann + 1)]
    df_v = df[
        ~df["is_sentinel"].fillna(False).astype(bool) &
        df["llm_winner"].notna() &
        (df["llm_winner"] != "Invalid_Bias")
    ].dropna(subset=ann_winner_cols)
    stratum_labels = []
    for _, row in df_v.iterrows():
        stratum_labels.extend([row["stratum"], row["stratum"]])

    fig, ax = plt.subplots(figsize=(7, 6))
    for st, color in STRATUM_COLORS.items():
        mask = np.array(stratum_labels) == st
        ax.scatter(human[mask], llm[mask], c=color, label=st,
                   alpha=0.75, edgecolors="white", s=60, linewidths=0.5)

    # Regression line
    m, b = np.polyfit(human, llm, 1)
    x_line = np.linspace(human.min(), human.max(), 100)
    ax.plot(x_line, m * x_line + b, color="black", linewidth=1.5,
            linestyle="-", label=f"Regression (rho={tsc['rho']:.3f})")

    ax.set_xlabel("Human Average Total Score (sum of 4 criteria)")
    ax.set_ylabel("LLM Total Score (avg of 2 passes, sum of 4 criteria)")
    ax.set_title(
        f"Human vs LLM Total Score Correlation\n"
        f"Spearman rho = {tsc['rho']:.3f}, p = {tsc['p']:.4f}, n = {tsc['n']} score pairs"
    )
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def fig6_verbosity_bias(df: pd.DataFrame, stats: dict, out: Path):
    """Scatter: test code word-count vs LLM total score. Flags verbosity bias if rho > 0.5."""
    vb = stats["verbosity_bias"]
    df_v = df[
        ~df["is_sentinel"].fillna(False).astype(bool) &
        df["llm_winner"].notna() &
        (df["llm_winner"] != "Invalid_Bias")
    ]
    if df_v.empty or "code_a_len" not in df_v.columns:
        return

    lengths, scores, strata = [], [], []
    for _, row in df_v.iterrows():
        lengths.extend([row["code_a_len"], row["code_b_len"]])
        scores.extend([row["llm_score_a"], row["llm_score_b"]])
        strata.extend([row["stratum"], row["stratum"]])

    fig, ax = plt.subplots(figsize=(7, 5))
    for st, color in STRATUM_COLORS.items():
        mask = [s == st for s in strata]
        ax.scatter(
            [l for l, m in zip(lengths, mask) if m],
            [s for s, m in zip(scores,  mask) if m],
            c=color, label=st, alpha=0.65, edgecolors="white", s=50, linewidths=0.4,
        )

    rho = vb["spearman_rho_length_vs_score"]
    if not math.isnan(rho):
        m, b = np.polyfit(lengths, scores, 1)
        x_line = np.linspace(min(lengths), max(lengths), 100)
        ax.plot(x_line, m * x_line + b, color="black", linewidth=1.3,
                linestyle="--", label=f"Regression (rho={rho:.3f})")

    bias_note = "⚠ Verbosity bias flagged (|rho| > 0.50)" if vb["flag"] else "No verbosity bias (|rho| ≤ 0.50)"
    rho_str = f"{rho:.3f}" if not math.isnan(rho) else "n/a"
    ax.set_xlabel("Test code word count")
    ax.set_ylabel("LLM total score (avg of 2 passes)")
    ax.set_title(f"Verbosity Bias Check\nSpearman rho = {rho_str}  —  {bias_note}")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def generate_figures(df: pd.DataFrame, stats: dict):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print("\nGenerating figures...")
    fig1_kappa_summary(stats,          FIGURES_DIR / "fig1_kappa_summary.png")
    fig2_criterion_correlation(stats,   FIGURES_DIR / "fig2_criterion_correlation.png")
    fig3_confusion_matrices(df, stats,  FIGURES_DIR / "fig3_confusion_matrices.png")
    fig4_stratum_breakdown(stats,       FIGURES_DIR / "fig4_stratum_breakdown.png")
    fig5_score_scatter(df, stats,       FIGURES_DIR / "fig5_score_scatter.png")
    fig6_verbosity_bias(df, stats,      FIGURES_DIR / "fig6_verbosity_bias.png")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load
    print("Loading input files...")
    ann_data, csv_df, jlookup = load_inputs()
    print(f"  {len(ann_data)} annotators, {len(csv_df)} comparisons, "
          f"{len(jlookup)} JSONL entries")

    # 2. Merge
    print("Merging datasets...")
    df = build_unified(ann_data, csv_df, jlookup)
    df.to_csv(OUT_DIR / "unified_human_eval.csv", index=False)
    print(f"  Saved: unified_human_eval.csv  ({len(df)} rows)")

    # 3. Compute statistics
    print("Computing statistics...")
    results = compute_statistics(df, ann_data)

    # 4. Console report
    print()
    print_report(df, results)

    # 5. Save JSON
    json_path = OUT_DIR / "kappa_results.json"

    def _serialisable(obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray):     return obj.tolist()
        raise TypeError(f"Not serialisable: {type(obj)}")

    # Strip the raw score arrays (too large for the JSON summary)
    save_results = {k: v for k, v in results.items()
                    if k != "total_score_correlation"}
    tsc = results["total_score_correlation"]
    save_results["total_score_correlation"] = {
        "rho": tsc["rho"], "p": tsc["p"], "n": tsc["n"],
        "interpretation": interpret_r(tsc["rho"]),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(save_results, f, indent=2, default=_serialisable)
    print(f"\nSaved: {json_path}")

    # 6. Figures
    generate_figures(df, results)

    print(f"\nAll outputs in: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
