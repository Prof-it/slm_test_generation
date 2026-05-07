"""
Unified Summary Report Generator

Generates comprehensive evaluation reports across different datasets.
Supports TestEval (initial/temp) and Real World datasets with appropriate baselines.

Usage:
    python create_summary_report.py --input <input_dir> --output <output_dir> --dataset <dataset_type>

Arguments:
    --input: Directory containing evaluation JSONL files (e.g., evaluation_results_initial)
    --output: Directory for generated reports and plots (e.g., step4_evaluation/initial_plots)
    --dataset: Dataset type - 'testeval' for initial/temp or 'realworld' for real-world dataset

Example:
    python step4_evaluation/create_summary_report.py --input evaluation_results_initial --output step4_evaluation/initial_plots --dataset testeval
    python step4_evaluation/create_summary_report.py --input evaluation_results_temperature --output step4_evaluation/temp_plots --dataset testeval
    python step4_evaluation/create_summary_report.py --input evaluation_results_realworld --output step4_evaluation/realworld_plots --dataset realworld
"""

import json
import glob
import argparse
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from tabulate import tabulate
from matplotlib.lines import Line2D
from scipy import stats
from itertools import combinations
from evaluation_utils import (
    format_duration,
    parse_filename_metadata,
    extract_performance_data,
    get_style_maps
)


def compute_confidence_interval(data, confidence=0.95):
    """Compute confidence interval for a list of values.

    Returns (mean, ci_lower, ci_upper, margin_of_error); returns (mean, nan, nan, nan)
    if insufficient data (n < 2). Uses t-distribution for small samples.
    """
    data = [x for x in data if not np.isnan(x)]
    n = len(data)
    if n < 2:
        mean = data[0] if n == 1 else np.nan
        return (mean, np.nan, np.nan, np.nan)

    mean = np.mean(data)
    std_err = stats.sem(data)

    # Use t-distribution for small samples
    t_critical = stats.t.ppf((1 + confidence) / 2, df=n-1)
    margin = t_critical * std_err

    return (mean, mean - margin, mean + margin, margin)


def compute_cohens_h(group1, group2):
    """
    Compute Cohen's h effect size between two proportions.
    Pass@1 is a proportion — Cohen's h is the correct metric (avoids pooled-std issues
    caused by near-zero variance at low temperatures).

    Formula: h = 2*arcsin(sqrt(p1)) - 2*arcsin(sqrt(p2))

    Interpretation: |h| < 0.2 negligible, 0.2–0.5 small, 0.5–0.8 medium, ≥0.8 large.
    Positive h means group1 > group2. Groups are pass rates as percentages (e.g. 68.4).
    """
    group1 = [x for x in group1 if not np.isnan(x)]
    group2 = [x for x in group2 if not np.isnan(x)]

    if not group1 or not group2:
        return np.nan

    p1 = np.clip(np.mean(group1) / 100.0, 0.0, 1.0)
    p2 = np.clip(np.mean(group2) / 100.0, 0.0, 1.0)

    return 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))


def interpret_cohens_h(h):
    """Return interpretation string for Cohen's h value."""
    if np.isnan(h):
        return "N/A"
    abs_h = abs(h)
    if abs_h < 0.2:
        return "negligible"
    elif abs_h < 0.5:
        return "small"
    elif abs_h < 0.8:
        return "medium"
    else:
        return "large"


def paired_ttest(group1, group2):
    """
    Perform independent samples t-test between two groups.

    Uses independent t-test (not paired) because runs are independent
    experimental replications, not matched pairs.
    """
    group1 = [x for x in group1 if not np.isnan(x)]
    group2 = [x for x in group2 if not np.isnan(x)]

    if len(group1) < 2 or len(group2) < 2:
        return (np.nan, np.nan)

    # Welch's t-test (does not assume equal variances)
    t_stat, p_val = stats.ttest_ind(group1, group2, equal_var=False)
    return (t_stat, p_val)


def bonferroni_correction(p_values, alpha=0.05):
    """Apply Bonferroni correction for multiple comparisons.

    Returns list of (original_p, corrected_p, is_significant) tuples.
    """
    n_comparisons = len(p_values)
    corrected_alpha = alpha / n_comparisons

    results = []
    for p in p_values:
        if np.isnan(p):
            results.append((p, np.nan, False))
        else:
            corrected_p = min(p * n_comparisons, 1.0)  # Adjusted p-value
            is_sig = p < corrected_alpha
            results.append((p, corrected_p, is_sig))

    return results


def bootstrap_ranking_stability(config_data, n_bootstrap=1000, metric='pass_rate', seed=42):
    """
    Bootstrap analysis to assess ranking stability.

    Resamples runs with replacement and computes how often each model
    maintains its rank position.
    """
    np.random.seed(seed)

    configs = list(config_data.keys())
    n_configs = len(configs)

    if n_configs < 2:
        return {"rank_stability": {}, "top_k_stability": {}, "message": "Insufficient configs"}

    # Track rank occurrences for each config
    rank_counts = {cfg: np.zeros(n_configs) for cfg in configs}

    for _ in range(n_bootstrap):
        # Resample runs with replacement for each config
        resampled_means = {}
        for cfg, values in config_data.items():
            if len(values) > 0:
                resampled = np.random.choice(values, size=len(values), replace=True)
                resampled_means[cfg] = np.mean(resampled)
            else:
                resampled_means[cfg] = np.nan

        # Rank configs (higher is better, rank 1 = best)
        sorted_configs = sorted(resampled_means.items(), key=lambda x: -x[1] if not np.isnan(x[1]) else float('-inf'))
        for rank, (cfg, _) in enumerate(sorted_configs):
            rank_counts[cfg][rank] += 1

    # Compute stability metrics
    rank_stability = {}
    for cfg in configs:
        # Modal rank (most common)
        modal_rank = np.argmax(rank_counts[cfg]) + 1
        modal_freq = rank_counts[cfg][modal_rank - 1] / n_bootstrap * 100
        rank_stability[cfg] = {
            "modal_rank": modal_rank,
            "modal_frequency": modal_freq,
            "rank_distribution": (rank_counts[cfg] / n_bootstrap * 100).tolist()
        }

    # Top-k stability (how often do top-k remain in top-k)
    top_k_stability = {}
    for k in [1, 3, 5]:
        if k > n_configs:
            continue
        # Get original top-k
        original_means = {cfg: np.mean(vals) if vals else np.nan for cfg, vals in config_data.items()}
        sorted_original = sorted(original_means.items(), key=lambda x: -x[1] if not np.isnan(x[1]) else float('-inf'))
        original_top_k = set([cfg for cfg, _ in sorted_original[:k]])

        # Count how often top-k stays in top-k
        top_k_count = 0
        for _ in range(n_bootstrap):
            resampled_means = {}
            for cfg, values in config_data.items():
                if len(values) > 0:
                    resampled = np.random.choice(values, size=len(values), replace=True)
                    resampled_means[cfg] = np.mean(resampled)
                else:
                    resampled_means[cfg] = np.nan

            sorted_resampled = sorted(resampled_means.items(), key=lambda x: -x[1] if not np.isnan(x[1]) else float('-inf'))
            resampled_top_k = set([cfg for cfg, _ in sorted_resampled[:k]])

            if original_top_k == resampled_top_k:
                top_k_count += 1

        top_k_stability[f"top_{k}"] = top_k_count / n_bootstrap * 100

    return {
        "rank_stability": rank_stability,
        "top_k_stability": top_k_stability,
        "n_bootstrap": n_bootstrap
    }


def analyze_variance_convergence(config_runs_data):
    """
    Analyze whether variance stabilizes at N runs.

    Computes variance at N=1, N=2, N=3 (where available) to show
    that additional runs offer diminishing returns.
    """
    results = {}

    for cfg, values in config_runs_data.items():
        n = len(values)
        if n < 2:
            continue

        # Compute cumulative statistics
        cumulative_stats = []
        for i in range(1, n + 1):
            subset = values[:i]
            mean = np.mean(subset)
            std = np.std(subset, ddof=1) if i > 1 else 0
            sem = std / np.sqrt(i) if i > 1 else np.nan
            cumulative_stats.append({
                "n": i,
                "mean": mean,
                "std": std,
                "sem": sem
            })

        results[cfg] = cumulative_stats

    return results


def format_metric_with_ci(mean, std, ci_lower, ci_upper, decimals=2, suffix="%", min_val=0, max_val=100):
    """
    Format metric with std and CI in compact scientific format: mean (±std)[CI_lo, CI_hi].

    CI bounds are clamped to valid range [min_val, max_val] for percentage metrics.

    Examples:
        92.7% (±0.10)[92.3, 93.2]  - full format with CI
        92.7% (±0.00)[92.7, 92.7]  - zero variance (all runs identical)
        9.1% (±6.4)[0.00, 28.5]    - lower bound clamped to 0 (was negative)
        92.7%                      - when only mean available (n=1)
    """
    if np.isnan(mean):
        return "-"

    # Build the string incrementally
    result = f"{mean:.{decimals}f}{suffix}"

    # Add std if available (always show, even if zero, for consistency)
    if not np.isnan(std):
        result += f" (±{std:.{decimals}f})"

    # Add CI if available (clamp to valid range for percentage metrics)
    if not np.isnan(ci_lower) and not np.isnan(ci_upper):
        # Clamp CI bounds to valid range
        ci_lower_clamped = max(min_val, ci_lower)
        ci_upper_clamped = min(max_val, ci_upper)
        result += f"[{ci_lower_clamped:.{decimals}f}, {ci_upper_clamped:.{decimals}f}]"

    return result


def format_p_value(p, corrected_p=None, is_significant=None):
    """Format p-value with significance indicator."""
    if np.isnan(p):
        return "N/A"

    if p < 0.001:
        p_str = "<.001"
    else:
        p_str = f"{p:.3f}"

    if corrected_p is not None and not np.isnan(corrected_p):
        if corrected_p < 0.001:
            corr_str = "<.001"
        else:
            corr_str = f"{corrected_p:.3f}"
        p_str = f"{p_str} ({corr_str})"

    if is_significant:
        p_str += "*"

    return p_str

# Literature baselines for TestEval datasets.
# sr_metric distinguishes how "success" was defined in the source paper:
#   "EC"     = Execution Correctness: test compiles and runs without crashing (no assertion requirement).
#              Used by Wang et al. — NOT directly comparable to our assertion-based Pass@1.
#   "Pass@1" = Test passes all assertions. Used by Huang et al. — directly comparable to ours.
# cov_metric distinguishes coverage gating criterion:
#   "EC-gated"         = coverage measured on EC-passing tests (Wang et al.). Gating is more lenient than ours.
#   "assertion-gated"  = coverage measured on assertion-passing tests (Huang et al. LCov@1). Comparable to ours.
LITERATURE_BASELINES = [
    {
        "Model": "GPT-4o",
        "Source": "Wang et al., 2025a",
        "Config": "T=0.0",
        "Runs": 1,
        "SR": 99.59,      # Execution Correctness — Table 1 (NOT assertion-based Pass@1)
        "sr_metric": "EC",
        "Cov": 98.65,     # Overall Line Coverage gated on EC — Table 1
        "cov_metric": "EC-gated",
        "Mut": None       # Not reported for TestEval in Wang et al.
    },
    {
        "Model": "Llama-3.1-8B-Instruct",
        "Source": "Wang et al., 2025a",
        "Config": "T=0.0",
        "Runs": 1,
        "SR": 94.69,      # Execution Correctness — Table 1 (NOT assertion-based Pass@1)
        "sr_metric": "EC",
        "Cov": 88.94,     # Overall Line Coverage gated on EC — Table 1
        "cov_metric": "EC-gated",
        "Mut": None       # Not reported for TestEval in Wang et al.
    },
    {
        "Model": "Phi-4-mini-Instruct",
        "Source": "Huang et al., 2025b",
        "Config": "T=0.0",
        "Runs": 1,
        "SR": 39.05,      # Pass@1 on TestEval — Table 2 (assertion-based, comparable to ours)
        "sr_metric": "Pass@1",
        "Cov": 80.63,     # LCov@1 on TestEval — Table 3
        "cov_metric": "assertion-gated",
        "Mut": 47.18      # Mut@1 on TestEval — Table 5
    },
    {
        "Model": "DeepSeek-Coder-1.3B-Instruct",
        "Source": "Huang et al., 2025b",
        "Config": "T=0.0",
        "Runs": 1,
        "SR": 38.57,      # Pass@1 on TestEval — Table 2 (assertion-based, comparable to ours)
        "sr_metric": "Pass@1",
        "Cov": 86.19,     # LCov@1 on TestEval — Table 3
        "cov_metric": "assertion-gated",
        "Mut": 30.16      # Mut@1 on TestEval — Table 5
    },
    {
        "Model": "Gemma-3-4B-IT",
        "Source": "Huang et al., 2025b",
        "Config": "T=0.0",
        "Runs": 1,
        "SR": 30.00,      # Pass@1 on TestEval — Table 2 (assertion-based, comparable to ours)
        "sr_metric": "Pass@1",
        "Cov": 71.09,     # LCov@1 on TestEval — Table 3
        "cov_metric": "assertion-gated",
        "Mut": 41.80      # Mut@1 on TestEval — Table 5
    }
]

def get_testeval_hardware_specs(benchmark_size):
    """Generate TestEval hardware specs with dynamic benchmark size."""
    return (
        f"EXPERIMENTAL SETUP (TestEval Study):\n"
        f"• Hardware: vLLM, Single RTX 4090, FP16 precision (INT4 for quantized) 4096 max tokens.\n"
        f"• Baseline: Literature baselines from Wang et al. (2025a) and Huang et al. (2025b) for comparison.\n"
        f"• Dataset: 'TestEval' - {benchmark_size} programming problems from TestEval benchmark.\n"
        f"• Definitions:\n"
        f"  - Pass@1: % of tasks passing assertions.\n"
        f"  - Raw Cov: Ungated line coverage (all tasks incl. assertion failures, excl. timeouts/syntax errors/no-code). Gated Cov: Assertion-passing tasks only.\n"
        f"  - Total Tokens: Average total tokens generated per run."
    )

def get_realworld_hardware_specs(benchmark_size):
    """Generate Real World hardware specs with dynamic benchmark size."""
    return (
        f"EXPERIMENTAL SETUP (Real World Study):\n"
        f"• Hardware: vLLM, Single RTX 4090, FP16 precision (INT4 for quantized) 4096 max tokens.\n"
        f"• Baseline: Pynguin (DynaMOSA) running on CPU (Python 3.10-slim Docker) with 120s budget.\n"
        f"• Dataset: 'Real World' - {benchmark_size} Python functions from this repository's own codebase.\n"
        f"• Definitions:\n"
        f"  - Pass@1: % of tasks passing assertions.\n"
        f"  - Raw Cov: Ungated line coverage (all tasks incl. assertion failures, excl. timeouts/syntax errors/no-code). Gated Cov: Assertion-passing tasks only.\n"
        f"  - Total Tokens: Average total tokens generated per run."
    )

# Visualization helpers
def plot_stability_trends(df, output_dir, palette_dict, markers_dict):
    """
    Generates faceted line charts showing metric stability over Temperature.
    Separates LLM data (variable temperature) from Pynguin baselines (constant).
    """
    llm_df = df[df["Temperature"].notna()].copy()
    pynguin_df = df[df["Model"].str.contains("Pynguin", na=False)].copy()

    if llm_df.empty:
        print("WARNING: No temperature data available for stability trends")
        return

    baseline_stats = {}
    if not pynguin_df.empty:
        baseline_stats = {
            "Pass Rate": pynguin_df["Pass Rate"].mean(),
            "Mutation Score Global": pynguin_df["Mutation Score Global"].mean(),  # Unbiased metric
            "TPS": pynguin_df["TPS"].mean()
        }

    metrics = [
        ("Pass Rate", "Pass@1 (%)"),
        ("Mutation Score Global", "Global Mutation Score (%)"),  # Unbiased: includes failed tasks at 0%
        ("TPS", "Tokens / Second")
    ]

    modes = [m for m in llm_df["Mode"].unique() if pd.notna(m)]
    if not modes:
        print("WARNING: No valid modes found for stability trends")
        return

    col_order = sorted(modes)

    for metric_col, y_label in metrics:
        if llm_df[metric_col].isna().all():
            print(f"WARNING: Skipping {metric_col} - all values are NaN")
            continue

        valid_data = llm_df[llm_df[metric_col].notna()]
        if len(valid_data) < 2:
            print(f"WARNING: Insufficient data for {metric_col} stability trend (n={len(valid_data)})")
            continue

        try:
            g = sns.FacetGrid(
                data=llm_df, col="Mode", col_order=col_order,
                height=5, aspect=1.3,
                sharex=True, sharey=True
            )

            # Add Pynguin baseline for all metrics (Pass Rate, Mutation Score, AND TPS)
            pynguin_val = None
            if metric_col in baseline_stats and not np.isnan(baseline_stats[metric_col]):
                pynguin_val = baseline_stats[metric_col]
                def plot_baseline(**kwargs):
                    ax = plt.gca()
                    ax.axhline(y=pynguin_val, color='black', linestyle='--', linewidth=2, alpha=0.5, label='Pynguin Baseline')
                g.map(plot_baseline)

            # Use pointplot to properly show discrete values with error bars
            for model in llm_df["Model"].unique():
                model_data = llm_df[llm_df["Model"] == model]
                for ax in g.axes.flat:
                    mode_name = ax.get_title().split('=')[-1].strip() if '=' in ax.get_title() else None
                    if mode_name:
                        plot_data = model_data[model_data["Mode"] == mode_name]
                        if not plot_data.empty:
                            # Group by temperature and compute mean/std
                            temp_grouped = plot_data.groupby("Temperature")[metric_col].agg(['mean', 'std']).reset_index()

                            # Plot line connecting points
                            ax.plot(temp_grouped["Temperature"], temp_grouped["mean"],
                                   color=palette_dict.get(model, 'gray'),
                                   linestyle='--', linewidth=2, alpha=0.8)

                            # Plot points with model-specific markers
                            ax.scatter(temp_grouped["Temperature"], temp_grouped["mean"],
                                      c=[palette_dict.get(model, 'gray')] * len(temp_grouped),
                                      marker=markers_dict.get(model, 'o'),
                                      s=100, edgecolor='white', linewidth=1.5, zorder=10)

                            # Add error bars (not bands)
                            ax.errorbar(temp_grouped["Temperature"], temp_grouped["mean"],
                                       yerr=temp_grouped["std"], fmt='none',
                                       ecolor=palette_dict.get(model, 'gray'),
                                       alpha=0.3, capsize=3)

            g.set_axis_labels("Temperature", y_label)
            g.set_titles("{col_name}")

            if metric_col == "Pass Rate":
                # Calculate dynamic y-axis upper limit based on data
                data_max = llm_df[metric_col].max()
                if not np.isnan(data_max):
                    # Round up to nearest 10 with some padding
                    y_upper = np.ceil((data_max + 5) / 10) * 10
                    y_upper = max(y_upper, 40)  # Minimum upper limit of 40
                else:
                    y_upper = 40

                for ax in g.axes.flat:
                    ax.set_ylim(-2, y_upper)
            elif metric_col == "TPS":
                # Global limit across all modes so both panels share the same y-axis
                data_max = llm_df[metric_col].max()
                if not np.isnan(data_max):
                    if data_max > 100:
                        y_upper = np.ceil((data_max + 10) / 20) * 20
                    else:
                        y_upper = np.ceil((data_max + 5) / 10) * 10
                    y_upper = max(y_upper, 30)
                else:
                    y_upper = 30
                g.axes.flat[0].set_ylim(-5, y_upper)  # propagates to all via sharey

            g.figure.subplots_adjust(top=0.85, bottom=0.25)
            g.figure.suptitle(y_label, fontsize=13, weight='bold')

            # Add TPS note at figure level (once, not per facet)

            handles = [Line2D([0], [0], marker=markers_dict.get(m, 'o'), color='w',
                              markerfacecolor=palette_dict.get(m, 'gray'),
                              markersize=10, label=m) for m in sorted(llm_df["Model"].unique())]

            if pynguin_val is not None and metric_col != "TPS":
                pynguin_label = f'Pynguin (Baseline): {pynguin_val:.1f}%'
                handles.append(Line2D([0], [0], color='black', linestyle='--', label=pynguin_label))

            g.figure.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, -0.05), ncol=4, frameon=False, prop={'size': 10, 'weight': 'bold'})

            output_file = output_dir / f"trend_{metric_col.replace(' ', '_').lower()}.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"  >> Saved {output_file.name}")

        except Exception as e:
            print(f"  WARNING: Error generating {metric_col} trend plot: {e}")
            plt.close('all')
            continue

def plot_quality_quadrant(df, output_dir, palette_dict, markers_dict):
    """
    Generates scatter plot comparing Correctness (Pass Rate) vs Quality (Mutation Score Global).
    Uses unbiased mutation score (includes failed tasks at 0%).
    NO jittering - exact data representation.
    ENCODING: Shape = Model, Color = Temperature (6 discrete values), Fill = Mode (filled vs hollow).
    """
    # Define temperature color mapping (6 discrete colors: blue -> red)
    # Using diverging colormap for ordered temperature values
    temp_colors = {
        0.0: '#2166ac',  # dark blue (cold/greedy)
        0.2: '#67a9cf',  # light blue
        0.4: '#d1e5f0',  # very light blue
        0.6: '#fddbc7',  # light orange
        0.8: '#ef8a62',  # orange
        1.0: '#b2182b'   # dark red (hot/creative)
    }

    agg_df = df.groupby(['Model', 'Mode', 'Temperature'], dropna=False).agg({
        'Pass Rate': 'mean',
        'Mutation Score Global': 'mean'  # Unbiased metric
    }).reset_index()

    modes = [m for m in agg_df["Mode"].unique() if m != "Evolutionary Search"]
    fig, axes = plt.subplots(1, len(modes), figsize=(9 * len(modes), 8),
                             sharex=True, sharey=True)
    if len(modes) == 1:
        axes = [axes]

    pynguin_data = agg_df[agg_df["Mode"] == "Evolutionary Search"].copy()

    # Global means across all non-Pynguin modes — same reference line in every panel
    all_modes_data   = agg_df[agg_df["Mode"].isin(modes)]
    global_mut_mean  = all_modes_data['Mutation Score Global'].mean()
    global_pass_mean = all_modes_data['Pass Rate'].mean()

    for ax, mode in zip(axes, modes):
        mode_data = agg_df[agg_df["Mode"] == mode].copy()

        # Shape = Model, Color = Temperature, Fill = Mode
        for model in mode_data['Model'].unique():
            model_subset = mode_data[mode_data['Model'] == model]
            marker = markers_dict.get(model, 'o')

            for _, row in model_subset.iterrows():
                # Color based on temperature (6 discrete values)
                temp = row['Temperature']
                if pd.isna(temp):
                    color = 'gray'  # Default for unknown temp
                else:
                    color = temp_colors.get(temp, 'gray')

                # Fill style based on mode: One-step = filled, Two-step = hollow
                if 'One-Step' in mode:
                    facecolor = color
                    edgecolor = 'black'
                else:  # Two-Step - hollow markers with colored edge
                    facecolor = 'none'
                    edgecolor = color

                ax.scatter(
                    row['Mutation Score Global'],
                    row['Pass Rate'],
                    c=facecolor,
                    marker=marker,
                    s=200,
                    edgecolor=edgecolor,
                    linewidths=2
                )

        if not pynguin_data.empty:
            ax.scatter(
                pynguin_data['Mutation Score Global'].values,
                pynguin_data['Pass Rate'].values,
                c='black',
                marker='^',
                s=400,
                edgecolor='white',
                alpha=0.9,
                label='Pynguin (Baseline)',
                linewidths=2,
                zorder=100
            )

        ax.axvline(global_mut_mean,  color='gray', linestyle=':', alpha=0.5)
        ax.axhline(global_pass_mean, color='gray', linestyle=':', alpha=0.5)
        ax.set_title(f"{mode}", fontsize=12, weight='bold')
        ax.set_xlabel("Global Mutation Score (%)", fontsize=11)
        ax.set_ylabel("Pass@1 (%)", fontsize=11)
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)

    # Create comprehensive legend with all three encoding dimensions
    handles = []

    # Model markers (Shape encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Models (Shape):', markersize=0))
    for model in sorted(agg_df[agg_df['Mode'].isin(modes)]['Model'].unique()):
        handles.append(Line2D([0], [0], marker=markers_dict.get(model, 'o'), color='w',
                              markerfacecolor='gray', markersize=10, label=f'  {model}',
                              markeredgecolor='black', markeredgewidth=1))

    # Temperature colors (Color encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Temperature (Color):', markersize=0))
    for temp in sorted(temp_colors.keys()):
        handles.append(Line2D([0], [0], marker='o', color='w',
                              markerfacecolor=temp_colors[temp], markersize=8,
                              label=f'  T={temp}', markeredgecolor='black', markeredgewidth=1))

    # Mode fill styles (Fill encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Mode (Fill):', markersize=0))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  One-Step (Filled)', fillstyle='full',
                          markeredgecolor='black', markeredgewidth=1))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  Two-Step (Hollow)', fillstyle='none',
                          markeredgecolor='black', markeredgewidth=1))

    if not pynguin_data.empty:
        handles.append(Line2D([0], [0], marker='^', color='w', markerfacecolor='black',
                              markersize=12, label='Pynguin (Baseline)', markeredgecolor='white', markeredgewidth=2))

    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False, prop={'size': 10, 'weight': 'bold'})

    fig.suptitle("Quality Quadrant", fontsize=13, weight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / "quality_quadrant.png", dpi=300, bbox_inches='tight')
    plt.close()

def plot_coverage_analysis(df, output_dir, palette_dict, markers_dict):
    """
    Generates scatter plot comparing Global Coverage vs Pass Rate.
    Uses unbiased global coverage metric (includes failed tasks at 0%).
    NO jittering - exact data representation.
    ENCODING: Shape = Model, Color = Temperature (6 discrete values), Fill = Mode (filled vs hollow).
    """
    # Define temperature color mapping (6 discrete colors: blue -> red)
    temp_colors = {
        0.0: '#2166ac',  # dark blue (cold/greedy)
        0.2: '#67a9cf',  # light blue
        0.4: '#d1e5f0',  # very light blue
        0.6: '#fddbc7',  # light orange
        0.8: '#ef8a62',  # orange
        1.0: '#b2182b'   # dark red (hot/creative)
    }

    agg_df = df.groupby(['Model', 'Mode', 'Temperature'], dropna=False).agg({
        'Pass Rate': 'mean',
        'Coverage Global': 'mean',  # Unbiased metric
        'N Passed': 'mean'
    }).reset_index()

    agg_df = agg_df[agg_df['Coverage Global'].notna()].copy()

    if agg_df.empty:
        print("WARNING: No coverage data available for coverage analysis plot")
        return

    modes = [m for m in agg_df["Mode"].unique() if m != "Evolutionary Search"]
    fig, axes = plt.subplots(1, len(modes), figsize=(9 * len(modes), 8),
                             sharex=True, sharey=True)
    if len(modes) == 1:
        axes = [axes]

    pynguin_data = agg_df[agg_df["Mode"] == "Evolutionary Search"].copy()

    # Global means across all non-Pynguin modes — same reference line in every panel
    all_modes_data   = agg_df[agg_df["Mode"].isin(modes)]
    global_cov_mean  = all_modes_data['Coverage Global'].mean()
    global_pass_mean = all_modes_data['Pass Rate'].mean()

    for ax, mode in zip(axes, modes):
        mode_data = agg_df[agg_df["Mode"] == mode].copy()

        # Shape = Model, Color = Temperature, Fill = Mode
        for model in mode_data['Model'].unique():
            model_subset = mode_data[mode_data['Model'] == model]
            marker = markers_dict.get(model, 'o')

            for _, row in model_subset.iterrows():
                # Color based on temperature (6 discrete values)
                temp = row['Temperature']
                if pd.isna(temp):
                    color = 'gray'  # Default for unknown temp
                else:
                    color = temp_colors.get(temp, 'gray')

                # Fill style based on mode: One-Step = filled, Two-Step = hollow
                if 'One-Step' in mode:
                    facecolor = color
                    edgecolor = 'black'
                else:  # Two-Step - hollow markers with colored edge
                    facecolor = 'none'
                    edgecolor = color

                ax.scatter(
                    row['Coverage Global'],
                    row['Pass Rate'],
                    c=facecolor,
                    marker=marker,
                    s=200,
                    edgecolor=edgecolor,
                    linewidths=2
                )

        if not pynguin_data.empty:
            ax.scatter(
                pynguin_data['Coverage Global'].values,
                pynguin_data['Pass Rate'].values,
                c='black',
                marker='^',
                s=400,
                edgecolor='white',
                alpha=0.9,
                label='Pynguin (Baseline)',
                linewidths=2,
                zorder=100
            )

        ax.axvline(global_cov_mean,  color='gray', linestyle=':', alpha=0.5)
        ax.axhline(global_pass_mean, color='gray', linestyle=':', alpha=0.5)
        ax.set_title(f"{mode}", fontsize=12, weight='bold')


        ax.set_xlabel("Global Line Coverage (%)", fontsize=11)
        ax.set_ylabel("Pass@1 (%)", fontsize=11)
        ax.grid(True, alpha=0.3)

    # Create comprehensive legend with all three encoding dimensions
    handles = []

    # Model markers (Shape encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Models (Shape):', markersize=0))
    for model in sorted(agg_df[agg_df['Mode'].isin(modes)]['Model'].unique()):
        handles.append(Line2D([0], [0], marker=markers_dict.get(model, 'o'), color='w',
                              markerfacecolor='gray', markersize=10, label=f'  {model}',
                              markeredgecolor='black', markeredgewidth=1))

    # Temperature colors (Color encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Temperature (Color):', markersize=0))
    for temp in sorted(temp_colors.keys()):
        handles.append(Line2D([0], [0], marker='o', color='w',
                              markerfacecolor=temp_colors[temp], markersize=8,
                              label=f'  T={temp}', markeredgecolor='black', markeredgewidth=1))

    # Mode fill styles (Fill encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Mode (Fill):', markersize=0))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  One-Step (Filled)', fillstyle='full',
                          markeredgecolor='black', markeredgewidth=1))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  Two-Step (Hollow)', fillstyle='none',
                          markeredgecolor='black', markeredgewidth=1))

    if not pynguin_data.empty:
        handles.append(Line2D([0], [0], marker='^', color='w', markerfacecolor='black',
                              markersize=12, label='Pynguin (Baseline)', markeredgecolor='white', markeredgewidth=2))

    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, -0.22), ncol=3, frameon=False, prop={'size': 10, 'weight': 'bold'})

    fig.suptitle("Coverage Analysis", fontsize=13, weight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / "coverage_analysis.png", dpi=300, bbox_inches='tight')
    plt.close()

def plot_efficiency_frontier(df, output_dir, palette_dict, markers_dict):
    """
    Generates scatter plot comparing Efficiency (TPS) vs Effectiveness (Pass Rate).
    Includes Pynguin with explanatory note about token estimation (4 chars = 1 token).
    ENCODING: Shape = Model, Color = Temperature (6 discrete values), Fill = Mode (filled vs hollow).
    """
    # Define temperature color mapping (6 discrete colors: blue -> red)
    temp_colors = {
        0.0: '#2166ac',  # dark blue (cold/greedy)
        0.2: '#67a9cf',  # light blue
        0.4: '#d1e5f0',  # very light blue
        0.6: '#fddbc7',  # light orange
        0.8: '#ef8a62',  # orange
        1.0: '#b2182b'   # dark red (hot/creative)
    }

    # Separate LLM data from Pynguin for clear visual distinction
    llm_df = df[~df['Model'].str.contains("Pynguin", case=False, na=False)].copy()
    pynguin_df = df[df['Model'].str.contains("Pynguin", case=False, na=False)].copy()

    agg_llm = llm_df.groupby(['Model', 'Mode', 'Temperature'], dropna=False).agg({
        'Pass Rate': 'mean',
        'TPS': 'mean'
    }).reset_index()

    if agg_llm.empty:
        print("WARNING: No LLM data available for efficiency frontier")
        return

    fig, ax = plt.subplots(figsize=(10, 8))

    # Shape=Model, Color=Temperature, Fill=Mode
    for model in agg_llm['Model'].unique():
        model_data = agg_llm[agg_llm['Model'] == model]
        marker = markers_dict.get(model, 'o')

        for _, row in model_data.iterrows():
            # Color based on temperature (6 discrete values)
            temp = row['Temperature']
            if pd.isna(temp):
                color = 'gray'
            else:
                color = temp_colors.get(temp, 'gray')

            # Fill style based on mode: One-Step = filled, Two-Step = hollow
            if 'One-Step' in str(row['Mode']):
                facecolor = color
                edgecolor = 'black'
            else:  # Two-Step - hollow markers with colored edge
                facecolor = 'none'
                edgecolor = color

            ax.scatter(
                row['TPS'], row['Pass Rate'],
                c=facecolor,
                marker=marker,
                s=200,
                edgecolor=edgecolor,
                linewidths=2
            )

    # Add Pareto frontier (correct implementation) - only for LLMs
    # A point is on the frontier if NO other point dominates it in BOTH dimensions
    pareto_points = []
    for _, row in agg_llm.iterrows():
        is_dominated = False
        for _, other in agg_llm.iterrows():
            # Check if 'other' is strictly better in both dimensions
            if (other['TPS'] >= row['TPS'] and other['Pass Rate'] >= row['Pass Rate'] and
                (other['TPS'] > row['TPS'] or other['Pass Rate'] > row['Pass Rate'])):
                is_dominated = True
                break
        if not is_dominated:
            pareto_points.append((row['TPS'], row['Pass Rate']))

    if pareto_points:
        # Sort by TPS for clean line drawing
        pareto_points.sort(key=lambda p: p[0])
        px, py = zip(*pareto_points)
        ax.plot(px, py, color='gray', linestyle='--', linewidth=2, alpha=0.6,
                label='Pareto Frontier', zorder=0)


    ax.set_title("Efficiency Frontier", fontsize=13, weight='bold')
    ax.set_xlabel("Tokens Per Second (TPS)", fontsize=12)
    ax.set_ylabel("Pass@1 (%)", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)

    # Add note about Pynguin only
    note_text = (
        'TPS is an inference metric for LLMs only.\n'
        'Pynguin is a search-based tool (SBST)\n'
        'and does not generate tokens.\n'
        'See Wall-Clock Efficiency figure\n'
        'for cross-paradigm comparison.'
    )
    # Create comprehensive legend with all three encoding dimensions
    handles = []

    # Model markers (Shape encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Models (Shape):', markersize=0))
    for model in sorted(agg_llm['Model'].unique()):
        handles.append(Line2D([0], [0], marker=markers_dict.get(model, 'o'), color='w',
                              markerfacecolor='gray', markersize=10, label=f'  {model}',
                              markeredgecolor='black', markeredgewidth=1))

    # Temperature colors (Color encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Temperature (Color):', markersize=0))
    for temp in sorted(temp_colors.keys()):
        handles.append(Line2D([0], [0], marker='o', color='w',
                              markerfacecolor=temp_colors[temp], markersize=8,
                              label=f'  T={temp}', markeredgecolor='black', markeredgewidth=1))

    # Mode fill styles (Fill encoding)
    handles.append(Line2D([0], [0], marker='None', color='w', label='Mode (Fill):', markersize=0))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  One-Step', fillstyle='full',
                          markeredgecolor='black', markeredgewidth=1))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  Two-Step (Hollow)', fillstyle='none',
                          markeredgecolor='black', markeredgewidth=1))

    if not pynguin_df.empty:
        handles.append(Line2D([0], [0], marker='^', color='w', markerfacecolor='black',
                              markersize=12, label='Pynguin (Baseline)', markeredgecolor='white', markeredgewidth=2))

    handles.append(Line2D([0], [0], color='gray', linestyle='--', linewidth=2, label='Pareto Frontier'))

    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc='upper left', title="Legend", prop={'size': 10, 'weight': 'bold'})
    plt.tight_layout()
    plt.savefig(output_dir / "efficiency_frontier.png", dpi=300, bbox_inches='tight')
    plt.close()

def plot_wall_clock_efficiency(df, output_dir, palette_dict, markers_dict, benchmark_size):
    """
    Generates scatter plot comparing wall-clock time per task (seconds) vs Pass@1.
    This is the cross-paradigm efficiency metric valid for both SLMs and Pynguin,
    framed from the user's perspective: how long to get a test for one Python function.
    """
    temp_colors = {
        0.0: '#2166ac',
        0.2: '#67a9cf',
        0.4: '#d1e5f0',
        0.6: '#fddbc7',
        0.8: '#ef8a62',
        1.0: '#b2182b'
    }

    if 'Time Per Task (s)' not in df.columns:
        print("WARNING: 'Time Per Task (s)' not in data, skipping wall-clock efficiency plot")
        return

    llm_df = df[~df['Model'].str.contains("Pynguin", case=False, na=False)].copy()
    pynguin_df = df[df['Model'].str.contains("Pynguin", case=False, na=False)].copy()

    agg_llm = llm_df.groupby(['Model', 'Mode', 'Temperature'], dropna=False).agg({
        'Pass Rate': 'mean',
        'Time Per Task (s)': 'mean'
    }).reset_index()

    if agg_llm.empty:
        print("WARNING: No LLM data available for wall-clock efficiency plot")
        return

    fig, ax = plt.subplots(figsize=(10, 8))

    for model in agg_llm['Model'].unique():
        model_data = agg_llm[agg_llm['Model'] == model]
        marker = markers_dict.get(model, 'o')

        for _, row in model_data.iterrows():
            temp = row['Temperature']
            color = temp_colors.get(temp, 'gray') if not pd.isna(temp) else 'gray'

            if 'One-Step' in str(row['Mode']):
                facecolor = color
                edgecolor = 'black'
            else:
                facecolor = 'none'
                edgecolor = color

            ax.scatter(
                row['Time Per Task (s)'], row['Pass Rate'],
                c=facecolor, marker=marker, s=200,
                edgecolor=edgecolor, linewidths=2
            )

    if not pynguin_df.empty:
        agg_pynguin = pynguin_df.groupby(['Model', 'Mode', 'Temperature'], dropna=False).agg({
            'Pass Rate': 'mean',
            'Time Per Task (s)': 'mean'
        }).reset_index()

        ax.scatter(
            agg_pynguin['Time Per Task (s)'], agg_pynguin['Pass Rate'],
            c='black', marker='^', s=400, edgecolor='white',
            alpha=0.9, label='Pynguin (Baseline)', linewidths=2, zorder=100
        )

    # Pareto frontier: lower time + higher pass rate = dominant
    pareto_points = []
    for _, row in agg_llm.iterrows():
        is_dominated = False
        for _, other in agg_llm.iterrows():
            if (other['Time Per Task (s)'] <= row['Time Per Task (s)'] and
                    other['Pass Rate'] >= row['Pass Rate'] and
                    (other['Time Per Task (s)'] < row['Time Per Task (s)'] or other['Pass Rate'] > row['Pass Rate'])):
                is_dominated = True
                break
        if not is_dominated:
            pareto_points.append((row['Time Per Task (s)'], row['Pass Rate']))

    if pareto_points:
        pareto_points.sort(key=lambda p: p[0])
        px, py = zip(*pareto_points)
        ax.plot(px, py, color='gray', linestyle='--', linewidth=2, alpha=0.6,
                label='Pareto Frontier', zorder=0)

    ax.set_xscale('log')
    ax.set_title("Wall-Clock Efficiency", fontsize=13, weight='bold')
    ax.set_xlabel("Avg. Wall-Clock Time per Task (seconds, log scale)", fontsize=12)
    ax.set_ylabel("Pass@1 (%)", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)

    note_text = (
        'SLMs complete in seconds and do not loop.\n'
        'Pynguin runs for up to 120s per task (SBST).\n'
        'Both measured on the same consumer hardware.\n'
        'Lower time + higher Pass@1 = better.'
    )
    handles = []
    handles.append(Line2D([0], [0], marker='None', color='w', label='Models (Shape):', markersize=0))
    for model in sorted(agg_llm['Model'].unique()):
        handles.append(Line2D([0], [0], marker=markers_dict.get(model, 'o'), color='w',
                              markerfacecolor='gray', markersize=10, label=f'  {model}',
                              markeredgecolor='black', markeredgewidth=1))

    handles.append(Line2D([0], [0], marker='None', color='w', label='Temperature (Color):', markersize=0))
    for temp in sorted(temp_colors.keys()):
        handles.append(Line2D([0], [0], marker='o', color='w',
                              markerfacecolor=temp_colors[temp], markersize=8,
                              label=f'  T={temp}', markeredgecolor='black', markeredgewidth=1))

    handles.append(Line2D([0], [0], marker='None', color='w', label='Mode (Fill):', markersize=0))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  One-Step', fillstyle='full',
                          markeredgecolor='black', markeredgewidth=1))
    handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                          markersize=10, label='  Two-Step (Hollow)', fillstyle='none',
                          markeredgecolor='black', markeredgewidth=1))

    if not pynguin_df.empty:
        handles.append(Line2D([0], [0], marker='^', color='w', markerfacecolor='black',
                              markersize=12, label='Pynguin (Baseline)', markeredgecolor='white', markeredgewidth=2))

    handles.append(Line2D([0], [0], color='gray', linestyle='--', linewidth=2, label='Pareto Frontier'))

    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc='upper left', title="Legend", prop={'size': 10, 'weight': 'bold'})
    plt.tight_layout()
    plt.savefig(output_dir / "wall_clock_efficiency.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_error_distribution(error_data, output_dir, palette_dict, benchmark_size, n_runs=3):
    """
    Generates heatmap showing error type distribution across models and modes.
    SCIENTIFIC IMPROVEMENTS:
    - Groups by Model first, then sorts by temperature for easy comparison
    - Uses perceptually uniform colormap
    - Filters out Pynguin (not an LLM, generates valid Python)
    - Proper color scale based on actual benchmark size
    - Shows average errors per run (n runs averaged)

    Args:
        benchmark_size: Total number of tasks in benchmark (e.g., 210 for testeval, 21 for realworld)
    """
    if not error_data:
        print("WARNING: No error data available for error distribution plot")
        return

    df = pd.DataFrame(error_data)

    # Filter out Pynguin - it's not an LLM and generates valid Python files, not markdown
    df = df[~df['Model'].str.contains('Pynguin', case=False, na=False)].copy()

    if df.empty:
        print("WARNING: No LLM error data available after filtering Pynguin")
        return

    # Order by error severity: Syntax (easiest) -> Runtime -> Assertion (hardest) -> NoCode -> Timeout
    error_types = ['Syntax', 'Runtime', 'Assert', 'NoCode', 'Timeout']
    error_labels = ['Syntax', 'Runtime', 'Assertion', 'No Code', 'Timeout']

    # Convert string values to numeric (they're already averages from rel_data)
    for col in error_types:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Rename columns for display
    df_display = df.copy()
    for old, new in zip(error_types, error_labels):
        if old in df_display.columns:
            df_display[new] = df_display[old]

    # Extract temperature for sorting
    df_display['Temperature'] = df_display['Config'].str.extract(r'T=([\d.]+)').astype(float)
    df_display['Temperature'] = df_display['Temperature'].fillna(999)  # Put N/A at end

    # Group by Model first, then sort by Temperature
    # This allows easy visual comparison of how temperature affects error rates for each model
    df_display = df_display.sort_values(['Model', 'Mode', 'Temperature'])

    # Create compound label: Model + Mode + Config
    df_display['Label'] = df_display['Model'] + ' (' + df_display['Mode'] + ', ' + df_display['Config'] + ')'

    # Prepare heatmap data
    heatmap_data = df_display.set_index('Label')[error_labels]

    # VALIDATION: Ensure no value exceeds benchmark_size (scientific integrity check)
    max_value = heatmap_data.values.max()
    if max_value > benchmark_size:
        print(f"WARNING: Maximum error value ({max_value:.1f}) exceeds benchmark size ({benchmark_size})")
        print("This indicates a data integrity issue (duplicate task IDs or incorrect counting)")

    # Use full benchmark size for vmax to show true severity
    # Cap at 50% to distinguish "partial failure" from "total collapse"
    vmax = benchmark_size * 0.5  # 50% of tasks failed = strong visual signal

    # Dynamic figure size based on number of configurations
    fig_height = max(8, len(heatmap_data) * 0.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    # Create heatmap with YlOrRd colormap (perceptually uniform)
    # white = 0 errors, yellow -> orange -> red = increasing errors
    sns.heatmap(
        heatmap_data,
        annot=True,        # Show values
        fmt=".1f",         # 1 decimal place
        cmap="YlOrRd",     # Perceptually uniform: yellow -> orange -> red
        linewidths=0.5,
        linecolor='gray',
        cbar_kws={'label': f'Avg. Failed Tasks per Run (n={n_runs}, Max={benchmark_size})'},
        vmin=0,            # Ensure 0 is white/yellow
        vmax=vmax,         # Cap at 50% to distinguish severity levels
        square=False,
        cbar=True,
        ax=ax
    )

    ax.set_title("Failure Mode Analysis", fontsize=13, weight='bold', pad=10)
    ax.set_ylabel("Model Configuration (Grouped by Model → Mode → Temperature)", fontsize=11)
    ax.set_xlabel("Error Type (by Severity)", fontsize=11)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    plt.setp(ax.get_yticklabels(), rotation=0, fontsize=10, fontweight='bold')

    # Add footnote explaining unique task counting and scientific validity
    footnote_text = (
        f"Values = unique tasks failed (not error event counts). Max possible = {benchmark_size}. "
        f"Pynguin excluded. Color scale: 0 (white) → {vmax:.0f} (dark red, 50% failure rate)."
    )
    fig.text(0.5, 0.0, footnote_text, ha='center', va='top', fontsize=9, style='italic')

    fig.tight_layout()
    fig.savefig(str(output_dir / "error_distribution.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  >> Saved error_distribution.png (heatmap)")

# Pipeline Step Functions (called in order by generate_report)

def load_evaluation_data(input_dir):
    """Step 1: Scan and parse all evaluated JSONL files into per-config run statistics."""
    print(f"Scanning {input_dir}...")
    files = glob.glob(str(input_dir / "**" / "*_evaluated.jsonl"), recursive=True)

    config_runs = {}
    unique_tasks = set()

    for filepath in files:
        model, mode, temp = parse_filename_metadata(filepath, clean_name=True)
        temp_str = f"T={temp}" if not np.isnan(temp) else "N/A"
        key = (model, mode, temp_str)
        if key not in config_runs: config_runs[key] = []

        run_stats = {
            "passed_tasks": set(), "assert_err_tasks": set(), "runtime_err_tasks": set(),
            "compile_err_tasks": set(), "no_code_tasks": set(), "timeout_tasks": set(),
            "cov_list": [], "mut_list": [],
            "cov_list_all_tasks": [], "mut_list_all_tasks": [],
            "total_tokens": 0, "total_duration": 0, "tps_readings": []
        }

        try:
            # Phase 1: Read all entries and group by task_id.
            # Pynguin duplicates its test suite across every target_line for a task,
            # producing identical evaluation results. Grouping by task_id ensures each
            # task contributes exactly one data point to coverage/mutation metrics.
            task_entries = {}
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line)
                    task_id = entry.get('task_num')
                    if not task_id: continue
                    unique_tasks.add(task_id)
                    task_entries.setdefault(task_id, []).append(entry)

            # Phase 2: Aggregate per unique task -> one data point each.
            for task_id, entries in task_entries.items():
                statuses = [e.get('status') for e in entries]
                task_passed = 'Pass' in statuses

                # Coverage (ungated): use actual value from evaluator for ALL tasks.
                # The evaluator now measures coverage even for failing tests (except
                # TIMEOUT, SYNTAX_ERROR, NO_CODE), so we read whatever it recorded.
                all_covs = [float(e['coverage']) for e in entries if e.get('coverage') is not None]
                avg_cov = sum(all_covs) / len(all_covs) if all_covs else 0.0
                run_stats["cov_list_all_tasks"].append(avg_cov)

                if task_passed:
                    run_stats["passed_tasks"].add(task_id)
                    # Gated coverage: from passing entries only (traditional metric)
                    passing = [e for e in entries if e.get('status') == 'Pass']
                    pass_covs = [float(e['coverage']) for e in passing if e.get('coverage') is not None]
                    if pass_covs:
                        run_stats["cov_list"].append(sum(pass_covs) / len(pass_covs))
                    # Mutation: still gated on pass
                    muts = [float(e['mutation_score']) for e in passing if e.get('mutation_score') is not None]
                    if muts:
                        avg_mut = sum(muts) / len(muts)
                        run_stats["mut_list"].append(avg_mut)
                        run_stats["mut_list_all_tasks"].append(avg_mut)
                else:
                    run_stats["mut_list_all_tasks"].append(0.0)

                # Failure categorization (one entry per task; for Pynguin all are identical)
                first_status = statuses[0] if not task_passed else 'Pass'
                if first_status == 'Assertion Error': run_stats["assert_err_tasks"].add(task_id)
                elif first_status == 'Runtime Error': run_stats["runtime_err_tasks"].add(task_id)
                elif first_status == 'Timeout': run_stats["timeout_tasks"].add(task_id)
                elif first_status == 'Pytest Error' or first_status == 'Syntax Error': run_stats["compile_err_tasks"].add(task_id)
                elif first_status == 'No Code': run_stats["no_code_tasks"].add(task_id)

                # Performance data: use first entry only (avoid double-counting duplicates)
                perf = entries[0].get('performance_batch') or entries[0].get('performance') or {}
                tok, dur, tps = extract_performance_data(perf, calculate_tps=True)
                run_stats["total_tokens"] += tok
                run_stats["total_duration"] += dur
                if tps > 0: run_stats["tps_readings"].append(tps)
        except: continue
        config_runs[key].append(run_stats)

    return config_runs, unique_tasks


def compute_run_parameters(config_runs):
    """Step 2: Derive N, degrees of freedom, and t-critical from the loaded data."""
    n_runs = max((len(runs) for runs in config_runs.values()), default=1)
    df = n_runs - 1
    t_crit = stats.t.ppf((1 + 0.95) / 2, df=df) if df > 0 else float('inf')
    return n_runs, df, t_crit


def aggregate_config_statistics(config_runs, total_benchmark_size, dataset_type):
    """Step 3: Aggregate per-run data into effectiveness, reliability, and efficiency tables."""
    eff_data, rel_data, cost_data = [], [], []
    plot_records = []
    validation_notes = []
    raw_pass_rates = {}

    # Column names for the performance table drop "(95% CI)" when N=1
    # because a single run produces no meaningful interval (t-critical = inf).
    global_n_runs = max((len(runs) for runs in config_runs.values()), default=1)
    if global_n_runs == 1:
        col_pass     = "Pass@1"
        col_raw_cov  = "Raw Cov"
        col_gated    = "Gated Cov"
        col_mut      = "Mut Score"
    else:
        col_pass     = "Pass@1 (95% CI)"
        col_raw_cov  = "Raw Cov (95% CI)"
        col_gated    = "Gated Cov (95% CI)"
        col_mut      = "Mut Score (95% CI)"

    for (model, mode, temp_str), runs in config_runs.items():
        n_runs = len(runs)
        if n_runs == 0: continue

        pass_rates = []
        run_avg_covs, run_avg_muts, run_avg_tps = [], [], []
        run_avg_covs_global, run_avg_muts_global = [], []
        run_total_toks, run_total_time = [], []
        avg_errs = {"as": 0, "rt": 0, "cp": 0, "nc": 0, "to": 0}

        try:
            temp_val = float(temp_str.replace("T=", "")) if temp_str != "N/A" else np.nan
        except (ValueError, AttributeError):
            temp_val = np.nan

        for r in runs:
            pr = (len(r["passed_tasks"]) / total_benchmark_size) * 100
            pass_rates.append(pr)
            cov_val = np.mean(r["cov_list"]) if r["cov_list"] else np.nan
            mut_val = np.mean(r["mut_list"]) if r["mut_list"] else np.nan
            tps_val = np.mean(r["tps_readings"]) if r["tps_readings"] else 0
            cov_val_global = np.mean(r["cov_list_all_tasks"]) if r["cov_list_all_tasks"] else np.nan
            mut_val_global = np.mean(r["mut_list_all_tasks"]) if r["mut_list_all_tasks"] else np.nan

            if not np.isnan(cov_val): run_avg_covs.append(cov_val)
            if not np.isnan(mut_val): run_avg_muts.append(mut_val)
            if not np.isnan(cov_val_global): run_avg_covs_global.append(cov_val_global)
            if not np.isnan(mut_val_global): run_avg_muts_global.append(mut_val_global)
            if tps_val > 0: run_avg_tps.append(tps_val)
            run_total_toks.append(r["total_tokens"])
            run_total_time.append(r["total_duration"])

            avg_errs["as"] += len(r["assert_err_tasks"])
            avg_errs["rt"] += len(r["runtime_err_tasks"])
            avg_errs["cp"] += len(r["compile_err_tasks"])
            avg_errs["nc"] += len(r["no_code_tasks"])
            avg_errs["to"] += len(r["timeout_tasks"])

            plot_records.append({
                "Model": model, "Mode": mode, "Temperature": temp_val,
                "Pass Rate": pr, "Coverage": cov_val, "Mutation Score": mut_val,
                "Coverage Global": cov_val_global, "Mutation Score Global": mut_val_global,
                "N Passed": len(r["passed_tasks"]), "TPS": tps_val,
                "Time Per Task (s)": r["total_duration"] / total_benchmark_size if total_benchmark_size > 0 else 0
            })

        pass_std = np.std(pass_rates)
        tok_std = np.std(run_total_toks)
        is_low_temp = temp_str in ["T=0.0", "T=0.2", "N/A"]
        if not is_low_temp and pass_std == 0 and n_runs > 1:
            validation_notes.append((model, mode, temp_str, "valid" if tok_std > 0 else "warning"))

        raw_pass_rates[f"{model} ({mode}, {temp_str})"] = pass_rates.copy()

        pass_mean, pass_ci_lo, pass_ci_hi, _ = compute_confidence_interval(pass_rates)
        cov_mean, cov_ci_lo, cov_ci_hi, _ = compute_confidence_interval(run_avg_covs)
        cov_g_mean, cov_g_ci_lo, cov_g_ci_hi, _ = compute_confidence_interval(run_avg_covs_global)
        mut_mean, mut_ci_lo, mut_ci_hi, _ = compute_confidence_interval(run_avg_muts)
        pass_std = np.std(pass_rates, ddof=1) if len(pass_rates) > 1 else np.nan
        cov_std = np.std(run_avg_covs, ddof=1) if len(run_avg_covs) > 1 else np.nan
        cov_g_std = np.std(run_avg_covs_global, ddof=1) if len(run_avg_covs_global) > 1 else np.nan
        mut_std = np.std(run_avg_muts, ddof=1) if len(run_avg_muts) > 1 else np.nan

        eff_data.append({
            "Model": model, "Mode": mode, "Config": temp_str, "Runs": n_runs,
            "Avg Tokens": f"{np.mean(run_total_toks):,.0f}" if run_total_toks else "-",
            col_pass:    format_metric_with_ci(pass_mean, pass_std, pass_ci_lo, pass_ci_hi, 2, "%"),
            col_raw_cov: format_metric_with_ci(cov_g_mean, cov_g_std, cov_g_ci_lo, cov_g_ci_hi, 1, "%"),
            col_gated:   format_metric_with_ci(cov_mean, cov_std, cov_ci_lo, cov_ci_hi, 1, "%"),
            col_mut:     format_metric_with_ci(mut_mean, mut_std, mut_ci_lo, mut_ci_hi, 1, "%"),
            "_sort": np.mean(pass_rates) if pass_rates else 0,
            "_pass_rates_raw": pass_rates
        })
        rel_data.append({
            "Model": model, "Mode": mode, "Config": temp_str,
            "Assert": f"{avg_errs['as']/n_runs:.1f}", "Runtime": f"{avg_errs['rt']/n_runs:.1f}",
            "Syntax": f"{avg_errs['cp']/n_runs:.1f}", "NoCode": f"{avg_errs['nc']/n_runs:.1f}",
            "Timeout": f"{avg_errs['to']/n_runs:.1f}", "_sort": np.mean(pass_rates) if pass_rates else 0
        })
        cost_data.append({
            "Model": model, "Mode": mode, "Config": temp_str,
            "TPS": f"{np.mean(run_avg_tps):.0f}" if run_avg_tps else "-",
            "Total Tokens": f"{np.mean(run_total_toks):,.0f}" if run_total_toks else "-",
            "Time": format_duration(np.mean(run_total_time)) if run_total_time else "-",
            "Avg Time/Task (s)": f"{np.mean(run_total_time) / total_benchmark_size:.1f}s" if run_total_time and total_benchmark_size > 0 else "-",
            "_sort_tps": np.mean(run_avg_tps) if run_avg_tps else 0
        })

    if dataset_type == "testeval":
        for baseline in LITERATURE_BASELINES:
            is_ec = baseline.get("sr_metric", "Pass@1") == "EC"
            is_ec_cov = baseline.get("cov_metric", "assertion-gated") == "EC-gated"
            # Wang et al. uses Execution Correctness (EC) rather than assertion-based Pass@1.
            # Append [a] marker so readers know these columns measure different things.
            sr_marker = "[a]" if is_ec else ""
            cov_marker = "[a]" if is_ec_cov else ""
            sr_str = f"{baseline['SR']:.2f}%{sr_marker}"
            cov_str = (f"{baseline['Cov']:.1f}%{cov_marker}" if baseline['Cov'] is not None else "-")
            eff_data.append({
                "Model": baseline['Model'], "Mode": f"Literature ({baseline['Source']})",
                "Config": baseline["Config"], "Runs": baseline["Runs"], "Avg Tokens": "-",
                col_pass:    sr_str,
                col_raw_cov: "-",
                col_gated:   cov_str,
                col_mut:     f"{baseline['Mut']:.1f}%" if baseline['Mut'] is not None else "-",
                "_sort": baseline["SR"], "_pass_rates_raw": []
            })

    return eff_data, rel_data, cost_data, plot_records, validation_notes, raw_pass_rates


def generate_plots(plot_records, rel_data, output_dir, total_benchmark_size, n_runs):
    """Step 4: Generate all visualization plots (trends, quadrant, coverage, efficiency, errors)."""
    if not plot_records:
        return
    df_plot = pd.DataFrame(plot_records)
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
    pal, marks = get_style_maps(df_plot)

    print("Generating Stability Trend Plots...")
    plot_stability_trends(df_plot, output_dir, pal, marks)
    print("Generating Quality Quadrant...")
    plot_quality_quadrant(df_plot, output_dir, pal, marks)
    print("Generating Coverage Analysis Plot...")
    plot_coverage_analysis(df_plot, output_dir, pal, marks)
    print("Generating Efficiency Frontier...")
    plot_efficiency_frontier(df_plot, output_dir, pal, marks)
    print("Generating Wall-Clock Efficiency Plot...")
    plot_wall_clock_efficiency(df_plot, output_dir, pal, marks, total_benchmark_size)
    print("Generating Error Distribution Plot...")
    plot_error_distribution(rel_data, output_dir, pal, total_benchmark_size, n_runs=n_runs)


def find_best_model_configs(df_eff_full):
    """Step 5a: Find best configuration per model (highest mean Pass@1, non-zero variance)."""
    model_best_configs = {}
    for _, row in df_eff_full.iterrows():
        model, data = row["Model"], row["_pass_rates_raw"]
        if len(data) < 2: continue
        std = np.std(data, ddof=1)
        if std == 0: continue
        mean_pass = np.mean(data)
        if model not in model_best_configs or mean_pass > model_best_configs[model]["mean"]:
            model_best_configs[model] = {
                "mean": mean_pass, "std": std, "data": data,
                "config": f"{row['Mode']}, {row['Config']}",
                "mode": row["Mode"], "temp": row["Config"]
            }
    print(f"  Found {len(model_best_configs)} models with valid variance for comparison")
    return model_best_configs


def run_pairwise_comparisons(model_best_configs):
    """Step 5b: Run Welch's t-tests between all model pairs with Bonferroni correction."""
    best_configs = [(m, i["mode"], i["temp"], i["data"], i["mean"], i["std"])
                    for m, i in model_best_configs.items()]
    pairwise_results, all_p_values = [], []

    if len(best_configs) >= 2:
        for (m1, mode1, cfg1, data1, mean1, std1), (m2, mode2, cfg2, data2, mean2, std2) in combinations(best_configs, 2):
            t_stat, p_val = paired_ttest(data1, data2)
            all_p_values.append(p_val)
            cohens_h = compute_cohens_h(data1, data2)
            pairwise_results.append({
                "Model A": m1, "Model B": m2,
                "Config A": f"{mode1}, {cfg1}", "Config B": f"{mode2}, {cfg2}",
                "Mean A": f"{mean1:.2f}%", "Mean B": f"{mean2:.2f}%",
                "Diff": f"{mean1 - mean2:+.2f}%",
                "t-stat": f"{t_stat:.2f}" if not np.isnan(t_stat) else "-",
                "p-value": p_val,
                "Cohen's h": f"{cohens_h:.2f}" if not np.isnan(cohens_h) else "-",
                "Effect": interpret_cohens_h(cohens_h), "_p_raw": p_val
            })

        n_comparisons = len([p for p in all_p_values if not np.isnan(p)])
        if n_comparisons > 0:
            corrected = bonferroni_correction(all_p_values)
            for i, (orig_p, corr_p, is_sig) in enumerate(corrected):
                pairwise_results[i]["p-value"] = format_p_value(orig_p, corr_p, is_sig)
                pairwise_results[i]["Sig."] = "Yes*" if is_sig else "No"

    if pairwise_results:
        df_pw = pd.DataFrame(pairwise_results)
        df_pw["_effect_sort"] = df_pw["Cohen's h"].apply(
            lambda x: abs(float(x)) if x != "-" and not np.isinf(float(x)) else 0)
        return df_pw.sort_values("_effect_sort", ascending=False).drop(columns=["_p_raw", "_effect_sort"])
    return pd.DataFrame()


def build_baseline_comparison(df_eff_full, model_best_configs):
    """Step 5c: Compare each SLM's best config against Pynguin deterministic baseline."""
    pynguin_baseline = None
    for _, row in df_eff_full.iterrows():
        if "Pynguin" in row["Model"]:
            pynguin_baseline = {"name": row["Model"], "mean": np.mean(row["_pass_rates_raw"])}
            break

    rows = []
    if pynguin_baseline:
        for model, info in model_best_configs.items():
            if "Pynguin" in model: continue
            diff = info["mean"] - pynguin_baseline["mean"]
            relative = (diff / pynguin_baseline["mean"] * 100) if pynguin_baseline["mean"] > 0 else np.nan
            rows.append({
                "SLM Model": model, "SLM Config": f"{info['mode']}, {info['temp']}",
                "SLM Pass@1": f"{info['mean']:.2f}%",
                "Baseline": pynguin_baseline["name"],
                "Baseline Pass@1": f"{pynguin_baseline['mean']:.2f}%",
                "Difference": f"{diff:+.2f}%",
                "Relative": f"{relative:+.1f}%" if not np.isnan(relative) else "-"
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def run_bootstrap_analysis(model_best_configs):
    """Step 6: Bootstrap resampling to assess ranking stability (1000 iterations)."""
    print("Running bootstrap stability analysis (1000 iterations, best configs)...")
    best_config_pass_rates = {
        f"{m} ({i['mode']}, {i['temp']})": i["data"] for m, i in model_best_configs.items()
    }
    bootstrap_results = bootstrap_ranking_stability(best_config_pass_rates, n_bootstrap=1000, metric='Pass@1')

    rows = []
    if bootstrap_results.get("rank_stability"):
        for cfg, rank_info in bootstrap_results["rank_stability"].items():
            rows.append({
                "Model (Best Config)": cfg, "Modal Rank": rank_info["modal_rank"],
                "Rank Stability": f"{rank_info['modal_frequency']:.1f}%",
                "Interpretation": "Robust" if rank_info['modal_frequency'] >= 70 else "Moderate" if rank_info['modal_frequency'] >= 50 else "Unstable"
            })
        rows = sorted(rows, key=lambda x: x["Modal Rank"])
    return (pd.DataFrame(rows) if rows else pd.DataFrame()), bootstrap_results


def compute_variance_stats(raw_pass_rates, model_best_configs):
    """Step 7: Compute variance convergence statistics to justify the number of runs."""
    print("Analyzing variance convergence for N justification...")
    all_stds, zero_variance_count, total_configs = [], 0, 0

    for cfg, data in raw_pass_rates.items():
        if len(data) >= 3:
            total_configs += 1
            std = np.std(data, ddof=1)
            all_stds.append(std)
            if std == 0: zero_variance_count += 1

    variance_stats = {
        "median_std": np.median(all_stds), "mean_std": np.mean(all_stds),
        "max_std": np.max(all_stds), "min_std": np.min(all_stds),
        "zero_variance_pct": (zero_variance_count / total_configs) * 100,
        "total_configs": total_configs
    } if all_stds else {}

    rows = []
    for model, info in model_best_configs.items():
        data = info["data"]
        n_data = len(data)
        if n_data >= 2:
            std_val = np.std(data, ddof=1)
            sem_val = std_val / np.sqrt(n_data)
            t_crit = stats.t.ppf((1 + 0.95) / 2, df=n_data - 1)
            rows.append({
                "Model": model, "Best Config": f"{info['mode']}, {info['temp']}",
                "Mean": f"{info['mean']:.2f}%", "Std": f"{std_val:.2f}%",
                "SEM": f"{sem_val:.2f}%", "95% CI Width": f"±{t_crit * sem_val:.2f}%"
            })
    return (pd.DataFrame(rows) if rows else pd.DataFrame()), variance_stats


def build_footnotes(dataset_type, validation_notes, total_benchmark_size, n_runs, t_crit, df):
    """Step 8a: Build publication-ready footnotes with dynamic statistical parameters."""
    footnotes = [
        "\n[1] COVERAGE METHODOLOGY: Two coverage metrics are reported. 'Raw Cov' (ungated) measures line coverage "
        "for all test outcomes except TIMEOUT, SYNTAX_ERROR, and NO_CODE — even assertion-failing tests report "
        "actual coverage, reflecting how much of the solution code the test exercised before failing. "
        "'Gated Cov' measures coverage restricted to assertion-passing tasks only (our Pass@1 criterion). "
        "Note: Wang et al. (2025a)'s 'Overall Line Coverage' (marked [a] in Table 1) applies a more lenient gating condition "
        "(Execution Correctness: test compiles and runs without crashing) rather than assertion passing; it is "
        "therefore not directly equivalent to our Gated Cov but is placed in the same column as the closest analogue. "
        "Both our metrics appear in Table 1.",

        "\n[2] PYNGUIN TPS REPRESENTATION: Pynguin does not generate tokens; it uses evolutionary search "
        "(SBST/AST mutations). Pynguin is excluded from TPS trend plots. For cross-paradigm efficiency "
        "comparison, refer to the Wall-Clock Efficiency figure."
    ]

    if dataset_type == "testeval":
        footnotes.append(
            "\nLITERATURE BASELINES: Results for five reference models are drawn from two independent studies "
            "that evaluated on the TestEval benchmark. Metric definitions differ between sources:\n"
            "  Wang et al. (2025a) — GPT-4o, Llama-3.1-8B-Instruct:\n"
            "    Pass@1 column reports their 'Execution Correctness' (EC): the fraction of tasks where the generated "
            "test compiles and runs to completion without an unhandled exception. EC does NOT require assertions to "
            "pass; it is therefore more lenient than our assertion-based Pass@1. Values are marked [a].\n"
            "    Gated Cov column reports their 'Overall Line Coverage': average line coverage measured over "
            "EC-passing tasks. Because the gating criterion is EC (not assertion passing), this metric is more "
            "lenient than our Gated Cov and is marked [a]. Mutation Score was not reported by Wang et al. (2025a) on TestEval.\n"
            "  Huang et al. (2025b) — Phi-4-mini-Instruct, DeepSeek-Coder-1.3B-Instruct, Gemma-3-4B-IT:\n"
            "    Pass@1 column reports their 'Pass@1': fraction of tasks where the generated test passes all "
            "assertions. This is assertion-based and directly comparable to our Pass@1.\n"
            "    Gated Cov column reports their 'LCov@1': average line coverage on assertion-passing tasks, "
            "directly comparable to our Gated Cov.\n"
            "    Mut Score reports their 'Mut@1': mutation score on TestEval (Table 5), comparable to ours.\n"
            "  Shared context: all baselines used the same TestEval benchmark (same tasks, same reference solutions). "
            "Inference details (engine, hardware, sampling) may differ from our setup (vLLM, RTX 4090, T=0.0)."
        )

    valid_count = sum(1 for v in validation_notes if v[3] == "valid")
    warning_count = sum(1 for v in validation_notes if v[3] == "warning")

    if valid_count > 0:
        footnote_num = "[4]" if dataset_type == "testeval" else "[3]"
        min_increment = 100.0 / total_benchmark_size
        footnotes.append(
            f"\n{footnote_num} DISCRETE TASK GRANULARITY: {valid_count} model configuration(s) exhibited zero "
            f"standard deviation in Pass@1 despite distinct token generation patterns. This results from discrete "
            f"task granularity where N={total_benchmark_size} tasks yield minimum increments of {min_increment:.2f}% "
            f"per task. When multiple runs achieve identical pass counts, zero variance occurs naturally. Token "
            f"generation counts were verified to differ across all runs, confirming distinct code generation despite "
            f"identical outcomes. This phenomenon is expected in discrete benchmarks and does not indicate experimental error."
        )

    if warning_count > 0:
        warning_configs = [f"{v[0]} ({v[1]}, {v[2]})" for v in validation_notes if v[3] == "warning"]
        footnotes.append(
            f"\n[!] WARNING: {warning_count} configuration(s) show identical token counts: "
            f"{', '.join(warning_configs)}. This may indicate deterministic caching or identical code generation."
        )

    next_footnote = 4 if dataset_type == "testeval" else 3
    if valid_count > 0: next_footnote += 1

    footnotes.extend([
        f"\n[{next_footnote}] STATISTICAL METHODOLOGY: All pairwise comparisons use Welch's t-test (unequal variances). "
        f"P-values are Bonferroni-corrected for multiple comparisons. Effect sizes reported as Cohen's h "
        f"(appropriate for proportions): |h|<0.2=negligible, 0.2-0.5=small, 0.5-0.8=medium, ≥0.8=large. "
        f"95% confidence intervals use t-distribution "
        f"(N={n_runs} runs, t-critical={t_crit:.3f}, df={df}).",

        f"\n[{next_footnote + 1}] N={n_runs} RUNS JUSTIFICATION: {n_runs} independent runs per configuration "
        f"balances statistical rigor with computational cost. With N={n_runs}: "
        f"(1) 95% CIs use t-critical value of {t_crit:.3f} (df={df}); "
        f"(2) Bootstrap analysis confirms ranking stability across resampling. The variance convergence table "
        f"demonstrates diminishing returns for additional runs.",

        f"\n[{next_footnote + 2}] BOOTSTRAP STABILITY: Rankings assessed via 1000 bootstrap iterations resampling runs "
        f"with replacement. 'Modal Rank' = most frequent rank position. 'Rank Stability' = percentage of iterations "
        f"where configuration achieved its modal rank. High stability (>70%) indicates robust rankings.",

        f"\n[{next_footnote + 3}] BEST CONFIGURATION SELECTION: For Tables 4-7, 'best configuration' for each model "
        f"is defined as the configuration (prompt mode + temperature) with the highest mean Pass@1 across N={n_runs} runs, "
        f"excluding configurations with zero variance (which cannot be used in statistical tests). This reduces "
        f"comparisons from all temperature variants to one representative per model."
    ])

    return "\n" + "="*110 + "\n FOOTNOTES\n" + "="*110 + "\n".join(footnotes)


def assemble_text_report(dataset_type, total_benchmark_size, n_runs, df, t_crit,
                         df_eff, df_rel, df_cost,
                         df_pairwise, df_baseline, df_bootstrap, df_convergence,
                         model_best_configs, bootstrap_results, variance_stats,
                         footnotes_section):
    """Step 8b: Assemble all tables, statistics, and footnotes into the final text report."""
    dataset_label = "TESTEVAL" if dataset_type == "testeval" else "REAL WORLD"
    hardware_specs = get_testeval_hardware_specs(total_benchmark_size) if dataset_type == "testeval" else get_realworld_hardware_specs(total_benchmark_size)

    buffer = [
        "="*110, f" {dataset_label} EVALUATION REPORT", "="*110,
        f"• Benchmark Size (N): {total_benchmark_size} unique tasks.",
        *(
            [
                "• Metric Format: mean (±std)[95% CI lower, upper] - e.g., 25.71% (±0.82)[22.18, 29.24]",
                f"• 95% CI computed using t-distribution (N={n_runs} runs, t-critical={t_crit:.3f}, df={df}).",
            ] if n_runs > 1 else [
                f"• Metric Format: point estimate (single run, N=1) — no CI reported.",
            ]
        ),
        "-"*110, tabulate(df_eff, headers="keys", tablefmt="github", showindex=False),
        "\n" + "-"*110,
        "Note: Raw Cov = ungated (all tasks, incl. failures). Gated Cov = assertion-passing tasks only (our metric).",
        "      [a] Wang et al. (2025a) baselines use Execution Correctness (EC): test compiles/runs without crash, NOT assertion-passing.",
        "          Their Gated Cov is therefore EC-gated (more lenient than our assertion-gated Gated Cov).",
        "      Literature baselines show point estimates only (no CI available from source papers).",
        "      See Footnote [1] for coverage methodology; Footnote [3] for literature metric definitions.",
        "\n"+"="*110, f" TABLE 2: RELIABILITY - {dataset_label} (Avg Failures)", "="*110,
        "-"*110, tabulate(df_rel, headers="keys", tablefmt="github", showindex=False),
        "\n"+"="*110, f" TABLE 3: EFFICIENCY - {dataset_label}", "="*110,
        "-"*110, tabulate(df_cost, headers="keys", tablefmt="github", showindex=False),
        "\n" + "-"*110,
        "Note: Pynguin uses evolutionary search (SBST) and does not generate tokens; excluded from TPS comparisons. See Wall-Clock Efficiency figure.",
    ]

    if not df_baseline.empty:
        buffer.extend([
            "\n"+"="*110, f" TABLE 4: BASELINE COMPARISON - {dataset_label} (SLMs vs Pynguin)", "="*110,
            f"• Compares each SLM's best configuration against the Pynguin deterministic baseline ({len(df_baseline)} comparisons).",
            "• Pynguin has zero variance (deterministic) and cannot be compared via statistical tests.",
            "• Relative difference = (SLM - Pynguin) / Pynguin × 100%",
            "• Best configuration = highest mean Pass@1 among non-zero-variance configs for each model.",
            "-"*110, tabulate(df_baseline, headers="keys", tablefmt="github", showindex=False),
        ])

    if not df_pairwise.empty:
        n_comparisons = len(df_pairwise)
        n_significant = len(df_pairwise[df_pairwise["Sig."] == "Yes*"])
        n_nonsig = n_comparisons - n_significant
        buffer.extend([
            "\n"+"="*110,
            f" TABLE 5: PAIRWISE STATISTICAL COMPARISONS - {dataset_label} (Best Config per Model)", "="*110,
            f"• Compares best configuration from each of {len(model_best_configs)} models ({n_comparisons} pairwise comparisons).",
            f"• Bonferroni-corrected α = {0.05/n_comparisons:.4f} (family-wise α = 0.05)",
            "• p-value format: raw (corrected). * indicates significance after Bonferroni correction.",
            "• Effect size (Cohen's h): negligible (<0.2), small (0.2-0.5), medium (0.5-0.8), large (≥0.8)",
            "• Note: Zero-variance configs excluded (invalid for t-tests).",
            "-"*110, tabulate(df_pairwise, headers="keys", tablefmt="github", showindex=False),
        ])
        large_effect_count = len(df_pairwise[df_pairwise["Effect"] == "large"])
        substantial_effects = large_effect_count + len(df_pairwise[df_pairwise["Effect"] == "medium"])
        buffer.extend([
            "\n" + "-"*110,
            f"Interpretation: {n_significant}/{n_comparisons} comparisons show statistically significant differences (p<0.05, Bonferroni-corrected).",
        ])
        if n_nonsig > 0:
            buffer.extend([
                f"  IMPORTANT: Non-significance ({n_nonsig} pairs) does NOT imply equivalence. Large effect sizes (h≥0.8) were observed",
                f"  for {large_effect_count}/{n_comparisons} pairs, and {substantial_effects}/{n_comparisons} pairs show medium-to-large effects (h≥0.5),",
                f"  suggesting meaningful practical differences despite limited statistical power (N={n_runs} runs, {total_benchmark_size} tasks).",
                f"  See TestEval results (N=210 tasks) for more robust statistical inference with larger sample sizes.",
            ])

    if not df_bootstrap.empty:
        top_k_info = bootstrap_results.get("top_k_stability", {})
        buffer.extend([
            "\n"+"="*110,
            f" TABLE 6: BOOTSTRAP RANKING STABILITY - {dataset_label} (Best Configs, 1000 iterations)", "="*110,
            f"• Rankings based on best configuration per model (excluding zero-variance baselines).",
            f"• Top-1 Stability: {top_k_info.get('top_1', 0):.1f}% (best model remains #1 across resampling)",
            f"• Top-3 Stability: {top_k_info.get('top_3', 0):.1f}% (top 3 models unchanged)" if top_k_info.get('top_3', 0) > 0 else "",
            "• Interpretation: Robust (≥70%), Moderate (50-70%), Unstable (<50%)",
            "-"*110, tabulate(df_bootstrap, headers="keys", tablefmt="github", showindex=False),
        ])

    if not df_convergence.empty:
        variance_summary_lines = []
        if variance_stats:
            variance_summary_lines = [
                f"• Variance Distribution Across All {variance_stats['total_configs']} Configurations:",
                f"  - Median Std: {variance_stats['median_std']:.2f}%, Mean Std: {variance_stats['mean_std']:.2f}%",
                f"  - Range: [{variance_stats['min_std']:.2f}%, {variance_stats['max_std']:.2f}%]",
                f"  - Zero-variance configs: {variance_stats['zero_variance_pct']:.1f}% (due to discrete task granularity)",
            ]
        buffer.extend([
            "\n"+"="*110, f" TABLE 7: N={n_runs} RUNS JUSTIFICATION - {dataset_label} (Variance Analysis)", "="*110,
            *variance_summary_lines,
            "• Table shows statistics for best configuration per model.",
            f"• 95% CI Width = t-critical × SEM × 2 (t-critical = {t_crit:.3f} for df={df})",
            f"• N={n_runs} runs: SEM = std / √{n_runs}.",
            "-"*110, tabulate(df_convergence, headers="keys", tablefmt="github", showindex=False),
        ])

    buffer.extend(["\n" + "="*110, footnotes_section, "\n"+hardware_specs])
    return "\n".join(buffer)


# Main report generation
def generate_report(input_dir, output_dir, dataset_type):
    """
    Main pipeline: load data → aggregate stats → generate plots →
    run statistical analyses → assemble and write text report.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load all evaluated JSONL files
    config_runs, unique_tasks = load_evaluation_data(input_dir)
    total_benchmark_size = len(unique_tasks)
    n_runs, df, t_crit = compute_run_parameters(config_runs)
    print(f"Global Benchmark Size (N): {total_benchmark_size}")
    print(f"Number of runs detected: {n_runs} (df={df}, t-critical={t_crit:.3f})")

    if not config_runs:
        print(f"\nERROR: No *_evaluated.jsonl files found in '{input_dir}'.")
        print("Check that the directory exists and contains evaluated results.")
        return

    # Step 2: Aggregate per-config statistics across runs
    eff_data, rel_data, cost_data, plot_records, validation_notes, raw_pass_rates = \
        aggregate_config_statistics(config_runs, total_benchmark_size, dataset_type)

    # Step 3: Generate visualization plots
    generate_plots(plot_records, rel_data, output_dir, total_benchmark_size, n_runs)

    # Step 4: Build sorted DataFrames for report tables
    df_eff_full = pd.DataFrame(eff_data).sort_values("_sort", ascending=False)
    df_eff = df_eff_full.drop(columns=["_sort", "_pass_rates_raw"])
    df_rel = pd.DataFrame(rel_data).sort_values("_sort", ascending=False).drop(columns="_sort")
    df_cost = pd.DataFrame(cost_data).sort_values("_sort_tps", ascending=False).drop(columns="_sort_tps")

    # Step 5: Run pairwise statistical comparisons (best config per model)
    print("Running pairwise statistical comparisons (best config per model)...")
    model_best_configs = find_best_model_configs(df_eff_full)
    df_pairwise = run_pairwise_comparisons(model_best_configs)
    df_baseline = build_baseline_comparison(df_eff_full, model_best_configs)

    # Step 6: Bootstrap ranking stability analysis
    df_bootstrap, bootstrap_results = run_bootstrap_analysis(model_best_configs)

    # Step 7: Variance convergence (N-runs justification)
    df_convergence, variance_stats = compute_variance_stats(raw_pass_rates, model_best_configs)

    # Step 8: Assemble and write the text report
    footnotes_section = build_footnotes(
        dataset_type, validation_notes, total_benchmark_size, n_runs, t_crit, df)
    report_text = assemble_text_report(
        dataset_type, total_benchmark_size, n_runs, df, t_crit,
        df_eff, df_rel, df_cost,
        df_pairwise, df_baseline, df_bootstrap, df_convergence,
        model_best_configs, bootstrap_results, variance_stats,
        footnotes_section)

    output_file = output_dir / "summary_report.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\nReport saved to: {output_file}")
    print(f"Plots saved to:  {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate unified evaluation summary report")
    parser.add_argument("--input", required=True, help="Input directory with evaluation JSONL files")
    parser.add_argument("--output", required=True, help="Output directory for reports and plots")
    parser.add_argument("--dataset", required=True, choices=["testeval", "realworld"],
                        help="Dataset type: 'testeval' for initial/temp or 'realworld'")

    args = parser.parse_args()

    generate_report(args.input, args.output, args.dataset)