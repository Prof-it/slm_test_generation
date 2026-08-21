# Pynguin (DynaMOSA) Baseline: Configuration, Rationale, and Results

## Status: complete, including paper.tex integration (methodology subsection `sec:pynguin-method`, results Table~\ref{tab:pynguin_results} and discussion at the end of RQ1, mutation comparison, xfail-excluded sensitivity, the runtime-validated classifier gate (Non-trivial=Strong=7.83%, `full_corpus_oracle_reanalysis_pynguin.py`), and the historical/recent negative control in RQ3)

Documents the final configuration used for the Pynguin search-based-testing
baseline on TestContextBench-Py (300 tasks), the diagnostic work that led to
each configuration choice, and the resulting Pass@1/assertion numbers. Written
before touching `paper.tex` so the methodology paragraph there can cite this
directly instead of re-deriving it.

## Configuration (final)

| Parameter | Value | Rationale |
|---|---|---|
| Pynguin version | 0.45.0 | pinned in `step3_modelling/requirements_pynguin.txt` |
| Algorithm | DYNAMOSA | Pynguin's default many-objective search algorithm |
| Search-time budget | 60 seconds | see "Budget selection" below |
| Assertion generation | `SIMPLE` | see "Assertion-mode selection" below (not Pynguin's own default, `MUTATION_ANALYSIS`) |
| Seeds | 42, 43 (2 replicates) | independent search runs, same budget/mode |
| Python (execution env) | 3.10.0, Docker (`slm-pynguin:v3`, `python:3.10-slim` base) | Pynguin's bytecode-instrumentation approach requires Python < 3.11 |
| Stopping condition | wall-clock `--maximum-search-time`; no coverage/goal-based early stop configured | matches Pynguin's default search termination behavior |
| xfail handling | tracked, not filtered — `has_xfail_tests`/`num_xfail_tests` recorded per task by `evaluate_results.py`, same as for LLM-generated suites | no special-casing needed; the existing harness already treats Pynguin output as just another prediction file (see `is_pynguin` branch) |
| Evaluator | `step4_evaluation/evaluate_results.py`, unmodified pipeline logic (one bug fix, see below), `.venv310_pynguin` (Python 3.10.0, pytest 8.4.2) | same evaluator as the LLM suites — Pynguin and LLM predictions are scored by the identical code path, not separate logic |

Runner: `step3_modelling/run_pynguin_v2.py`. Generation command (final run):

```
docker run --rm -v "<repo>:/app" -w /app slm-pynguin:v3 \
  python step3_modelling/run_pynguin_v2.py --search-time 60 --seeds 2 --base-seed 42 \
  --assertion-generation SIMPLE \
  --output-dir step4_evaluation/pynguin_final_run_simple --python-exec python
```

Scoring command (run once per mode):

```
step4_evaluation/.venv310_pynguin/Scripts/python.exe step4_evaluation/evaluate_results.py \
  --input-dir step4_evaluation/pynguin_final_run_simple \
  --output-dir evaluation_results/pynguin_simple --workers 8
```

## Budget selection: 60 seconds

Initial pilot compared 30/60/120/600s on the full 300-task set: Pass@1 and
`has_assertions` were identical across all four budgets. Because identical
results across a 20x budget range is exactly what a search-time propagation
bug would also look like, this was independently audited (not just accepted)
via `step3_modelling/pynguin_budget_audit.py`, which reran 5 representative
tasks (3 DONE, 2 NO_CODE at every budget) capturing Pynguin's own internal
statistics (`SearchTime`, `TotalTime`, `AlgorithmIterations`,
`FinalBranchCoverage`, `Goals`) and a normalized SHA256 hash of the generated
test file per (task, budget) pair. Findings:

- `SearchTime`/`TotalTime` in Pynguin's own statistics CSV matched the
  requested budget exactly at every level — the CLI argument is reaching
  Pynguin's runtime, not being silently dropped or clamped.
- `AlgorithmIterations` scaled with budget (real search work continued to
  happen at 600s vs 30s) while `FinalBranchCoverage` plateaued — consistent
  with a genuine coverage ceiling for these targets, not a premature-stopping
  artifact.
- NO_CODE failures (import errors, `NameError`s from missing type stubs,
  coroutine-detection rejections) were structural and budget-independent —
  more search time cannot fix a target Pynguin cannot import or instrument.
- Generated-test hashes were consistent with genuine convergence for the
  audited tasks.

**Framing used in the paper**: measured effectiveness saturated within the
shortest evaluated budget (30s) for this benchmark's targets; this is *not*
claimed to generalize beyond TestContextBench-Py, and is not phrased as
"Pynguin always converges within 30s" (some tasks do additional search work at
higher budgets without a coverage improvement — saturation, not literal
instantaneous convergence). 60s (not the observed-sufficient 30s) was chosen
as the final budget as a conservative margin above the measured saturation
point, while still keeping full-corpus wall time (300 tasks x 2 seeds x 60s,
plus per-task overhead) within a run replicable in a few hours rather than
requiring the 600s budget's prohibitive multi-day full-corpus runtime.

## Assertion-mode selection: SIMPLE over MUTATION_ANALYSIS

Pynguin's own default assertion-generation mode, `MUTATION_ANALYSIS`, prunes
any assertion that doesn't kill one of Pynguin's own internally-generated
mutants. This is a methodological asymmetry against the SLM baseline: SLMs
write assertions blind to any specific fault/mutant target, so scoring
Pynguin's assertions only after mutant-informed pruning would not be a fair
tool-level comparison.

Confirmed via `step3_modelling/pynguin_assertion_mode_check.py` (5 audit
tasks, 60s, MUTATION_ANALYSIS vs SIMPLE) that switching to SIMPLE is free:
equal-or-more assertions per task, identical `FinalBranchCoverage` in every
case. Confirmed again at full scale after generation+scoring
(600 records per mode, seeds 42+43 combined):

| Mode | Pass@1 | has_assertions | has_xfail_tests |
|---|---:|---:|---:|
| SIMPLE (final) | 47.3% | 39.0% | 19.2% |
| MUTATION_ANALYSIS (secondary) | 47.2% | 6.0% | 20.5% |

Pass@1 is statistically indistinguishable between modes (47.3% vs 47.2%, a
0.1pp difference over 600 tasks) while `has_assertions` differs by nearly 7x
(39.0% vs 6.0%). SIMPLE mode is used as the primary/reported baseline;
MUTATION_ANALYSIS is retained as a secondary artifact
(`step4_evaluation/pynguin_final_run/`, scored at
`evaluation_results/pynguin_mutation_analysis/`) rather than deleted, in case
a mutation-aware comparison is useful elsewhere.

## Harness fix: `strip_markdown()` SyntaxError corruption

Pynguin sometimes copies the SUT's own docstring — including any
```-fenced usage example the docstring documents — into a generated test's
string-literal input data. `evaluate_results.py`'s `strip_markdown()` used a
`re.search`-based fence-stripping regex that matched this embedded sequence
anywhere in the text (not just at true LLM-response boundaries), corrupting
otherwise-valid Python into a `SyntaxError`. Fixed with an early-return: if
the raw code already parses via `ast.parse()`, return it unchanged before any
fence-stripping heuristic runs (those heuristics exist only to recover code
from conversational/fenced LLM wrapping, which by definition doesn't already
parse cleanly).

Impact, quantified before and after:
- Pilot re-scored after the fix: Pass@1 40.0% -> 43.3%, `has_assertions`
  3.3% -> 6.7% (30-task pilot, MUTATION_ANALYSIS mode, all four budgets
  identically affected).
- Zero exposure on the existing, already-published 9,000-suite LLM corpus
  (`evaluation_results/second_experiment/run_1/`): confirmed 0 records with
  `raw_exception_class == "SyntaxError"` in that corpus, so this bug is
  Pynguin-specific and does not affect any previously reported LLM numbers.
- Regression tests added to
  `tests/test_step4_evaluation/test_evaluate_results.py::test_strip_markdown`:
  (1) already-valid Python containing a literal ` ``` ` inside a string
  stays unchanged; (2) a genuinely fenced LLM response with an inner ` ``` `
  in its own string literal is still cleaned correctly. Verified passing,
  and verified non-regressive against the pre-fix behavior via a
  `git stash`-based before/after comparison of the full existing test suite.

## Final full-corpus results (SIMPLE mode, seeds 42+43 combined, n=600)

| Status | Count | % |
|---|---:|---:|
| Pass | 284 | 47.3% |
| Pytest Error | 171 | 28.5% |
| No Code | 132 | 22.0% |
| Assertion Error | 9 | 1.5% |
| Runtime Error | 4 | 0.7% |

`has_assertions`: 39.0%. `has_xfail_tests`: 19.2%.

Per-seed DONE/NO_CODE split at generation time (before scoring): seed 42 =
234 DONE / 66 NO_CODE; seed 43 = 234 DONE / 66 NO_CODE (0 TIMEOUT — the
`psutil`-based process-tree kill fix, see below, eliminated the stalls
present in earlier attempts).

## Known infrastructure issues encountered and fixed (generation run)

- **Subprocess-tree hang on timeout** (Windows/Docker): Pynguin's internal
  `multiprocess`-based worker isolation places a forked grandchild into its
  own session/process group, so `os.killpg`-based tree-killing (as used
  elsewhere in `evaluate_results.py`'s `_run_with_killtree`) does not reach
  it — observed as multi-hour stalls with a nearly-idle direct child and a
  ~90%-CPU grandchild. Fixed with `_run_with_psutil_killtree()` in
  `run_pynguin_v2.py`, which walks the actual OS PID ancestry via
  `psutil.Process(...).children(recursive=True)` and SIGKILLs each
  descendant directly by PID, independent of process-group membership.
  Verified via a synthetic `os.setsid()`-forking reproduction inside the same
  Docker image before trusting it on the real run.
- Import-fixing (`fix_relative_imports`/`fix_absolute_imports`, reused from
  `evaluate_results.py`) is applied to the module Pynguin instruments at
  *generation* time, matching the fix applied at *evaluation* time for both
  Pynguin and LLM predictions — the predictions file itself stores the
  original unfixed `python_solution_full`, so both Pynguin and LLM suites go
  through the identical fix step in the evaluator, not a special Pynguin path.

## Canary/audit task selection

The 5 tasks used in both the budget audit and assertion-mode check
(229284, 28838, 619902, 889249, 363593) were chosen from the initial 30-task
pilot as 3 tasks with `pynguin_status == "DONE"` across every pilot budget
and 2 tasks with `pynguin_status == "NO_CODE"` across every pilot budget —
i.e., a small set spanning both the "generation succeeds" and "generation
structurally fails" outcomes, so the audit would catch a budget-sensitivity
regression in either direction.

## Statistics variables captured during diagnostics

Via Pynguin's `--statistics_backend CSV --output-variables ...`:
`TargetModule`, `SearchTime`, `TotalTime`, `AlgorithmIterations`, `Goals`,
`FinalBranchCoverage`, `FinalLineCoverage`, `Assertions`, `DeletedAssertions`,
`NumberOfCreatedMutants`, `NumberOfKilledMutants`, `MutationScore`,
`RandomSeed`.
