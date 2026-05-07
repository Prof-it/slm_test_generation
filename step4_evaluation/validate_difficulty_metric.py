"""
validate_difficulty_metric.py

Validates the custom composite difficulty metric used to stratify the real-world dataset.
Addresses the concern that the metric was applied without prior validation.

Two tests:
  1. Construct validity  - Spearman rho between the composite score and Radon's built-in A-F rating,
                           an established static analysis standard.
  2. Predictive validity - Kruskal-Wallis test on mean pass@1 across Easy / Medium / Hard groups,
                           showing the metric predicts actual SLM behaviour.

Usage:
    python step4_evaluation/validate_difficulty_metric.py
"""

import ast
import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from radon.complexity import cc_visit, cc_rank
from radon.metrics import h_visit
from scipy import stats


# Paths
REPO_ROOT    = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "TestEval" / "data" / "realworld-py.jsonl"
RESULTS_DIR  = REPO_ROOT / "evaluation_results_realworld_10"
FIGURES_DIR  = Path(__file__).resolve().parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

DIFFICULTY_LABELS = {1: "Easy", 2: "Medium", 3: "Hard"}
DIFFICULTY_COLORS = {1: "#2ecc71", 2: "#f39c12", 3: "#e74c3c"}

# Radon's A-F rank mapped to ordinal integers for Spearman correlation
RADON_RANK_MAP = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6}


# Composite score logic (mirrors create_realworld_dataset.py exactly)
class DifficultyAnalyzer(ast.NodeVisitor):
    """AST visitor that tracks control-flow nesting depth and unique variable names."""

    def __init__(self):
        self.max_depth = 0
        self.current_depth = 0
        self.state_vars = set()

    def generic_visit(self, node):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            self.current_depth += 1
            self.max_depth = max(self.max_depth, self.current_depth)
            super().generic_visit(node)
            self.current_depth -= 1
        else:
            super().generic_visit(node)

    def visit_FunctionDef(self, node):
        for arg in node.args.args:
            self.state_vars.add(arg.arg)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Tuple):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self.state_vars.add(elt.id)
            elif isinstance(target, ast.Name):
                self.state_vars.add(target.id)
        self.generic_visit(node)


def compute_scores(source_code: str):
    """
    Computes both the composite score and the maximum Radon rank (A-F → 1-6).

    Returns (composite_score, max_radon_rank_numeric) or (None, None) on failure.
    """
    try:
        cc_results = cc_visit(source_code)
        if not cc_results:
            return None, None

        # cc_visit returns Function, Method, and Class objects.
        # .letter is the type identifier (F/M/C), NOT the A-F complexity rating.
        # Use cc_rank(complexity) to obtain the A-F rating for each result.
        complexities = [c.complexity for c in cc_results]
        ranks        = [RADON_RANK_MAP.get(cc_rank(c.complexity), 1) for c in cc_results]

        min_cc   = min(complexities)
        avg_cc   = sum(complexities) / len(complexities)
        max_rank = max(ranks)

        tree = ast.parse(source_code)
        analyzer = DifficultyAnalyzer()
        analyzer.visit(tree)

        ssc       = len(analyzer.state_vars)
        cfg_depth = analyzer.max_depth
        score     = min_cc + math.ceil(avg_cc) + ssc + cfg_depth

        return score, max_rank

    except Exception as e:
        print(f"  Warning: analysis failed - {e}", file=sys.stderr)
        return None, None


# Step 1: Load dataset and compute scores
def load_dataset() -> pd.DataFrame:
    records = []
    with open(DATASET_PATH) as f:
        for line in f:
            task = json.loads(line)
            composite, radon_rank = compute_scores(task["python_solution"])
            if composite is None:
                continue
            # Halstead difficulty — returns 0 for tasks with relative imports
            # or other patterns that Radon's Halstead visitor cannot parse.
            h = h_visit(task["python_solution"])
            halstead_diff = h.total.difficulty if h.total.difficulty > 0 else None

            records.append({
                "task_num":        str(task["task_num"]),
                "func_name":       task["func_name"],
                "difficulty":      task["difficulty"],
                "composite_score": composite,
                "halstead_diff":   halstead_diff,
                "radon_rank":      radon_rank,
            })
    return pd.DataFrame(records)


# Step 2: Spearman correlation (construct validity)
def spearman_analysis(df: pd.DataFrame):
    rho, p = stats.spearmanr(df["composite_score"], df["radon_rank"])
    if abs(rho) >= 0.7:
        strength = "strong"
    elif abs(rho) >= 0.4:
        strength = "moderate"
    else:
        strength = "weak"
    return rho, p, strength


def plot_correlation(df: pd.DataFrame, rho: float, p: float):
    fig, ax = plt.subplots(figsize=(7, 5))

    for diff, grp in df.groupby("difficulty"):
        ax.scatter(
            grp["radon_rank"], grp["composite_score"],
            c=DIFFICULTY_COLORS[diff], label=DIFFICULTY_LABELS[diff],
            alpha=0.85, edgecolors="k", linewidths=0.5, s=70,
        )

    ax.set_xlabel("Radon A-F Rating (numeric)", fontsize=12)
    ax.set_ylabel("Composite Score", fontsize=12)
    ax.set_title(
        f"Composite Score vs. Radon A-F Rating\n"
        f"Spearman rho = {rho:.3f}  (p = {p:.3f})",
        fontsize=12,
    )
    ax.set_xticks(range(1, 7))
    ax.set_xticklabels(["A (1)", "B (2)", "C (3)", "D (4)", "E (5)", "F (6)"])
    ax.legend(title="Difficulty", framealpha=0.9)
    plt.tight_layout()

    out = FIGURES_DIR / "difficulty_metric_correlation.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")


# Step 3: Load evaluation results
def load_eval_results(df_dataset: pd.DataFrame) -> pd.DataFrame:
    task_difficulty = dict(zip(df_dataset["task_num"], df_dataset["difficulty"]))
    rows = []

    for run_dir in sorted(RESULTS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        for jf in sorted(run_dir.glob("*.jsonl")):
            with open(jf) as f:
                for line in f:
                    rec      = json.loads(line)
                    task_num = str(rec.get("task_num", ""))
                    if task_num not in task_difficulty:
                        continue
                    rows.append({
                        "task_num":   task_num,
                        "difficulty": task_difficulty[task_num],
                        "passed":     1 if rec.get("status") == "Pass" else 0,
                        "run":        run_dir.name,
                        "file":       jf.name,
                    })

    return pd.DataFrame(rows)


# Step 4: Kruskal-Wallis + bar chart (predictive validity)
def predictive_validity(df_evals: pd.DataFrame):
    # Aggregate to one pass rate per task (mean over all models and runs)
    per_task = (
        df_evals
        .groupby(["task_num", "difficulty"])["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    groups = [
        per_task.loc[per_task["difficulty"] == d, "pass_rate"].values
        for d in [1, 2, 3]
    ]
    non_empty = [g for g in groups if len(g) > 0]
    H, p = stats.kruskal(*non_empty)
    return per_task, H, p


def plot_predictive(per_task: pd.DataFrame, H: float, p: float):
    fig, ax = plt.subplots(figsize=(6, 5))

    for i, diff in enumerate([1, 2, 3]):
        grp = per_task.loc[per_task["difficulty"] == diff, "pass_rate"]
        ax.bar(
            i, grp.mean(),
            color=DIFFICULTY_COLORS[diff], alpha=0.85, edgecolor="k",
            yerr=grp.std(), capsize=6, label=DIFFICULTY_LABELS[diff],
        )

    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["Easy", "Medium", "Hard"])
    ax.set_ylabel("Mean Pass@1 (averaged over all models & runs)", fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_title(
        f"Predictive Validity: Pass@1 by Difficulty Level\n"
        f"Kruskal-Wallis H = {H:.2f},  p = {p:.3f}",
        fontsize=12,
    )
    plt.tight_layout()

    out = FIGURES_DIR / "difficulty_predictive_validity.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")


# Step 5: Composite vs. Radon as predictors of pass@1
def compare_predictors(df_dataset: pd.DataFrame, per_task: pd.DataFrame):
    """
    Side-by-side Spearman rho against pass@1 for three metrics:
      - composite_score (our metric)
      - radon_rank      (McCabe CC A-F)
      - halstead_diff   (Radon Halstead difficulty, where available)
    Answers: do established Radon metrics predict pass@1 as well as our composite?
    """
    merged = df_dataset.merge(per_task[["task_num", "pass_rate"]], on="task_num")

    rho_c, p_c = stats.spearmanr(merged["composite_score"], merged["pass_rate"])
    rho_r, p_r = stats.spearmanr(merged["radon_rank"],      merged["pass_rate"])

    # Halstead: only for tasks where it returned a non-zero value
    h_valid = merged.dropna(subset=["halstead_diff"])
    n_halstead = len(h_valid)
    n_total    = len(merged)
    if n_halstead >= 10:
        rho_h, p_h = stats.spearmanr(h_valid["halstead_diff"], h_valid["pass_rate"])
        h_str = f"{rho_h:+.3f}  (p={p_h:.4f})  [n={n_halstead}/{n_total} parseable]"
    else:
        rho_h, p_h = None, None
        h_str = f"insufficient data ({n_halstead}/{n_total} tasks parseable)"

    print(f"    Spearman rho (composite_score vs pass@1): {rho_c:+.3f}  (p={p_c:.4f})")
    print(f"    Spearman rho (radon CC rank   vs pass@1): {rho_r:+.3f}  (p={p_r:.4f})")
    print(f"    Spearman rho (halstead_diff   vs pass@1): {h_str}")

    if n_halstead < n_total:
        print(f"\n    Note: Halstead difficulty returned 0 (unparseable) for")
        print(f"    {n_total - n_halstead}/{n_total} tasks due to relative imports and")
        print(f"    __future__ annotations in the wrapped code. This coverage gap")
        print(f"    itself demonstrates why Halstead is not suitable as the sole")
        print(f"    stratification metric for this dataset.")

    candidates = {"composite": (abs(rho_c), "composite_score")}
    candidates["radon_cc"]   = (abs(rho_r), "radon CC rank")
    if rho_h is not None:
        candidates["halstead"] = (abs(rho_h), "Halstead difficulty")

    best_key  = max(candidates, key=lambda k: candidates[k][0])
    best_name = candidates[best_key][1]
    print(f"\n    => '{best_name}' is the strongest predictor of pass@1")


def main():
    print("=" * 55)
    print("  Difficulty Metric Validation")
    print("=" * 55)

    # Step 1
    print("\n[1] Loading dataset and computing scores...")
    df = load_dataset()
    print(f"    {len(df)} tasks loaded")
    print(f"    Difficulty distribution: " + ", ".join(
        f"{DIFFICULTY_LABELS[d]}={sum(df['difficulty'] == d)}"
        for d in [1, 2, 3]
    ))

    # Step 2
    print("\n[2] Construct validity -- Spearman rho (composite vs Radon A-F)")
    rho, p, strength = spearman_analysis(df)
    print(f"    Spearman rho = {rho:.3f}   p = {p:.4f}")
    print(f"    Interpretation: {strength} correlation with Radon's established rating")
    plot_correlation(df, rho, p)

    # Step 3
    print("\n[3] Loading evaluation results...")
    df_evals = load_eval_results(df)
    if df_evals.empty:
        print("    ERROR: No evaluation records found. Check RESULTS_DIR path.")
        sys.exit(1)
    n_files = df_evals[["run", "file"]].drop_duplicates().shape[0]
    print(f"    {len(df_evals):,} records from {n_files} result files")

    # Step 4
    print("\n[4] Predictive validity - pass@1 by difficulty level")
    per_task, H, p_kw = predictive_validity(df_evals)
    for diff in [1, 2, 3]:
        grp = per_task.loc[per_task["difficulty"] == diff, "pass_rate"]
        label = DIFFICULTY_LABELS[diff]
        print(f"    {label:<8} (n={len(grp):2d} tasks): {grp.mean():.3f} +/- {grp.std():.3f}")
    print(f"    Kruskal-Wallis H = {H:.3f},  p = {p_kw:.4f}")
    sig = "significant" if p_kw < 0.05 else "not significant"
    print(f"    => {sig} stratification (alpha = 0.05)")
    plot_predictive(per_task, H, p_kw)

    # Step 5
    print("\n[5] Composite vs. Radon: which better predicts pass@1?")
    compare_predictors(df, per_task)

    print("\nDone. Figures saved to step4_evaluation/figures/")


if __name__ == "__main__":
    main()
