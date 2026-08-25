"""Recompute Experiment B outcomes on the 281-task defect-excluded set.

Reads existing evaluated generations and runtime-oracle results.  It performs
no generation or re-evaluation and writes only to
step4_evaluation/oracle_validation/clean_set_reanalysis/.
"""

from __future__ import annotations

import glob
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.contingency_tables import mcnemar


ROOT = Path(__file__).resolve().parent.parent
STEP4 = ROOT / "step4_evaluation"
OUT = STEP4 / "oracle_validation" / "clean_set_reanalysis"
OUT.mkdir(parents=True, exist_ok=True)

with (STEP4 / "dataset_health.json").open(encoding="utf-8") as handle:
    EXCLUDED = {str(value) for value in json.load(handle)["broken_task_ids"]}

RUNTIME_PATH = STEP4 / "oracle_validation" / "full_corpus_reanalysis_results_experiment_b.csv"
EVAL_GLOB = str(ROOT / "evaluation_results" / "second_experiment" / "run_1" / "tier_*" / "*_evaluated.jsonl")
MUTATION_IDS_PATH = STEP4 / "mutation_subset_v2_ids.json"
DATASET_PATH = ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl"
CONTEXT_PATH = STEP4 / "oracle_validation" / "context_utilization_rows_with_ids.json"
PYNGUIN_EVAL_GLOB = str(ROOT / "evaluation_results" / "pynguin_simple" / "*_evaluated.jsonl")
PYNGUIN_RUNTIME_PATH = STEP4 / "oracle_validation" / "full_corpus_reanalysis_results_pynguin.csv"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if not n:
        return math.nan, math.nan, math.nan
    p = k / n
    denominator = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p * 100, (centre - half) / denominator * 100, (centre + half) / denominator * 100


def holm(values: list[float]) -> np.ndarray:
    order = np.argsort(values)
    result = np.empty(len(values))
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(values) - rank) * values[index])
        result[index] = min(running, 1.0)
    return result


def normalize_model(filename: str) -> str:
    stem = Path(filename).stem.replace("_evaluated", "")
    return stem.replace("linecov2_", "").replace("linecov_", "").split("_temp")[0]


def load_evaluated() -> pd.DataFrame:
    rows: list[dict] = []
    for filename in sorted(glob.glob(EVAL_GLOB)):
        tier = Path(filename).parent.name.replace("tier_", "")
        pipeline = "Two-step" if Path(filename).stem.startswith("linecov2_") else "Single-step"
        model = normalize_model(filename)
        with open(filename, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                task_id = str(record.get("task_num"))
                if task_id in EXCLUDED:
                    continue
                record.update(task_id=task_id, model=model, pipeline=pipeline, tier=tier)
                rows.append(record)
    frame = pd.DataFrame(rows)
    assert len(frame) == 281 * 5 * 2 * 3, len(frame)
    metadata = {}
    with DATASET_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                metadata[str(item["task_num"])] = item.get("dependency_level")
    frame["dependency_level"] = frame.task_id.map(metadata)
    assert frame.dependency_level.notna().all()
    return frame


def add_rate(rows: list[dict], keys: dict, field: str, values: pd.Series) -> None:
    n = len(values)
    k = int(values.sum())
    point, low, high = wilson(k, n)
    rows.append({**keys, "metric": field, "N": n, "successes": k,
                 "rate_pct": round(point, 2), "ci_low": round(low, 2), "ci_high": round(high, 2)})


def grouped_rates(frame: pd.DataFrame, group_columns: list[str], metrics: dict[str, str]) -> pd.DataFrame:
    rows: list[dict] = []
    for key, subset in frame.groupby(group_columns, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        labels = dict(zip(group_columns, key))
        for label, column in metrics.items():
            add_rate(rows, labels, label, subset[column].astype(bool))
    return pd.DataFrame(rows)


def paired_tests(runtime: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, tier), subset in runtime.groupby(["model_short", "tier"]):
        single = subset[subset.pipeline == "Single-step"].set_index("task_id")["executed_nontrivial_gate"].astype(bool)
        two = subset[subset.pipeline == "Two-step"].set_index("task_id")["executed_nontrivial_gate"].astype(bool)
        common = single.index.intersection(two.index)
        single, two = single.loc[common], two.loc[common]
        single_only = int((single & ~two).sum())
        two_only = int((~single & two).sum())
        result = mcnemar([[int((single & two).sum()), single_only],
                          [two_only, int((~single & ~two).sum())]], exact=True)
        rows.append({"model": model, "tier": tier, "N_paired": len(common),
                     "single_only": single_only, "two_only": two_only,
                     "odds_ratio_single_over_two": single_only / two_only if two_only else math.inf,
                     "p_raw": result.pvalue})
    output = pd.DataFrame(rows)
    output["p_holm"] = holm(output.p_raw.tolist())
    output["significant"] = output.p_holm < 0.05
    return output


def mutation_rates(evaluated: pd.DataFrame) -> pd.DataFrame:
    with MUTATION_IDS_PATH.open(encoding="utf-8") as handle:
        mutation_ids = {str(value) for value in json.load(handle)} - EXCLUDED
    rows = []
    for (model, pipeline), subset in evaluated.groupby(["model", "pipeline"]):
        sampled = subset[subset.task_id.isin(mutation_ids)]
        # Pool tiers exactly as in the original ten-cell Exp B comparison.
        values = sampled.apply(
            lambda row: float(row.mutation_score)
            if row.status == "Pass" and pd.notna(row.mutation_score) else 0.0,
            axis=1,
        )
        completed = sampled[(sampled.status == "Pass") & sampled.mutation_score.notna()]
        rows.append({"model": model, "pipeline": pipeline,
                     "N_sample_observations": len(sampled),
                     "N_completed": len(completed),
                     "uMut_pct": round(values.mean(), 2),
                     "cMut_pct": round(completed.mutation_score.astype(float).mean(), 2) if len(completed) else math.nan})
    return pd.DataFrame(rows)


def context_rates() -> pd.DataFrame:
    with CONTEXT_PATH.open(encoding="utf-8") as handle:
        rows = [row for row in json.load(handle) if str(row["task_id"]) not in EXCLUDED]
    frame = pd.DataFrame(rows)
    output = []
    for (tier, passed), subset in frame.groupby(["tier", "passed"]):
        for metric in ["dep_used", "mock_used"]:
            values = subset[metric].dropna().astype(bool)
            if len(values):
                output.append({"tier": tier, "passed": bool(passed), "metric": metric,
                               "N": len(values), "used": int(values.sum()),
                               "rate_pct": round(values.mean() * 100, 1)})
    for tier, subset in frame.groupby("tier"):
        for metric in ["dep_used", "mock_used"]:
            values = subset[metric].dropna().astype(bool)
            if len(values):
                output.append({"tier": tier, "passed": "all", "metric": metric,
                               "N": len(values), "used": int(values.sum()),
                               "rate_pct": round(values.mean() * 100, 1)})
    return pd.DataFrame(output)


def pynguin_rates() -> tuple[pd.DataFrame, dict]:
    rows = []
    for filename in sorted(glob.glob(PYNGUIN_EVAL_GLOB)):
        seed = Path(filename).stem.split("seed")[-1].split("_")[0]
        with open(filename, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    task_id = str(row.get("task_num"))
                    if task_id not in EXCLUDED:
                        row.update(task_id=task_id, seed=seed)
                        rows.append(row)
    evaluated = pd.DataFrame(rows)
    assert len(evaluated) == 281 * 2, len(evaluated)
    evaluated["execution_success"] = evaluated.status.eq("Pass")
    has_assertions = evaluated.has_assertions.astype("boolean").fillna(False).astype(bool)
    has_xfail_tests = evaluated.has_xfail_tests.astype("boolean").fillna(False).astype(bool)
    evaluated["static_success"] = evaluated.execution_success & has_assertions
    evaluated["xfail_excluded_success"] = evaluated.execution_success & ~has_xfail_tests

    instrumented = pd.read_csv(PYNGUIN_RUNTIME_PATH, dtype={"task_id": str})
    instrumented = instrumented[~instrumented.task_id.isin(EXCLUDED)]
    # Pynguin task IDs repeat across seeds; preserve source_file as the seed key.
    gate_count = int(instrumented.executed_nontrivial_gate.fillna(False).astype(bool).sum())

    metrics = {
        "N": len(evaluated),
        "execution_passes": int(evaluated.execution_success.sum()),
        "execution_pct": round(evaluated.execution_success.mean() * 100, 2),
        "static_passes": int(evaluated.static_success.sum()),
        "static_pct": round(evaluated.static_success.mean() * 100, 2),
        "xfail_excluded_passes": int(evaluated.xfail_excluded_success.sum()),
        "xfail_excluded_pct": round(evaluated.xfail_excluded_success.mean() * 100, 2),
        "runtime_nontrivial_passes": gate_count,
        "runtime_nontrivial_pct": round(gate_count / len(evaluated) * 100, 2),
    }
    return evaluated, metrics


def main() -> None:
    evaluated = load_evaluated()
    evaluated["execution_success"] = evaluated.status.eq("Pass")
    evaluated["static_assertion_success"] = evaluated.execution_success & evaluated.has_assertions.fillna(False).astype(bool)

    instrumented = pd.read_csv(RUNTIME_PATH, dtype={"task_id": str})
    instrumented = instrumented[~instrumented.task_id.isin(EXCLUDED)].copy()
    instrumented["model_short"] = instrumented.model.str.split("/").str[-1]
    instrumented["pipeline"] = instrumented.pipeline.map({"single-step": "Single-step", "two-step": "Two-step"})
    instrumented = instrumented[["task_id", "model_short", "pipeline", "tier",
                                 "executed_nontrivial_gate"]]

    # Instrumentation has no row when a generation contains no extractable test
    # code.  Such generations remain in the experimental denominator and cannot
    # satisfy the oracle gate, so join onto the complete evaluated corpus and
    # conservatively fill the missing gate outcome as False.
    runtime = evaluated[["task_id", "model", "pipeline", "tier", "execution_success"]].copy()
    runtime = runtime.rename(columns={"model": "model_short"}).merge(
        instrumented,
        on=["task_id", "model_short", "pipeline", "tier"],
        how="left",
        validate="one_to_one",
    )
    runtime["executed_nontrivial_gate"] = (
        runtime.executed_nontrivial_gate.astype("boolean").fillna(False).astype(bool)
    )
    assert len(runtime) == 281 * 5 * 2 * 3

    grouped_rates(evaluated, ["model", "pipeline"], {
        "Execution Pass@1": "execution_success",
        "Static assertion-presence Pass@1": "static_assertion_success",
    }).to_csv(OUT / "execution_static_by_model_pipeline.csv", index=False)

    grouped_rates(runtime, ["model_short", "pipeline"], {
        "Execution Pass@1": "execution_success",
        "Non-trivial Pass@1": "executed_nontrivial_gate",
    }).to_csv(OUT / "runtime_gate_by_model_pipeline.csv", index=False)

    grouped_rates(runtime, ["model_short", "pipeline", "tier"], {
        "Non-trivial Pass@1": "executed_nontrivial_gate",
    }).to_csv(OUT / "runtime_gate_by_model_pipeline_tier.csv", index=False)

    grouped_rates(evaluated, ["tier"], {"Execution Pass@1": "execution_success"}).to_csv(
        OUT / "execution_by_tier.csv", index=False)

    grouped_rates(evaluated, ["tier"], {
        "Execution Pass@1": "execution_success",
        "Static assertion-presence Pass@1": "static_assertion_success",
    }).to_csv(OUT / "execution_static_by_tier.csv", index=False)

    grouped_rates(evaluated, ["dependency_level"], {
        "Execution Pass@1": "execution_success",
        "Static assertion-presence Pass@1": "static_assertion_success",
    }).to_csv(OUT / "execution_static_by_dependency_level.csv", index=False)

    status = evaluated.status.value_counts().rename_axis("status").reset_index(name="count")
    status["N"] = len(evaluated)
    status["share_pct"] = (status["count"] / len(evaluated) * 100).round(2)
    status.to_csv(OUT / "terminal_status.csv", index=False)

    paired_tests(runtime).to_csv(OUT / "runtime_nontrivial_mcnemar.csv", index=False)
    mutation_rates(evaluated).to_csv(OUT / "mutation_by_model_pipeline.csv", index=False)
    context_rates().to_csv(OUT / "context_utilization.csv", index=False)
    pynguin_frame, pynguin_summary = pynguin_rates()
    pd.DataFrame([pynguin_summary]).to_csv(OUT / "pynguin_summary.csv", index=False)

    summary = {
        "excluded_task_ids": sorted(EXCLUDED),
        "n_tasks": 281,
        "n_evaluated_generations": len(evaluated),
        "n_runtime_rows": len(runtime),
        "execution_passes": int(evaluated.execution_success.sum()),
        "execution_pass1_pct": round(evaluated.execution_success.mean() * 100, 2),
        "static_passes": int(evaluated.static_assertion_success.sum()),
        "static_pass1_pct": round(evaluated.static_assertion_success.mean() * 100, 2),
        "runtime_execution_passes": int(runtime.execution_success.sum()),
        "runtime_execution_pct": round(runtime.execution_success.mean() * 100, 2),
        "runtime_nontrivial_passes": int(runtime.executed_nontrivial_gate.sum()),
        "runtime_nontrivial_pct": round(runtime.executed_nontrivial_gate.mean() * 100, 2),
        "pynguin": pynguin_summary,
    }
    with (OUT / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
