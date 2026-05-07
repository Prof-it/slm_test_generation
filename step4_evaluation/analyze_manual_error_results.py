"""
Analyze Manually Reviewed Error Analysis CSVs

Reads the manually-filled CSVs from error_analysis_output/ and produces a
structured summary report grouped by:
  1. Dataset (TestEval Initial, TestEval Temperature, Real-World)
  2. Model name
  3. Root cause category

For each model the report includes:
  - Root cause distribution (counts + percentages)
  - Proximity-to-success breakdown
  - Recurring failure patterns with example specific_issues
  - Cross-model comparison tables

Output: Markdown report + console summary.

Usage:
    python step4_evaluation/analyze_manual_error_results.py
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict, Counter


# Normalize synonymous root-cause labels that differ across datasets
ROOT_CAUSE_SYNONYMS = {
    "HallucinatedAPI": "APIHallucination",  # TestEval used HallucinatedAPI
    "error": "Unknown",                     # non-descriptive
    "N/A": "Unknown",                       # non-descriptive
}

# Values that explicitly mean "not recurring"
RECURRING_NEGATIVE = {"", "NO", "N/A", "FALSE", "0"}


# Data loading
def load_csv(path):
    """Load a manually-reviewed CSV and return list of row dicts."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize recurring_pattern to boolean:
            # Any non-empty value that isn't explicitly negative is treated as
            # recurring (catches free-text notes like "Scope issue; ...")
            recur_raw = (row.get("recurring_pattern") or "").strip()
            row["is_recurring"] = recur_raw.upper() not in RECURRING_NEGATIVE
            # Keep the raw text for recurring notes
            row["recurring_raw"] = recur_raw
            # Normalize proximity
            row["proximity"] = (row.get("proximity_to_success") or "").strip().lower()
            # Normalize root cause (apply synonym mapping)
            raw_cause = (row.get("root_cause_category") or "").strip()
            row["root_cause"] = ROOT_CAUSE_SYNONYMS.get(raw_cause, raw_cause)
            rows.append(row)
    return rows


# Analysis helpers
PROXIMITY_ORDER = ["high", "near", "moderate", "low", "far"]


def proximity_sort_key(val):
    val = val.lower()
    if val in PROXIMITY_ORDER:
        return PROXIMITY_ORDER.index(val)
    return len(PROXIMITY_ORDER)


def analyze_dataset(rows, dataset_label):
    """Analyze a single dataset's rows and return a structured dict."""
    # Group by model
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)

    analysis = {
        "label": dataset_label,
        "total": len(rows),
        "models": {},
    }

    for model, model_rows in sorted(by_model.items()):
        root_cause_counts = Counter(r["root_cause"] for r in model_rows if r["root_cause"])
        proximity_counts = Counter(r["proximity"] for r in model_rows if r["proximity"])
        recurring_rows = [r for r in model_rows if r["is_recurring"]]

        # Collect recurring issues with their specific_issue text
        recurring_issues = []
        for r in recurring_rows:
            issue_text = (r.get("specific_issue") or "").strip()
            cause = r["root_cause"]
            if issue_text:
                recurring_issues.append({"root_cause": cause, "issue": issue_text, "task_id": r.get("task_id", "")})

        # Count rows with filled root_cause for accurate percentages
        labeled_count = sum(1 for r in model_rows if r["root_cause"])

        analysis["models"][model] = {
            "total": len(model_rows),
            "labeled_count": labeled_count,
            "root_cause_counts": root_cause_counts,
            "proximity_counts": proximity_counts,
            "recurring_count": len(recurring_rows),
            "recurring_issues": recurring_issues,
        }

    # Cross-model root cause aggregation
    all_causes = Counter()
    for r in rows:
        if r["root_cause"]:
            all_causes[r["root_cause"]] += 1
    analysis["all_causes"] = all_causes
    analysis["labeled_count"] = sum(1 for r in rows if r["root_cause"])

    all_proximity = Counter()
    for r in rows:
        if r["proximity"]:
            all_proximity[r["proximity"]] += 1
    analysis["all_proximity"] = all_proximity

    return analysis



# Report generation
def pct(count, total):
    if total == 0:
        return "0.0%"
    return f"{100.0 * count / total:.1f}%"


def format_report(analyses):
    """Build a markdown report string from the list of dataset analyses."""
    lines = []
    w = lines.append

    w("# Manual Error Analysis — Summary Report\n")
    w("This report summarizes the manually categorized failure analysis across")
    w("all datasets and models.\n")

    # Per-dataset sections
    for analysis in analyses:
        w(f"\n---\n")
        w(f"## {analysis['label']}\n")
        labeled = analysis["labeled_count"]
        unlabeled = analysis["total"] - labeled
        w(f"**Total failures analyzed:** {analysis['total']}")
        if unlabeled:
            w(f"  ({unlabeled} row(s) without a root-cause label — percentages use N={labeled})\n")
        else:
            w("")

        # --- Aggregate root cause table ---
        w(f"### Overall Root Cause Distribution\n")
        w(f"| Root Cause | Count | % |")
        w(f"|---|---|---|")
        for cause, count in analysis["all_causes"].most_common():
            w(f"| {cause} | {count} | {pct(count, labeled)} |")

        # --- Aggregate proximity ---
        w(f"\n### Overall Proximity to Success\n")
        w(f"| Proximity | Count | % |")
        w(f"|---|---|---|")
        for prox in sorted(analysis["all_proximity"], key=proximity_sort_key):
            count = analysis["all_proximity"][prox]
            w(f"| {prox} | {count} | {pct(count, analysis['total'])} |")

        # --- Cross-model comparison table ---
        models = sorted(analysis["models"].keys())
        all_causes_ordered = [c for c, _ in analysis["all_causes"].most_common()]

        w(f"\n### Root Cause by Model (counts)\n")
        header = "| Root Cause | " + " | ".join(models) + " |"
        sep = "|---|" + "|".join(["---"] * len(models)) + "|"
        w(header)
        w(sep)
        for cause in all_causes_ordered:
            cols = []
            for m in models:
                c = analysis["models"][m]["root_cause_counts"].get(cause, 0)
                cols.append(str(c))
            w(f"| {cause} | " + " | ".join(cols) + " |")
        # Totals row
        totals = [str(analysis["models"][m]["total"]) for m in models]
        w(f"| **Total** | " + " | ".join(totals) + " |")

        # --- Proximity by Model ---
        all_prox_ordered = sorted(analysis["all_proximity"].keys(), key=proximity_sort_key)
        w(f"\n### Proximity to Success by Model\n")
        header = "| Proximity | " + " | ".join(models) + " |"
        w(header)
        w(sep)
        for prox in all_prox_ordered:
            cols = []
            for m in models:
                c = analysis["models"][m]["proximity_counts"].get(prox, 0)
                cols.append(str(c))
            w(f"| {prox} | " + " | ".join(cols) + " |")

        # --- Per-model detail ---
        for model in models:
            mdata = analysis["models"][model]
            w(f"\n#### {model}\n")
            w(f"- **Failures analyzed:** {mdata['total']}")
            w(f"- **Recurring failures:** {mdata['recurring_count']}")

            # Root cause breakdown (percentages over labeled rows only)
            denom = mdata["labeled_count"]
            w(f"\n**Root Cause Breakdown:**\n")
            for cause, count in mdata["root_cause_counts"].most_common():
                bar = "█" * count
                w(f"- {cause}: {count} ({pct(count, denom)}) {bar}")

            # Proximity
            w(f"\n**Proximity to Success:**\n")
            for prox in sorted(mdata["proximity_counts"], key=proximity_sort_key):
                count = mdata["proximity_counts"][prox]
                w(f"- {prox}: {count} ({pct(count, mdata['total'])})")

            # Recurring patterns
            if mdata["recurring_issues"]:
                w(f"\n**Recurring Failure Patterns:**\n")
                # Group recurring issues by root cause
                by_cause = defaultdict(list)
                for ri in mdata["recurring_issues"]:
                    by_cause[ri["root_cause"]].append(ri)
                for cause, items in sorted(by_cause.items()):
                    w(f"- **{cause}** ({len(items)} recurring):")
                    for item in items[:5]:  # Show up to 5 examples
                        w(f"  - {item['issue']} (task: {item['task_id']})")
                    if len(items) > 5:
                        w(f"  - ... and {len(items) - 5} more")


    # Grand summary across all datasets
    w(f"\n---\n")
    w(f"## Grand Summary Across All Datasets\n")

    grand_total = sum(a["total"] for a in analyses)
    grand_labeled = sum(a["labeled_count"] for a in analyses)
    grand_causes = Counter()
    grand_proximity = Counter()
    grand_recurring = 0
    for a in analyses:
        grand_causes.update(a["all_causes"])
        grand_proximity.update(a["all_proximity"])
        for m in a["models"].values():
            grand_recurring += m["recurring_count"]

    w(f"**Total failures analyzed:** {grand_total}")
    w(f"**Total recurring:** {grand_recurring}\n")
    w("> **Note:** The grand totals combine stratified samples (TestEval, 50 each)")
    w("> with an exhaustive census (Real-World, 226). The real-world dataset")
    w("> therefore dominates the aggregate counts. Per-dataset tables above")
    w("> should be preferred for cross-dataset comparisons.\n")

    w(f"### Root Cause Distribution (All Datasets)\n")
    w(f"| Root Cause | Count | % |")
    w(f"|---|---|---|")
    for cause, count in grand_causes.most_common():
        w(f"| {cause} | {count} | {pct(count, grand_labeled)} |")

    w(f"\n### Proximity to Success (All Datasets)\n")
    w(f"| Proximity | Count | % |")
    w(f"|---|---|---|")
    for prox in sorted(grand_proximity, key=proximity_sort_key):
        count = grand_proximity[prox]
        w(f"| {prox} | {count} | {pct(count, grand_total)} |")

    # Key findings
    w(f"\n### Key Findings\n")

    # Top 3 root causes
    top_causes = grand_causes.most_common(3)
    w(f"1. **Top root causes:** " + ", ".join(f"{c} ({pct(n, grand_labeled)})" for c, n in top_causes))

    # Proximity: how many are near/high (fixable)?
    fixable = grand_proximity.get("high", 0) + grand_proximity.get("near", 0)
    w(f"2. **Potentially fixable (high+near proximity):** {fixable} ({pct(fixable, grand_total)})")

    # Hard failures
    hard = grand_proximity.get("far", 0) + grand_proximity.get("low", 0)
    w(f"3. **Hard failures (low+far proximity):** {hard} ({pct(hard, grand_total)})")

    w(f"4. **Recurring patterns:** {grand_recurring} failures flagged as recurring")

    return "\n".join(lines)


def main():
    base = Path(__file__).parent / "error_analysis_output"

    csv_files = {
        "TestEval — Initial Experiment (T=0.0, N=1, all 11 SLMs + Pynguin)": "initial_1_failure_analysis.csv",
        "Real-World Dataset (all failures, N=1, N=226)": "realworld_1_failure_analysis.csv",
    }

    analyses = []
    for label, filename in csv_files.items():
        path = base / filename
        if not path.exists():
            print(f"WARNING: {path} not found, skipping.", file=sys.stderr)
            continue
        rows = load_csv(path)
        analyses.append(analyze_dataset(rows, label))

    report = format_report(analyses)

    # Write markdown report
    out_path = base / "error_analysis_summary.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to {out_path}")

    # Also print to console
    print()
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()