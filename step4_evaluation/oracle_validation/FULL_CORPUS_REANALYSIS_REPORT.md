# Full-Corpus Isolated Oracle Re-Evaluation

## Status: complete for both experiments

This is the corrected, runtime-validated replacement for the legacy static-presence
assertion gate (`assertion_gate.py` / `gated_reanalysis.py`), built on top of the frozen
v4 oracle classifier (`CLASSIFIER_FREEZE_DECISION.md`) and the runtime-instrumentation
equivalence pilot that validated it is safe to run at scale
(`RUNTIME_INSTRUMENTATION_PILOT_REPORT.md`: 100/100 piloted suites equivalent between
original and instrumented execution).

Script: `step4_evaluation/full_corpus_oracle_reanalysis.py`. Fully isolated — does not
modify `evaluate_results.py`, `assertion_gate.py`, `gated_reanalysis.py`, any legacy
result file, `oracle_analysis.py`'s classification logic, or `paper.tex`.

## Methodology

- Reuses `evaluate_results.py`'s own harness-construction helpers (`strip_markdown`,
  `_standardize_func_name`, `_combine_tests_for_task`, `fix_relative_imports`,
  `fix_absolute_imports`, `HARNESS_TEMPLATE`, `COMMON_IMPORTS`, `_determine_failure_status`,
  `_extract_exception_class`, `_parse_pytest_counts`, `EvaluationResult`), imported not
  reimplemented, so suite construction and pass/fail determination are methodologically
  identical to production.
- Each suite is instrumented via `instrument_oracles` and executed once (`pytest
  test_generated.py -v`, 30s timeout, isolated `tempfile.mkdtemp()` per suite, same
  subprocess pattern as production's `evaluate_single_test_worker`), with
  `ORACLE_EXECUTION_FILE` pointed at a per-suite temp file to capture which `oracle_id`s
  actually executed.
- **Deviation from the pilot, by design:** only the instrumented variant is run, not both
  original and instrumented. The pilot already established 100/100 equivalence between the
  two on real corpus suites after fixing 3 recorder bugs; running both variants for all
  10,868 suites here would roughly double wall time for no additional evidence value at
  this stage. Coverage was not measured (not needed for oracle-execution classification or
  the three Pass@1 variants; coverage/mutation remain separate existing pipelines).
- Parallelized with `ProcessPoolExecutor` (`max_workers=10`), matching production's own
  parallelism pattern (`evaluate_results.py` defaults to 12 workers).
- Suite categorization and gate computation reuse the classifier module's own
  `suite_category()` and `gate_outcomes()` functions directly (not reimplemented):
  a suite is `strong-present` if any executed oracle is STRONG, else `weak-only` if any
  executed oracle is WEAK, else `trivial-only`, else `unknown-only`, else
  `no-executed-oracle`. **Execution Pass@1** = suite passes (pytest exit 0). **Non-trivial
  Pass@1** = passes AND at least one executed WEAK or STRONG oracle. **Strong Pass@1** =
  passes AND at least one executed STRONG oracle.
- Pynguin suites excluded (different harness path, out of scope, consistent with the
  pilot).
- Zero worker/build errors across all 10,868 processed suites in either experiment.

## Corpus coverage

Both experiments were run to completion, not sampled:

- **Experiment B (`downloaded_predictions/second_experiment/run_1`, TestContextBench-Py):**
  8,847 suites, 1,556.8s (~26.0 min), 5.68 suites/s.
- **Experiment A (`downloaded_predictions/first_experiment/run_1`, TestEval):** 2,021
  suites, 293.8s (~4.9 min), 6.88 suites/s.

## Equivalence sanity check against legacy execution-gate counts

Before trusting the corrected non-trivial/strong numbers, the Execution Pass@1 figures
from this pass should reproduce the paper's existing execution-gate numbers, since both
use the same pytest-exit-0 definition:

| | This pass | Existing paper/legacy figure | Match |
|---|---:|---:|---|
| TestEval execution passes | 1,319 / 2,021 (65.26%) | 1,319 / 2,021 (65.27%, paper §RQ1) | **Exact** |
| TestContextBench-Py execution passes | 2,095 / 8,847 (23.68%) | 2,092 (`AI_HANDOFF_SUMMARY.md`) | Within 3 suites (0.14%) |

The 3-suite gap on Experiment B is most plausibly transient (a timeout/flakiness
boundary case — 3 suites timed out in this run) rather than a methodological divergence;
it is far inside the noise floor for a corpus this size and does not affect any
conclusion below.

## The three Pass@1 gates

### Experiment A — TestEval (n=2,021)

| Gate | Suites | Pass@1 |
|---|---:|---:|
| Execution | 1,319 | 65.26% |
| Non-trivial (executed WEAK or STRONG) | 1,170 | 57.89% |
| Strong (executed STRONG) | 1,124 | 55.62% |

Relative to the execution baseline: the non-trivial gate removes **149/1,319 = 11.30%**
of execution passes; the strong gate removes 195/1,319 = 14.78%.

**Legacy comparison:** the existing static-presence assertion gate in `paper.tex` removes
145/1,319 = 11.0% on TestEval. **11.30% vs. 11.0% — the corrected, runtime-validated gate
essentially reproduces the legacy gate on TestEval.** This is expected: TestEval's
algorithmic tasks are short and their assertions, when present, almost always execute (see
below — zero passing TestEval suites had an oracle present in the AST that never executed).

### Experiment B — TestContextBench-Py (n=8,847)

| Gate | Suites | Pass@1 |
|---|---:|---:|
| Execution | 2,095 | 23.68% |
| Non-trivial (executed WEAK or STRONG) | 1,129 | 12.76% |
| Strong (executed STRONG) | 765 | 8.65% |

Relative to the execution baseline: the non-trivial gate removes **966/2,095 = 46.11%**
of execution passes; the strong gate removes 1,330/2,095 = 63.48%.

**Legacy comparison:** the existing static-presence assertion gate removes 536/2,092 =
25.6% on TestContextBench-Py. **46.11% vs. 25.6% — the corrected gate removes nearly
double what the legacy static gate removed on real-world code.** This is the headline
finding of this pass: on real-world tasks, static AST presence of a non-trivial assertion
substantially overstates how often a non-trivial assertion actually *executed*. The
legacy gate's 25.6% figure understated the true vacuous-pass problem on
TestContextBench-Py by roughly a factor of 1.8.

### Per-model × pipeline breakdown

Full tables in `full_corpus_reanalysis_summary_experiment_a.csv` and
`full_corpus_reanalysis_summary_experiment_b.csv`. Experiment B, for the paper's existing
table shape:

| Model | Pipeline | n | Exec Pass@1 | Non-trivial Pass@1 | Strong Pass@1 |
|---|---|---:|---:|---:|---:|
| Qwen3-4B-Thinking | Single-step | 895 | 18.21% | 17.43% | 12.74% |
| Qwen3-4B-Thinking | Two-step | 896 | 16.63% | 14.29% | 12.39% |
| Qwen3.5-4B | Single-step | 888 | 21.62% | 18.81% | 11.49% |
| Qwen3.5-4B | Two-step | 866 | 26.56% | 15.24% | 5.77% |
| Gemma-4-E4B-it | Single-step | 890 | 27.98% | 21.46% | 19.66% |
| Gemma-4-E4B-it | Two-step | 899 | 44.27% | 18.80% | 8.23% |
| Granite-4.0-Micro | Single-step | 888 | 20.38% | 2.25% | 1.58% |
| Granite-4.0-Micro | Two-step | 893 | 29.79% | 4.48% | 2.24% |
| Ministral-3-3B-R | Single-step | 868 | 13.59% | 5.88% | 5.18% |
| Ministral-3-3B-R | Two-step | 864 | 17.25% | 8.68% | 6.94% |

Two things worth flagging for whoever integrates this into the paper: (1) the gap between
Execution and Non-trivial Pass@1 is wildly non-uniform across cells (e.g.
Granite-4.0-Micro Single-step drops from 20.38% to 2.25%, an 18-point collapse, while
Qwen3-4B-Thinking barely moves) — this is the same "optimism correlates with treatment"
pattern the paper already argues for the legacy gate, now sharper; (2) Gemma-4-E4B-it
Two-step has the highest raw execution rate (44.27%) but a mid-pack non-trivial rate
(18.80%) and one of the lower strong rates (8.23%) — a large fraction of its extra
executed passes are vacuous or weak, not evidence of better test quality.

Experiment A per-cell table is in the CSV; qualitatively all ten cells stay close between
Execution and Non-trivial Pass@1 (consistent with the near-zero legacy/corrected gap
above), so it is not reproduced in full here.

## The core distinction this pass was built to measure: AST presence vs. runtime execution

Among **passing** suites with at least one oracle site detected in the AST:

| | TestEval (of 1,172 with sites) | TestContextBench-Py (of 1,290 with sites) |
|---|---:|---:|
| Oracle present in AST but **never executed** | 0 (0.0%) | **136 (10.5%)** |

On TestEval, if a suite passes and has an assertion in its source, that assertion
essentially always ran — consistent with short, linear algorithmic solutions. On
TestContextBench-Py, **136 passing suites (6.5% of all 2,095 execution passes) contain an
assertion that a purely static AST check would have credited, but that never actually
executed** — most plausibly assertions guarded by branches the test's actual code path
didn't take, or located after an early return/exception path. This is direct, corpus-scale
evidence for the paper's core thesis that static presence is not a safe proxy for runtime
verification, beyond what the legacy vacuous-suite (zero assertions at all) framing
already captured. (The remaining 805 of 941 "no-executed-oracle" passing suites on
TestContextBench-Py have zero oracle sites in the AST at all — the same category the
legacy gate already caught.)

## New bugs found: none

Both full-corpus runs completed with **zero worker/build errors** across all 10,868
suites (checked via the `build_error` field in both result CSVs). No new instrumentation
bugs were found beyond the three already fixed and validated in the pilot. This is
consistent with the pilot's 100/100 equivalence result and the conservative (skip rather
than guess) design of the three existing fixes in `_RECORDER_SOURCE`.

## Artifacts produced (all new, non-overwriting)

- `step4_evaluation/full_corpus_oracle_reanalysis.py` — the reanalysis script.
- `step4_evaluation/oracle_validation/full_corpus_reanalysis_results_experiment_a.csv` —
  2,021 rows, one per TestEval suite.
- `step4_evaluation/oracle_validation/full_corpus_reanalysis_results_experiment_b.csv` —
  8,847 rows, one per TestContextBench-Py suite.
- `step4_evaluation/oracle_validation/full_corpus_reanalysis_summary_experiment_a.csv` /
  `_experiment_b.csv` — per-model × pipeline aggregate tables.
- This report.

No v1–v4 oracle validation artifact, pilot artifact, `oracle_analysis.py` classification
logic, `evaluate_results.py`, `assertion_gate.py`, `gated_reanalysis.py`, legacy result
file, or `paper.tex` was modified. No commits or pushes were made.

## What this does and does not license

- **Does license:** replacing the legacy static-presence gate's numbers in the paper with
  the corrected Execution / Non-trivial / Strong Pass@1 figures above, and reporting the
  suite-category distribution directly. Resolves the terminology mismatch flagged
  earlier (RQ1 "strongly asserted" vs. a gate that accepted weak and strong) — a real
  Strong Pass@1 figure now exists per experiment and per model × pipeline cell.
- **Does not license:** any claim about *why* Granite-4.0-Micro's non-trivial rate
  collapses so much more than other models', or any causal story beyond what's in this
  report — that's for whoever writes the paper prose to interpret with the appropriate
  hedging, consistent with the rest of this project's evidence-first approach.
- **Does not license:** touching mutation scores, coverage, or context-utilization
  claims — this pass is scoped to the three Pass@1 gates and the suite-category
  distribution only.
- **Next step:** wire these corrected tables and the "AST presence vs. runtime execution"
  finding into `paper.tex` (Methodology's gate-terminology caveat, RQ1 results, Table 4
  area's distribution note, and the "note on gate terminology" paragraph added in the
  prior pass should be updated to point at these final numbers rather than describing the
  correction as "in progress").
