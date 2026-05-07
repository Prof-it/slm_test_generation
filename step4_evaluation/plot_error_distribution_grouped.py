"""
Standalone script to regenerate error_distribution.png with temperatures
grouped into 0.4-wide bins: [0.0-0.2], [0.4-0.6], [0.8-1.0].

Does NOT modify create_summary_report.py.
Output: step4_evaluation/temperature_3_plots/error_distribution_grouped.png
"""

import glob
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).parent))
from evaluation_utils import parse_filename_metadata

BENCHMARK_SIZE = 210
DATA_DIR = Path(__file__).parent.parent / "evaluation_results_temperature_3"
OUTPUT_DIR = Path(__file__).parent / "temperature_3_plots"

TEMP_BIN_MAP = {0.0: "T=[0.0-0.2]", 0.2: "T=[0.0-0.2]",
                0.4: "T=[0.4-0.6]", 0.6: "T=[0.4-0.6]",
                0.8: "T=[0.8-1.0]", 1.0: "T=[0.8-1.0]"}
BIN_ORDER = ["T=[0.0-0.2]", "T=[0.4-0.6]", "T=[0.8-1.0]"]


def load_error_data(data_dir):
    files = glob.glob(str(data_dir / "**" / "*_evaluated.jsonl"), recursive=True)
    rows = []
    for filepath in files:
        model, mode, temp = parse_filename_metadata(filepath, clean_name=True)
        if np.isnan(temp):
            continue  # skip Pynguin
        if model.lower().startswith("pynguin"):
            continue

        task_entries = {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    task_id = entry.get("task_num")
                    if not task_id:
                        continue
                    task_entries.setdefault(task_id, []).append(entry)
        except Exception:
            continue

        assert_err = set()
        runtime_err = set()
        compile_err = set()
        no_code = set()
        timeout = set()

        for task_id, entries in task_entries.items():
            statuses = [e.get("status") for e in entries]
            if "Pass" in statuses:
                continue
            first = statuses[0]
            if first == "Assertion Error":
                assert_err.add(task_id)
            elif first == "Runtime Error":
                runtime_err.add(task_id)
            elif first in ("Pytest Error", "Syntax Error"):
                compile_err.add(task_id)
            elif first == "No Code":
                no_code.add(task_id)
            elif first == "Timeout":
                timeout.add(task_id)

        rows.append({
            "Model": model,
            "Mode": mode,
            "Temperature": temp,
            "Assert": len(assert_err),
            "Runtime": len(runtime_err),
            "Syntax": len(compile_err),
            "NoCode": len(no_code),
            "Timeout": len(timeout),
        })
    return rows


def main():
    print(f"Scanning {DATA_DIR} ...")
    rows = load_error_data(DATA_DIR)
    if not rows:
        print("ERROR: No data found.")
        return

    df = pd.DataFrame(rows)

    # Average across runs (same file across run_1/run_2/run_3 → same model/mode/temp)
    error_cols = ["Assert", "Runtime", "Syntax", "NoCode", "Timeout"]
    df_avg = df.groupby(["Model", "Mode", "Temperature"])[error_cols].mean().reset_index()

    # Map each temperature to a bin
    df_avg["TempBin"] = df_avg["Temperature"].map(TEMP_BIN_MAP)
    df_avg = df_avg.dropna(subset=["TempBin"])

    # Average within each bin
    df_grouped = (
        df_avg.groupby(["Model", "Mode", "TempBin"])[error_cols]
        .mean()
        .reset_index()
    )

    # Sort: model name, then mode, then bin order
    df_grouped["_bin_order"] = df_grouped["TempBin"].map({b: i for i, b in enumerate(BIN_ORDER)})
    df_grouped = df_grouped.sort_values(["Model", "Mode", "_bin_order"])

    # Build display label
    df_grouped["Label"] = (
        df_grouped["Model"] + " (" + df_grouped["Mode"] + ", " + df_grouped["TempBin"] + ")"
    )

    error_labels = ["Syntax", "Runtime", "Assert", "NoCode", "Timeout"]
    display_labels = ["Syntax", "Runtime", "Assertion", "No Code", "Timeout"]
    rename_map = dict(zip(error_labels, display_labels))
    df_grouped = df_grouped.rename(columns=rename_map)

    heatmap_data = df_grouped.set_index("Label")[display_labels]

    vmax = BENCHMARK_SIZE * 0.5
    fig_height = max(8, len(heatmap_data) * 0.55)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        linewidths=0.5,
        linecolor="gray",
        cbar_kws={"label": f"Avg. Failed Tasks per Run (Max={BENCHMARK_SIZE})"},
        vmin=0,
        vmax=vmax,
        square=False,
        cbar=True,
        ax=ax,
    )

    ax.set_title("Failure Mode Analysis (Temperatures Grouped by ±0.2)", fontsize=13, weight="bold", pad=10)
    ax.set_ylabel("Model Configuration (Grouped by Model → Mode → Temp Range)", fontsize=11)
    ax.set_xlabel("Error Type (by Severity)", fontsize=11)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    plt.setp(ax.get_yticklabels(), rotation=0, fontsize=10, fontweight="bold")

    footnote = (
        f"Values = avg. unique tasks failed per run (averaged over T bins of width 0.2). "
        f"Max possible = {BENCHMARK_SIZE}. Pynguin excluded. "
        f"Color scale: 0 (white) → {vmax:.0f} (dark red, 50% failure rate)."
    )
    fig.text(0.5, 0.0, footnote, ha="center", va="top", fontsize=9, style="italic")

    fig.tight_layout()
    out_path = OUTPUT_DIR / "error_distribution_grouped.png"
    fig.savefig(str(out_path), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  >> Saved {out_path}")


if __name__ == "__main__":
    main()
