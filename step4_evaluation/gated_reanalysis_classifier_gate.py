"""
Re-run of gated_reanalysis.py's paired McNemar / Holm-Bonferroni analysis
(RQ2/RQ3's Single-step vs Two-step significance tests), but using the
corrected, runtime-validated classifier-based non-trivial gate
(`executed_nontrivial_gate` from full_corpus_oracle_reanalysis.py's output)
instead of the original static assertion-presence gate
(`has_detectable_assertion` from assertion_gate.py, used by gated_reanalysis.py).

This is the item flagged as open in paper.tex Section~\ref{sec:rq1} ("the
paired significance tests ... still use the original static-presence gate")
and in the new Limitations section (sec:limitations). Does not modify
gated_reanalysis.py, assertion_gate.py, or full_corpus_oracle_reanalysis.py;
purely additive, reads their already-computed CSV outputs.

Scope note: full_corpus_oracle_reanalysis.py's output
(full_corpus_reanalysis_results_experiment_{a,b}.csv) only covers non-Pynguin
generations and, per its own report, has a small denominator difference from
the original evaluated corpus (8,847 vs 8,900-ish for Exp B; see
FULL_CORPUS_REANALYSIS_REPORT.md) reflecting suites outside this pass's scope
(e.g. suites with zero detected oracle sites still get a status but may be
absent from certain edge-case rows). We report Ns explicitly per contrast so
any denominator drift versus gated_reanalysis.py's original Ns is visible,
rather than silently assuming they match.

Run: python step4_evaluation/gated_reanalysis_classifier_gate.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.contingency_tables import mcnemar

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "step4_evaluation" / "oracle_validation"

RESULTS_A = OUT_DIR / "full_corpus_reanalysis_results_experiment_a.csv"
RESULTS_B = OUT_DIR / "full_corpus_reanalysis_results_experiment_b.csv"

MODEL_ORDER = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
               "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]

PIPELINE_MAP = {"single-step": "Single-step", "two-step": "Two-step"}


def short_model(name):
    return name.split("/")[-1]


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    denom = 1 + z ** 2 / n
    center = p + z ** 2 / (2 * n)
    half = z * (p * (1 - p) / n + z ** 2 / (4 * n ** 2)) ** 0.5
    lo = (center - half) / denom
    hi = (center + half) / denom
    return (p * 100, lo * 100, hi * 100)


def holm_bonferroni(pvals):
    n = len(pvals)
    order = np.argsort(pvals)
    adjusted = np.empty(n)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (n - rank) * pvals[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


def mcnemar_pair(df, model, pipeline_a, pipeline_b, tier=None, gate_col="executed_nontrivial_gate"):
    sub = df[df["model"].apply(short_model) == model]
    if tier is not None:
        sub = sub[sub["tier"] == tier]
    a = sub[sub["pipeline"] == pipeline_a].set_index("task_id")[gate_col]
    b = sub[sub["pipeline"] == pipeline_b].set_index("task_id")[gate_col]
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]
    both_pass = int(((a) & (b)).sum())
    both_fail = int(((~a) & (~b)).sum())
    a_only = int(((a) & (~b)).sum())
    b_only = int(((~a) & (b)).sum())
    table = [[both_pass, a_only], [b_only, both_fail]]
    result = mcnemar(table, exact=True)
    odds_ratio = (a_only / b_only) if b_only > 0 else float("inf")
    return {
        "n_common": len(common), "both_pass": both_pass, "both_fail": both_fail,
        "single_only_pass": a_only, "two_step_only_pass": b_only,
        "odds_ratio_single_over_two": odds_ratio,
        "statistic": result.statistic, "p_value": result.pvalue,
    }


def main():
    df_a = pd.read_csv(RESULTS_A, dtype={"task_id": str})
    df_b = pd.read_csv(RESULTS_B, dtype={"task_id": str})
    df_a["pipeline"] = df_a["pipeline"].map(PIPELINE_MAP)
    df_b["pipeline"] = df_b["pipeline"].map(PIPELINE_MAP)

    print("=" * 100)
    print("1. Corrected-gate (executed_nontrivial_gate) Pass@1 per model x pipeline, Exp A, Wilson 95% CI")
    print("=" * 100)
    rows = []
    for model in MODEL_ORDER:
        for pipeline in ["Single-step", "Two-step"]:
            sub = df_a[(df_a["model"].apply(short_model) == model) & (df_a["pipeline"] == pipeline)]
            n = len(sub)
            k = int(sub["executed_nontrivial_gate"].sum())
            p, lo, hi = wilson_ci(k, n)
            rows.append(dict(Model=model, Pipeline=pipeline, N=n, gated_Pass1=round(p, 2),
                              gated_lo=round(lo, 2), gated_hi=round(hi, 2)))
            print(f"  {model:26s} {pipeline:10s} n={n:5d}  gated={p:6.2f}% [{lo:5.2f},{hi:5.2f}]")
    df1a = pd.DataFrame(rows)
    df1a.to_csv(OUT_DIR / "gated_classifier_1_expA.csv", index=False)

    print("\n" + "=" * 100)
    print("2. Corrected-gate Pass@1 per model x pipeline, Exp B pooled over tiers, Wilson 95% CI")
    print("=" * 100)
    rows = []
    for model in MODEL_ORDER:
        for pipeline in ["Single-step", "Two-step"]:
            sub = df_b[(df_b["model"].apply(short_model) == model) & (df_b["pipeline"] == pipeline)]
            n = len(sub)
            k = int(sub["executed_nontrivial_gate"].sum())
            p, lo, hi = wilson_ci(k, n)
            rows.append(dict(Model=model, Pipeline=pipeline, N=n, gated_Pass1=round(p, 2),
                              gated_lo=round(lo, 2), gated_hi=round(hi, 2)))
            print(f"  {model:26s} {pipeline:10s} n={n:5d}  gated={p:6.2f}% [{lo:5.2f},{hi:5.2f}]")
    df2b = pd.DataFrame(rows)
    df2b.to_csv(OUT_DIR / "gated_classifier_2_expB_pooled.csv", index=False)

    print("\n" + "=" * 100)
    print("3. McNemar on corrected-gate outcomes, Single-step vs Two-step, Exp A (5 contrasts)")
    print("=" * 100)
    rows = []
    for model in MODEL_ORDER:
        res = mcnemar_pair(df_a, model, "Single-step", "Two-step")
        res["Model"] = model
        rows.append(res)
    dfm_a = pd.DataFrame(rows)
    dfm_a["p_holm"] = holm_bonferroni(dfm_a["p_value"].values)
    dfm_a["significant_holm_0.05"] = dfm_a["p_holm"] < 0.05
    dfm_a = dfm_a[["Model", "n_common", "both_pass", "both_fail", "single_only_pass", "two_step_only_pass",
                   "odds_ratio_single_over_two", "statistic", "p_value", "p_holm", "significant_holm_0.05"]]
    dfm_a.to_csv(OUT_DIR / "gated_classifier_3_mcnemar_expA.csv", index=False)
    print(dfm_a.to_string(index=False))

    print("\n" + "=" * 100)
    print("4. McNemar on corrected-gate outcomes, Single-step vs Two-step, Exp B (15 contrasts, model x tier)")
    print("=" * 100)
    rows = []
    for model in MODEL_ORDER:
        for tier in ["A", "B", "C"]:
            res = mcnemar_pair(df_b, model, "Single-step", "Two-step", tier=tier)
            res["Model"] = model
            res["Tier"] = tier
            rows.append(res)
    dfm_b = pd.DataFrame(rows)
    dfm_b["p_holm"] = holm_bonferroni(dfm_b["p_value"].values)
    dfm_b["significant_holm_0.05"] = dfm_b["p_holm"] < 0.05
    dfm_b = dfm_b[["Model", "Tier", "n_common", "both_pass", "both_fail", "single_only_pass", "two_step_only_pass",
                   "odds_ratio_single_over_two", "statistic", "p_value", "p_holm", "significant_holm_0.05"]]
    dfm_b.to_csv(OUT_DIR / "gated_classifier_4_mcnemar_expB.csv", index=False)
    print(dfm_b.to_string(index=False))

    # ------------------------------------------------------------------
    # Compare against the ORIGINAL static-gate McNemar results, to see
    # whether any significance conclusion actually flips.
    # ------------------------------------------------------------------
    orig_a_path = ROOT / "step4_evaluation" / "rq_reanalysis_output" / "gated_4_mcnemar_expA.csv"
    orig_b_path = ROOT / "step4_evaluation" / "rq_reanalysis_output" / "gated_5_mcnemar_expB.csv"
    print("\n" + "=" * 100)
    print("5. Comparison: does any significance conclusion change vs. the original static gate?")
    print("=" * 100)
    if orig_a_path.exists():
        orig_a = pd.read_csv(orig_a_path)
        cmp_a = orig_a[["Model", "p_holm", "significant_holm_0.05"]].merge(
            dfm_a[["Model", "p_holm", "significant_holm_0.05"]], on="Model",
            suffixes=("_static", "_classifier"))
        cmp_a["flipped"] = cmp_a["significant_holm_0.05_static"] != cmp_a["significant_holm_0.05_classifier"]
        cmp_a.to_csv(OUT_DIR / "gated_classifier_5_comparison_expA.csv", index=False)
        print("\nExp A:")
        print(cmp_a.to_string(index=False))
    else:
        print(f"  (original static-gate file not found at {orig_a_path}, run gated_reanalysis.py first)")

    if orig_b_path.exists():
        orig_b = pd.read_csv(orig_b_path)
        cmp_b = orig_b[["Model", "Tier", "p_holm", "significant_holm_0.05"]].merge(
            dfm_b[["Model", "Tier", "p_holm", "significant_holm_0.05"]], on=["Model", "Tier"],
            suffixes=("_static", "_classifier"))
        cmp_b["flipped"] = cmp_b["significant_holm_0.05_static"] != cmp_b["significant_holm_0.05_classifier"]
        cmp_b.to_csv(OUT_DIR / "gated_classifier_5_comparison_expB.csv", index=False)
        print("\nExp B:")
        print(cmp_b.to_string(index=False))
        n_flipped = int(cmp_b["flipped"].sum()) + (int(cmp_a["flipped"].sum()) if orig_a_path.exists() else 0)
        print(f"\nTotal contrasts with a flipped significance conclusion: {n_flipped} / {len(cmp_a) + len(cmp_b)}")
    else:
        print(f"  (original static-gate file not found at {orig_b_path}, run gated_reanalysis.py first)")

    print(f"\nAll gated_classifier_*.csv written to {OUT_DIR}")


if __name__ == "__main__":
    main()
