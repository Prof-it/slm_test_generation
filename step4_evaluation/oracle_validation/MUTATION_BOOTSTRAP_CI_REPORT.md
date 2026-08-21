# Bootstrap Confidence Intervals for Mutation Scores

## Status: complete

Replaces the paper's "we do not report confidence intervals [for mutation]"
wording with actual task-cluster and paired bootstrap intervals.

Script: `step4_evaluation/mutation_bootstrap_ci.py`. Isolated — imports
`load_experiment_a`/`load_experiment_b`/`MODEL_ORDER` from `rq_reanalysis.py`
rather than reimplementing them, and reuses the existing frozen mutation-sample
id files (`mutation_subset_ids.json`, 67 tasks, Experiment A;
`mutation_subset_v2_ids.json`, 73 tasks, Experiment B). Does not modify
`rq_reanalysis.py`, `evaluate_results.py`, or any evaluated result file.

## Method

- **Resampling unit is the task, not the record.** Each task recurs across
  every model/pipeline/tier configuration; bootstrapping at the record level
  would treat repeated observations of the same task as independent and
  understate interval width. Every bootstrap here resamples task_nums with
  replacement.
- **uMut (unconditional mutation score)**, same definition already used in
  `rq_reanalysis.py`'s `analysis_6_mutation_expA`: scored only over the fixed
  mutation-sample task subset; a sampled task that failed evaluation or has no
  mutation score counts as 0; tasks outside the mutation sample are excluded
  entirely (never eligible), not folded in as 0.
- **Task-cluster CI**: resample the mutation-sample task_nums (B=10,000,
  seed 20260819), recompute uMut per replicate, take the percentile
  [2.5%, 97.5%] interval.
- **Paired CI**: for Single-step vs Two-step within each model, resample the
  common mutation-sample task_nums shared by both pipelines, recompute
  (uMut_single − uMut_two) per replicate, percentile interval. A CI excluding
  0 would be evidence of a real paired difference.

## Headline finding: no paired Single-step vs Two-step mutation difference is significant

Every single one of the 10 paired bootstrap intervals (5 models x 2
experiments) includes 0:

| Experiment | Model | diff (Single − Two, pp) | 95% CI |
|---|---|---:|---|
| A (TestEval) | Qwen3-4B-Thinking | −1.59 | [−4.73, 1.58] |
| A (TestEval) | Qwen3.5-4B | −2.42 | [−6.55, 1.71] |
| A (TestEval) | gemma-4-E4B-it | −3.35 | [−7.76, 0.98] |
| A (TestEval) | granite-4.0-micro | +1.29 | [−2.43, 5.12] |
| A (TestEval) | Ministral-3-3B-Reasoning | −0.48 | [−4.12, 3.27] |
| B (TestContextBench-Py) | Qwen3-4B-Thinking | +0.43 | [−1.50, 2.25] |
| B (TestContextBench-Py) | Qwen3.5-4B | +2.16 | [−0.26, 4.65] |
| B (TestContextBench-Py) | gemma-4-E4B-it | +0.58 | [−1.68, 2.77] |
| B (TestContextBench-Py) | granite-4.0-micro | −0.01 | [−2.40, 2.27] |
| B (TestContextBench-Py) | Ministral-3-3B-Reasoning | +1.34 | [−1.48, 4.25] |

**This directly licenses the point the paper should make: small point
differences in mutation score between pipelines are not evidence of a real
ranking.** (Qwen3.5-4B on Experiment B comes closest, CI [−0.26, 4.65], but
still crosses zero.)

## Unconditional mutation scores with intervals (for reporting tables)

Experiment A (TestEval, n=67 mutation-sample tasks per config):

| Model | Single-step uMut% [95% CI] | Two-step uMut% [95% CI] |
|---|---|---|
| Qwen3-4B-Thinking | 17.41 [14.37, 20.43] | 19.00 [16.17, 21.74] |
| Qwen3.5-4B | 13.13 [9.89, 16.42] | 15.55 [12.11, 19.00] |
| gemma-4-E4B-it | 12.97 [9.47, 16.56] | 16.32 [12.87, 19.75] |
| granite-4.0-micro | 12.92 [9.44, 16.66] | 11.63 [8.26, 15.11] |
| Ministral-3-3B-Reasoning | 7.28 [4.46, 10.39] | 7.76 [4.76, 10.91] |

Experiment B (TestContextBench-Py, n=73 mutation-sample tasks per config,
pooled across tiers A/B/C):

| Model | Single-step uMut% [95% CI] | Two-step uMut% [95% CI] |
|---|---|---|
| Qwen3-4B-Thinking | 3.88 [1.85, 6.15] | 3.45 [1.47, 5.77] |
| Qwen3.5-4B | 4.22 [2.07, 6.59] | 2.06 [0.64, 3.85] |
| gemma-4-E4B-it | 2.20 [0.59, 4.14] | 1.62 [0.42, 3.21] |
| granite-4.0-micro | 2.55 [0.95, 4.43] | 2.56 [0.87, 4.59] |
| Ministral-3-3B-Reasoning | 3.73 [1.40, 6.47] | 2.39 [0.78, 4.40] |

Note the much wider relative uncertainty on Experiment B (small mutation-sample
n=73 against a much lower base rate, 2-4% vs. 7-19% on Experiment A) — the CIs
themselves show the real-world benchmark's mutation-kill signal is barely
distinguishable from noise at this sample size, which is itself worth stating
plainly rather than reporting the bare point estimates as if precise.

## Artifacts

- `step4_evaluation/oracle_validation/mutation_bootstrap_single_expA.csv` /
  `_expB.csv` — per-model x pipeline uMut with task-cluster CIs.
- `step4_evaluation/oracle_validation/mutation_bootstrap_paired_expA.csv` /
  `_expB.csv` — per-model paired Single-vs-Two-step differences with CIs.

## What this does and does not license

- **Does license:** replacing "we do not report confidence intervals" with the
  intervals above; explicitly stating that no paired pipeline mutation
  difference is statistically distinguishable from zero at n=67/73 mutation
  tasks, in either experiment.
- **Does not license:** any claim of a real pipeline-level mutation-score
  ranking (single-step "better" or "worse" than two-step) — the data does not
  support one.
- **Does not license:** touching the Pass@1 gates, coverage, or
  context-utilization results — this pass is scoped to mutation-score
  uncertainty only.
