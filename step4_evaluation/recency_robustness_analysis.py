"""
Recency-effect robustness checks (Phase 3, Step 1 of PIPELINE_FIX_PLAN.md):
everything that can be answered from the *existing* Python-3.10 evaluated
results, without re-running anything. The Python-3.11 re-execution is a
separate, later, genuinely long-running step -- this script answers whether
the recency effect survives on the data we already have, which determines
whether that rerun is even necessary before drawing conclusions.

Isolated, non-overwriting: reuses rq_reanalysis.py's own loaders
(`load_experiment_b`, `load_task_meta`, `MODEL_ORDER`) rather than
reimplementing them. Does not modify rq_reanalysis.py or any evaluated file.

Covers:
  1. Full-set vs. clean-set (19 broken tasks excluded) logistic regression,
     side by side.
  2. Two further sensitivity splits: exclude only the 15 genuine extraction
     defects, and exclude only the 4 Python-3.11-only artifacts.
  3. Clustering-level check: task_num-clustered SEs (existing choice) vs.
     repo-clustered SEs.
  4. Per-model recency effect (pool x model interaction).
  5. Continuous code-age sensitivity: checked for feasibility, not run --
     see the printed note (dates are not fine-grained enough on either pool).

Run: python step4_evaluation/recency_robustness_analysis.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "step4_evaluation"))
from rq_reanalysis import load_experiment_b, load_task_meta, MODEL_ORDER  # noqa: E402

OUT_DIR = Path(__file__).parent / "oracle_validation"

with open(Path(__file__).parent / "dataset_health.json", encoding="utf-8") as f:
    HEALTH = json.load(f)

BROKEN_ALL = set(HEALTH["broken_task_ids"])
# Split by error class using the per-task rows already computed by preflight_dataset_health.
PY311_ARTIFACT_IDS = {
    r["task_id"] for r in HEALTH["rows"]
    if r.get("task_id") in BROKEN_ALL and r.get("error_class") == "ImportError"
}
GENUINE_DEFECT_IDS = BROKEN_ALL - PY311_ARTIFACT_IDS

assert len(PY311_ARTIFACT_IDS) == 4, f"expected 4 py3.11 artifacts, got {len(PY311_ARTIFACT_IDS)}"
assert len(GENUINE_DEFECT_IDS) == 15, f"expected 15 genuine defects, got {len(GENUINE_DEFECT_IDS)}"


def build_task_frame(exp_b, meta, exclude_ids=frozenset()):
    rows = []
    for (model, pipeline, tier), recs in exp_b.items():
        for r in recs:
            tn = str(r.get("task_num"))
            if tn in exclude_ids or tn not in meta:
                continue
            m = meta[tn]
            rows.append({
                "task_num": tn,
                "model": model,
                "pipeline": pipeline,
                "tier": tier,
                "repo": m.get("repo"),
                "passed": 1 if r.get("status") == "Pass" else 0,
                "leaked": 1 if m["leaked"] else 0,  # leaked == historical pool
                "cc": m.get("cyclomatic_complexity"),
                "loc": m.get("loc"),
                "level": m.get("dependency_level"),
            })
    df = pd.DataFrame(rows).dropna(subset=["cc", "loc", "level"])
    df["cc"] = df["cc"].astype(float)
    df["loc"] = df["loc"].astype(float)
    return df


def fit_logit(df, cluster_col="task_num", formula="passed ~ leaked + cc + loc + C(level, Treatment(reference='L0'))"):
    fit = smf.glm(formula=formula, data=df, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": df[cluster_col]}
    )
    return fit


def summarize(fit, label, n_obs, n_clusters):
    or_ = np.exp(fit.params["leaked"])
    ci = np.exp(fit.conf_int().loc["leaked"])
    return {
        "Spec": label, "N_obs": n_obs, "N_clusters": n_clusters,
        "OR_leaked_historical": round(or_, 3),
        "OR_ci_lo": round(ci[0], 3), "OR_ci_hi": round(ci[1], 3),
        "p_value": fit.pvalues["leaked"],
    }


def main():
    exp_b = load_experiment_b()
    meta = load_task_meta()

    # 1. Full-set vs clean-set (19 excluded) vs the two partial-exclusion sensitivities.
    specs = {
        "Full set (N=300 tasks, existing paper spec)": frozenset(),
        "Clean set (19 broken tasks excluded)": BROKEN_ALL,
        "Sensitivity: exclude only 15 genuine extraction defects": GENUINE_DEFECT_IDS,
        "Sensitivity: exclude only 4 Python-3.11-only artifacts": PY311_ARTIFACT_IDS,
    }
    rows = []
    for label, excl in specs.items():
        df = build_task_frame(exp_b, meta, exclude_ids=excl)
        fit = fit_logit(df, cluster_col="task_num")
        rows.append(summarize(fit, label, len(df), df["task_num"].nunique()))
    df_specs = pd.DataFrame(rows)
    df_specs.to_csv(OUT_DIR / "recency_robustness_full_vs_clean.csv", index=False)

    # 2. Clustering-level check: task_num vs repo, on the clean set.
    df_clean = build_task_frame(exp_b, meta, exclude_ids=BROKEN_ALL)
    fit_task_cluster = fit_logit(df_clean, cluster_col="task_num")
    fit_repo_cluster = fit_logit(df_clean, cluster_col="repo")
    df_cluster = pd.DataFrame([
        summarize(fit_task_cluster, "Clustered by task_num (existing choice)", len(df_clean), df_clean["task_num"].nunique()),
        summarize(fit_repo_cluster, "Clustered by repo", len(df_clean), df_clean["repo"].nunique()),
    ])
    df_cluster.to_csv(OUT_DIR / "recency_robustness_clustering_check.csv", index=False)

    # 3. Per-model recency effect (pool x model interaction), on the clean set.
    df_clean["model"] = pd.Categorical(df_clean["model"], categories=MODEL_ORDER)
    fit_interact = fit_logit(
        df_clean, cluster_col="task_num",
        formula="passed ~ leaked * C(model) + cc + loc + C(level, Treatment(reference='L0'))",
    )
    per_model_rows = []
    base_or = np.exp(fit_interact.params.get("leaked", np.nan))
    per_model_rows.append({"Model": MODEL_ORDER[0] + " (reference)", "OR_leaked": round(base_or, 3),
                            "p_value": fit_interact.pvalues.get("leaked", np.nan)})
    for model in MODEL_ORDER[1:]:
        interact_term = f"leaked:C(model)[T.{model}]"
        if interact_term not in fit_interact.params.index:
            continue
        combined_log_or = fit_interact.params["leaked"] + fit_interact.params[interact_term]
        # Wald test for whether this model's leaked effect differs from the reference model's.
        p_diff = fit_interact.pvalues[interact_term]
        per_model_rows.append({
            "Model": model, "OR_leaked": round(np.exp(combined_log_or), 3),
            "p_value_diff_vs_reference": round(p_diff, 4),
        })
    df_permodel = pd.DataFrame(per_model_rows)
    df_permodel.to_csv(OUT_DIR / "recency_robustness_per_model.csv", index=False)

    # 4. Continuous code-age sensitivity: feasibility check only.
    historical_dates = {m.get("commit_date") for tn, m in meta.items() if m.get("leaked")}
    recent_dates = {m.get("commit_date") for tn, m in meta.items() if not m.get("leaked")}
    date_note = (
        f"Historical pool: {len(historical_dates)} distinct commit_date value(s) "
        f"({sorted(historical_dates)}) -- all historical tasks share the placeholder "
        f"'pre-2026-06-10' inherited from TestEval, not real per-task dates. "
        f"Recent pool: {len(recent_dates)} distinct dates spanning "
        f"{min(recent_dates)} to {max(recent_dates)}. "
        f"A continuous code-age regression is NOT feasible: the historical pool has "
        f"no real dates at all (binary pool membership is the only available signal), "
        f"and the recent pool's {len(recent_dates)} distinct values span only a few days, "
        f"far too narrow to estimate a meaningful continuous slope. This sensitivity "
        f"analysis is not run; the binary historical/recent split is the only date "
        f"granularity the data actually supports."
    )

    with open(OUT_DIR / "RECENCY_ROBUSTNESS_REPORT.md", "w", encoding="utf-8") as f:
        f.write("# Recency-Effect Robustness Checks (Step 1, no re-execution)\n\n")
        f.write("## Full-set vs. clean-set vs. partial-exclusion sensitivity\n\n")
        f.write(df_specs.to_markdown(index=False))
        f.write("\n\n## Clustering-level check (task_num vs. repo), clean set\n\n")
        f.write(df_cluster.to_markdown(index=False))
        f.write("\n\n## Per-model recency effect (pool x model interaction), clean set\n\n")
        f.write(df_permodel.to_markdown(index=False))
        f.write("\n\n## Continuous code-age sensitivity: feasibility\n\n")
        f.write(date_note + "\n")

    pd.set_option("display.width", 160)
    print(df_specs.to_string(index=False))
    print()
    print(df_cluster.to_string(index=False))
    print()
    print(df_permodel.to_string(index=False))
    print()
    print(date_note)
    print()
    print(f"Report written to {OUT_DIR / 'RECENCY_ROBUSTNESS_REPORT.md'}")


if __name__ == "__main__":
    main()
