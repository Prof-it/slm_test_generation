"""
Step 4: Analyze LLM-as-Judge Results

This script analyzes the judge results and creates summary tables, text reports,
and visualizations to understand model performance, win rates, and score distributions.

Usage:
    python step4_evaluation/analyze_judge_results.py --judge_dir TestEval/predictions_judgellm
"""

import argparse
import json
import os
import logging
from collections import defaultdict
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)

sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10


def load_judge_results(judge_dir):
    """Load all JSONL judge result files from directory.

    Only loads files with the current format pattern 'pairwise_judgements_*.jsonl'
    to avoid mixing results from different evaluation runs or old formats.
    """
    results = []
    for filename in os.listdir(judge_dir):
        # ONLY load current format files to avoid mixing different runs
        if filename.startswith('pairwise_judgements_') and filename.endswith('.jsonl'):
            filepath = os.path.join(judge_dir, filename)
            logger.info(f"Loading: {filename}")
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    results.append(json.loads(line))
    return results


def compute_bradley_terry_ratings(results, n_bootstrap=1000):
    """
    Compute Bradley-Terry model ratings with confidence intervals.

    This is the same model used by LMArena.

    Mathematical model:
        P(Model A beats Model B) = σ(rating_A - rating_B)
        where σ is the logistic sigmoid function

    Returns:
        DataFrame with columns: Model, Rating, CI_lower, CI_upper, Rank, Rank_lower, Rank_upper

    References:
        - Bradley & Terry (1952): "Rank Analysis of Incomplete Block Designs"
        - LMArena technical report: https://lmarena.ai/blog/2023-05-03-arena/
    """
    # Get all unique models
    models = list(set([r['model_a'] for r in results] + [r['model_b'] for r in results]))
    model_to_idx = {m: i for i, m in enumerate(models)}
    n_models = len(models)

    # Filter unbiased results
    unbiased = [r for r in results if r.get('bias_status', 'None') == 'None']

    if len(unbiased) == 0:
        logger.warning("No unbiased comparisons available!")
        return None

    # Build comparison matrix
    # wins[i][j] = number of times model i beat model j
    wins = np.zeros((n_models, n_models))
    total_games = np.zeros((n_models, n_models))

    for r in unbiased:
        i = model_to_idx[r['model_a']]
        j = model_to_idx[r['model_b']]
        winner = r['final_winner_model']  # Now "A", "B", "Tie", or "Invalid_Bias"

        total_games[i][j] += 1
        total_games[j][i] += 1

        # Winner is "A" or "B" instead of model names
        if winner == "A":
            wins[i][j] += 1
        elif winner == "B":
            wins[j][i] += 1
        else:  # Tie - count as 0.5 for each
            wins[i][j] += 0.5
            wins[j][i] += 0.5

    # Bradley-Terry MLE via iterative scaling
    def fit_bradley_terry(wins, total_games, max_iter=100, tol=1e-6):
        """Maximum Likelihood Estimation for Bradley-Terry model."""
        n = wins.shape[0]
        strengths = np.ones(n)  # Initial strengths

        for iteration in range(max_iter):
            old_strengths = strengths.copy()

            for i in range(n):
                # Update formula from Bradley-Terry
                total_wins_i = np.sum(wins[i, :])
                denominator = 0

                for j in range(n):
                    if i != j and total_games[i][j] > 0:
                        denominator += total_games[i][j] / (strengths[i] + strengths[j])

                if denominator > 0:
                    strengths[i] = total_wins_i / denominator

            # Normalize to prevent overflow
            strengths = strengths / np.mean(strengths)

            # Check convergence
            if np.max(np.abs(strengths - old_strengths)) < tol:
                break

        # Convert to Elo-scale ratings (for interpretability)
        # rating_i = 400 * log10(strength_i) + 1500
        ratings = 400 * np.log10(strengths) + 1500
        return ratings

    # Compute point estimate
    ratings = fit_bradley_terry(wins, total_games)

    # Bootstrap for confidence intervals
    bootstrap_ratings = []
    for b in range(n_bootstrap):
        # Resample comparisons with replacement
        resampled_indices = np.random.choice(len(unbiased), size=len(unbiased), replace=True)
        resampled = [unbiased[i] for i in resampled_indices]

        # Build resampled matrices
        wins_boot = np.zeros((n_models, n_models))
        total_boot = np.zeros((n_models, n_models))

        for r in resampled:
            i = model_to_idx[r['model_a']]
            j = model_to_idx[r['model_b']]
            winner = r['final_winner_model']  # Now "A", "B", "Tie", or "Invalid_Bias"

            total_boot[i][j] += 1
            total_boot[j][i] += 1

            # Winner is "A" or "B" instead of model names
            if winner == "A":
                wins_boot[i][j] += 1
            elif winner == "B":
                wins_boot[j][i] += 1
            else:
                wins_boot[i][j] += 0.5
                wins_boot[j][i] += 0.5

        try:
            ratings_boot = fit_bradley_terry(wins_boot, total_boot)
            bootstrap_ratings.append(ratings_boot)
        except:
            continue  # Skip failed bootstrap samples

    bootstrap_ratings = np.array(bootstrap_ratings)

    # Compute confidence intervals (95%)
    ci_lower = np.percentile(bootstrap_ratings, 2.5, axis=0)
    ci_upper = np.percentile(bootstrap_ratings, 97.5, axis=0)

    # Compute rank statistics
    ranks = np.argsort(-ratings) + 1  # Higher rating = lower rank number

    # Bootstrap rank ranges
    bootstrap_ranks = np.argsort(-bootstrap_ratings, axis=1) + 1
    rank_lower = np.percentile(bootstrap_ranks, 2.5, axis=0)
    rank_upper = np.percentile(bootstrap_ranks, 97.5, axis=0)

    # Build results DataFrame
    results_df = pd.DataFrame({
        'Model': models,
        'Rating': ratings,
        'CI_lower': ci_lower,
        'CI_upper': ci_upper,
        'CI_width': ci_upper - ci_lower,
        'Rank': ranks,
        'Rank_lower': rank_lower.astype(int),
        'Rank_upper': rank_upper.astype(int)
    }).sort_values('Rating', ascending=False)

    results_df['Rank'] = range(1, len(results_df) + 1)

    return results_df


def compute_elo_ratings(results, initial_rating=1500, k_factor=32):
    """
    Compute Elo ratings for models based on pairwise comparisons.

    NOTE: This is kept for comparison, but Bradley-Terry is preferred.
    Bradley-Terry provides:
    - Statistical confidence intervals
    - Better handling of sparse data
    - Used by LMArena leaderboard

    Elo is a standard rating system that updates based on wins/losses.
    Higher rating = better performance.
    """
    # Get all unique models
    models = set()
    for r in results:
        models.add(r['model_a'])
        models.add(r['model_b'])

    # Initialize ratings
    ratings = {model: initial_rating for model in models}

    # Process each comparison
    for r in results:
        model_a = r['model_a']
        model_b = r['model_b']
        winner = r['final_winner_model']  # Now "A", "B", "Tie", or "Invalid_Bias"

        # Skip if position bias detected (unreliable)
        if r.get('bias_status', 'None') != 'None':
            continue

        # Expected scores (probability of winning)
        expected_a = 1 / (1 + 10 ** ((ratings[model_b] - ratings[model_a]) / 400))
        expected_b = 1 - expected_a

        # Actual scores: winner is "A"/"B"/"Tie" instead of model names
        if winner == "A":
            actual_a, actual_b = 1.0, 0.0
        elif winner == "B":
            actual_a, actual_b = 0.0, 1.0
        else:  # Tie
            actual_a, actual_b = 0.5, 0.5

        # Update ratings
        ratings[model_a] += k_factor * (actual_a - expected_a)
        ratings[model_b] += k_factor * (actual_b - expected_b)

    return ratings


def compute_win_matrix(results):
    """Create a win/loss/tie matrix between all models."""
    # Get all unique models
    models = set()
    for r in results:
        models.add(r['model_a'])
        models.add(r['model_b'])
    models = sorted(list(models))

    # Initialize matrix
    matrix = defaultdict(lambda: defaultdict(lambda: {'wins': 0, 'losses': 0, 'ties': 0, 'total': 0}))

    for r in results:
        # Skip if position bias detected
        if r.get('bias_status', 'None') != 'None':
            continue

        model_a = r['model_a']
        model_b = r['model_b']
        winner = r['final_winner_model']  # Now "A", "B", "Tie", or "Invalid_Bias"

        matrix[model_a][model_b]['total'] += 1
        matrix[model_b][model_a]['total'] += 1

        # Winner is "A"/"B"/"Tie" instead of model names
        if winner == "A":
            matrix[model_a][model_b]['wins'] += 1
            matrix[model_b][model_a]['losses'] += 1
        elif winner == "B":
            matrix[model_a][model_b]['losses'] += 1
            matrix[model_b][model_a]['wins'] += 1
        else:  # Tie
            matrix[model_a][model_b]['ties'] += 1
            matrix[model_b][model_a]['ties'] += 1

    return matrix, models


def compute_average_scores(results):
    """
    Compute average criterion scores for each model.

    llm_as_judge.py now outputs:
    - model_a_total_score, model_b_total_score (weighted sums, not averages)
    - No per-criterion scores in output (only total weighted scores)

    We can only compute total score statistics, not per-criterion breakdown.
    """
    model_scores = defaultdict(lambda: {'total': []})

    for r in results:
        score_a = r.get('model_a_total_score') or r.get('test_a_total', 0)
        score_b = r.get('model_b_total_score') or r.get('test_b_total', 0)

        model_scores[r['model_a']]['total'].append(score_a)
        model_scores[r['model_b']]['total'].append(score_b)

    # Compute averages
    avg_scores = {}
    for model, scores in model_scores.items():
        avg_scores[model] = {
            'total': np.mean(scores['total']),
            'total_std': np.std(scores['total']),
            'n_comparisons': len(scores['total'])
        }

    return avg_scores


def analyze_position_bias(results, stats_file):
    """Analyze position bias patterns."""
    bias_info = {
        'total': 0,
        'rate': 0.0,
        'by_pair': []
    }

    # Try to load from stats file first
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            stats = json.load(f)
            if 'bias_analysis' in stats:
                bias_info['total'] = stats['bias_analysis'].get('total_biased', 0)
                bias_info['rate'] = stats.get('position_bias_rate', 0.0)
                bias_info['by_pair'] = stats['bias_analysis'].get('biased_pairs', [])

    # Fallback: compute from results
    if bias_info['total'] == 0:
        biased = [r for r in results if r.get('bias_status', 'None') != 'None']
        bias_info['total'] = len(biased)
        bias_info['rate'] = len(biased) / len(results) if results else 0.0

        # Count by pair
        pair_counts = defaultdict(int)
        for r in biased:
            pair = (r['model_a'], r['model_b'])
            pair_counts[pair] += 1

        bias_info['by_pair'] = [
            {'model_a': k[0], 'model_b': k[1], 'bias_count': v}
            for k, v in sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)
        ]

    return bias_info


def shorten_model_name(model):
    """Shorten model names for display."""
    if "Pynguin" in model:
        return "Pynguin"
    elif "Qwen3" in model:
        temp = model.split('T=')[1] if 'T=' in model else "?"
        shot = "2S" if "Two-Shot" in model else "1S"
        return f"Qwen3-{shot}-{temp}"
    elif "Ministral-3-8B" in model:
        temp = model.split('T=')[1] if 'T=' in model else "?"
        shot = "2S" if "Two-Shot" in model else "1S"
        return f"M8B-{shot}-{temp}"
    elif "granite" in model:
        temp = model.split('T=')[1] if 'T=' in model else "?"
        shot = "2S" if "Two-Shot" in model else "1S"
        return f"granite-{shot}-{temp}"
    elif "Ministral-3-3B" in model:
        temp = model.split('T=')[1] if 'T=' in model else "?"
        shot = "2S" if "Two-Shot" in model else "1S"
        return f"M3B-{shot}-{temp}"
    elif "gemma" in model:
        temp = model.split('T=')[1] if 'T=' in model else "?"
        shot = "2S" if "Two-Shot" in model else "1S"
        return f"gemma-{shot}-{temp}"
    else:
        return model[:20]


def plot_bradley_terry_ratings(bt_df, output_dir):
    """Create Bradley-Terry rating plot with confidence intervals."""
    fig, ax = plt.subplots(figsize=(16, 9))  # Wider figure for more space

    # Use FULL MODEL NAMES (no abbreviations)
    y_pos = np.arange(len(bt_df))

    # Plot with error bars showing confidence intervals
    colors = sns.color_palette("viridis", len(bt_df))
    ax.barh(y_pos, bt_df['Rating'],
            xerr=[(bt_df['Rating'] - bt_df['CI_lower']),
                  (bt_df['CI_upper'] - bt_df['Rating'])],
            color=colors, alpha=0.7,
            error_kw={'linewidth': 2, 'ecolor': 'black', 'capsize': 5})

    # Set y-tick labels to FULL names
    ax.set_yticks(y_pos)
    ax.set_yticklabels(bt_df['Model'], fontsize=9)

    # Add rating values with confidence intervals at END of error bars (not at bar position)
    for i, (rating, ci_low, ci_high) in enumerate(zip(bt_df['Rating'], bt_df['CI_lower'], bt_df['CI_upper'])):
        # Place text at the right edge of the error bar + small offset
        text_x = ci_high + 10  # 10 points to the right of upper CI
        ax.text(text_x, i, f'{rating:.0f} [{ci_low:.0f}, {ci_high:.0f}]',
                va='center', ha='left', fontsize=8, fontweight='bold')

    # Baseline reference
    ax.axvline(1500, color='red', linestyle='--', linewidth=1, alpha=0.7, label='Baseline (1500)')

    ax.set_xlabel('Bradley-Terry Rating (Elo Scale)', fontsize=12, fontweight='bold')
    ax.set_title('Model Rankings by Bradley-Terry Rating\n(Error bars show 95% confidence intervals)',
                 fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    ax.grid(axis='x', alpha=0.3)

    # Extend x-axis to accommodate text labels
    x_max = bt_df['CI_upper'].max() + 100  # Extra space for labels
    ax.set_xlim(left=ax.get_xlim()[0], right=x_max)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'bradley_terry_ratings.png'), dpi=300, bbox_inches='tight')
    plt.close()


def plot_elo_ratings(elo_df, output_dir):
    """Create Elo rating bar plot."""
    fig, ax = plt.subplots(figsize=(14, 8))

    # Use FULL MODEL NAMES (no abbreviations)
    y_pos = np.arange(len(elo_df))

    # Plot
    colors = sns.color_palette("viridis", len(elo_df))
    bars = ax.barh(y_pos, elo_df['Elo Rating'], color=colors, alpha=0.7)

    # Set y-tick labels to FULL names
    ax.set_yticks(y_pos)
    ax.set_yticklabels(elo_df['Model'], fontsize=9)

    # Add value labels
    for i, rating in enumerate(elo_df['Elo Rating']):
        ax.text(rating, i, f' {rating:.0f}',
                va='center', fontsize=10, fontweight='bold')

    # Baseline reference
    ax.axvline(1500, color='red', linestyle='--', linewidth=1, alpha=0.7, label='Baseline (1500)')

    ax.set_xlabel('Elo Rating', fontsize=12, fontweight='bold')
    ax.set_title('Model Rankings by Elo Rating\n(Higher = Better Performance)', fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    ax.grid(axis='x', alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'elo_ratings.png'), dpi=300, bbox_inches='tight')
    plt.close()


def plot_criterion_scores(score_df, output_dir):
    """
    Create grouped bar chart for criterion scores.

    This uses a grouped bar chart instead of stacked bars for better scientific comparison:
    - Each criterion shown side-by-side allows direct comparison across models
    - Normalized scores (as % of max) make comparisons fair across different scales
    - Reference lines show maximum achievable scores
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    score_df = score_df.copy()

    # LEFT PLOT: Grouped bars for each criterion (normalized as % of max)
    criteria = ['Robustness', 'Assertions', 'Readability', 'Conciseness']
    max_scores = [2, 2, 2, 1]  # Maximum possible for each criterion

    # Normalize to percentage of maximum
    normalized_df = score_df.copy()
    for criterion, max_score in zip(criteria, max_scores):
        normalized_df[criterion] = (score_df[criterion] / max_score) * 100

    x = np.arange(len(criteria))
    width = 0.15  # Width of each bar
    colors = sns.color_palette("husl", len(score_df))

    # Plot grouped bars
    for i, (idx, row) in enumerate(normalized_df.iterrows()):
        positions = x + (i - len(score_df)/2 + 0.5) * width
        values = [row[criterion] for criterion in criteria]
        ax1.bar(positions, values, width, label=row['Model'], color=colors[i], alpha=0.8)

    # Reference line at 100%
    ax1.axhline(100, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Maximum (100%)')

    ax1.set_xlabel('Criterion', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Score (% of Maximum)', fontsize=12, fontweight='bold')
    ax1.set_title('Criterion Scores by Model (Normalized)\n' +
                  'Robustness & Assertions & Readability: max 2 pts | Conciseness: max 1 pt',
                  fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(criteria, fontsize=11, fontweight='bold')
    ax1.set_ylim(0, 110)
    ax1.legend(loc='lower right', fontsize=8, ncol=1)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # RIGHT PLOT: Total scores with error bars (standard deviation)
    y_pos = np.arange(len(score_df))
    total_scores = score_df['Total'].values
    std_scores = score_df['Std'].values

    bars = ax2.barh(y_pos, total_scores, xerr=std_scores,
                    color=colors, alpha=0.7,
                    error_kw={'linewidth': 2, 'ecolor': 'black', 'capsize': 5})

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(score_df['Model'], fontsize=9)
    ax2.set_xlabel('Total Score (0-7 scale)', fontsize=12, fontweight='bold')
    ax2.set_title('Total Scores with Standard Deviation\n(Error bars show ±1 SD)',
                  fontsize=12, fontweight='bold')
    ax2.axvline(7, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Maximum (7)')
    ax2.grid(axis='x', alpha=0.3, linestyle='--')
    ax2.legend(loc='lower right', fontsize=9)

    # Add value labels at end of error bars to avoid overlap
    for i, (score, std) in enumerate(zip(total_scores, std_scores)):
        # Place text at right edge of error bar + offset
        text_x = score + std + 0.2  # Position after error bar
        ax2.text(text_x, i, f'{score:.2f}±{std:.2f}',
                va='center', ha='left', fontsize=7, fontweight='bold')

    # Extend x-axis to accommodate text labels
    x_max = max(total_scores + std_scores) + 1.0  # Extra space for labels
    ax2.set_xlim(0, x_max)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'criterion_scores.png'), dpi=300, bbox_inches='tight')
    plt.close()


def plot_win_rates(record_df, output_dir):
    """Create win/loss/tie stacked bar chart."""
    fig, ax = plt.subplots(figsize=(14, 8))

    # Use FULL MODEL NAMES (no abbreviations)
    record_df = record_df.copy()

    # Calculate percentages
    record_df['Win %'] = record_df['Wins'] / record_df['Total'] * 100
    record_df['Loss %'] = record_df['Losses'] / record_df['Total'] * 100
    record_df['Tie %'] = record_df['Ties'] / record_df['Total'] * 100

    x = np.arange(len(record_df))
    width = 0.6

    # Stacked bars
    p1 = ax.bar(x, record_df['Win %'], width, label='Wins', color='#2ecc71')
    p2 = ax.bar(x, record_df['Tie %'], width, bottom=record_df['Win %'], label='Ties', color='#95a5a6')
    p3 = ax.bar(x, record_df['Loss %'], width, bottom=record_df['Win %'] + record_df['Tie %'],
                label='Losses', color='#e74c3c')

    ax.set_ylabel('Percentage', fontsize=12, fontweight='bold')
    ax.set_title('Win/Loss/Tie Distribution by Model', fontsize=14, fontweight='bold', pad=30)
    ax.set_xticks(x)
    ax.set_xticklabels(record_df['Model'], rotation=45, ha='right', fontsize=8)
    ax.legend(loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, 115)  # Extend y-axis to make room for labels

    # Add win rate labels (moved much higher to avoid overlap with title)
    for i, (wins, total) in enumerate(zip(record_df['Wins'], record_df['Total'])):
        win_rate = wins / total if total > 0 else 0
        ax.text(i, 108, f'{win_rate:.1%}', ha='center', va='bottom', fontweight='bold', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'win_loss_tie.png'), dpi=300, bbox_inches='tight')
    plt.close()


def plot_position_bias(bias_info, output_dir):
    """Create position bias analysis plot."""
    if not bias_info['by_pair']:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # 1. Overall bias rate
    labels = ['Unbiased', 'Position Bias\nDetected']
    sizes = [100 - bias_info['rate'] * 100, bias_info['rate'] * 100]
    colors = ['#2ecc71', '#e74c3c']
    explode = (0, 0.1)

    ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
            shadow=True, startangle=90, textprops={'fontsize': 12, 'fontweight': 'bold'})
    ax1.set_title('Position Bias Detection Rate', fontsize=14, fontweight='bold')

    # 2. Bias by model pair (top 5) - USE FULL NAMES
    if len(bias_info['by_pair']) > 0:
        top_pairs = bias_info['by_pair'][:5]
        # Use full model names, formatted more compactly
        pair_labels = [f"{p['model_a']}\nvs\n{p['model_b']}"
                       for p in top_pairs]
        counts = [p['bias_count'] for p in top_pairs]

        ax2.barh(pair_labels, counts, color='#e74c3c')
        ax2.set_xlabel('Bias Count', fontsize=12, fontweight='bold')
        ax2.set_title('Top 5 Model Pairs Affected by Position Bias', fontsize=14, fontweight='bold')
        ax2.grid(axis='x', alpha=0.3)
        ax2.tick_params(axis='y', labelsize=8)

        # Add count labels
        for i, count in enumerate(counts):
            ax2.text(count, i, f' {count}', va='center', fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'position_bias_analysis.png'), dpi=300, bbox_inches='tight')
    plt.close()


def save_text_table(df, filepath, title):
    """Save DataFrame as formatted text table."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write(title.center(100) + "\n")
        f.write("=" * 100 + "\n\n")
        f.write(df.to_string(index=False))
        f.write("\n\n" + "=" * 100 + "\n")


def load_stats_file(judge_dir):
    """Locate and load the evaluation statistics JSON file."""
    stats_file = None
    for filename in os.listdir(judge_dir):
        if (filename.startswith('evaluation_statistics_') or filename.startswith('stats_vfinal_')) and filename.endswith('.json'):
            stats_file = os.path.join(judge_dir, filename)
            break
    if not stats_file:
        stats_file = os.path.join(judge_dir, "judge_statistics_best_configs.json")

    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            return json.load(f), stats_file
    return None, stats_file


def build_elo_dataframe(unbiased_results):
    """Compute Elo ratings and return a sorted DataFrame."""
    elo_ratings = compute_elo_ratings(unbiased_results)
    elo_df = pd.DataFrame([
        {'Model': model, 'Elo Rating': rating, 'Rank': 0}
        for model, rating in elo_ratings.items()
    ]).sort_values('Elo Rating', ascending=False)
    elo_df['Rank'] = range(1, len(elo_df) + 1)
    return elo_df


def build_record_dataframe(unbiased_results):
    """Compute win/loss/tie records and return a sorted DataFrame."""
    matrix, models = compute_win_matrix(unbiased_results)
    records = []
    for model in models:
        total_wins = sum(matrix[model][other]['wins'] for other in models if other != model)
        total_losses = sum(matrix[model][other]['losses'] for other in models if other != model)
        total_ties = sum(matrix[model][other]['ties'] for other in models if other != model)
        total_games = total_wins + total_losses + total_ties
        records.append({
            'Model': model,
            'Wins': total_wins,
            'Losses': total_losses,
            'Ties': total_ties,
            'Total': total_games,
            'Win Rate': total_wins / total_games if total_games > 0 else 0,
        })
    return pd.DataFrame(records).sort_values('Win Rate', ascending=False)


def build_score_dataframe(results):
    """Compute average total scores and return a sorted DataFrame."""
    avg_scores = compute_average_scores(results)
    return pd.DataFrame([
        {'Model': model, 'Total': s['total'], 'Std': s['total_std'], 'N': s['n_comparisons']}
        for model, s in avg_scores.items()
    ]).sort_values('Total', ascending=False)


def compute_reliability_threshold(record_df, n_models, n_comparable_tasks):
    """
    Compute dynamic minimum comparison threshold for reliable Bradley-Terry rankings.

    A model's Bradley-Terry strength estimate is only reliable when it has participated
    in enough comparisons for the MLE to converge. Threshold = Q1 (25th percentile) of
    the comparison-count distribution: models below Q1 have participated in fewer
    comparisons than 75% of peers and are excluded from ranking claims.

    Returns a dict with threshold, excluded/included model lists, and supporting stats.
    """
    n_values = record_df['Total'].values.astype(float)
    q1 = float(np.percentile(n_values, 25))
    threshold = int(np.floor(q1))

    excluded_df = record_df[record_df['Total'] < threshold].copy()
    included_df = record_df[record_df['Total'] >= threshold].copy()

    return {
        'threshold': threshold,
        'n_models': n_models,
        'n_comparable_tasks': n_comparable_tasks,
        'max_theoretical': (n_models - 1) * n_comparable_tasks,
        'max_n': int(n_values.max()),
        'min_n': int(n_values.min()),
        'median_n': float(np.median(n_values)),
        'q1': q1,
        'excluded': excluded_df[['Model', 'Total']].to_dict('records'),
        'included': included_df[['Model', 'Total']].to_dict('records'),
        'n_excluded': len(excluded_df),
        'n_included': len(included_df),
    }


def generate_reliability_section(threshold_info):
    """Compact summary of the reliability threshold decision for the console report."""
    t = threshold_info
    lines = [
        f"Dynamic threshold (Q1 of comparison counts): N >= {t['threshold']}",
        f"Tournament: {t['n_models']} configurations, {t['n_comparable_tasks']} comparable tasks",
        f"Participation range: {t['min_n']}–{t['max_n']} comparisons (median {t['median_n']:.0f})",
        "",
        f"{'Configuration':<45s}  {'N':>5}  {'Status'}",
        "-" * 70,
    ]
    excluded_names = {m['Model'] for m in t['excluded']}
    all_models = t['excluded'] + t['included']
    all_models_sorted = sorted(all_models, key=lambda m: m['Total'])
    for m in all_models_sorted:
        status = "EXCLUDED (below Q1 — no ranking claim)" if m['Model'] in excluded_names else "retained"
        lines.append(f"  {m['Model']:<43s}  {m['Total']:>5}  {status}")
    lines += [
        "",
        f"Retained for ranking: {t['n_included']}/{t['n_models']} configurations",
        f"See bradley_terry_ratings_filtered.txt for the valid ranking.",
    ]
    return lines


def compile_key_findings(elo_df, score_df, record_df, bias_info):
    """Compile key findings into a list of text lines."""
    top_elo = elo_df.iloc[0]
    top_score = score_df.iloc[0]
    top_winrate = record_df.iloc[0]

    findings = [
        f"[ELO] Top model by Elo rating: {top_elo['Model']}",
        f"      Elo: {top_elo['Elo Rating']:.0f}",
        "",
        f"[SCORE] Top model by average score: {top_score['Model']}",
        f"        Score: {top_score['Total']:.2f} +/- {top_score['Std']:.2f}",
        "",
        f"[WIN RATE] Top model by win rate: {top_winrate['Model']}",
        f"           Win rate: {top_winrate['Win Rate']:.1%} ({top_winrate['Wins']}W-{top_winrate['Losses']}L-{top_winrate['Ties']}T)",
        "",
    ]

    if top_elo['Model'] == top_score['Model'] == top_winrate['Model']:
        findings.append(f"[*] Consistent winner across all metrics: {top_elo['Model']}")
    else:
        findings.extend([
            "[!] Different winners across metrics:",
            f"    Elo: {top_elo['Model']}",
            f"    Score: {top_score['Model']}",
            f"    Win rate: {top_winrate['Model']}",
        ])

    findings.extend([
        "",
        f"[BIAS] Position bias detected in {bias_info['rate']:.1%} of comparisons",
        "       This is expected and handled by double-pass methodology",
    ])
    return findings


def generate_text_report(stats, bias_info, elo_df, bt_df, record_df, score_df, findings, threshold_info=None):
    """Build the full analysis report as a single string."""
    lines = []

    def section(title):
        lines.append("")
        lines.append("=" * 100)
        lines.append(f"  {title}")
        lines.append("=" * 100)

    section("LLM-AS-JUDGE RESULTS ANALYSIS")

    # Overall statistics
    section("1. OVERALL STATISTICS")
    if stats:
        lines.append(f"Total comparisons: {stats['total_comparisons']}")
        if 'position_bias_detected' in stats:
            lines.append(f"Position bias detected: {stats['position_bias_detected']} ({stats['position_bias_rate']*100:.1f}%)")

        lines.append("")
        lines.append("Winner distribution:")
        for model, count in sorted(stats.get('winner_distribution', {}).items(), key=lambda x: x[1], reverse=True):
            pct = count / stats['total_comparisons'] * 100
            lines.append(f"  {model:50s}: {count:3d} ({pct:5.1f}%)")

        if 'pass_rate_statistics' in stats:
            lines.append("")
            lines.append("-" * 80)
            lines.append("PASS RATE STATISTICS (Selection Bias Check)")
            lines.append("-" * 80)
            lines.append(f"{'Model':<50s} {'Pass':<8s} {'Total':<8s} {'Pass Rate':<10s}")
            lines.append("-" * 80)
            pass_stats = stats['pass_rate_statistics']
            for model, stat in sorted(pass_stats.items(), key=lambda x: x[1]['pass_rate'], reverse=True):
                lines.append(f"{model:<50s} {stat['pass_count']:<8d} {stat['total_count']:<8d} {stat['pass_rate']:>9.1f}%")

            pass_counts = [s['pass_count'] for s in pass_stats.values()]
            if pass_counts:
                min_pass, max_pass = min(pass_counts), max(pass_counts)
                if max_pass > 0 and (max_pass - min_pass) / max_pass > 0.3:
                    lines.append(f"\nWARNING: Significant variation in pass counts: {min_pass}-{max_pass}")
                else:
                    lines.append(f"\nPass counts well-balanced: {min_pass}-{max_pass} tests (acceptable)")

    # Position bias
    section("2. POSITION BIAS ANALYSIS")
    lines.append(f"Total biased comparisons: {bias_info['total']} ({bias_info['rate']*100:.1f}%)")
    lines.append("")
    lines.append("Most affected model pairs:")
    for i, pair in enumerate(bias_info['by_pair'][:5], 1):
        lines.append(f"  {i}. {pair['model_a'][:40]:40s} vs {pair['model_b'][:40]:40s}: {pair['bias_count']} times")

    # Elo ratings
    section("3. ELO RATINGS (Higher = Better)")
    lines.append("Elo rating system: 1500 baseline, +32 per win, -32 per loss, +/-16 per tie")
    lines.append("")
    lines.append(elo_df.to_string(index=False))

    # Bradley-Terry ratings
    section("4. BRADLEY-TERRY RATINGS (RECOMMENDED)")
    lines.append("Same approach as LMArena leaderboard with 95% bootstrap confidence intervals")
    if threshold_info:
        lines.append(f"Note: configurations with N < {threshold_info['threshold']} comparisons (below Q1) "
                     f"are marked ⚠️ BELOW THRESHOLD and excluded from ranking claims.")
    lines.append("")
    if bt_df is not None:
        bt_display = bt_df[['Model', 'Rating', 'CI_lower', 'CI_upper', 'Rank', 'Rank_lower', 'Rank_upper']].copy()
        if threshold_info:
            excluded_names = {m['Model'] for m in threshold_info['excluded']}
            bt_display = bt_display.copy()
            bt_display['Model'] = bt_display['Model'].apply(
                lambda m: f"{m}  ⚠️ BELOW THRESHOLD" if m in excluded_names else m
            )
        lines.append(bt_display.to_string(index=False))
    else:
        lines.append("Could not compute (insufficient unbiased data)")

    # Win/Loss/Tie
    section("5. WIN/LOSS/TIE RECORD")
    lines.append(record_df.to_string(index=False))

    # Average scores
    section("6. AVERAGE TOTAL SCORES")
    lines.append(score_df.to_string(index=False))

    # Key findings
    section("7. KEY FINDINGS")
    lines.extend(findings)

    # Reliability threshold analysis
    if threshold_info:
        section("8. RELIABILITY THRESHOLD ANALYSIS")
        lines.extend(generate_reliability_section(threshold_info))

    return "\n".join(lines)


def save_all_outputs(output_dir, elo_df, bt_df, record_df, score_df, bias_info, findings, report_text, threshold_info=None):
    """Save all CSV, TXT, and PNG outputs to the output directory."""
    # CSV
    elo_df.to_csv(os.path.join(output_dir, "elo_ratings.csv"), index=False)
    if bt_df is not None:
        bt_df.to_csv(os.path.join(output_dir, "bradley_terry_ratings.csv"), index=False)
    record_df.to_csv(os.path.join(output_dir, "win_loss_record.csv"), index=False)
    score_df.to_csv(os.path.join(output_dir, "average_scores.csv"), index=False)

    # TXT tables
    save_text_table(elo_df, os.path.join(output_dir, "elo_ratings.txt"), "ELO RATINGS")
    if bt_df is not None:
        save_text_table(bt_df, os.path.join(output_dir, "bradley_terry_ratings.txt"), "BRADLEY-TERRY RATINGS (ALL)")
        if threshold_info:
            excluded_names = {m['Model'] for m in threshold_info['excluded']}
            bt_filtered = bt_df[~bt_df['Model'].isin(excluded_names)].copy()
            bt_filtered['Rank'] = range(1, len(bt_filtered) + 1)
            bt_filtered.to_csv(os.path.join(output_dir, "bradley_terry_ratings_filtered.csv"), index=False)
            save_text_table(
                bt_filtered,
                os.path.join(output_dir, "bradley_terry_ratings_filtered.txt"),
                f"BRADLEY-TERRY RATINGS (FILTERED: N >= {threshold_info['threshold']}, "
                f"{threshold_info['n_included']}/{threshold_info['n_models']} configurations)"
            )
    save_text_table(record_df, os.path.join(output_dir, "win_loss_record.txt"), "WIN/LOSS/TIE RECORDS")
    save_text_table(score_df, os.path.join(output_dir, "average_scores.txt"), "AVERAGE TOTAL SCORES")

    # Key findings
    with open(os.path.join(output_dir, "key_findings.txt"), 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("KEY FINDINGS - LLM-AS-JUDGE EVALUATION".center(100) + "\n")
        f.write("=" * 100 + "\n\n")
        f.write("\n".join(findings))
        f.write("\n\n" + "=" * 100 + "\n")

    # Full report
    with open(os.path.join(output_dir, "full_report.txt"), 'w', encoding='utf-8') as f:
        f.write(report_text)

    # Plots
    plot_elo_ratings(elo_df, output_dir)
    if bt_df is not None:
        plot_bradley_terry_ratings(bt_df, output_dir)
    plot_win_rates(record_df, output_dir)
    plot_position_bias(bias_info, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Analyze LLM-as-Judge Results")
    parser.add_argument("--judge_dir", type=str, default="TestEval/predictions_judgellm",
                        help="Directory containing judge results")
    parser.add_argument("--output_dir", type=str, default="step4_evaluation/llm_evaluation",
                        help="Output directory for analysis")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Load data
    results = load_judge_results(args.judge_dir)
    unbiased_results = [r for r in results if r.get('bias_status', 'None') == 'None']
    stats, stats_file = load_stats_file(args.judge_dir)

    logger.info(f"Loaded {len(results)} comparisons ({len(unbiased_results)} unbiased)")

    # Compute all analyses
    bias_info = analyze_position_bias(results, stats_file)
    elo_df = build_elo_dataframe(unbiased_results)
    bt_df = compute_bradley_terry_ratings(unbiased_results, n_bootstrap=1000)
    record_df = build_record_dataframe(unbiased_results)
    score_df = build_score_dataframe(results)

    # Reliability threshold: dynamic Q1-based minimum comparison count
    n_comparable_tasks = len(set(r['task_id'] for r in unbiased_results))
    n_models = len(record_df)
    threshold_info = compute_reliability_threshold(record_df, n_models, n_comparable_tasks)
    logger.info(f"Reliability threshold: N >= {threshold_info['threshold']} "
                f"(Q1 of comparison counts, {threshold_info['n_included']}/{n_models} configurations retained)")
    if threshold_info['excluded']:
        for m in threshold_info['excluded']:
            logger.warning(f"BELOW THRESHOLD: {m['Model']} (N={m['Total']}) — excluded from ranking claims")

    findings = compile_key_findings(elo_df, score_df, record_df, bias_info)

    # Generate report and save everything
    report = generate_text_report(stats, bias_info, elo_df, bt_df, record_df, score_df, findings, threshold_info)
    save_all_outputs(args.output_dir, elo_df, bt_df, record_df, score_df, bias_info, findings, report, threshold_info)

    # Print report to console
    print(report)
    logger.info(f"All outputs saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
