"""
Standalone script to generate the two Results-section figures requested for the
revised paper: the RQ2 "CoT paradox" chart and the RQ3 "reality gap" chart.

Computes every value directly from the evaluated JSONL result files -- nothing
here is hand-typed, so the figures stay reproducible if the underlying results
change.

Does NOT modify create_summary_report.py.

Output:
    paper/v2/figures/p1_cot_paradox.png
    paper/v2/figures/p2_reality_gap.png

Usage:
    python step4_evaluation/create_paper_rq_charts.py
"""

import glob
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIRST_EXP_DIR = ROOT / "evaluation_results" / "first_experiment" / "run_1"
SECOND_EXP_GLOB = str(ROOT / "evaluation_results" / "second_experiment" / "run_1" / "tier_*" / "*_evaluated.jsonl")
DATASET_PATH = ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl"
FIG_DIR = ROOT / "paper" / "v2" / "figures"

MODEL_ORDER = [
    "Qwen3-4B-Thinking-2507",
    "Qwen3.5-4B",
    "gemma-4-E4B-it",
    "granite-4.0-micro",
    "Ministral-3-3B-Reasoning-2512",
]
MODEL_COLORS = {
    "Qwen3-4B-Thinking-2507": "#d35400",
    "Qwen3.5-4B": "#2ecc71",
    "gemma-4-E4B-it": "#e74c3c",
    "granite-4.0-micro": "#3498db",
    "Ministral-3-3B-Reasoning-2512": "#e67e22",
}


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pass_rate(records):
    if not records:
        return float("nan")
    return sum(1 for r in records if r.get("status") == "Pass") / len(records) * 100.0


def model_from_stem(stem):
    return stem.replace("linecov2_", "").replace("linecov_", "").split("_temp")[0]


def build_cot_paradox_chart():
    """RQ2: Experiment A (TestEval) -- Pass@1 grouped by model, Single-call vs Two-stage."""
    files = sorted(glob.glob(str(FIRST_EXP_DIR / "*_evaluated.jsonl")))
    if not files:
        raise RuntimeError(f"No evaluated files found under {FIRST_EXP_DIR}")

    single, two_stage = {}, {}
    for f in files:
        stem = Path(f).stem.replace("_evaluated", "")
        model = model_from_stem(stem)
        rate = pass_rate(load_jsonl(f))
        if stem.startswith("linecov2_"):
            two_stage[model] = rate
        else:
            single[model] = rate

    missing = [m for m in MODEL_ORDER if m not in single or m not in two_stage]
    if missing:
        raise RuntimeError(f"Missing single-call or two-stage results for: {missing}")

    x = list(range(len(MODEL_ORDER)))
    width = 0.35
    colors = [MODEL_COLORS[m] for m in MODEL_ORDER]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_single = ax.bar([i - width / 2 for i in x], [single[m] for m in MODEL_ORDER], width,
                          label="Single-call", color=colors, edgecolor="black")
    bars_two = ax.bar([i + width / 2 for i in x], [two_stage[m] for m in MODEL_ORDER], width,
                       label="Two-stage", color=colors, edgecolor="black", hatch="//")

    for bar in bars_single:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{bar.get_height():.1f}", ha="center", fontsize=9)
    for bar in bars_two:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{bar.get_height():.1f}", ha="center", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(MODEL_ORDER, rotation=20, ha="right")
    ax.set_ylabel("Pass@1 (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Experiment A (TestEval, N=210): Single-call vs. Two-stage Pass@1")
    ax.legend(title="Pipeline")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "p1_cot_paradox.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved {out}")


def load_task_meta():
    """task_num -> (dependency_level, leaked), keeping the first occurrence of any
    duplicate task_num (matches the dedup rule used elsewhere in the paper)."""
    meta = {}
    for row in load_jsonl(DATASET_PATH):
        tn = str(row["task_num"])
        if tn in meta:
            continue
        meta[tn] = (row["dependency_level"], row["leaked"])
    return meta


def build_reality_gap_chart():
    """RQ3: Experiment B (RealWorldTests-Py v2) -- pooled Pass@1 by dependency
    level (L0-L3) and by recency pool (historical/leaked vs. recent/unleaked),
    pooled across all 30 model x pipeline x tier configurations."""
    meta = load_task_meta()
    files = sorted(glob.glob(SECOND_EXP_GLOB))
    if not files:
        raise RuntimeError(f"No evaluated files found matching {SECOND_EXP_GLOB}")

    level_counts = defaultdict(lambda: [0, 0])      # level -> [n_pass, n_total]
    recency_counts = defaultdict(lambda: [0, 0])    # pool -> [n_pass, n_total]

    for f in files:
        for r in load_jsonl(f):
            tn = str(r.get("task_num"))
            if tn not in meta:
                continue
            level, leaked = meta[tn]
            ok = 1 if r.get("status") == "Pass" else 0
            level_counts[level][0] += ok
            level_counts[level][1] += 1
            pool = "Historical" if leaked else "Recent"
            recency_counts[pool][0] += ok
            recency_counts[pool][1] += 1

    level_order = ["L0", "L1", "L2", "L3"]
    missing_levels = [l for l in level_order if level_counts[l][1] == 0]
    if missing_levels:
        raise RuntimeError(f"No pooled records found for dependency level(s): {missing_levels}")
    level_rates = [level_counts[l][0] / level_counts[l][1] * 100.0 for l in level_order]
    level_ns = [level_counts[l][1] for l in level_order]

    recency_order = ["Historical", "Recent"]
    missing_pools = [p for p in recency_order if recency_counts[p][1] == 0]
    if missing_pools:
        raise RuntimeError(f"No pooled records found for recency pool(s): {missing_pools}")
    recency_rates = [recency_counts[p][0] / recency_counts[p][1] * 100.0 for p in recency_order]
    recency_ns = [recency_counts[p][1] for p in recency_order]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))

    ax = axes[0]
    bars = ax.bar(level_order, level_rates,
                   color=["#4E79A7", "#F28E2B", "#59A14F", "#E15759"], edgecolor="black")
    for bar, rate, n in zip(bars, level_rates, level_ns):
        ax.text(bar.get_x() + bar.get_width() / 2, rate + 1, f"{rate:.1f}%\n(n={n})",
                 ha="center", fontsize=9)
    ax.set_ylabel("Pooled Pass@1 (%)")
    ax.set_title("(a) Pass@1 by Dependency Level")
    ax.set_ylim(0, max(level_rates) + 12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    ax = axes[1]
    bars = ax.bar(recency_order, recency_rates, color=["#4E79A7", "#F28E2B"], edgecolor="black")
    for bar, rate, n in zip(bars, recency_rates, recency_ns):
        ax.text(bar.get_x() + bar.get_width() / 2, rate + 1, f"{rate:.1f}%\n(n={n})",
                 ha="center", fontsize=9)
    ax.set_ylabel("Pooled Pass@1 (%)")
    ax.set_title("(b) Pass@1 by Recency Pool (contamination-risk proxy)")
    ax.set_ylim(0, max(recency_rates) + 12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle("Experiment B (RealWorldTests-Py v2, 299 unique tasks): The Reality Gap",
                  fontsize=13, weight="bold")
    fig.tight_layout()

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "p2_reality_gap.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved {out}")


if __name__ == "__main__":
    build_cot_paradox_chart()
    build_reality_gap_chart()
