"""
validate_difficulty_metric.py

Validates that McCabe cyclomatic complexity (CC) tiers predict actual SLM behaviour
on the real-world dataset.

Test: Kruskal-Wallis test on mean pass@1 across Easy (CC 1-5) / Medium (6-10) / Hard (>10)
      groups, showing the CC-based stratification predicts model pass rates.

Usage:
    python step4_evaluation/validate_difficulty_metric.py
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from radon.complexity import cc_visit
from scipy import stats


# Paths
REPO_ROOT    = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "TestEval" / "data" / "realworld-py.jsonl"
RESULTS_DIR  = REPO_ROOT / "evaluation_results_realworld_10"
FIGURES_DIR  = Path(__file__).resolve().parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

DIFFICULTY_LABELS = {1: "Easy", 2: "Medium", 3: "Hard"}
DIFFICULTY_COLORS = {1: "#2ecc71", 2: "#f39c12", 3: "#e74c3c"}


def compute_max_cc(source_code: str):
    """Returns max cyclomatic complexity over all blocks, or None on failure."""
    try:
        cc_results = cc_visit(source_code)
        if not cc_results:
            return None
        return max(c.complexity for c in cc_results)
    except Exception as e:
        print(f"  Warning: CC analysis failed - {e}", file=sys.stderr)
        return None


# Step 1: Load dataset and compute CC values
def load_dataset() -> pd.DataFrame:
    records = []
    with open(DATASET_PATH) as f:
        for line in f:
            task = json.loads(line)
            max_cc = compute_max_cc(task["python_solution"])
            if max_cc is None:
                continue
            records.append({
                "task_num":   str(task["task_num"]),
                "func_name":  task["func_name"],
                "difficulty": task["difficulty"],
                "max_cc":     max_cc,
            })
    return pd.DataFrame(records)


# Step 2: CC distribution per difficulty tier
def plot_cc_distribution(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7, 5))
    rng = np.random.default_rng(42)

    for diff in [1, 2, 3]:
        grp = df.loc[df["difficulty"] == diff, "max_cc"].values
        jitter = rng.uniform(-0.15, 0.15, len(grp))
        ax.scatter(
            diff + jitter, grp,
            c=DIFFICULTY_COLORS[diff], label=DIFFICULTY_LABELS[diff],
            alpha=0.6, edgecolors="k", linewidths=0.4, s=50,
        )

    ax.axhline(5,  color="grey", linestyle="--", linewidth=0.8, label="Easy/Medium boundary (CC=5)")
    ax.axhline(10, color="grey", linestyle=":",  linewidth=0.8, label="Medium/Hard boundary (CC=10)")
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Easy\n(CC 1-5)", "Medium\n(CC 6-10)", "Hard\n(CC >10)"])
    ax.set_ylabel("Max Cyclomatic Complexity", fontsize=12)
    ax.set_title("CC Distribution by Difficulty Tier (McCabe thresholds)", fontsize=12)
    ax.legend(fontsize=9, framealpha=0.9)
    plt.tight_layout()

    out = FIGURES_DIR / "difficulty_cc_distribution.png"
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


# Step 5: Spearman rho — CC vs pass@1 (continuous predictor check)
def cc_vs_pass_rate(df_dataset: pd.DataFrame, per_task: pd.DataFrame):
    merged = df_dataset.merge(per_task[["task_num", "pass_rate"]], on="task_num")
    rho, p = stats.spearmanr(merged["max_cc"], merged["pass_rate"])
    print(f"    Spearman rho (max_cc vs pass@1): {rho:+.3f}  (p={p:.4f})")
    direction = "negative" if rho < 0 else "positive"
    print(f"    => {direction} relationship (higher CC = {'harder' if rho < 0 else 'easier'} for SLMs)")


def main():
    print("=" * 55)
    print("  Difficulty Metric Validation (McCabe CC)")
    print("=" * 55)

    # Step 1
    print("\n[1] Loading dataset and computing CC values...")
    df = load_dataset()
    print(f"    {len(df)} tasks loaded")
    print(f"    Difficulty distribution: " + ", ".join(
        f"{DIFFICULTY_LABELS[d]}={sum(df['difficulty'] == d)}"
        for d in [1, 2, 3]
    ))
    print(f"    CC range: {df['max_cc'].min()} - {df['max_cc'].max()}  "
          f"(median {df['max_cc'].median():.1f})")

    # Step 2
    print("\n[2] CC distribution per tier...")
    plot_cc_distribution(df)

    # Step 3
    print("\n[3] Loading evaluation results...")
    df_evals = load_eval_results(df)
    if df_evals.empty:
        print("    ERROR: No evaluation records found. Check RESULTS_DIR path.")
        sys.exit(1)
    n_files = df_evals[["run", "file"]].drop_duplicates().shape[0]
    print(f"    {len(df_evals):,} records from {n_files} result files")

    # Step 4
    print("\n[4] Predictive validity — pass@1 by difficulty tier (Kruskal-Wallis)")
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
    print("\n[5] Continuous CC vs pass@1 (Spearman)")
    cc_vs_pass_rate(df, per_task)

    print("\nDone. Figures saved to step4_evaluation/figures/")


if __name__ == "__main__":
    main()
