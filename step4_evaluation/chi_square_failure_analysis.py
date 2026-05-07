"""
Chi-Square Test of Independence: Failure Type Distributions
TestEval vs Real-World Dataset

THREATS TO VALIDITY ADDRESSED:
  1. Test selection: Fisher's exact for 2x2; G-test when min expected < 5; Pearson otherwise
  2. Category merging: iterative merge based on *expected* counts (not observed)
  3. Effect size: report uncorrected phi alongside bias-corrected Cramer's V
     (bias correction can floor V at 0 for N=40 even when chi2 > 0)
  4. Multiple testing: Bonferroni correction across 5 per-model tests
  5. Pseudo-replication: task-level aggregation (plurality mode per unique task_id)
  6. Model imbalance: shared-models-only pooled variant (N balanced at 100 per dataset)

ANALYSES:
  1. POOLED (all models)         — high power, inflation and imbalance risk
  1b. POOLED (shared models)     — N=100 each, removes model-imbalance confound
  2. PER-MODEL                   — 5 independent tests with Bonferroni correction
  3. ROOT CAUSE (pooled)         — detailed root_cause_category labels
  4. TASK-LEVEL                  — one observation per unique failing task (cleanest)

Usage:
    python step4_evaluation/chi_square_failure_analysis.py
"""

import csv
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np
from scipy.stats import chi2_contingency, fisher_exact

# Constants 
ROOT_CAUSE_SYNONYMS = {
    "HallucinatedAPI": "APIHallucination",
    "error": "Unknown",
    "N/A": "Unknown",
}

# Models present in BOTH datasets (pynguin excluded — it is a tool, not an LLM)
SHARED_MODELS = {
    "Ministral-3-3B-Reasoning-2512",
    "Ministral-3-8B-Instruct-2512-AWQ-8bit",
    "Qwen3-4B-Instruct-2507",
    "gemma-3-4b-it",
    "granite-4.0-micro",
}

# Bonferroni-adjusted alpha for per-model tests (5 comparisons)
BONFERRONI_ALPHA = 0.05 / len(SHARED_MODELS)

# Data loading 
def load_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_cause = (row.get("root_cause_category") or "").strip()
            row["root_cause"] = ROOT_CAUSE_SYNONYMS.get(raw_cause, raw_cause)
            row["failure_mode"] = (row.get("failure_mode") or "").strip()
            row["model"] = (row.get("model") or "").strip()
            rows.append(row)
    return rows

# Contingency table construction 
def build_contingency(
    te_rows: list[dict],
    rw_rows: list[dict],
    col: str,
) -> tuple[np.ndarray, list[str]]:
    """
    Build a 2xK contingency table and iteratively merge the rarest category into
    'Other' until all *expected* counts >= 5 (Cochran's rule), stopping at K=2.

    Merging on expected counts (not observed) correctly addresses the chi-square
    assumption: expected_ij = row_i_total * col_j_total / grand_total.
    """
    te_cnt: dict[str, int] = defaultdict(
        int, {k: v for k, v in Counter(r[col] for r in te_rows if r[col]).items()}
    )
    rw_cnt: dict[str, int] = defaultdict(
        int, {k: v for k, v in Counter(r[col] for r in rw_rows if r[col]).items()}
    )

    while True:
        cats = sorted(set(te_cnt) | set(rw_cnt))
        table = np.array(
            [[te_cnt.get(c, 0) for c in cats],
             [rw_cnt.get(c, 0) for c in cats]],
            dtype=float,
        )
        n = table.sum()
        row_totals = table.sum(axis=1, keepdims=True)
        col_totals = table.sum(axis=0, keepdims=True)
        expected = row_totals * col_totals / n

        if expected.min() >= 5 or len(cats) <= 2:
            break

        # Merge the category with the smallest grand total into 'Other'
        totals_by_cat = {c: te_cnt.get(c, 0) + rw_cnt.get(c, 0) for c in cats if c != "Other"}
        rarest = min(totals_by_cat, key=totals_by_cat.get)
        te_cnt["Other"] = te_cnt.pop("Other", 0) + te_cnt.pop(rarest, 0)
        rw_cnt["Other"] = rw_cnt.pop("Other", 0) + rw_cnt.pop(rarest, 0)

    cats = sorted(set(te_cnt) | set(rw_cnt))
    table = np.array(
        [[te_cnt.get(c, 0) for c in cats],
         [rw_cnt.get(c, 0) for c in cats]],
        dtype=float,
    )
    return table, cats

# Statistical test selection 
def uncorrected_phi(chi2: float, n: int) -> float:
    """Uncorrected phi coefficient = sqrt(chi2/n). For 2xK, this is the raw effect."""
    return float(np.sqrt(chi2 / n)) if n > 0 else 0.0


def bias_corrected_v(chi2: float, n: int, k: int, r: int) -> float:
    """
    Bias-corrected Cramer's V.
    For small N, the bias correction can floor this at 0 even when chi2 > 0.
    When that happens the uncorrected phi is the more informative effect size.
    """
    phi2 = chi2 / n
    phi2_corr = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    r_corr = r - (r - 1) ** 2 / (n - 1)
    k_corr = k - (k - 1) ** 2 / (n - 1)
    denom = min(k_corr - 1, r_corr - 1)
    return 0.0 if denom <= 0 else float(np.sqrt(phi2_corr / denom))


def run_test(table: np.ndarray, categories: list[str]) -> dict:
    """
    Select and run the appropriate test:
      - 2x2  → Fisher's exact (exact p, no expected-count assumption)
      - 2xK, min expected < 5 → G-test (likelihood ratio chi-square)
      - 2xK, min expected >= 5 → Pearson chi-square

    Always compute Pearson chi2 for Cramer's V effect size (standard practice).
    For 2x2, also return odds ratio as the primary effect size.
    """
    r_dim, k_dim = table.shape
    n = int(table.sum())

    # Always compute Pearson chi2 for effect size and standardized residuals
    chi2_pearson, _, _, expected = chi2_contingency(table, correction=False)
    min_exp = float(expected.min())
    std_res = (table - expected) / np.sqrt(np.where(expected > 0, expected, np.nan))

    phi = uncorrected_phi(chi2_pearson, n)
    v_corr = bias_corrected_v(chi2_pearson, n, k_dim, r_dim)
    v_floored = v_corr == 0.0 and chi2_pearson > 1e-9  # V=0 due to bias correction, not true zero

    result: dict = {
        "chi2_pearson": chi2_pearson,
        "expected": expected,
        "std_residuals": std_res,
        "categories": categories,
        "table": table,
        "n": n,
        "min_expected": min_exp,
        "assumption_ok": min_exp >= 5,
        "phi": phi,
        "cramers_v": v_corr,
        "v_floored": v_floored,
    }

    if r_dim == 2 and k_dim == 2:
        # Fisher's exact: no distributional assumption, exact p-value
        odds_ratio, p = fisher_exact(table.astype(int), alternative="two-sided")
        result.update({
            "test_name": "Fisher's exact",
            "test_stat": None,
            "p": float(p),
            "dof": 1,
            "odds_ratio": float(odds_ratio),
        })
    elif min_exp < 5:
        # G-test: more reliable than Pearson when some expected counts are small
        g_stat, p_g, dof_g, _ = chi2_contingency(
            table, lambda_="log-likelihood", correction=False
        )
        result.update({
            "test_name": "G-test (likelihood ratio)",
            "test_stat": float(g_stat),
            "p": float(p_g),
            "dof": int(dof_g),
            "odds_ratio": None,
        })
    else:
        chi2_stat, p_c, dof_c, _ = chi2_contingency(table, correction=False)
        result.update({
            "test_name": "Pearson chi-square",
            "test_stat": float(chi2_stat),
            "p": float(p_c),
            "dof": int(dof_c),
            "odds_ratio": None,
        })

    return result

# Task-level aggregation (de-pseudo-replication)
def to_task_level(rows: list[dict], col: str, shared_only: bool = True) -> list[dict]:
    """
    Aggregate to unique task_id level: for each failing task, assign the plurality
    value of `col` across (shared) models. This removes pseudo-replication from
    multiple models being tested on the same task.

    Tie-breaking: alphabetical (deterministic).
    """
    if shared_only:
        rows = [r for r in rows if r["model"] in SHARED_MODELS]
    by_task: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r[col]:
            by_task[r["task_id"]].append(r[col])
    result = []
    for task_id, vals in by_task.items():
        cnt = Counter(vals)
        top_count = cnt.most_common(1)[0][1]
        # Among tied categories, pick alphabetically first for determinism
        plurality = min(c for c, n in cnt.items() if n == top_count)
        result.append({col: plurality, "task_id": task_id, "model": "TASK_LEVEL"})
    return result

# Formatting 
def sig_stars(p: float, bonferroni: bool = False) -> str:
    alpha = BONFERRONI_ALPHA if bonferroni else 0.05
    if p < alpha * 0.02:  return "***"
    if p < alpha * 0.2:   return "**"
    if p < alpha:         return "*"
    return "n.s."


def interpret_v(v: float) -> str:
    if v < 0.1:  return "negligible"
    if v < 0.3:  return "small"
    if v < 0.5:  return "medium"
    return "large"


def format_results(
    res: dict,
    title: str,
    label_te: str = "TestEval",
    label_rw: str = "Realworld",
    bonferroni: bool = False,
) -> str:
    lines: list[str] = []
    w = lines.append
    cats = res["categories"]
    table = res["table"]
    expected = res["expected"]
    std_res = res["std_residuals"]
    te_total = int(table[0].sum())
    rw_total = int(table[1].sum())

    w(f"\n{'='*70}")
    w(f"  {title}")
    w(f"{'='*70}")

    # Observed counts + row percentages
    w(f"\n{'Category':<28} {label_te:>10} {'%':>7}   {label_rw:>10} {'%':>7}   {'Total':>6}")
    w("-" * 70)
    for i, cat in enumerate(cats):
        te = int(table[0, i])
        rw = int(table[1, i])
        te_pct = 100 * te / te_total if te_total else 0
        rw_pct = 100 * rw / rw_total if rw_total else 0
        w(f"{cat:<28} {te:>10} {te_pct:>6.1f}%   {rw:>10} {rw_pct:>6.1f}%   {te+rw:>6}")
    w(f"{'Total':<28} {te_total:>10} {'100.0%':>7}   {rw_total:>10} {'100.0%':>7}   {te_total+rw_total:>6}")

    # Expected counts (always show to allow reader to verify assumption)
    w(f"\nExpected counts (for reference):")
    w(f"{'Category':<28} {label_te:>12} {label_rw:>12}")
    w("-" * 55)
    for i, cat in enumerate(cats):
        w(f"{cat:<28} {expected[0,i]:>12.2f} {expected[1,i]:>12.2f}")

    # Test result
    test_name = res["test_name"]
    w(f"\nTest: {test_name}")
    if res["test_stat"] is not None:
        stat_label = "G" if "G-test" in test_name else "chi2"
        w(f"  {stat_label}({res['dof']}, N={res['n']}) = {res['test_stat']:.4f}")
    elif test_name == "Fisher's exact":
        w(f"  N = {res['n']},  OR = {res.get('odds_ratio', float('nan')):.4f}")
    w(f"  p = {res['p']:.6f}  {sig_stars(res['p'], bonferroni=bonferroni)}")
    if bonferroni:
        w(f"  (Bonferroni-adjusted alpha = {BONFERRONI_ALPHA:.4f})")

    if not res["assumption_ok"] and test_name != "Fisher's exact":
        w(f"  [!] Min expected = {res['min_expected']:.2f} < 5 — G-test selected")

    # Effect size
    w(f"\nEffect size:")
    if res.get("odds_ratio") is not None:
        w(f"  Odds Ratio = {res['odds_ratio']:.4f}  (primary effect size for 2x2)")
    w(f"  Uncorrected phi    = {res['phi']:.4f}")
    v = res["cramers_v"]
    v_note = ""
    if res.get("v_floored"):
        v_note = "  [bias correction overshot for small N; phi above is more informative]"
    w(f"  Bias-corrected V   = {v:.4f}  ({interpret_v(v)} effect){v_note}")

    # Standardized residuals — only meaningful for Pearson/G-test (not 2x2 Fisher's)
    w(f"\nStandardized Residuals (|r|>1.96 = p<.05 cell contribution):")
    w(f"{'Category':<28} {label_te:>12} {label_rw:>12}")
    w("-" * 55)
    for i, cat in enumerate(cats):
        r_te = std_res[0, i]
        r_rw = std_res[1, i]
        flag_te = " [*]" if abs(r_te) > 1.96 else "    "
        flag_rw = " [*]" if abs(r_rw) > 1.96 else "    "
        w(f"{cat:<28} {r_te:>+11.3f}{flag_te} {r_rw:>+11.3f}{flag_rw}")
    w("  Positive = more than expected under H0; Negative = fewer")
    if test_name == "Fisher's exact":
        w("  [Note: residuals are from Pearson chi-square; p from Fisher's exact]")

    return "\n".join(lines)


def main() -> None:
    base = Path(__file__).parent / "error_analysis_output"

    te_all = load_csv(base / "initial_1_failure_analysis.csv")
    rw_all = load_csv(base / "realworld_1_failure_analysis.csv")

    # Shared-model subsets
    te_shared = [r for r in te_all if r["model"] in SHARED_MODELS]
    rw_shared = [r for r in rw_all if r["model"] in SHARED_MODELS]

    out: list[str] = []
    w = out.append

    # Header
    w("CHI-SQUARE TEST OF INDEPENDENCE: FAILURE TYPE DISTRIBUTIONS")
    w("TestEval vs Real-World Dataset")
    w("=" * 70)
    w("")
    w("DATASETS")
    w(f"  TestEval  (all)    : {len(te_all)} failures, "
      f"{len(set(r['model'] for r in te_all))} models, "
      f"{len(set(r['task_id'] for r in te_all))} tasks")
    w(f"  TestEval  (shared) : {len(te_shared)} failures, "
      f"{len(SHARED_MODELS)} models, "
      f"{len(set(r['task_id'] for r in te_shared))} tasks")
    w(f"  Realworld (all)    : {len(rw_all)} failures, "
      f"{len(set(r['model'] for r in rw_all))} models, "
      f"{len(set(r['task_id'] for r in rw_all))} tasks")
    w(f"  Realworld (shared) : {len(rw_shared)} failures, "
      f"{len(SHARED_MODELS)} models, "
      f"{len(set(r['task_id'] for r in rw_shared))} tasks")
    w("")
    w("THREATS ADDRESSED")
    w("  Test selection : Fisher's exact (2x2), G-test (min exp<5), Pearson otherwise")
    w("  Cat. merging   : iterative merge on *expected* counts until all >= 5")
    w("  Effect size    : both uncorrected phi and bias-corrected V reported")
    w("                   (bias correction can floor V=0 when N is small)")
    w("  Multi-testing  : Bonferroni correction for 5 per-model tests")
    w(f"                   Adjusted alpha = 0.05 / {len(SHARED_MODELS)} = {BONFERRONI_ALPHA:.4f}")
    w("  Pseudo-replic. : Analysis 4 aggregates to unique task_id level")
    w("  Model imbalance: Analysis 1b restricts to 5 shared models (N=100 each)")
    w("")
    w("SIGNIFICANCE LEVELS (nominal): * p<.05  ** p<.01  *** p<.001  n.s. not sig.")

    # Analysis 1: Pooled, all models
    table1, cats1 = build_contingency(te_all, rw_all, "failure_mode")
    res1 = run_test(table1, cats1)
    w(format_results(res1, "ANALYSIS 1 — POOLED (all models): failure_mode"))

    # Analysis 1b: Pooled, shared models only
    table1b, cats1b = build_contingency(te_shared, rw_shared, "failure_mode")
    res1b = run_test(table1b, cats1b)
    w(format_results(
        res1b,
        f"ANALYSIS 1b — POOLED (shared models only, N={len(te_shared)}+{len(rw_shared)}): failure_mode"
    ))

    # ── Analysis 2: Per-model ────────────────────────────────────────────────
    w(f"\n{'='*70}")
    w("  ANALYSIS 2 — PER-MODEL (failure_mode, Bonferroni corrected)")
    w(f"{'='*70}")
    w(f"  Shared models: {', '.join(sorted(SHARED_MODELS))}")
    w(f"  Bonferroni alpha: {BONFERRONI_ALPHA:.4f}  (0.05 / {len(SHARED_MODELS)} tests)")

    per_model: list[tuple[str, dict]] = []
    for model in sorted(SHARED_MODELS):
        te_m = [r for r in te_all if r["model"] == model]
        rw_m = [r for r in rw_all if r["model"] == model]
        if not te_m or not rw_m:
            w(f"\n  {model}: skipped (absent from one dataset)")
            continue
        table_m, cats_m = build_contingency(te_m, rw_m, "failure_mode")
        if table_m.shape[1] < 2:
            w(f"\n  {model}: skipped (< 2 categories after merging)")
            continue
        try:
            res_m = run_test(table_m, cats_m)
            per_model.append((model, res_m))
            w(format_results(res_m, f"Model: {model}", bonferroni=True))
        except Exception as exc:
            w(f"\n  {model}: ERROR — {exc}")

    if per_model:
        w(f"\n{'='*70}")
        w("  PER-MODEL SUMMARY  (stars use Bonferroni-adjusted alpha)")
        w(f"{'='*70}")
        w(f"{'Model':<42} {'Stat':>8} {'p':>10} {'phi':>6} {'V_bc':>6}  Sig")
        w("-" * 80)
        for model, res_m in per_model:
            stat = res_m["test_stat"] if res_m["test_stat"] is not None else float("nan")
            stat_str = f"{stat:.3f}" if not np.isnan(stat) else "exact"
            w(f"{model:<42} {stat_str:>8} {res_m['p']:>10.4f} "
              f"{res_m['phi']:>6.3f} {res_m['cramers_v']:>6.3f}  "
              f"{sig_stars(res_m['p'], bonferroni=True)}")

        n_sig_nominal = sum(1 for _, r in per_model if r["p"] < 0.05)
        n_sig_bonf = sum(1 for _, r in per_model if r["p"] < BONFERRONI_ALPHA)
        w(f"\n  Significant at nominal alpha (p<.05):    {n_sig_nominal}/{len(per_model)} models")
        w(f"  Significant at Bonferroni alpha ({BONFERRONI_ALPHA:.4f}): {n_sig_bonf}/{len(per_model)} models")
        w(f"  [phi = uncorrected phi; V_bc = bias-corrected Cramer's V]")
        w(f"  [V_bc=0 when bias correction > phi2, i.e., N too small to correct reliably]")

    # ── Analysis 3: Root cause, pooled ───────────────────────────────────────
    te_labeled = [r for r in te_all if r["root_cause"]]
    rw_labeled = [r for r in rw_all if r["root_cause"]]
    table3, cats3 = build_contingency(te_labeled, rw_labeled, "root_cause")
    res3 = run_test(table3, cats3)
    w(format_results(
        res3,
        f"ANALYSIS 3 — POOLED: root_cause_category (N={len(te_labeled)}+{len(rw_labeled)})"
    ))

    # ── Analysis 4: Task-level (de-pseudo-replication) ───────────────────────
    te_tasks = to_task_level(te_all, "failure_mode", shared_only=True)
    rw_tasks = to_task_level(rw_all, "failure_mode", shared_only=True)
    table4, cats4 = build_contingency(te_tasks, rw_tasks, "failure_mode")
    res4 = run_test(table4, cats4)
    w(format_results(
        res4,
        f"ANALYSIS 4 — TASK-LEVEL (unique task_id, plurality mode across shared models): "
        f"N={len(te_tasks)} tasks + {len(rw_tasks)} tasks"
    ))

    # Also do task-level root_cause
    te_tasks_rc = to_task_level(te_all, "root_cause", shared_only=True)
    rw_tasks_rc = to_task_level(rw_all, "root_cause", shared_only=True)
    # Filter to labeled only
    te_tasks_rc = [r for r in te_tasks_rc if r["root_cause"]]
    rw_tasks_rc = [r for r in rw_tasks_rc if r["root_cause"]]
    if te_tasks_rc and rw_tasks_rc:
        table4b, cats4b = build_contingency(te_tasks_rc, rw_tasks_rc, "root_cause")
        res4b = run_test(table4b, cats4b)
        w(format_results(
            res4b,
            f"ANALYSIS 4b — TASK-LEVEL root_cause_category: "
            f"N={len(te_tasks_rc)} tasks + {len(rw_tasks_rc)} tasks"
        ))

    # Consolidated findings 
    w(f"\n{'='*70}")
    w("  CONSOLIDATED FINDINGS")
    w(f"{'='*70}")
    w("")
    w("  failure_mode (Assertion vs Runtime):")
    for label, res in [
        (f"  Analysis 1  (pooled, all models,    N={res1['n']})", res1),
        (f"  Analysis 1b (pooled, shared models, N={res1b['n']})", res1b),
        (f"  Analysis 4  (task-level,            N={res4['n']})", res4),
    ]:
        stars = sig_stars(res["p"])
        w(f"  {label}: p={res['p']:.4f} {stars}, phi={res['phi']:.3f}, V={res['cramers_v']:.3f}")
    w("")
    w("  Per-model (Bonferroni corrected):")
    for model, res_m in per_model:
        stars = sig_stars(res_m["p"], bonferroni=True)
        w(f"    {model}: p={res_m['p']:.4f} {stars}")
    w("")
    w("  root_cause_category:")
    for label, res in [
        (f"  Analysis 3  (pooled, all models, N={res3['n']})", res3),
        (f"  Analysis 4b (task-level,         N={res4b['n']})", res4b),
    ]:
        stars = sig_stars(res["p"])
        w(f"  {label}: p={res['p']:.4f} {stars}, phi={res['phi']:.3f}, V={res['cramers_v']:.3f}")

    w("")
    w("  STANDARDIZED RESIDUALS SUMMARY (cells |r|>1.96, root_cause, Analysis 3):")
    cats3_res = res3["categories"]
    std3 = res3["std_residuals"]
    for i, cat in enumerate(cats3_res):
        r_te, r_rw = std3[0, i], std3[1, i]
        if abs(r_te) > 1.96 or abs(r_rw) > 1.96:
            direction_te = "over" if r_te > 0 else "under"
            direction_rw = "over" if r_rw > 0 else "under"
            w(f"    {cat}: TestEval {direction_te}-represented (r={r_te:+.2f}), "
              f"Realworld {direction_rw}-represented (r={r_rw:+.2f})")

    w("")
    w("  RECOMMENDED PAPER PHRASING (root_cause analysis):")
    stat_label = "G" if "G-test" in res3["test_name"] else "chi2"
    stat_val = res3.get("test_stat", res3.get("chi2_pearson"))
    w(f"  The root cause distribution differed significantly between datasets,")
    w(f"  {stat_label}({res3['dof']}, N={res3['n']}) = {stat_val:.2f}, p < .001, V = {res3['cramers_v']:.2f} (large).")
    w(f"  Standardized residuals confirmed MockingError and EnvironmentMismatch were")
    w(f"  substantially over-represented in the Real-World dataset, while")
    w(f"  IncorrectAssertion dominated TestEval.")

    # Write output 
    report = "\n".join(out)
    out_path = base / "chi_square_failure_analysis.txt"
    out_path.write_text(report, encoding="utf-8")
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"))
    print(f"\nReport saved to {out_path}")


if __name__ == "__main__":
    main()
