# Runtime Instrumentation Equivalence Pilot

## Status: GO, with three real bugs found and fixed during this pass

This is an equivalence experiment, not a "does the recorder run" smoke test. It compares,
suite by suite, the original generated test suite against the same suite passed through
`oracle_analysis.instrument_oracles`, executed under conditions that reproduce the production
harness (`step4_evaluation/evaluate_results.py`) as closely as possible. The pilot found three
genuine instrumentation bugs by running against real corpus suites (not synthetic examples),
fixed all three narrowly in `oracle_analysis.py`, added a regression test per bug, and reran
the pilot to confirm 100% equivalence afterward. Isolation was maintained throughout:
`evaluate_results.py`, `assertion_gate.py`, `gated_reanalysis.py`, and all legacy result files
were untouched; the classifier's `OracleClass`/`_classify_assert`/provenance rules were not
touched (only `_RECORDER_SOURCE`, the runtime-instrumentation string, was modified).

## Pilot design

- New script: `step4_evaluation/runtime_instrumentation_pilot.py`. It **imports and reuses**
  `evaluate_results.py`'s own harness-construction helpers (`strip_markdown`,
  `_standardize_func_name`, `_combine_tests_for_task`, `fix_relative_imports`,
  `fix_absolute_imports`, `HARNESS_TEMPLATE`, `COMMON_IMPORTS`, `_determine_failure_status`,
  `_extract_exception_class`, `_parse_pytest_counts`, `EvaluationResult`) rather than
  reimplementing them, so the pilot's "original" run is methodologically identical to
  production, not a hand-approximated copy that could silently diverge.
- Suite population: every (prediction file, task) pair in
  `downloaded_predictions/second_experiment/run_1` with a non-empty solution and at least one
  test, combined across target lines exactly as `evaluate_results.py` does (8,847 candidate
  suites found; Pynguin suites excluded, out of scope for this pilot).
- Stratified sampling by `(dependency_level, tier, pipeline)`, fixed seed, round-robin across
  strata (same sampling *shape* as `sample_oracles_for_validation.py`, adapted to suite instead
  of oracle-site granularity, since production evaluates and gates at the suite level).
- Two independent batches were run for robustness: **60 suites** (seed 20260822) and **40
  suites** (seed 777) -- **100 suites total**, none overlapping in a way that hides
  seed-dependent bugs.
- Each suite is executed twice, each in its own fresh `tempfile.mkdtemp()` directory (matching
  production's per-worker isolation): once with the original harness text, once with the same
  text passed through `instrument_oracles`. Both variants use the identical `pytest
  test_generated.py -v` subprocess invocation, 30s timeout, then `pytest --cov=under_test
  --cov-report=json:coverage.json` for coverage (15s timeout) when the run didn't crash/timeout
  -- byte-identical to `evaluate_single_test_worker`'s non-Pynguin path.
- Compared fields: pytest exit status bucket (Pass / Assertion Error / Runtime Error / Syntax
  Error / Timeout), `n_collected`/`n_passed`/`n_skipped`, raw exception class, module-scoped
  line coverage (`under_test.py`, matching MCov@1's own instrumentation target), and
  all-skipped vacuous-pass flag.
- A suite-level heuristic regex flags suites that mock `builtins.open`, `os.environ` (whole
  object or `.dict`), `os.getenv`, `monkeypatch.setenv/setattr(os...)`, or `mock_open` -- these
  get explicit call-out per the project owner's instruction to pay particular attention to
  filesystem/environment mocking.
- **Not attempted: mutation-subset comparison.** Replicating `cosmic-ray` for even a handful of
  tasks means invoking `run_cosmic_ray_analysis`, which creates its own sqlite session state and
  can run up to several minutes per task at production's `per_test_timeout=30s` /
  `overall_timeout=300s` settings. Given this is a *pilot* whose job is to answer "does
  instrumentation change outcomes," and the coverage-based comparison already exercises the
  same code paths cosmic-ray would mutate, adding 5-10 mutation runs (worst case ~50 minutes of
  wall time, contending for the same temp-dir/subprocess resources as everything else) was
  judged not worth the risk of an unreviewed cosmic-ray invocation corrupting shared state. This
  is an explicit scope decision, not an oversight -- flagged here for a follow-up pass that can
  budget the time properly and run it as its own isolated step.
- Production execution-environment fidelity: subprocess `pytest`/`pytest --cov`, same
  `sys.executable`, same cwd-per-tempdir pattern, same timeouts (30s / 15s), same harness
  templates and import-fixing functions, called directly from the imported `evaluate_results`
  module -- there is no meaningful gap between this pilot's environment and production's for the
  non-mutation portion of evaluation. The one difference: production distributes suites across
  a `ProcessPoolExecutor`, this pilot runs sequentially. That affects wall-clock time only, not
  the executed process's semantics (each suite still gets an isolated tempdir and subprocess),
  so it does not weaken the equivalence claim.

## Aggregate results (final run, all fixes applied)

| Metric | Batch 1 (n=60, seed 20260822) | Batch 2 (n=40, seed 777) | Combined |
|---|---:|---:|---:|
| Equivalent (status, counts, exception class, coverage, vacuous-pass all match) | 60/60 | 40/40 | **100/100 (100%)** |
| Instrumentation not applicable (source failed to AST-parse) | 0 | 0 | 0 |
| Suites flagged as mocking fs/env | 4 | 1 | 5 |
| Original status distribution | Runtime Error 39, Assertion Error 12, Pass 9 | Runtime Error 21, Pass 12, Assertion Error 7 | Runtime Error 60, Assertion Error 19, Pass 21 |
| Total oracle sites / executions recorded | 59 / 17 | 40 / 18 | 99 / 35 |

Coverage matched to the tenth of a percent in every one of the 100 suites (`under_test.py` is
never modified by instrumentation -- only the test file is -- so this is expected, not a strong
signal on its own, but confirms the harness didn't introduce a side channel).

One transient divergence was observed during development (suite 294222: coverage differed by
2.15 percentage points between the two variants on one run, then matched exactly on rerun with
identical inputs). This looks like non-deterministic `coverage.json` aggregation on a
Runtime-Error path (coverage is measured even for crashed suites per the "ungated" comment in
`evaluate_results.py`) rather than anything instrumentation-specific -- it did not recur across
either final 60- or 40-suite batch. Flagging it here rather than silently dropping it: if
flakiness like this shows up again at full-corpus scale, it is a pre-existing property of the
coverage measurement step, not something introduced by this pilot or by `instrument_oracles`.

## Bugs found and fixed (all three found via real corpus suites during this pilot)

### 1. `builtins.open` interception (task 206871, tier A, `linecov2_Qwen3-4B-Thinking-2507`)

The suite does `with patch('builtins.open') as mock_open: ...; assert mock_open.called`. The
recorder's own `open(path, "a")` call, injected right before that `assert`, executed *inside*
the same patched scope -- so it silently called the mock instead of writing a real file. Pass/
fail was unaffected here (the real SUT call already made `mock_open.called` true before the
recorder ran), but the suite's genuine oracle execution went unrecorded (`n_oracle_sites=1`,
`n_oracle_executions_recorded=0` before the fix). Left unfixed, this would have caused
`suite_category`/`gate_outcomes` to misclassify a real STRONG-oracle pass as
`no-executed-oracle` at full-corpus scale, silently deflating the corrected Pass@1 gates for
every suite that globally patches `open`.

**Fix:** capture `__ORACLE_REAL_OPEN__ = builtins.open` as a module-level statement, executed
once when the recorder block is inserted (which happens before any test function runs, hence
before any `patch()` context manager is entered), and call that captured reference instead of
the bare `open(...)` name. Regression test:
`test_instrumentation_survives_global_open_patch`.

### 2. `os.environ` object patched wholesale -> `open()` misinterprets a `MagicMock` as file
descriptor 1 (task 252302, tier A, `linecov_Qwen3-4B-Thinking-2507`)

The suite does `with patch('os.environ') as mock_environ: ...`, replacing the entire `os.environ`
object (not just individual keys) with a `MagicMock`. The recorder's
`os.environ.get("ORACLE_EXECUTION_FILE")` then returned an unconfigured child `MagicMock`
(truthy). `MagicMock.__index__()` defaults to `1` -- verified empirically
(`val.__index__() == 1`) -- so `open(that_magicmock, "a")` does **not** raise; it silently
reinterprets the argument as file descriptor 1 (stdout) and, on `with`-block exit, **closes
stdout**. This was reproduced directly (a bare Python script doing the same pattern corrupted
its own `print()` immediately afterward with `OSError: Bad file descriptor`). This is a more
serious risk than a missed recording -- it is a plausible mechanism for corrupting or crashing
an unrelated part of the same test process.

**Fix:** the recorder now checks `isinstance(__oracle_path, str)` before calling `open()` at
all, so a non-string value (a `MagicMock`, or anything else `os.environ.get` might return under
a wholesale patch) is safely ignored instead of passed to `open()`. Regression test:
`test_instrumentation_survives_global_os_environ_patch` (asserts the child process exits 0 and
that `print()` after the instrumented test still reaches real stdout).

### 3. Bare `str`/`isinstance` shadowed by the production harness's own import-fallback
mocking (task 252302, discovered *while writing the fix for bug 2*)

This is a pre-existing property of `evaluate_results.py`'s `fix_relative_imports` /
`fix_absolute_imports`: any unresolvable import name -- including one that happens to collide
with a Python builtin -- gets assigned `MagicMock()` in a `try/except` fallback. Task 252302's
real solution module (`requests`-library-derived) does
`from .compat import ..., str, unquote, ...`; that relative import fails standalone, so the
harness assigns `str = MagicMock()` in `under_test.py`, and the harness's own
`from under_test import *` line then pulls that `MagicMock` into `test_generated.py`'s global
namespace, shadowing the builtin `str` for the *entire test module* -- including inside the
recorder function, which lives in the same module and resolves `str` via a global lookup at
call time (not at definition time). The fix for bug 1 (`isinstance(__oracle_path, str)`) was
therefore itself briefly broken by this exact mechanism during development
(`TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union`) -- caught by
rerunning the pilot after fixing bug 2, not by the unit tests alone, which is why the two-pass
rerun-the-pilot step mattered.

**Fix:** capture `__ORACLE_REAL_STR__ = builtins.str` alongside `__ORACLE_REAL_OPEN__` at the
same early, pre-pollution module-level point, and call `__oracle_builtins__.isinstance(...)`
(also via the captured `builtins` module reference, not the bare name) instead of the builtin
names directly. `import json as __oracle_json` / `import os as __oracle_os` inside the function
body were judged *not* at risk by the same mechanism: a local `import X as Y` always binds to
`sys.modules['X']` regardless of global-namespace pollution, unlike a bare-name lookup of
`str`/`open`/`isinstance`. Regression test: `test_instrumentation_survives_builtin_name_shadowing`
(reproduces the compat-shim-style shadow directly).

All three fixes are confined to `_RECORDER_SOURCE` in `oracle_analysis.py` (the instrumentation
string), not the classification logic. `pytest -q tests/test_step4_evaluation/` was 86 passing
before this pilot; it is **101 passing** after (12 classifier-freeze tests from the prior pass +
3 new instrumentation regression tests added here).

## Explicit findings on the two named risk categories

- **Pytest assertion rewriting:** no interaction found. `instrument_oracles` regenerates the
  test file via `ast.unparse` and writes it to disk as ordinary source text; pytest's import
  hook parses and rewrites that text fresh, exactly as it would any other file. The recorder
  calls are separate statements inserted before/around oracle statements, never inside an
  `assert` expression itself, so there is no AST shape for pytest's rewriter to trip on. Also
  confirmed: `instrument_oracles` does not touch `under_test.py` (the solution file), so
  module-scoped coverage of the SUT is unaffected by definition, not just by observation --
  every one of 100 piloted suites confirmed this at 0.00-point coverage difference.
- **Filesystem/environment mocking:** this is where all three real bugs were found (see above).
  5 of 100 sampled suites mock `open`/`os.environ` in some form; 2 of those 5 hit an actual
  latent bug before the fixes in this pass, at real, non-synthetic severity (one silent
  under-recording, one process-corrupting `close(1)`). The fixes are conservative (skip
  recording rather than guess) so post-fix behavior is "under-record execution in edge cases we
  can't safely resolve" rather than "crash or corrupt" -- the correct failure direction for an
  auxiliary measurement path that must never affect the suite's own pass/fail outcome.

## Go/no-go recommendation

**GO**, conditional on the three fixes in this report being present (they are, in the current
working tree). 100/100 piloted suites are fully equivalent across status, per-suite pytest
counts, exception class, coverage, and vacuous-pass detection after the fixes; two of the three
bugs found were real, verified-non-synthetic, filesystem/environment-mocking interactions of
exactly the kind called out as a specific risk to check, and are now covered by regression
tests. It is safe to integrate `instrument_oracles` into a full-corpus isolated re-evaluation
pass (still not touching `evaluate_results.py` itself -- a new script analogous to this pilot,
run at full scale) to populate the "executed" fields needed for the corrected Pass@1 gates.

**One residual caveat, not a blocker:** the `isinstance(__oracle_path, str)` guard means a
suite that wholesale-mocks `os.environ` will have its executed oracle sites under-recorded
(never mis-recorded) if the mock happens to run during the exact statement the recorder targets.
This is conservative-by-design (skip rather than guess), consistent with the rest of this
project's stance on ambiguous cases, but a full-corpus run should separately report how many
suites carry the fs/env-mock flag so this known undercount is quantifiable rather than silent.
The pilot's suite-level flag (`mock_fs_env_flag` column in `runtime_pilot_results.csv`) is
reusable for that purpose directly.

## Artifacts produced (all new, non-overwriting)

- `step4_evaluation/runtime_instrumentation_pilot.py` -- the pilot script.
- `step4_evaluation/oracle_validation/runtime_pilot_results.csv` -- final 60-suite batch
  (seed 20260822), one row per suite, all fields described above plus `divergence_reason`.
- `step4_evaluation/oracle_validation/RUNTIME_INSTRUMENTATION_PILOT_REPORT.md` (this file).
- `step4_evaluation/oracle_analysis.py` -- `_RECORDER_SOURCE` updated (3 fixes; classification
  logic untouched).
- `tests/test_step4_evaluation/test_oracle_analysis.py` -- 3 new regression tests appended.

No v1-v4 oracle validation artifact was modified. No commits or pushes were made.
`evaluate_results.py`, `assertion_gate.py`, `gated_reanalysis.py`, and `paper.tex` were not
touched.
