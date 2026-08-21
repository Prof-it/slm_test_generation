"""
Pynguin historical-vs-recent negative control (Phase 4 follow-up).

RQ3 reports a historical-pool advantage for the SLM cohort (OR=1.69,
p=1.7e-4, clean set) and interprets it cautiously because two competing
explanations are consistent with the raw numbers: (a) LLM memorization of
historical code from pretraining data, or (b) a genuine property of the
tasks themselves (e.g. older code in this corpus being shorter/simpler/more
conventional, independent of any model ever having seen it).

Pynguin has no pretraining-data exposure to any task in this benchmark --
it is a search-based test generator with no memorization pathway. If
Pynguin's own historical-pool tasks are *also* easier (comparable or larger
OR), that is evidence for explanation (b): the historical/recent split
correlates with a task-intrinsic difficulty difference that has nothing to
do with contamination. If Pynguin shows no historical-pool advantage (OR
near 1, not significant), that is more consistent with (a).

Isolated, non-overwriting: reuses rq_reanalysis.py's load_task_meta (does
not modify it or any evaluated file). Reads the already-scored Pynguin
SIMPLE-mode evaluated files (evaluation_results/pynguin_simple/).

Run: python step4_evaluation/pynguin_recency_negative_control.py
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
from rq_reanalysis import load_task_meta  # noqa: E402

OUT_DIR = Path(__file__).parent / "oracle_validation"

PYNGUIN_SEED_FILES = [
    ROOT / "evaluation_results" / "pynguin_simple" / "pynguin_seed42_evaluated.jsonl",
    ROOT / "evaluation_results" / "pynguin_simple" / "pynguin_seed43_evaluated.jsonl",
]

with open(Path(__file__).parent / "dataset_health.json", encoding="utf-8") as f:
    HEALTH = json.load(f)
BROKEN_ALL = set(HEALTH["broken_task_ids"])


def load_pynguin_records():
    rows = []
    for i, path in enumerate(PYNGUIN_SEED_FILES):
        seed = 42 + i
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                rows.append({"task_num": str(r["task_num"]), "seed": seed,
                             "passed": 1 if r.get("status") == "Pass" else 0})
    return rows


def build_frame(meta, exclude_ids=frozenset()):
    rows = []
    for r in load_pynguin_records():
        tn = r["task_num"]
        if tn in exclude_ids or tn not in meta:
            continue
        m = meta[tn]
        if m.get("cyclomatic_complexity") is None or m.get("loc") is None or m.get("dependency_level") is None:
            continue
        rows.append({
            "task_num": tn,
            "seed": r["seed"],
            "passed": r["passed"],
            "leaked": 1 if m["leaked"] else 0,
            "cc": float(m["cyclomatic_complexity"]),
            "loc": float(m["loc"]),
            "level": m["dependency_level"],
        })
    return pd.DataFrame(rows)


def fit_logit(df, cluster_col="task_num"):
    formula = "passed ~ leaked + cc + loc + C(level, Treatment(reference='L0'))"
    return smf.glm(formula=formula, data=df, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": df[cluster_col]}
    )


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
    meta = load_task_meta()

    specs = {
        "Full set (600 obs = 300 tasks x 2 seeds)": frozenset(),
        "Clean set (19 broken tasks excluded)": BROKEN_ALL,
    }
    rows = []
    dfs = {}
    for label, excl in specs.items():
        df = build_frame(meta, exclude_ids=excl)
        dfs[label] = df
        fit = fit_logit(df, cluster_col="task_num")
        rows.append(summarize(fit, label, len(df), df["task_num"].nunique()))
    df_specs = pd.DataFrame(rows)

    # Raw pooled Pass@1 by pool membership, clean set, for the headline comparison.
    df_clean = dfs["Clean set (19 broken tasks excluded)"]
    hist_rate = df_clean.loc[df_clean["leaked"] == 1, "passed"].mean() * 100
    recent_rate = df_clean.loc[df_clean["leaked"] == 0, "passed"].mean() * 100
    n_hist = (df_clean["leaked"] == 1).sum()
    n_recent = (df_clean["leaked"] == 0).sum()

    df_specs.to_csv(OUT_DIR / "pynguin_recency_negative_control.csv", index=False)

    with open(OUT_DIR / "PYNGUIN_RECENCY_NEGATIVE_CONTROL_REPORT.md", "w", encoding="utf-8") as f:
        f.write("# Pynguin Historical-vs-Recent Negative Control\n\n")
        f.write("## Status: complete\n\n")
        f.write(
            "Pynguin has no pretraining-data exposure to any task in this benchmark "
            "(it is a search-based generator, not a language model), so it cannot "
            "exhibit training-data memorization. Comparing its historical-pool vs. "
            "recent-pool Pass@1 tests whether the SLM cohort's historical-pool "
            "advantage (Section RQ3, OR=1.69 clean set) reflects a task-intrinsic "
            "property of the historical pool (which would also affect Pynguin) or "
            "is specific to LLM memorization (which would not).\n\n"
        )
        f.write(f"## Raw pooled Pass@1, clean set (n={len(df_clean)} obs = 300 tasks x 2 seeds, "
                f"19 broken tasks excluded)\n\n")
        f.write(f"- Historical pool (n={n_hist}): {hist_rate:.2f}%\n")
        f.write(f"- Recent pool (n={n_recent}): {recent_rate:.2f}%\n")
        f.write(f"- Raw gap: {hist_rate - recent_rate:+.2f} points\n\n")
        f.write("## Logistic regression (passed ~ leaked + cc + loc + C(level)), clustered by task_num\n\n")
        f.write(df_specs.to_markdown(index=False))
        f.write("\n\n")
        f.write("## Interpretation\n\n")
        if df_specs.iloc[1]["p_value"] < 0.05 and df_specs.iloc[1]["OR_leaked_historical"] > 1:
            f.write(
                "Pynguin also shows a significant historical-pool advantage after "
                "controlling for complexity/length/dependency level. Since Pynguin "
                "cannot memorize training data, this is evidence that the recency "
                "effect observed for the SLM cohort is driven at least in part by a "
                "task-intrinsic property correlated with the historical/recent split "
                "(e.g. historical-pool code being shorter, less idiomatically modern, "
                "or otherwise more tractable for automated test generation in "
                "general), not solely by LLM memorization of historical code.\n"
            )
        else:
            f.write(
                "Pynguin does NOT show the same historical-pool advantage the SLM "
                "cohort shows (or shows one in the opposite direction / not "
                "significant). This is more consistent with the SLM recency effect "
                "being specific to LLM memorization of historical training data "
                "rather than a general task-intrinsic property of the historical "
                "pool.\n"
            )

    pd.set_option("display.width", 160)
    print(df_specs.to_string(index=False))
    print(f"\nRaw: historical {hist_rate:.2f}% (n={n_hist}) vs recent {recent_rate:.2f}% (n={n_recent})")
    print(f"\nReport written to {OUT_DIR / 'PYNGUIN_RECENCY_NEGATIVE_CONTROL_REPORT.md'}")


if __name__ == "__main__":
    main()
