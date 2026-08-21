# Extraction Defect Repair

## Status: complete for 14 of 19 residual tasks; 5 remain, 4 deliberately unrepaired

Repairs the 19 residual "defective" TestContextBench-Py tasks reported in
`dataset_health.json` and discussed throughout `paper.tex`'s Dataset
Construction / Threats to Validity / Limitations sections.

## Root-cause breakdown (19 tasks)

| Category | Count | Task IDs | Repaired? |
|---|---:|---|---|
| Same-file extraction gap (`NameError`) | 13 | 363593, 896053, 25953, 162266, 51723, 119665, 872607, 718898, 990106, 432562, 234352, 235598, 577470 | **Yes** |
| `fix_relative_imports` harness bug (`SyntaxError`) | 1 | 916895 | **Yes** (harness-level fix, no dataset patch) |
| Nested closure over per-call local state (`SyntaxError`, `nonlocal`) | 1 | 894422 | **No** — not repairable without changing behavior (see below) |
| Python 3.11-only feature (`ImportError`: `typing.Self`, `datetime.UTC`) | 4 | 696476, 221252, 86422, 461140 | **No** — deliberate environment choice, already investigated via the full-corpus Python 3.11 re-execution (`RECENCY_ROBUSTNESS_REPORT.md`-adjacent Table~\ref{tab:py_version}); not an extraction defect |

**Residual defective count after this repair: 5 of 300 (1.67%)**, down from
19 (6.33%), for the *released dataset files* going forward (ceiling 98.33%, not
93.67%). This paper's own already-reported Pass@1 figures were computed under the
original 19-defect specification (ceiling 93.67%) and are **not** retroactively
recomputed under the repair; the two specifications and their ceilings should not be
blended. See "Corpus-level effect" below for the bounded, separately-reported
sensitivity check under the repaired specification.

## Root cause: `create_v2_dataset.py` only preserves imports, not same-file dependencies

The extraction pipeline wraps the target function in `class Solution:` and
prepends whatever `import` statements already existed at the top of the
source file. It has no logic to detect or pull in other **same-file**
module-level definitions (classes, `TypeAlias` assignments, constants) that
the function's signature or body reference. For all 13 `NameError` cases
investigated, the missing name is defined earlier in the exact same source
file the function was extracted from (verified against the cloned repo at
`sources/repos/<repo>/...` for every case).

Two of the 13 required a second, non-obvious repair round: the initial
single-shot fix (patching just the *reported* missing name) still failed to
import for tasks 718898 (also needed `TasksMaster` and `app_logger`, both
referenced deeper in the function) and 432562 (also needed
`ISOELECTRIC_POINT_MAX`), and task 235598's `Deserializer` fix initially used
a bare `unittest.mock.MagicMock()` fallback which behaves inconsistently as
a base class in Python's `class` statement (works under some `exec()`
globals configurations, fails under others with a confusing `KeyError`); the
task's repair was rewritten to a proper minimal `Generic`-subscriptable stub
class instead. This is exactly why every repair is followed by an actual
subprocess import test (not just `ast.parse`), not accepted on a single
static check.

## A separate, more consequential bug found in the same investigation

Task 916895's reported `SyntaxError` ("'(' was never closed") is **not**
an extraction defect at all. `evaluate_results.py`'s `fix_relative_imports()`
operates line-by-line and had no handling for multi-line, parenthesized
relative imports (`from ...pkg import (\n    a,\n    b,\n)`); it matched
only the opening line, producing a corrupted `( = _MagicMock()` statement
and silently orphaning the continuation lines. This function is used to
build the reference module for **every** SLM prediction and every Pynguin
prediction across the whole study (9,000 + 600 generations), so this was
audited for blast radius before being treated as a one-off: scanned all 300
TestContextBench-Py `python_solution_full` values and all TestEval dataset
files for the same pattern. Exactly one task in the entire corpus
(916895) contains a multi-line parenthesized relative import. Fixed at the
function level in `evaluate_results.py` (also used by `run_pynguin_v2.py`,
which imports the same function rather than duplicating it), with a new
regression test (`test_fix_relative_imports`) covering both the pre-existing
single-line behavior (unchanged) and the new multi-line case. Verified
non-regressive: a before/after comparison of `fix_relative_imports()`'s
output over all 300 tasks' reference modules shows exactly one task's output
differs (916895); the other 299 are byte-identical.

## Why the already-generated predictions did not need to be regenerated

All 13 `NameError` repairs only **add** missing module-level definitions
immediately before the wrapping `class Solution:` block — they never change
the target function's own signature or docstring, which is the only part of
`python_solution_full` visible to the SLM cohort at generation time (Tier A:
signature + docstring; Tier B/C: additionally, dependency stubs and mock
hints, neither of which include these same-file sibling definitions either).
The already-generated predictions for these 13 tasks (390 = 13 tasks x 30 configs)
therefore remain valid artifacts of the original prompts. Only **re-evaluation**
against the corrected reference modules was needed, not regeneration via
SLM inference. (916895's own 30 predictions are likewise unaffected, for the
same reason — its defect was in the evaluation harness, not the prompt content
at all. Together, 390 + 30 = 420 predictions were re-scored; see "Re-scoring"
below. The remaining 5 tasks' 150 predictions were not touched.)

## A note on repair fidelity: importability-verified, not all behaviorally exact

The 13 `NameError` repairs vary in how closely they reconstruct the original source.
Most (`BBoxType`, `_SHARE_OBJECT_TYPES`, `XrLike`, `ZarrArray`/`VLenUTF8`,
`IterableRoiT`/`RoiT`, `MINUTES`/`HOURS`, `BackgroundScheduler` import,
`MaterializeSessionRequest`, `TOP_N`/`ISOELECTRIC_POINT_MAX`, `TypeGuard`/`TYPE`,
`DaskArray`/`DaskJsonDict`) are verbatim reconstructions of the actual missing
definition, copied from the cloned source repository. A smaller subset are
necessarily minimal, hand-written stand-ins rather than exact reconstructions,
sufficient to make the module import and execute but not behaviorally identical to
the real class: the `Filter`/`MetadataQuery`/`MetadataResult`/`QueryObject`/
`QueryResult` family (task 363593), `ResultAsyncGenerator` (task 119665),
`TasksMaster` (task 718898), and `Deserializer`/`MsgPackDeserializer` (task 235598).
All 13 are validated as **importability** repairs (every one confirmed to actually
import and execute via a real subprocess test before the dataset was patched, and
the full 284-suite re-scoring below confirms zero regressions against the original
static-gate outcomes). They are not all separately demonstrated to be **behaviorally**
faithful to the original source — the one place this limitation surfaces directly in
the results is task 119665's single status change from Assertion Error to Runtime
Error (`unittest.mock.InvalidSpecError`, see below), where a generated test's
`mock.patch(..., spec=ResultAsyncGenerator)` call exposes that the stand-in doesn't
carry the same interface `unittest.mock`'s spec validation checks for.

## Task 894422: not repairable without changing behavior

`inference_loop` is a nested `async def` inside a larger enclosing method in
the original source (`streaming_kyutai_stt.py`), closing over two variables
(`opus_stream_inbound`, `transcription_queue`) that are **local to each
invocation** of the enclosing method (freshly created per call: `opus_stream_inbound = sphn.OpusStreamReader(...)`,
`transcription_queue = asyncio.Queue()`). There is no faithful textual
repair that preserves per-invocation lifetime semantics without inventing
new behavior. Converting the `nonlocal` references into `self.` instance
attributes (the only readily-scriptable fix) would change per-call fresh
state into shared instance state, altering what the code actually does
across repeated or concurrent calls to a `Solution()` instance — precisely
the kind of change this project's standing discipline (never silently change
behavior while calling it a "fix") rules out. Left as a genuine, permanent
residual defect.

## Re-scoring: the 420 existing predictions for these 14 repaired tasks were re-evaluated, not regenerated

`step2_data_preperation/build_repair_rescoring_subset.py` builds scratch,
filtered copies of all 30 `downloaded_predictions/second_experiment/run_1/`
files (14 tasks each, 420 rows total) with the 13 `NameError` tasks'
`python_solution_full` replaced by the repaired value (pulled from the
now-patched `TestEval/data/realworld-py-v2.jsonl`, single source of truth);
916895 is copied unchanged (only the harness function needed fixing). The
original `downloaded_predictions/` files are never modified. Scored via the
normal `evaluate_results.py` against this scratch subset, output at
`evaluation_results/extraction_repair_rescoring/`.

### Result (420 records: 14 tasks x 30 configs)

| Status | Before repair | After repair |
|---|---:|---:|
| Pass | 37 | 73 |
| Assertion Error | 17 | 43 |
| Runtime Error | 350 | 288 |
| Pytest Error | 9 | 9 |
| No Code | 7 | 7 |

64/420 (15.2%) records change status. Every change moves from `Runtime
Error` (forced by the broken reference module, independent of what the SLM
generated) to a real, content-dependent outcome: 36 to `Pass`, 27 to
`Assertion Error`, and one from `Assertion Error` to `Runtime Error`
(`unittest.mock.InvalidSpecError`, task 119665 — a generated test does
`mock.patch(..., spec=ResultAsyncGenerator)` and the repair's necessarily
minimal stub class doesn't carry the same interface `unittest.mock`'s spec
validation checks for; a known, acceptable limitation of using lightweight
stand-ins rather than full reimplementations for one class out of 13
repairs). Pass@1 within this 14-task/420-record subset moves from
37/420=8.81% to 73/420=17.38%.

### Corpus-level effect

Incorporating the 36 newly-genuine passes into the full 9,000-generation
Experiment B corpus: **23.24% (2,092/9,000) -> 23.64% (2,128/9,000)**, a
+0.40 percentage-point movement. This is comparable in size to the Python
3.11 robustness check's own movement (23.24% -> 23.57%, +0.33pp) and does
not change any conclusion in the paper. Consistent with how that check was
reported, the pre-repair 23.24% specification is retained as the paper's
primary reported figure (keeps every other headline table, RQ section, and
robustness check computed on one consistent denominator), and this repair's
effect is reported as a bounded, quantified correction rather than used to
silently re-baseline the whole corpus.
