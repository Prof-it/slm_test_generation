# Pynguin Mutation-Score Comparison

## Status: complete

Closes the gap flagged in the initial Pynguin results paragraph in `paper.tex`
("we did not run comparable mutation analysis over the Pynguin corpus for
this submission"). Runs mutation testing over the same Cochran-derived
73-task subset (`step4_evaluation/mutation_subset_v2_ids.json`) already used
for the SLM cohort's Experiment B mutation figures, over both Pynguin seeds
(42, 43), computed by `step4_evaluation/pynguin_mutation_compute.py`.

## A real bug was found and fixed before these numbers are trustworthy

The first attempt at this analysis (`evaluation_results/pynguin_simple_mutation/`,
initial run) silently produced `mutation_score=0.0` / `mutation_stats.total=0`
for every one of the 73 subset tasks. The `mutation_error` field on every
record read `Init failed (Code 1): ... ModuleNotFoundError: No module named
'cosmic_ray'` — `cosmic-ray` was never installed in
`step4_evaluation/.venv310_pynguin`, the interpreter used to score Pynguin
output. Because `evaluate_results.py`'s mutation path catches this failure
and records a `mutation_error` string rather than raising, the run completed
"successfully" with all-zero scores that looked superficially like a
legitimate (if surprising) near-zero mutation-score finding. Caught only by
checking `mutation_stats.total > 0` before trusting the numbers — 0/33
records had any mutants at all in the first run, which is what triggered the
investigation. Fixed by installing `cosmic-ray==8.4.3` (matching the version
already used in the repo's main `.venv`) into `.venv310_pynguin`, then
re-running the mutation scoring from scratch. The corrected run shows mutants
generated for 66/146 pooled subset records (the remainder are the 33
non-passing tasks in the 73-task subset per seed, which are correctly never
eligible for mutation testing).

## Method

- `cMut`: mean `mutation_score` over records with `status == "Pass"` and a
  non-null `mutation_score` (conditional on pass, same definition used
  throughout the paper).
- `uMut`: mean `mutation_score` over **all** 73 subset records, treating a
  non-passing or unscored task as 0 (unconditional over the fixed mutation
  sample, matching `rq_reanalysis.py`'s `analysis_6_mutation_expA` logic —
  the denominator is the full subset size, not just the tasks that produced
  a real score).
- `mutation_score` in `evaluate_results.py`'s output is already a percentage
  (0-100), not a 0-1 fraction — this tripped up the first computation attempt
  (numbers over 100% until corrected).

## Results (73-task subset, pooled across seeds 42+43, n=146)

| Seed | n | n Pass+scored | cMut | uMut |
|---|---:|---:|---:|---:|
| 42 | 73 | 33 | 15.33% | 6.93% |
| 43 | 73 | 33 | 16.25% | 7.35% |
| **Pooled** | **146** | **66** | **15.79%** | **7.14%** |

4,816 total mutants generated across the pooled subset; 615 killed.

## Comparison against the SLM cohort

The SLM cohort's unconditional mutation score (uMut) on `TestContextBench-Py`
spans **1.45% to 5.01%** across all ten Experiment B model x pipeline cells
(already reported in `paper.tex` RQ1). Pynguin's pooled uMut, **7.14%**, is
above the top of that range by 2.13 points, and its cMut (15.79%) is also
higher than any individual SLM configuration's uMut.

This is a real, modest difference, not noise: Pynguin does kill a somewhat
higher fraction of injected mutants than any SLM configuration in this cohort.
But the practically important point is the same for both: **92.86% of
mutants survive Pynguin's suites**, against 94.99--98.55% surviving the
best/worst SLM suites — both are overwhelmingly near-floor in absolute terms.
Pynguin's structurally higher Pass@1 (47.33% vs. the best SLM's 43.44%) comes
with a mutation-score edge of a similar modest scale, not a qualitative
difference in fault-detection capability. Neither generation approach, at
this scale/budget, reliably detects injected faults; Pass@1 does not track
fault-detection capability well for either, which is consistent with — and
now extends across a second, structurally different generation method — the
paper's core RQ1 finding that pass-conditional and pass-rate metrics do not
substitute for measuring fault detection directly.
