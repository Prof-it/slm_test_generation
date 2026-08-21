"""
Task-cluster bootstrap 95% confidence intervals for mutation scores, and paired
bootstrap intervals for model/pipeline mutation-score differences.

Reviewer-requested replacement for the paper's "we do not report confidence
intervals [for mutation]" wording. Isolated, non-overwriting: reuses
rq_reanalysis.py's own loaders (`load_experiment_a`, `load_experiment_b`,
`model_from_stem` via re-import) rather than reimplementing them, and reuses
the same mutation-sample id files (`mutation_subset_ids.json` for Experiment A,
`mutation_subset_v2_ids.json` for Experiment B). Does not modify
rq_reanalysis.py, evaluate_results.py, or any evaluated result file.

Resampling unit is the task_num, not the individual record, in every bootstrap
here: each task recurs across many model/pipeline/tier configurations, so
resampling records directly would treat repeated observations of the same
underlying task as independent draws and understate the true interval width.

Definitions (matching rq_reanalysis.py analysis_6 exactly):
  - uMut (unconditional mutation score): scored over the fixed mutation-sample
    task subset only; a sampled task that failed or has no mutation score
    counts as 0. Tasks outside the mutation sample are excluded entirely
    (never eligible), not folded in as missing/zero.
  - Task-cluster CI: bootstrap resample the mutation-sample task_nums (with
    replacement, B=10000), recompute uMut each replicate, take the
    percentile [2.5%, 97.5%] interval.
  - Paired CI (Single-step vs Two-step, per model): resample the *common*
    task_nums (with replacement) shared by both pipelines' mutation samples,
    recompute (uMut_single - uMut_two) each replicate, percentile interval.
    A CI excluding 0 is evidence of a real paired difference; this replaces
    any unqualified point-difference ranking claim.

Run: python step4_evaluation/mutation_bootstrap_ci.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "step4_evaluation"))
from rq_reanalysis import load_experiment_a, load_experiment_b, MODEL_ORDER  # noqa: E402

OUT_DIR = Path(__file__).parent / "oracle_validation"
RNG_SEED = 20260819
N_BOOT = 10000

with open(Path(__file__).parent / "mutation_subset_ids.json", encoding="utf-8") as f:
    MUTATION_SUBSET_EXPA = set(str(x) for x in json.load(f))
with open(Path(__file__).parent / "mutation_subset_v2_ids.json", encoding="utf-8") as f:
    MUTATION_SUBSET_EXPB = set(str(x) for x in json.load(f))


def umut_values_by_task(recs, subset_ids):
    """Return {task_num: mutation_value} for tasks in subset_ids, 0.0 if
    failed/missing mutation data, restricted to the fixed mutation sample."""
    by_task = {str(r["task_num"]): r for r in recs}
    out = {}
    for tn in subset_ids:
        r = by_task.get(tn)
        if r is None:
            continue  # task not present in this config at all -- exclude, not zero
        val = r.get("mutation_score") if r.get("status") == "Pass" else None
        out[tn] = float(val) if val is not None else 0.0
    return out


def bootstrap_ci_single(values: dict, n_boot=N_BOOT, seed=RNG_SEED):
    tasks = sorted(values)
    arr = np.array([values[t] for t in tasks])
    n = len(arr)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), 0
    point = arr.mean()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_means = arr[idx].mean(axis=1)
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    return point, lo, hi, n


def bootstrap_ci_paired(values_a: dict, values_b: dict, n_boot=N_BOOT, seed=RNG_SEED):
    common = sorted(set(values_a) & set(values_b))
    n = len(common)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), 0
    a = np.array([values_a[t] for t in common])
    b = np.array([values_b[t] for t in common])
    point = a.mean() - b.mean()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_diff = a[idx].mean(axis=1) - b[idx].mean(axis=1)
    lo, hi = np.percentile(boot_diff, [2.5, 97.5])
    return point, lo, hi, n


def run_experiment_a():
    exp_a = load_experiment_a()
    single_rows, paired_rows = [], []
    per_model_values = {}
    for model in MODEL_ORDER:
        vals = {}
        for pipeline in ["Single-call", "Two-stage"]:
            recs = exp_a[(model, pipeline)]
            v = umut_values_by_task(recs, MUTATION_SUBSET_EXPA)
            vals[pipeline] = v
            point, lo, hi, n = bootstrap_ci_single(v)
            single_rows.append({"Experiment": "A (TestEval)", "Model": model, "Pipeline": pipeline,
                                 "n_mutation_sample": n, "uMut_%": round(point, 2),
                                 "boot_lo": round(lo, 2), "boot_hi": round(hi, 2)})
        per_model_values[model] = vals
        point, lo, hi, n = bootstrap_ci_paired(vals["Single-call"], vals["Two-stage"])
        paired_rows.append({"Experiment": "A (TestEval)", "Model": model,
                             "n_paired": n, "diff_Single_minus_Two_%": round(point, 2),
                             "boot_lo": round(lo, 2), "boot_hi": round(hi, 2),
                             "excludes_zero": not (lo <= 0 <= hi)})
    return pd.DataFrame(single_rows), pd.DataFrame(paired_rows)


def run_experiment_b():
    exp_b = load_experiment_b()
    single_rows, paired_rows = [], []
    for model in MODEL_ORDER:
        pooled_vals = {}
        for pipeline in ["Single-call", "Two-stage"]:
            recs = []
            for tier in ["A", "B", "C"]:
                recs.extend(exp_b.get((model, pipeline, tier), []))
            v = umut_values_by_task(recs, MUTATION_SUBSET_EXPB)
            pooled_vals[pipeline] = v
            point, lo, hi, n = bootstrap_ci_single(v)
            single_rows.append({"Experiment": "B (TestContextBench-Py)", "Model": model, "Pipeline": pipeline,
                                 "n_mutation_sample": n, "uMut_%": round(point, 2),
                                 "boot_lo": round(lo, 2), "boot_hi": round(hi, 2)})
        point, lo, hi, n = bootstrap_ci_paired(pooled_vals["Single-call"], pooled_vals["Two-stage"])
        paired_rows.append({"Experiment": "B (TestContextBench-Py)", "Model": model,
                             "n_paired": n, "diff_Single_minus_Two_%": round(point, 2),
                             "boot_lo": round(lo, 2), "boot_hi": round(hi, 2),
                             "excludes_zero": not (lo <= 0 <= hi)})
    return pd.DataFrame(single_rows), pd.DataFrame(paired_rows)


if __name__ == "__main__":
    single_a, paired_a = run_experiment_a()
    single_b, paired_b = run_experiment_b()

    single_a.to_csv(OUT_DIR / "mutation_bootstrap_single_expA.csv", index=False)
    paired_a.to_csv(OUT_DIR / "mutation_bootstrap_paired_expA.csv", index=False)
    single_b.to_csv(OUT_DIR / "mutation_bootstrap_single_expB.csv", index=False)
    paired_b.to_csv(OUT_DIR / "mutation_bootstrap_paired_expB.csv", index=False)

    pd.set_option("display.width", 140)
    print("=" * 100)
    print(f"Experiment A -- unconditional mutation score, task-cluster bootstrap 95% CI (mutation sample n={len(MUTATION_SUBSET_EXPA)})")
    print("=" * 100)
    print(single_a.to_string(index=False))
    print()
    print("Paired (Single-step - Two-step), per model:")
    print(paired_a.to_string(index=False))
    print()
    print("=" * 100)
    print(f"Experiment B -- unconditional mutation score, task-cluster bootstrap 95% CI (mutation sample n={len(MUTATION_SUBSET_EXPB)})")
    print("=" * 100)
    print(single_b.to_string(index=False))
    print()
    print("Paired (Single-step - Two-step), per model:")
    print(paired_b.to_string(index=False))
    print()
    print(f"CSVs written to {OUT_DIR}")
