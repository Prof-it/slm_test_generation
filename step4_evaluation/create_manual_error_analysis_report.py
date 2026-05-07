"""
Generate thesis tables from manual error analysis CSVs and evaluation data.

Produces three tables:
  - Table 3: Average Assertions per Test and Pass@1 Rates
  - Table 4: Failure Mode Distribution (Manual Analysis)
  - Table 5: Failure Categories by Dataset

Data sources:
  - Prediction JSONL files  → assertion counts
  - Evaluation JSONL files  → pass@1 rates  (task-level dedup applied)
  - Manual error CSVs       → root cause categories, failure groupings

Output: error_analysis_output/thesis_tables.txt

Usage:
    python step4_evaluation/create_manual_error_analysis_report.py
    python step4_evaluation/create_manual_error_analysis_report.py --datasets realworld
"""

import csv
import json
import re
import glob
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from tabulate import tabulate

from evaluation_utils import parse_filename_metadata

# ── Paths ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "error_analysis_output"

DATASETS = {
    "testeval": {
        "predictions": "TestEval/predictions_initial",
        "evaluations": "evaluation_results_initial",
        "n_tasks": 210,
        "label": "TestEval",
    },
    "realworld": {
        "predictions": "TestEval/predictions_realworld",
        "evaluations": "evaluation_results_realworld",
        "n_tasks": 50,
        "label": "Real-World",
    },
}

CSV_FILES = {
    "testeval_initial": {
        "file": "testeval_initial_failure_analysis.csv",
        "label": "TestEval Initial (T=0.2)",
    },
    "testeval_temp": {
        "file": "testeval_temperature_failure_analysis.csv",
        "label": "TestEval Temperature (T=0.4/0.8)",
    },
    "realworld": {
        "file": "realworld_failure_analysis.csv",
        "label": "Real-World",
    },
}

# ── Root cause normalisation ────────────────────────────────────────────────

ROOT_CAUSE_SYNONYMS = {
    "HallucinatedAPI": "APIHallucination",
    "error": "Unknown",
    "N/A": "Unknown",
}

# Grouping individual root causes into high-level failure categories
CATEGORY_GROUPS = {
    "Logic": ["IncorrectAssertion"],
    "Environmental": [
        "MissingDefinition", "MissingImport", "EnvironmentMismatch",
        "Runtime", "MalformedSyntax", "MockingError",
    ],
    "Semantic": ["SemanticMisunderstanding", "APIHallucination"],
    "Other": ["Unknown", "ModelFailure", "HallucinatedPath", "NoCode"],
}

# Reverse map: root_cause -> category
_CAUSE_TO_CATEGORY = {}
for cat, causes in CATEGORY_GROUPS.items():
    for c in causes:
        _CAUSE_TO_CATEGORY[c] = cat


def categorise(root_cause: str) -> str:
    return _CAUSE_TO_CATEGORY.get(root_cause, "Other")


def normalise_root_cause(raw: str) -> str:
    raw = raw.strip()
    return ROOT_CAUSE_SYNONYMS.get(raw, raw)


# ── Table 3: Assertions & Pass@1 ───────────────────────────────────────────

def count_asserts_in_code(code: str) -> int:
    if not code:
        return 0
    return len(re.findall(r'\bassert\b', code))


def compute_assertion_counts(pred_dir: Path) -> dict:
    """Return {(model, mode, temp_str): avg_asserts_per_test}."""
    config_counts = defaultdict(lambda: [0, 0])  # [total_asserts, total_tests]
    for run_dir in sorted(glob.glob(str(pred_dir / "run_*"))):
        for filepath in sorted(glob.glob(f"{run_dir}/*.jsonl")):
            model, mode, temp = parse_filename_metadata(filepath, clean_name=True)
            temp_str = f"T={temp}" if not np.isnan(temp) else "N/A"
            key = (model, mode, temp_str)
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line)
                    tests = entry.get('tests', {})
                    if isinstance(tests, dict):
                        for _tl, tdata in tests.items():
                            code = tdata.get('test_code', '') if isinstance(tdata, dict) else str(tdata)
                            config_counts[key][0] += count_asserts_in_code(code)
                            config_counts[key][1] += 1
    return {k: (v[0] / v[1] if v[1] else 0.0) for k, v in config_counts.items()}


def compute_pass_rates(eval_dir: Path, n_tasks: int) -> dict:
    """Return {(model, mode, temp_str): mean_pass_rate_%} with task-level dedup."""
    config_runs = defaultdict(list)
    for run_dir in sorted(glob.glob(str(eval_dir / "run_*"))):
        for filepath in sorted(glob.glob(f"{run_dir}/*_evaluated.jsonl")):
            model, mode, temp = parse_filename_metadata(filepath, clean_name=True)
            temp_str = f"T={temp}" if not np.isnan(temp) else "N/A"
            key = (model, mode, temp_str)
            task_entries = {}
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        entry = json.loads(line)
                        tid = entry.get('task_num')
                        if not tid:
                            continue
                        task_entries.setdefault(tid, []).append(entry)
            except Exception:
                continue
            passed = sum(
                1 for entries in task_entries.values()
                if any(e.get('status') == 'Pass' for e in entries)
            )
            config_runs[key].append(passed / n_tasks * 100)
    return {k: np.mean(v) for k, v in config_runs.items()}


def best_config_per_model(pass_rates: dict, assertion_avgs: dict) -> dict:
    """Pick highest-Pass@1 config per model. Returns {model: {...}}."""
    model_configs = defaultdict(list)
    for (model, mode, temp_str), pr in pass_rates.items():
        avg_a = assertion_avgs.get((model, mode, temp_str), 0.0)
        model_configs[model].append({
            "mode": mode, "temp": temp_str,
            "pass1": pr, "avg_asserts": avg_a,
        })
    best = {}
    for model, configs in model_configs.items():
        configs.sort(key=lambda c: c["pass1"], reverse=True)
        best[model] = configs[0]
    return best


def build_table3(dataset_keys) -> str:
    """Build Table 3 text."""
    lines = []
    w = lines.append

    w("=" * 90)
    w(" TABLE 3: Average Assertions per Test and Pass@1 Rates")
    w("=" * 90)
    w("")

    rows_summary = []
    rows_detail = []

    for ds_key in dataset_keys:
        cfg = DATASETS.get(ds_key)
        if not cfg:
            continue
        pred_dir = ROOT / cfg["predictions"]
        eval_dir = ROOT / cfg["evaluations"]
        label = cfg["label"]
        n_tasks = cfg["n_tasks"]
        if not pred_dir.exists() or not eval_dir.exists():
            w(f"WARNING: directories for {ds_key} not found, skipping.")
            continue

        assertion_avgs = compute_assertion_counts(pred_dir)
        pass_rates = compute_pass_rates(eval_dir, n_tasks)
        best = best_config_per_model(pass_rates, assertion_avgs)

        pynguin_key = "Pynguin (Baseline)"
        slm_models = {m: v for m, v in best.items() if m != pynguin_key}

        if pynguin_key in best:
            p = best[pynguin_key]
            rows_summary.append([
                "Pynguin", label,
                f"{p['avg_asserts']:.2f}", f"{p['pass1']:.2f}%",
            ])
        if slm_models:
            avg_a = np.mean([v["avg_asserts"] for v in slm_models.values()])
            avg_p = np.mean([v["pass1"] for v in slm_models.values()])
            rows_summary.append([
                f"SLMs (avg, n={len(slm_models)})", label,
                f"{avg_a:.2f}", f"{avg_p:.2f}%",
            ])

        for model in sorted(slm_models, key=lambda m: slm_models[m]["pass1"], reverse=True):
            v = slm_models[model]
            rows_detail.append([
                model, label, f"{v['mode']}, {v['temp']}",
                f"{v['avg_asserts']:.2f}", f"{v['pass1']:.2f}%",
            ])

    w("Summary:")
    w(tabulate(
        rows_summary,
        headers=["Generator", "Dataset", "Avg Asserts/Test", "Best Pass@1"],
        tablefmt="github",
        colalign=("left", "left", "right", "right"),
    ))
    w("")
    w("Per-Model Breakdown (Best Config):")
    w(tabulate(
        rows_detail,
        headers=["Model", "Dataset", "Best Config", "Avg Asserts/Test", "Pass@1"],
        tablefmt="github",
        colalign=("left", "left", "left", "right", "right"),
    ))
    w("")
    return "\n".join(lines)


# ── Table 4 & 5: Manual error analysis ──────────────────────────────────────

def load_csv_rows(path: Path) -> list:
    """Load a manually-reviewed CSV and normalise key fields."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_cause = (row.get("root_cause_category") or "").strip()
            row["root_cause"] = normalise_root_cause(raw_cause)
            row["category"] = categorise(row["root_cause"]) if row["root_cause"] else ""
            rows.append(row)
    return rows


def build_table4(csv_configs) -> str:
    """Build Table 4: Failure Mode Distribution per dataset."""
    lines = []
    w = lines.append

    w("=" * 90)
    w(" TABLE 4: Failure Mode Distribution (Manual Analysis)")
    w("=" * 90)
    w("")

    for key, cfg in csv_configs.items():
        path = OUTPUT_DIR / cfg["file"]
        if not path.exists():
            w(f"WARNING: {path.name} not found, skipping.")
            continue

        rows = load_csv_rows(path)
        label = cfg["label"]

        # Optionally filter to SLMs only for real-world
        is_realworld = "realworld" in key
        if is_realworld:
            slm_rows = [r for r in rows if "pynguin" not in r.get("model", "").lower()]
            pyng_rows = [r for r in rows if "pynguin" in r.get("model", "").lower()]
        else:
            slm_rows = rows
            pyng_rows = []

        # SLM table
        labeled = [r for r in slm_rows if r["root_cause"]]
        n_labeled = len(labeled)
        cause_counts = Counter(r["root_cause"] for r in labeled)

        subtitle = f"SLMs only, N={n_labeled} labeled" if is_realworld else f"N={n_labeled}"
        w(f"--- {label} ({subtitle}) ---")
        w("")
        table_rows = []
        for cause, count in cause_counts.most_common():
            pct = f"{100.0 * count / n_labeled:.1f}%" if n_labeled else "0.0%"
            table_rows.append([cause, count, pct])
        w(tabulate(
            table_rows,
            headers=["Root Cause", "Count", "%"],
            tablefmt="github",
            colalign=("left", "right", "right"),
        ))
        w("")

        # Pynguin sub-table for real-world
        if pyng_rows:
            pyng_labeled = [r for r in pyng_rows if r["root_cause"]]
            n_pyng = len(pyng_labeled)
            pyng_counts = Counter(r["root_cause"] for r in pyng_labeled)
            w(f"--- {label} — Pynguin only (N={n_pyng}) ---")
            w("")
            pyng_table = []
            for cause, count in pyng_counts.most_common():
                pct = f"{100.0 * count / n_pyng:.1f}%" if n_pyng else "0.0%"
                pyng_table.append([cause, count, pct])
            w(tabulate(
                pyng_table,
                headers=["Root Cause", "Count", "%"],
                tablefmt="github",
                colalign=("left", "right", "right"),
            ))
            w("")

    return "\n".join(lines)


def build_table5(csv_configs) -> str:
    """Build Table 5: Failure Categories (grouped) by Dataset."""
    lines = []
    w = lines.append

    w("=" * 90)
    w(" TABLE 5: Failure Categories by Dataset")
    w("=" * 90)
    w("")

    category_order = ["Logic", "Environmental", "Semantic", "Other"]

    # Collect per-dataset grouped counts for the comparison table
    dataset_results = []
    for key, cfg in csv_configs.items():
        path = OUTPUT_DIR / cfg["file"]
        if not path.exists():
            continue
        rows = load_csv_rows(path)
        label = cfg["label"]

        is_realworld = "realworld" in key
        if is_realworld:
            rows = [r for r in rows if "pynguin" not in r.get("model", "").lower()]
            label += " (SLMs)"

        labeled = [r for r in rows if r["root_cause"]]
        n = len(labeled)
        cat_counts = Counter(r["category"] for r in labeled)
        dataset_results.append((label, n, cat_counts))

    # Build comparison table
    header = ["Category"] + [f"{lbl} (N={n})" for lbl, n, _ in dataset_results]
    table_rows = []
    for cat in category_order:
        row = [cat]
        for _lbl, n, counts in dataset_results:
            c = counts.get(cat, 0)
            pct = f"{100.0 * c / n:.1f}%" if n else "0.0%"
            row.append(f"{c} ({pct})")
        table_rows.append(row)

    # Env/Logic ratio row
    ratio_row = ["Env/Logic Ratio"]
    for _lbl, _n, counts in dataset_results:
        logic = counts.get("Logic", 0)
        env = counts.get("Environmental", 0)
        ratio = f"{env / logic:.2f}" if logic > 0 else "N/A"
        ratio_row.append(ratio)
    table_rows.append(ratio_row)

    w(tabulate(
        table_rows,
        headers=header,
        tablefmt="github",
        colalign=("left",) + ("right",) * len(dataset_results),
    ))
    w("")

    # Category composition key
    w("Category composition:")
    for cat, causes in CATEGORY_GROUPS.items():
        w(f"  {cat}: {', '.join(causes)}")
    w("")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate thesis tables (3, 4, 5) from evaluation data and manual error CSVs"
    )
    parser.add_argument(
        "--datasets", nargs="+", default=["testeval", "realworld"],
        choices=list(DATASETS.keys()),
        help="Datasets for Table 3 (default: both)",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sections = []

    # Table 3
    print("Computing Table 3 (assertions & pass rates)...")
    sections.append(build_table3(args.datasets))

    # Tables 4 & 5 always use all available CSVs
    print("Computing Table 4 (failure mode distribution)...")
    sections.append(build_table4(CSV_FILES))

    print("Computing Table 5 (failure categories by dataset)...")
    sections.append(build_table5(CSV_FILES))

    report = "\n".join(sections)

    out_path = OUTPUT_DIR / "thesis_tables.txt"
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {out_path}")

    # Also print to console
    print()
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()
