"""
Create Failure Root-Cause Heatmaps

Reads the manually-annotated failure analysis CSVs and produces heatmaps
showing root_cause_category × model for:
  - TestEval Initial (N=1, T=0.2, 50 samples)
  - Real-World Dataset (N=1, all failures)

Each dataset gets two PNG files:
  - failure_heatmap_counts.png  — raw counts per cell
  - failure_heatmap_pct.png     — column-normalised (% of each model's failures)

Outputs saved to:
  step4_evaluation/initial_1_plots/failure_heatmap_counts.png
  step4_evaluation/initial_1_plots/failure_heatmap_pct.png
  step4_evaluation/realworld_1_plots/failure_heatmap_counts.png
  step4_evaluation/realworld_1_plots/failure_heatmap_pct.png

Usage:
    python step4_evaluation/create_failure_heatmaps.py
"""

import csv
from pathlib import Path
from collections import defaultdict, Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns


ROOT_CAUSE_SYNONYMS = {
    "HallucinatedAPI": "APIHallucination",
    "error": "Unknown",
    "N/A": "Unknown",
}

# Short display names for models (preserves order on axis)
MODEL_SHORT = {
    "granite-4.0-micro": "Granite-4B",
    "Qwen3-4B-Instruct": "Qwen3-4B",
    "Qwen3-4B-Instruct-2507": "Qwen3-4B",
    "Qwen3-4B-Thinking-2507": "Qwen3-4B-Think",
    "Qwen3-8B-AWQ": "Qwen3-8B (4bit)",
    "Meta-Llama-3.1-8B-Instruct-AWQ-INT4": "Llama3.1-8B (4bit)",
    "Llama-3.2-3B-Instruct": "Llama3.2-3B",
    "Ministral-3-3B-Instruct-2512": "Ministral-3B-Inst",
    "Ministral-3-3B-Reasoning-2512": "Ministral-3B-Reas",
    "Ministral-3-8B-Instruct-2512-AWQ-4bit": "Ministral-8B (4bit)",
    "Ministral-3-8B-Instruct-2512-AWQ-8bit": "Ministral-8B (8bit)",
    "gemma-3-4b-it": "Gemma-3-4B",
    "pynguin_results": "Pynguin",
}

# Preferred model display order — approach-labelled variants first, then bare names
# for any CSV that does not have a config column (backward compat).
MODEL_ORDER = [
    "Granite-4B (1S)", "Granite-4B (2S-CoT)",
    "Qwen3-4B (1S)", "Qwen3-4B (2S-CoT)",
    "Qwen3-4B-Think (1S)", "Qwen3-4B-Think (2S-CoT)",
    "Qwen3-8B (4bit) (1S)", "Qwen3-8B (4bit) (2S-CoT)",
    "Llama3.2-3B (1S)", "Llama3.2-3B (2S-CoT)",
    "Llama3.1-8B (4bit) (1S)", "Llama3.1-8B (4bit) (2S-CoT)",
    "Ministral-3B-Inst (1S)", "Ministral-3B-Inst (2S-CoT)",
    "Ministral-3B-Reas (1S)", "Ministral-3B-Reas (2S-CoT)",
    "Ministral-8B (4bit) (1S)", "Ministral-8B (4bit) (2S-CoT)",
    "Ministral-8B (8bit) (1S)", "Ministral-8B (8bit) (2S-CoT)",
    "Gemma-3-4B (1S)", "Gemma-3-4B (2S-CoT)",
    "Pynguin (1S)", "Pynguin (2S-CoT)", "Pynguin",
]

# Preferred root-cause display order (roughly: logical → structural → env)
CAUSE_ORDER = [
    "IncorrectAssertion",
    "SemanticMisunderstanding",
    "MissingDefinition",
    "MissingImport",
    "APIHallucination",
    "HallucinatedPath",
    "MockingError",
    "MalformedSyntax",
    "EnvironmentMismatch",
    "Runtime",
    "ModelFailure",
    "Unknown",
]

# Display labels with line breaks to prevent x-axis overlap
CAUSE_DISPLAY = {
    "IncorrectAssertion":      "Incorrect\nAssertion",
    "SemanticMisunderstanding":"Semantic\nMisunderstand\ning",
    "MissingDefinition":       "Missing\nDefinition",
    "MissingImport":           "Missing\nImport",
    "APIHallucination":        "API\nHallucination",
    "HallucinatedPath":        "Hallucinated\nPath",
    "MockingError":            "Mocking\nError",
    "MalformedSyntax":         "Malformed\nSyntax",
    "EnvironmentMismatch":     "Environment\nMismatch",
    "Runtime":                 "Runtime",
    "ModelFailure":            "Model\nFailure",
    "Unknown":                 "Unknown",
}


def load_csv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_cause = (row.get("root_cause_category") or "").strip()
            cause = ROOT_CAUSE_SYNONYMS.get(raw_cause, raw_cause)
            raw_model = (row.get("model") or "").strip()
            model = MODEL_SHORT.get(raw_model, raw_model)
            # Extract approach from config column ("One-Step, T=0.0" or "Two-Step, T=0.0")
            raw_config = (row.get("config") or "").strip()
            approach_part = raw_config.split(",")[0].strip() if raw_config else ""
            approach_short = "2S-CoT" if approach_part == "Two-Step" else "1S"
            model_label = f"{model} ({approach_short})" if model else ""
            if cause and model_label:
                rows.append({"model": model_label, "root_cause": cause})
    return rows


def build_matrix(rows):
    """Return (matrix, causes, models) where matrix[i][j] = count."""
    # Determine present models and causes, applying preferred ordering
    present_models = {r["model"] for r in rows}
    present_causes = {r["root_cause"] for r in rows}

    models = [m for m in MODEL_ORDER if m in present_models]
    # Any model not in MODEL_ORDER appended at end
    models += sorted(present_models - set(models))

    causes = [c for c in CAUSE_ORDER if c in present_causes]
    causes += sorted(present_causes - set(causes))

    # Count
    counts = defaultdict(Counter)
    for r in rows:
        counts[r["root_cause"]][r["model"]] += 1

    matrix = np.zeros((len(causes), len(models)), dtype=float)
    for i, cause in enumerate(causes):
        for j, model in enumerate(models):
            matrix[i, j] = counts[cause][model]

    return matrix, causes, models


def _save_heatmap(matrix, causes, models, title, out_path,
                  normalise=False, fmt_int=True):
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

    # Transpose: models on rows (Y), causes on columns (X)
    if normalise:
        col_sums = matrix.sum(axis=0, keepdims=True)
        col_sums[col_sums == 0] = 1  # avoid divide-by-zero
        plot_data = (100.0 * matrix / col_sums).T
        cbar_label = "% of model's failures"
        fmt = ".1f"
        vmax = 100.0
    else:
        plot_data = matrix.T
        cbar_label = "Count"
        fmt = ".0f"
        vmax = None

    cause_labels = [CAUSE_DISPLAY.get(c, c) for c in causes]

    # Dynamic figure size: wider for more causes, taller for more models
    fig_w = max(6, 0.9 * len(causes) + 1.5)
    fig_h = max(4, 0.65 * len(models) + 1.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    mask = (plot_data == 0)

    sns.heatmap(
        plot_data,
        ax=ax,
        annot=True,
        fmt=fmt,
        mask=mask,
        cmap="YlOrRd",
        linewidths=0.4,
        linecolor="white",
        vmin=0,
        vmax=vmax,
        cbar_kws={"label": cbar_label, "shrink": 0.8},
        xticklabels=cause_labels,
        yticklabels=models,
        annot_kws={"size": 9},
    )

    # Zero cells shown as blank with very light fill
    sns.heatmap(
        plot_data,
        ax=ax,
        annot=False,
        mask=~mask,
        cmap=["#f7f7f7"],
        linewidths=0.4,
        linecolor="white",
        cbar=False,
        xticklabels=cause_labels,
        yticklabels=models,
    )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Root Cause Category", fontsize=10)
    ax.set_ylabel("Model (Prompting Approach)", fontsize=10)
    ax.tick_params(axis="x", rotation=30, labelsize=9)
    ax.tick_params(axis="y", rotation=0, labelsize=10)
    plt.setp(ax.get_yticklabels(), fontweight='bold')

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def make_heatmaps(csv_path, out_dir, dataset_label):
    rows = load_csv(csv_path)
    if not rows:
        print(f"WARNING: No annotated rows found in {csv_path}")
        return

    matrix, causes, models = build_matrix(rows)
    out_dir = Path(out_dir)

    _save_heatmap(
        matrix, causes, models,
        title="Manual Failure Analysis",
        out_path=out_dir / "failure_heatmap_counts.png",
        normalise=False,
    )

    _save_heatmap(
        matrix, causes, models,
        title="Manual Failure Analysis",
        out_path=out_dir / "failure_heatmap_pct.png",
        normalise=True,
    )


def main():
    base = Path(__file__).parent
    err_dir = base / "error_analysis_output"

    datasets = [
        {
            "csv": err_dir / "initial_1_failure_analysis.csv",
            "out_dir": base / "initial_1_plots",
            "label": "TestEval Initial (N=1, T=0.2)",
        },
        {
            "csv": err_dir / "realworld_1_failure_analysis.csv",
            "out_dir": base / "realworld_1_plots",
            "label": "Real-World (N=1)",
        },
    ]

    for ds in datasets:
        if not ds["csv"].exists():
            print(f"WARNING: CSV not found: {ds['csv']}")
            continue
        print(f"\nProcessing: {ds['label']}")
        make_heatmaps(ds["csv"], ds["out_dir"], ds["label"])


if __name__ == "__main__":
    main()
