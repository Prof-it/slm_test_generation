"""
Assertion-gated re-analysis: a task only counts as "gated pass" if
status == Pass AND the generated suite has a statically-detectable assertion
(same has_detectable_assertion() check as assertion_gate.py).

Produces, for both experiments:
  - per model x pipeline assertion-gated Pass@1 with Wilson 95% CI
  - Exp B also broken out per tier (re-tests the Tier-C washout under gating)
  - McNemar paired tests (Single-call vs Two-stage) on GATED outcomes,
    5 contrasts for Exp A, 15 for Exp B (Holm-Bonferroni corrected)
  - best config per experiment under gating

Run: python step4_evaluation/gated_reanalysis.py
"""
import json, math, sys, glob, os
from pathlib import Path
import numpy as np
import pandas as pd
from statsmodels.stats.contingency_tables import mcnemar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "step4_evaluation"))
from evaluate_results import _combine_tests_for_task, strip_markdown  # noqa: E402
from assertion_gate import has_detectable_assertion  # noqa: E402

FIRST_EXP_DIR = ROOT / "evaluation_results" / "first_experiment" / "run_1"
SECOND_EXP_GLOB = str(ROOT / "evaluation_results" / "second_experiment" / "run_1" / "tier_*" / "*_evaluated.jsonl")
PRED_A_DIR = ROOT / "downloaded_predictions" / "first_experiment" / "run_1"
PRED_B_GLOB = str(ROOT / "downloaded_predictions" / "second_experiment" / "run_1" / "tier_*" / "*.jsonl")
OUT_DIR = ROOT / "step4_evaluation" / "rq_reanalysis_output"

MODEL_ORDER = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
               "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def model_from_stem(stem):
    return stem.replace("linecov2_", "").replace("linecov_", "").split("_temp")[0]


def wilson_ci(k, n, z=1.96):
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
    n = len(pvals)
    order = np.argsort(pvals)
    adjusted = np.empty(n)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (n - rank) * pvals[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


def assertion_pass_ids(pred_path, pass_ids):
    """For a single prediction file, return the subset of pass_ids whose
    generated suite has a statically-detectable assertion."""
    out = set()
    for line in open(pred_path, encoding="utf-8"):
        if not line.strip():
            continue
        entry = json.loads(line)
        tn = str(entry.get("task_num"))
        if tn not in pass_ids:
            continue
        tests = entry.get("tests")
        if not tests:
            continue
        test_list = list(tests.items()) if isinstance(tests, dict) else [(str(i), t) for i, t in enumerate(tests)]
        func_name = entry.get("func_name", "solution")
        combined = _combine_tests_for_task(test_list, func_name)
        source = strip_markdown(combined)
        if not source.strip():
            continue
        ok, _kind = has_detectable_assertion(source)
        if ok:
            out.add(tn)
    return out


# ============================================================================
# Load + attach gated status
# ============================================================================
print("Loading Exp A...")
exp_a = {}
for f in sorted(glob.glob(str(FIRST_EXP_DIR / "*_evaluated.jsonl"))):
    stem = Path(f).stem.replace("_evaluated", "")
    model = model_from_stem(stem)
    pipeline = "Two-stage" if stem.startswith("linecov2_") else "Single-call"
    recs = load_jsonl(f)
    pass_ids = {str(r["task_num"]) for r in recs if r.get("status") == "Pass"}
    pred_path = PRED_A_DIR / f"{stem}.jsonl"
    a_pass_ids = assertion_pass_ids(pred_path, pass_ids)
    for r in recs:
        r["_gated_pass"] = str(r["task_num"]) in a_pass_ids
    exp_a[(model, pipeline)] = recs

print("Loading Exp B...")
exp_b = {}
pred_b_files = {Path(f).parent.name + "/" + Path(f).stem: f for f in glob.glob(PRED_B_GLOB)}
for f in sorted(glob.glob(SECOND_EXP_GLOB)):
    tier = Path(f).parent.name.replace("tier_", "")
    stem = Path(f).stem.replace("_evaluated", "")
    model = model_from_stem(stem)
    pipeline = "Two-stage" if stem.startswith("linecov2_") else "Single-call"
    recs = load_jsonl(f)
    pass_ids = {str(r["task_num"]) for r in recs if r.get("status") == "Pass"}
    pred_path = pred_b_files.get(f"tier_{tier}/{stem}")
    a_pass_ids = assertion_pass_ids(pred_path, pass_ids) if pred_path else set()
    for r in recs:
        r["_gated_pass"] = str(r["task_num"]) in a_pass_ids
    exp_b[(model, pipeline, tier)] = recs

# sanity check: gated-pass count must equal assertion_gate.py's "with_assertion" totals
tot_a = sum(1 for recs in exp_a.values() for r in recs if r["_gated_pass"])
tot_b = sum(1 for recs in exp_b.values() for r in recs if r["_gated_pass"])
print(f"Sanity: total gated-pass Exp A = {tot_a} (assertion_gate.py reported 1174)")
print(f"Sanity: total gated-pass Exp B = {tot_b} (assertion_gate.py reported 1556)")

# ============================================================================
print("\n" + "=" * 100)
print("1. ASSERTION-GATED Pass@1 per model x pipeline, Exp A, Wilson 95% CI")
print("=" * 100)
rows = []
for model in MODEL_ORDER:
    for pipeline in ["Single-call", "Two-stage"]:
        recs = exp_a[(model, pipeline)]
        n = len(recs)
        k_exec = sum(1 for r in recs if r.get("status") == "Pass")
        k_gate = sum(1 for r in recs if r["_gated_pass"])
        p_e, lo_e, hi_e = wilson_ci(k_exec, n)
        p_g, lo_g, hi_g = wilson_ci(k_gate, n)
        rows.append(dict(Model=model, Pipeline=pipeline, N=n,
                          exec_Pass1=round(p_e, 2), exec_lo=round(lo_e, 2), exec_hi=round(hi_e, 2),
                          gated_Pass1=round(p_g, 2), gated_lo=round(lo_g, 2), gated_hi=round(hi_g, 2)))
        print(f"  {model:26s} {pipeline:10s} exec={p_e:6.2f}% [{lo_e:5.2f},{hi_e:5.2f}]  "
              f"gated={p_g:6.2f}% [{lo_g:5.2f},{hi_g:5.2f}]")
df1a = pd.DataFrame(rows)
df1a.to_csv(OUT_DIR / "gated_1_expA.csv", index=False)

print("\n" + "=" * 100)
print("2. ASSERTION-GATED Pass@1 per model x pipeline, Exp B pooled over tiers, Wilson 95% CI")
print("=" * 100)
rows = []
for model in MODEL_ORDER:
    for pipeline in ["Single-call", "Two-stage"]:
        recs = []
        for tier in ["A", "B", "C"]:
            recs.extend(exp_b[(model, pipeline, tier)])
        n = len(recs)
        k_exec = sum(1 for r in recs if r.get("status") == "Pass")
        k_gate = sum(1 for r in recs if r["_gated_pass"])
        p_e, lo_e, hi_e = wilson_ci(k_exec, n)
        p_g, lo_g, hi_g = wilson_ci(k_gate, n)
        rows.append(dict(Model=model, Pipeline=pipeline, N=n,
                          exec_Pass1=round(p_e, 2), exec_lo=round(lo_e, 2), exec_hi=round(hi_e, 2),
                          gated_Pass1=round(p_g, 2), gated_lo=round(lo_g, 2), gated_hi=round(hi_g, 2)))
        print(f"  {model:26s} {pipeline:10s} exec={p_e:6.2f}% [{lo_e:5.2f},{hi_e:5.2f}]  "
              f"gated={p_g:6.2f}% [{lo_g:5.2f},{hi_g:5.2f}]")
df2b = pd.DataFrame(rows)
df2b.to_csv(OUT_DIR / "gated_2_expB_pooled.csv", index=False)

print("\n" + "=" * 100)
print("3. ASSERTION-GATED Pass@1 per model x pipeline x TIER, Exp B, Wilson 95% CI")
print("=" * 100)
rows = []
for model in MODEL_ORDER:
    for pipeline in ["Single-call", "Two-stage"]:
        for tier in ["A", "B", "C"]:
            recs = exp_b[(model, pipeline, tier)]
            n = len(recs)
            k_exec = sum(1 for r in recs if r.get("status") == "Pass")
            k_gate = sum(1 for r in recs if r["_gated_pass"])
            p_e, lo_e, hi_e = wilson_ci(k_exec, n)
            p_g, lo_g, hi_g = wilson_ci(k_gate, n)
            rows.append(dict(Model=model, Pipeline=pipeline, Tier=tier, N=n,
                              exec_Pass1=round(p_e, 2), gated_Pass1=round(p_g, 2),
                              gated_lo=round(lo_g, 2), gated_hi=round(hi_g, 2)))
            print(f"  {model:26s} {pipeline:10s} Tier {tier}  exec={p_e:6.2f}%  "
                  f"gated={p_g:6.2f}% [{lo_g:5.2f},{hi_g:5.2f}]")
df3b = pd.DataFrame(rows)
df3b.to_csv(OUT_DIR / "gated_3_expB_by_tier.csv", index=False)

# Tier-level pooled-over-model gated Pass@1 (the washout re-test)
print("\n  Tier-pooled (all models/pipelines) gated Pass@1, Exp B:")
for tier in ["A", "B", "C"]:
    n = k_e = k_g = 0
    for model in MODEL_ORDER:
        for pipeline in ["Single-call", "Two-stage"]:
            recs = exp_b[(model, pipeline, tier)]
            n += len(recs)
            k_e += sum(1 for r in recs if r.get("status") == "Pass")
            k_g += sum(1 for r in recs if r["_gated_pass"])
    p_e, _, _ = wilson_ci(k_e, n)
    p_g, lo_g, hi_g = wilson_ci(k_g, n)
    print(f"    Tier {tier}: exec={p_e:6.2f}%  gated={p_g:6.2f}% [{lo_g:5.2f},{hi_g:5.2f}]  (n={n})")

# ============================================================================
print("\n" + "=" * 100)
print("4. McNemar on GATED outcomes, Single-call vs Two-stage, Exp A (5 contrasts)")
print("=" * 100)

def mcnemar_pair_gated(recs_a, recs_b):
    status_a = {str(r["task_num"]): r["_gated_pass"] for r in recs_a}
    status_b = {str(r["task_num"]): r["_gated_pass"] for r in recs_b}
    common = set(status_a) & set(status_b)
    both_pass = sum(1 for t in common if status_a[t] and status_b[t])
    both_fail = sum(1 for t in common if not status_a[t] and not status_b[t])
    a_only = sum(1 for t in common if status_a[t] and not status_b[t])
    b_only = sum(1 for t in common if not status_a[t] and status_b[t])
    table = [[both_pass, a_only], [b_only, both_fail]]
    result = mcnemar(table, exact=True)
    odds_ratio = (a_only / b_only) if b_only > 0 else float("inf")
    return {"n_common": len(common), "single_only_pass": a_only, "two_stage_only_pass": b_only,
            "both_pass": both_pass, "both_fail": both_fail,
            "statistic": result.statistic, "p_value": result.pvalue, "odds_ratio_single_over_two": odds_ratio}

rows = []
for model in MODEL_ORDER:
    res = mcnemar_pair_gated(exp_a[(model, "Single-call")], exp_a[(model, "Two-stage")])
    res["Model"] = model
    rows.append(res)
dfm_a = pd.DataFrame(rows)
dfm_a["p_holm"] = holm_bonferroni(dfm_a["p_value"].values)
dfm_a["significant_holm_0.05"] = dfm_a["p_holm"] < 0.05
dfm_a = dfm_a[["Model", "n_common", "both_pass", "both_fail", "single_only_pass", "two_stage_only_pass",
               "odds_ratio_single_over_two", "statistic", "p_value", "p_holm", "significant_holm_0.05"]]
dfm_a.to_csv(OUT_DIR / "gated_4_mcnemar_expA.csv", index=False)
print(dfm_a.to_string(index=False))

print("\n" + "=" * 100)
print("5. McNemar on GATED outcomes, Single-call vs Two-stage, Exp B (15 contrasts, model x tier)")
print("=" * 100)
rows = []
for model in MODEL_ORDER:
    for tier in ["A", "B", "C"]:
        res = mcnemar_pair_gated(exp_b[(model, "Single-call", tier)], exp_b[(model, "Two-stage", tier)])
        res["Model"] = model
        res["Tier"] = tier
        rows.append(res)
dfm_b = pd.DataFrame(rows)
dfm_b["p_holm"] = holm_bonferroni(dfm_b["p_value"].values)
dfm_b["significant_holm_0.05"] = dfm_b["p_holm"] < 0.05
dfm_b = dfm_b[["Model", "Tier", "n_common", "both_pass", "both_fail", "single_only_pass", "two_stage_only_pass",
               "odds_ratio_single_over_two", "statistic", "p_value", "p_holm", "significant_holm_0.05"]]
dfm_b.to_csv(OUT_DIR / "gated_5_mcnemar_expB.csv", index=False)
print(dfm_b.to_string(index=False))

# ============================================================================
print("\n" + "=" * 100)
print("6. Best config per experiment under GATING")
print("=" * 100)
best_a = df1a.loc[df1a["gated_Pass1"].idxmax()]
print(f"Exp A best under gating: {best_a['Model']} / {best_a['Pipeline']}  "
      f"gated_Pass@1={best_a['gated_Pass1']:.2f}%  [{best_a['gated_lo']:.2f}, {best_a['gated_hi']:.2f}]  "
      f"(exec was {best_a['exec_Pass1']:.2f}%)")
best_b = df2b.loc[df2b["gated_Pass1"].idxmax()]
print(f"Exp B best under gating: {best_b['Model']} / {best_b['Pipeline']}  "
      f"gated_Pass@1={best_b['gated_Pass1']:.2f}%  [{best_b['gated_lo']:.2f}, {best_b['gated_hi']:.2f}]  "
      f"(exec was {best_b['exec_Pass1']:.2f}%)")

print("\nAll gated_*.csv written to", OUT_DIR)
