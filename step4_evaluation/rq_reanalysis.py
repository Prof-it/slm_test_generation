"""
Reviewer-requested re-analysis of results already collected -- no new inference
runs, no new human annotation. Every number below is computed directly from:

  - evaluation_results/first_experiment/run_1/*_evaluated.jsonl   (Experiment A, TestEval, N=210)
  - evaluation_results/second_experiment/run_1/tier_*/*_evaluated.jsonl (Experiment B, RealWorldTests-Py v2 / TestContextBench-Py, 299 unique tasks)
  - TestEval/data/realworld-py-v2.jsonl  (per-task dependency_level, leaked, cyclomatic_complexity, loc, domain)

Covers the "Tier 3" reviewer items:
  1. Single-step vs Two-step pooled table for the real-world benchmark
  2. Tier x dependency-level cross-tab (the actual RQ3 answer)
  3. Failure-mode counts by dependency level and pipeline
  4. Wilson score CIs on every Pass@1 (Experiment A table + reality-gap figure)
  5. McNemar paired tests (Single-step vs Two-step) per model, with odds ratios
     and Holm-Bonferroni correction, for both experiments
  6. Mutation score two ways: conditional-on-pass (cMut) and unconditional
     over all attempted tasks (uMut), for Experiment A (already had both for B)
  7. Wall-clock / tokens / GPU-hours per task from existing performance logs
  8. Logistic regression on the contamination gap (pool + CC + LOC + dependency
     level), with cluster-robust SEs by task_num since each task recurs across
     30 configurations
  9. Descriptive balance between the historical and recent pools

Usage:
    python step4_evaluation/rq_reanalysis.py

Output:
    step4_evaluation/rq_reanalysis_output/*.csv   (one file per analysis)
    step4_evaluation/rq_reanalysis_output/report.md  (human-readable summary)
"""

import glob
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from statsmodels.stats.contingency_tables import mcnemar
import statsmodels.api as sm
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
FIRST_EXP_DIR = ROOT / "evaluation_results" / "first_experiment" / "run_1"
SECOND_EXP_GLOB = str(ROOT / "evaluation_results" / "second_experiment" / "run_1" / "tier_*" / "*_evaluated.jsonl")
DATASET_PATH = ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl"
OUT_DIR = Path(__file__).parent / "rq_reanalysis_output"
OUT_DIR.mkdir(exist_ok=True)

MODEL_ORDER = [
    "Qwen3-4B-Thinking-2507",
    "Qwen3.5-4B",
    "gemma-4-E4B-it",
    "granite-4.0-micro",
    "Ministral-3-3B-Reasoning-2512",
]


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def model_from_stem(stem):
    return stem.replace("linecov2_", "").replace("linecov_", "").split("_temp")[0]


def wilson_ci(k, n, z=1.96):
    """Wilson score interval for a binomial proportion. Returns (point, lo, hi) as percentages."""
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    denom = 1 + z ** 2 / n
    center = p + z ** 2 / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))
    lo = (center - half) / denom
    hi = (center + half) / denom
    return (p * 100, lo * 100, hi * 100)


def holm_bonferroni(pvals):
    """Return adjusted p-values (Holm's step-down method), same order as input."""
    n = len(pvals)
    order = np.argsort(pvals)
    adjusted = np.empty(n)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (n - rank) * pvals[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


# ---------------------------------------------------------------------------
# Load raw records
# ---------------------------------------------------------------------------

def load_experiment_a():
    """Returns dict[(model, pipeline)] -> list of per-task records with task_num, status, etc."""
    files = sorted(glob.glob(str(FIRST_EXP_DIR / "*_evaluated.jsonl")))
    if not files:
        raise RuntimeError(f"No files found under {FIRST_EXP_DIR}")
    out = {}
    for f in files:
        stem = Path(f).stem.replace("_evaluated", "")
        model = model_from_stem(stem)
        pipeline = "Two-stage" if stem.startswith("linecov2_") else "Single-call"
        out[(model, pipeline)] = load_jsonl(f)
    return out


def load_task_meta():
    meta = {}
    for row in load_jsonl(DATASET_PATH):
        tn = str(row["task_num"])
        if tn in meta:
            continue
        meta[tn] = row
    return meta


def load_experiment_b():
    """Returns dict[(model, pipeline, tier)] -> list of per-task records.

    task_num 316020 previously collided between two distinct pandas-dev/pandas
    functions (a .zip-archive and a .tar-archive variant of `infer_filename`,
    in different classes of the same file) because the id/task_num hash in
    create_v2_dataset.py keyed only on (repo, file stem, function name), not
    the enclosing class. This has been fixed at the source: the dataset now
    carries 300 unique task_nums (the tar variant was reassigned task_num
    399128), the corrupted prediction-file metadata for the affected rows
    was restored from the pre-fix git history, and the two affected rows in
    every evaluated file were re-evaluated in Docker against the corrected
    solution/test pairing. No dedup is needed anymore -- every file has
    exactly 300 unique tasks.
    """
    files = sorted(glob.glob(SECOND_EXP_GLOB))
    if not files:
        raise RuntimeError(f"No files found matching {SECOND_EXP_GLOB}")
    out = {}
    for f in files:
        tier = Path(f).parent.name.replace("tier_", "")
        stem = Path(f).stem.replace("_evaluated", "")
        model = model_from_stem(stem)
        pipeline = "Two-stage" if stem.startswith("linecov2_") else "Single-call"
        recs = load_jsonl(f)
        assert len({str(r.get("task_num")) for r in recs}) == len(recs), (
            f"Duplicate task_num found in {f} -- expected 300 unique tasks."
        )
        out[(model, pipeline, tier)] = recs
    return out


# ---------------------------------------------------------------------------
# 1. Single-step vs Two-step pooled table (Experiment B)
# ---------------------------------------------------------------------------

def analysis_1_pipeline_table(exp_b, meta):
    rows = []
    for model in MODEL_ORDER:
        for pipeline in ["Single-call", "Two-stage"]:
            # pooled across all 3 tiers
            recs = []
            for tier in ["A", "B", "C"]:
                recs.extend(exp_b.get((model, pipeline, tier), []))
            n = len(recs)
            k = sum(1 for r in recs if r.get("status") == "Pass")
            p, lo, hi = wilson_ci(k, n)
            rows.append({"Model": model, "Pipeline": pipeline, "N": n, "Pass": k,
                         "Pass@1_%": round(p, 2), "Wilson_lo": round(lo, 2), "Wilson_hi": round(hi, 2)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "1_pipeline_table_expB.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 2. Tier x dependency-level cross-tab (Experiment B) -- the actual RQ3 answer
# ---------------------------------------------------------------------------

def analysis_2_tier_by_level(exp_b, meta):
    rows = []
    for tier in ["A", "B", "C"]:
        for level in ["L0", "L1", "L2", "L3"]:
            n = k = 0
            for model in MODEL_ORDER:
                for pipeline in ["Single-call", "Two-stage"]:
                    for r in exp_b.get((model, pipeline, tier), []):
                        tn = str(r.get("task_num"))
                        if tn not in meta or meta[tn]["dependency_level"] != level:
                            continue
                        n += 1
                        k += 1 if r.get("status") == "Pass" else 0
            p, lo, hi = wilson_ci(k, n)
            rows.append({"Tier": tier, "Level": level, "N": n, "Pass": k,
                         "Pass@1_%": round(p, 2), "Wilson_lo": round(lo, 2), "Wilson_hi": round(hi, 2)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "2_tier_by_level_expB.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 3. Failure-mode counts by dependency level and pipeline (Experiment B)
# ---------------------------------------------------------------------------

def analysis_3_failure_modes(exp_b, meta):
    rows = []
    for pipeline in ["Single-call", "Two-stage"]:
        for level in ["L0", "L1", "L2", "L3"]:
            counts = defaultdict(int)
            total = 0
            for model in MODEL_ORDER:
                for tier in ["A", "B", "C"]:
                    for r in exp_b.get((model, pipeline, tier), []):
                        tn = str(r.get("task_num"))
                        if tn not in meta or meta[tn]["dependency_level"] != level:
                            continue
                        total += 1
                        counts[r.get("status", "Unknown")] += 1
            row = {"Pipeline": pipeline, "Level": level, "N": total}
            # NOTE: EvaluationResult.SYNTAX_ERROR's literal string value is "Pytest Error"
            # (the Python constant name and its string value diverge in evaluate_results.py).
            for status in ["Pass", "Pytest Error", "Assertion Error", "Runtime Error", "Timeout", "No Code"]:
                row[status] = counts.get(status, 0)
                row[f"{status}_%"] = round(counts.get(status, 0) / total * 100, 1) if total else float("nan")
            expected = {"Pass", "Pytest Error", "Assertion Error", "Runtime Error", "Timeout", "No Code"}
            row["_other_statuses_seen"] = [s for s in counts if s not in expected]
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "3_failure_modes_expB.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 4. Wilson CIs on Experiment A's Table 1
# ---------------------------------------------------------------------------

def analysis_4_wilson_expA(exp_a):
    rows = []
    for model in MODEL_ORDER:
        for pipeline in ["Single-call", "Two-stage"]:
            recs = exp_a[(model, pipeline)]
            n = len(recs)
            k = sum(1 for r in recs if r.get("status") == "Pass")
            p, lo, hi = wilson_ci(k, n)
            rows.append({"Model": model, "Pipeline": pipeline, "N": n, "Pass": k,
                         "Pass@1_%": round(p, 2), "Wilson_lo": round(lo, 2), "Wilson_hi": round(hi, 2)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "4_wilson_expA.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 5. McNemar tests: Single-call vs Two-stage, paired per model (+ per tier for B)
# ---------------------------------------------------------------------------

def _mcnemar_pair(recs_a, recs_b):
    """recs_a, recs_b: lists of per-task records for the two paired conditions
    (same underlying tasks). Returns (b_disc, c_disc, stat, p, odds_ratio)."""
    status_a = {str(r["task_num"]): (r.get("status") == "Pass") for r in recs_a}
    status_b = {str(r["task_num"]): (r.get("status") == "Pass") for r in recs_b}
    common = set(status_a) & set(status_b)
    both_pass = sum(1 for t in common if status_a[t] and status_b[t])
    both_fail = sum(1 for t in common if not status_a[t] and not status_b[t])
    a_only = sum(1 for t in common if status_a[t] and not status_b[t])   # pass under A, fail under B
    b_only = sum(1 for t in common if not status_a[t] and status_b[t])   # fail under A, pass under B
    table = [[both_pass, a_only], [b_only, both_fail]]
    result = mcnemar(table, exact=True)
    odds_ratio = (a_only / b_only) if b_only > 0 else float("inf")
    return {"n_common": len(common), "single_only_pass": a_only, "two_stage_only_pass": b_only,
            "both_pass": both_pass, "both_fail": both_fail,
            "statistic": result.statistic, "p_value": result.pvalue, "odds_ratio_single_over_two": odds_ratio}


def analysis_5_mcnemar_expA(exp_a):
    rows = []
    for model in MODEL_ORDER:
        res = _mcnemar_pair(exp_a[(model, "Single-call")], exp_a[(model, "Two-stage")])
        res["Model"] = model
        rows.append(res)
    df = pd.DataFrame(rows)
    df["p_holm"] = holm_bonferroni(df["p_value"].values)
    df["significant_holm_0.05"] = df["p_holm"] < 0.05
    df = df[["Model", "n_common", "both_pass", "both_fail", "single_only_pass", "two_stage_only_pass",
             "odds_ratio_single_over_two", "statistic", "p_value", "p_holm", "significant_holm_0.05"]]
    df.to_csv(OUT_DIR / "5_mcnemar_expA.csv", index=False)
    return df


def analysis_5_mcnemar_expB(exp_b):
    rows = []
    for model in MODEL_ORDER:
        for tier in ["A", "B", "C"]:
            res = _mcnemar_pair(exp_b[(model, "Single-call", tier)], exp_b[(model, "Two-stage", tier)])
            res["Model"] = model
            res["Tier"] = tier
            rows.append(res)
    df = pd.DataFrame(rows)
    df["p_holm"] = holm_bonferroni(df["p_value"].values)
    df["significant_holm_0.05"] = df["p_holm"] < 0.05
    df = df[["Model", "Tier", "n_common", "both_pass", "both_fail", "single_only_pass", "two_stage_only_pass",
             "odds_ratio_single_over_two", "statistic", "p_value", "p_holm", "significant_holm_0.05"]]
    df.to_csv(OUT_DIR / "5_mcnemar_expB.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 6. Mutation score two ways for Experiment A (cMut already reported; add uMut)
# ---------------------------------------------------------------------------

def analysis_6_mutation_expA(exp_a):
    rows = []
    for model in MODEL_ORDER:
        for pipeline in ["Single-call", "Two-stage"]:
            recs = exp_a[(model, pipeline)]
            n = len(recs)
            passed = [r for r in recs if r.get("status") == "Pass"]
            mut_vals = [r["mutation_score"] for r in passed if r.get("mutation_score") is not None]
            cmut = sum(mut_vals) / len(mut_vals) if mut_vals else float("nan")
            # unconditional: every attempted task, failures/missing mutation = 0
            all_mut = [(r["mutation_score"] if (r.get("status") == "Pass" and r.get("mutation_score") is not None) else 0.0)
                       for r in recs]
            umut = sum(all_mut) / n if n else float("nan")
            rows.append({"Model": model, "Pipeline": pipeline, "N": n,
                         "n_mutation_completed": len(mut_vals),
                         "cMut_%_conditional_on_pass": round(cmut, 2),
                         "uMut_%_unconditional": round(umut, 2)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "6_mutation_two_ways_expA.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 7. Wall-clock / tokens / GPU-hours per task
# ---------------------------------------------------------------------------

def _extract_perf(r):
    perf = r.get("performance") or {}
    tok = perf.get("total_generated_tokens")
    if tok is None:
        tok = (perf.get("total_tokens_conditions", 0) or 0) + (perf.get("total_tokens_tests", 0) or 0)
    dur = perf.get("duration_seconds")
    if dur is None:
        dur = (perf.get("duration_conditions_sec", 0) or 0) + (perf.get("duration_tests_sec", 0) or 0)
    return tok or 0, dur or 0


def analysis_7_cost_table(exp_a, exp_b):
    rows = []
    for label, source in [("Experiment A (TestEval)", exp_a), ("Experiment B (RealWorldTests-Py v2)", None)]:
        if source is not None:
            for model in MODEL_ORDER:
                for pipeline in ["Single-call", "Two-stage"]:
                    recs = source[(model, pipeline)]
                    toks, durs = zip(*[_extract_perf(r) for r in recs]) if recs else ([], [])
                    total_tok = sum(toks)
                    total_dur_sec = sum(durs)
                    rows.append({"Experiment": label, "Model": model, "Pipeline": pipeline,
                                 "N_tasks": len(recs), "Total_tokens": total_tok,
                                 "Total_GPU_seconds": round(total_dur_sec, 1),
                                 "Total_GPU_hours": round(total_dur_sec / 3600, 3),
                                 "Avg_tokens_per_task": round(total_tok / len(recs), 1) if recs else float("nan"),
                                 "Avg_seconds_per_task": round(total_dur_sec / len(recs), 2) if recs else float("nan")})
        else:
            for model in MODEL_ORDER:
                for pipeline in ["Single-call", "Two-stage"]:
                    recs = []
                    for tier in ["A", "B", "C"]:
                        recs.extend(exp_b[(model, pipeline, tier)])
                    toks, durs = zip(*[_extract_perf(r) for r in recs]) if recs else ([], [])
                    total_tok = sum(toks)
                    total_dur_sec = sum(durs)
                    rows.append({"Experiment": label, "Model": model, "Pipeline": pipeline,
                                 "N_tasks": len(recs), "Total_tokens": total_tok,
                                 "Total_GPU_seconds": round(total_dur_sec, 1),
                                 "Total_GPU_hours": round(total_dur_sec / 3600, 3),
                                 "Avg_tokens_per_task": round(total_tok / len(recs), 1) if recs else float("nan"),
                                 "Avg_seconds_per_task": round(total_dur_sec / len(recs), 2) if recs else float("nan")})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "7_cost_table.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 8. Logistic regression: Pass ~ leaked + CC + LOC + dependency_level,
#    cluster-robust SEs by task_num (each task recurs across 30 configs)
# ---------------------------------------------------------------------------

def analysis_8_logistic_regression(exp_b, meta):
    rows = []
    for (model, pipeline, tier), recs in exp_b.items():
        for r in recs:
            tn = str(r.get("task_num"))
            if tn not in meta:
                continue
            m = meta[tn]
            rows.append({
                "task_num": tn,
                "config": f"{model}|{pipeline}|{tier}",
                "passed": 1 if r.get("status") == "Pass" else 0,
                "leaked": 1 if m["leaked"] else 0,
                "cc": m.get("cyclomatic_complexity"),
                "loc": m.get("loc"),
                "level": m.get("dependency_level"),
            })
    df = pd.DataFrame(rows).dropna(subset=["cc", "loc", "level"])
    df["cc"] = df["cc"].astype(float)
    df["loc"] = df["loc"].astype(float)

    model_fit = smf.glm(
        formula="passed ~ leaked + cc + loc + C(level, Treatment(reference='L0'))",
        data=df, family=sm.families.Binomial()
    ).fit(cov_type="cluster", cov_kwds={"groups": df["task_num"]})

    summary_df = pd.DataFrame({
        "coef": model_fit.params,
        "std_err_cluster": model_fit.bse,
        "z": model_fit.tvalues,
        "p_value": model_fit.pvalues,
        "odds_ratio": np.exp(model_fit.params),
        "OR_ci_lo": np.exp(model_fit.conf_int()[0]),
        "OR_ci_hi": np.exp(model_fit.conf_int()[1]),
    })
    summary_df.to_csv(OUT_DIR / "8_logistic_regression_contamination_gap.csv")
    with open(OUT_DIR / "8_logistic_regression_full_summary.txt", "w", encoding="utf-8") as f:
        f.write(str(model_fit.summary()))
        f.write(f"\n\nN observations: {len(df)}  |  N unique tasks (cluster groups): {df['task_num'].nunique()}\n")
    return summary_df, len(df), df["task_num"].nunique()


# ---------------------------------------------------------------------------
# 9. Descriptive balance between historical and recent pools
# ---------------------------------------------------------------------------

def analysis_9_pool_balance(meta):
    df = pd.DataFrame(list(meta.values()))
    df["pool"] = df["leaked"].map({True: "Historical", False: "Recent"})

    numeric_summary = df.groupby("pool")[["cyclomatic_complexity", "loc"]].agg(["mean", "median", "std", "min", "max"])
    numeric_summary.to_csv(OUT_DIR / "9a_pool_balance_numeric.csv")

    level_dist = pd.crosstab(df["pool"], df["dependency_level"], normalize="index").round(4) * 100
    level_dist.to_csv(OUT_DIR / "9b_pool_balance_level.csv")

    domain_dist = pd.crosstab(df["pool"], df["domain"], normalize="index").round(4) * 100
    domain_dist.to_csv(OUT_DIR / "9c_pool_balance_domain.csv")

    n_by_pool = df["pool"].value_counts()

    return numeric_summary, level_dist, domain_dist, n_by_pool


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(sections):
    lines = ["# RQ Re-analysis Report", "",
             "Computed directly from existing evaluated JSONL files -- no new inference runs.", ""]
    for title, df_or_text in sections:
        lines.append(f"## {title}")
        lines.append("")
        if isinstance(df_or_text, pd.DataFrame):
            lines.append(df_or_text.to_markdown(index=False))
        else:
            lines.append(str(df_or_text))
        lines.append("")
    (OUT_DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    print("Loading Experiment A (TestEval)...")
    exp_a = load_experiment_a()
    print("Loading Experiment B (RealWorldTests-Py v2)...")
    exp_b = load_experiment_b()
    print("Loading dataset metadata...")
    meta = load_task_meta()

    sections = []

    print("1. Pipeline table (Experiment B)...")
    df1 = analysis_1_pipeline_table(exp_b, meta)
    sections.append(("1. Single-step vs Two-step, pooled across tiers (Experiment B)", df1))

    print("2. Tier x dependency-level cross-tab...")
    df2 = analysis_2_tier_by_level(exp_b, meta)
    sections.append(("2. Tier x Dependency-Level cross-tab (Experiment B) -- RQ3", df2))

    print("3. Failure-mode counts...")
    df3 = analysis_3_failure_modes(exp_b, meta)
    sections.append(("3. Failure modes by level and pipeline (Experiment B)", df3))

    print("4. Wilson CIs (Experiment A)...")
    df4 = analysis_4_wilson_expA(exp_a)
    sections.append(("4. Wilson 95% CIs for Experiment A Table 1", df4))

    print("5. McNemar tests (Experiment A)...")
    df5a = analysis_5_mcnemar_expA(exp_a)
    sections.append(("5a. McNemar (paired) Single-call vs Two-stage, Experiment A, Holm-Bonferroni over 5 models", df5a))

    print("5. McNemar tests (Experiment B)...")
    df5b = analysis_5_mcnemar_expB(exp_b)
    sections.append(("5b. McNemar (paired) Single-call vs Two-stage, Experiment B, Holm-Bonferroni over 15 model x tier tests", df5b))

    print("6. Mutation score two ways (Experiment A)...")
    df6 = analysis_6_mutation_expA(exp_a)
    sections.append(("6. Mutation score: conditional (cMut) vs unconditional (uMut), Experiment A", df6))

    print("7. Cost table...")
    df7 = analysis_7_cost_table(exp_a, exp_b)
    sections.append(("7. Wall-clock / tokens / GPU-hours per model x pipeline", df7))

    print("8. Logistic regression...")
    df8, n_obs, n_clusters = analysis_8_logistic_regression(exp_b, meta)
    sections.append((f"8. Logistic regression, Pass ~ leaked + CC + LOC + level "
                      f"(cluster-robust SE by task_num; N={n_obs} obs, {n_clusters} clusters)", df8))

    print("9. Pool balance...")
    numeric_summary, level_dist, domain_dist, n_by_pool = analysis_9_pool_balance(meta)
    sections.append(("9a. Historical vs Recent pool -- CC/LOC balance", numeric_summary))
    sections.append(("9b. Historical vs Recent pool -- dependency-level distribution (row %)", level_dist))
    sections.append(("9c. Historical vs Recent pool -- domain distribution (row %)", domain_dist))
    sections.append(("9d. Pool sizes (unique tasks)", n_by_pool.to_frame("n_unique_tasks")))

    write_report(sections)
    print(f"\nAll outputs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
