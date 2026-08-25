# Classifier v4 changelog

**Status: this is a fix pass triggered by the v3 AI-assisted audit, not a freeze.** At
the time this document was written, the classifier was a *candidate* for freeze pending
real human review of the v4 enriched sample. An AI-assisted audit (this document's own
investigation included) is a supplementary signal, useful for finding systematic bugs,
but was not sufficient on its own to certify the taxonomy implementation for the paper's
claims. That full human review has since been completed on all 250 sample rows — see
`HUMAN_VALIDATION_V4_FULL250_RESULTS.md` for the validated accuracy figure (62.8%) and
`CLASSIFIER_FREEZE_DECISION.md` for the resulting freeze decision. Do not cite this
document's own AI-audit agreement figures as classifier accuracy.

## Why this pass happened

The v3 AI-assisted audit (`oracle_ai_audit_v3_report.md`) found 78/250 disagreements
between an LLM auditor (full test context, blinded to the classifier's prediction) and
the static classifier, with 65 of those attributable to the classifier over-predicting
UNKNOWN. Per the project owner's instruction ("if errors reveal systematic rules, fix
once, regenerate the validation sample, and then freeze"), this pass investigated each
disagreement's actual source before writing any fix, confirmed genuine root causes vs.
AI-auditor errors, implemented narrowly-scoped fixes for the confirmed causes only, and
regenerated the validation sample (v4) rather than reusing v3.

## Investigation method

For every disagreement cluster, the full `enclosing_test_source` of several representative
rows (not just the truncated `oracle_source` snippet in the report table) was read before
any code change, per the directive's explicit requirement. This surfaced two important
corrections to the v3 report's own conclusions:

1. Several "35 STRONG(ai)/UNKNOWN(classifier)" rows are **not** classifier bugs. The
   dominant example is `assert solution.twoSum([2,7,11,15], 9) == [0, 1]`, a LeetCode
   boilerplate template that recurs across dozens of unrelated tasks. It calls a method
   (`twoSum`) that is **not** the task's actual focal function — the classifier is
   correctly conservative in refusing to treat an off-target boilerplate call as
   SUT-derived. The AI auditor mislabeled these as STRONG by assuming any `solution.*`
   call is meaningful. Confirmed by checking `func_name` against the call target for
   several instances (e.g. task 864549's real focal function is `to_key_val_list`, not
   `twoSum`).
2. The v3 report's own "Patterns observed" section claims `assert False, "msg"`
   fail-if-reached idioms had zero disagreements. This is incorrect — the disagreement
   table itself lists 8 such rows (predicted `UNKNOWN` via `statically_failing_constant`,
   AI-labeled `TRIVIAL`). On inspection, the classifier's choice is the textually correct
   one: `TRIVIAL` requires "statically satisfied" (i.e. passes), but `assert False` is
   statically **unsatisfied** — it fails whenever reached. Whether reaching it is a bug
   or a reachable "should never happen" sentinel is a control-flow question the taxonomy
   deliberately punts to UNKNOWN. No fix applied; this is an AI-auditor definitional
   error, not a classifier gap.

## Confirmed root causes fixed in this pass

### Cluster A — provenance under-resolution

| Root cause | Fix | Function | Example (before -> after) |
|---|---|---|---|
| `sut_names` doesn't match calls that differ from the focal name only by a leading underscore (e.g. focal `_load_history`, test calls module-level `load_history`) | Underscore-insensitive name comparison in call-to-focal matching | `_call_is_focal` (new `_normalize_focal_name`) | `result = load_history(...)` with focal `_load_history`: `UNKNOWN comparison_without_sut_provenance` -> `STRONG sut_derived_specific_comparison` |
| A bare `assert solution.method(...)` whose call form doesn't match any recognized special pattern (startswith/isinstance/len/...) fell through to `opaque_predicate_call` even when the call itself is directly the focal function | If the call itself (not a nested subcall) is focal, treat as coarse truthiness, matching how bare `Name` truthiness is already handled | `_classify_assert` (Call branch) | `assert solution.is_banned_ip(...)`: `UNKNOWN opaque_predicate_call` -> `WEAK sut_derived_truthiness_direct_focal_call` |
| `with redirect_stdout(f): sol.remove_item(...)` followed by `assert f.getvalue()...` — the with-target `f` captures a side effect of the focal call but wasn't tracked as derived (only `patch`/`patch.object` targets were) | Track `redirect_stdout`/`redirect_stderr`/`contextlib.redirect_stdout`/`contextlib.redirect_stderr` with-targets as derived, but only when a focal call occurs somewhere in the block body (conservative — no capture, no derivation) | `analyze_block` (With/AsyncWith handling) | `assert f.getvalue().strip() == expected_output`: `UNKNOWN` -> `STRONG sut_derived_specific_comparison` |
| `args, kwargs = mock_method.call_args` then `assert isinstance(args[0], str)` — mock call-argument state was tracked in a separate `mocks` set used only by mock-contract rules, never fed into the general `derived` set consulted by isinstance/comparison rules | Names assigned from `<mock>.call_args`/`.call_args_list`/`.await_args`/`.await_args_list` now also join `derived`, not just `mocks` | `analyze_block` (Assign handling, new `_rhs_is_mock_call_capture`) | `assert isinstance(args[0], str)`: `UNKNOWN coarse_check_without_sut_provenance` -> `WEAK sut_derived_runtime_type` |
| `os.environ[...]` / `os.getenv(...)` reads after a focal call (a common side-effect-verification idiom, e.g. env-var-setting functions) were never modeled as SUT-derived at all — `os.environ` is a global, not a local variable name | A sentinel marker is added to the `derived` set once any focal call is seen in a statement; `os.environ[...]`/`os.environ.get(...)`/`os.getenv(...)` accesses are treated as derived only when that sentinel is present (i.e. only after some prior focal call in the same scope — no sentinel, no derivation) | `_expr_is_derived`, `_is_environ_access`, `_ENVIRON_SENTINEL` | `assert os.environ[name] == 'new_value'` (after `solution.set_environ(...)`): `UNKNOWN` -> `STRONG sut_derived_specific_comparison`; `assert os.getenv(name) is None`: `UNKNOWN` -> `WEAK sut_derived_nullity` |
| `torch.allclose(result, x)` on a derived tensor result wasn't recognized — only `np.allclose`/`numpy.allclose`/etc. were in the allowlist | Added `torch.allclose`, `torch.equal` to the derived-content-equality call set | `_NUMPY_PROPERTY_CALLS` | `assert torch.allclose(result, x)`: `UNKNOWN opaque_predicate_call` -> `STRONG sut_derived_numpy_property_allclose` |

### Cluster B — bogus mock API vacuous truthiness

`mock_x.called_once` (attribute, no call) and `mock_x.called_once_with(...)` (call) are not
real `unittest.mock` API (real: `assert_called_once()`, `assert_called_once_with(...)`).
Because `Mock`/`MagicMock` auto-vivify child attributes, both forms always evaluate truthy
regardless of the mock's actual call history and verify nothing.

| Before | After |
|---|---|
| `assert mock_dep.called_once` (mock-derived receiver): `STRONG mock_state_contract_called_once` | `TRIVIAL bogus_mock_attribute_vacuous` |
| `assert mock_dep.called_once_with(x)` (mock-derived receiver): `UNKNOWN opaque_predicate_call` | `TRIVIAL bogus_mock_attribute_vacuous` |

The real `.called` attribute and the real `assert_called_once`/`assert_called_once_with`/
`assert_not_called`/etc. methods are untouched — a dedicated regression test
(`test_real_mock_called_attribute_is_unaffected_by_bogus_denylist`) pins this.

## Explicitly considered and NOT fixed (deferred, out of scope for this pass)

These were confirmed as real, recurring patterns during investigation, but each requires a
broader design decision or more invasive control-flow modeling than a narrow provenance
fix, so they were left alone and are documented here for a future pass:

- **WEAK/STRONG boundary for coarse-shaped comparisons** (`len(result) > 0`,
  `all(isinstance(x, T) for x in result)`). The classifier currently treats any
  comparison/quantifier over derived data as STRONG once any specific operator is used,
  but the taxonomy's own examples list existence/coarse-type checks as WEAK. Whether
  `len(x) > 0` is "existence" (WEAK) or "a specific numeric comparison" (STRONG) is a
  taxonomy-application judgment call with corpus-wide impact (dozens of sites), not a
  provenance bug. Recommend a dedicated decision by the paper authors before changing.
- **Nested-closure-over-async-generator provenance** (e.g. `result = []` in outer scope;
  a nested `async def` iterates a focal async generator and appends into `result`; outer
  code asserts on `result` after `asyncio.run(...)`). Confirmed recurring (2/78 sample
  rows). Fixing requires not resetting `derived` to empty for nested `FunctionDef`/
  `AsyncFunctionDef` bodies and merging mutations back into the enclosing scope after the
  function is invoked — a genuine control-flow modeling change with real regression risk,
  not a narrow fix.
- **`sys.stdout = captured_output` manual redirection** (as opposed to the
  `with redirect_stdout(...)` form fixed above). Same underlying idea (output capture
  around a focal call), different AST shape (plain global-attribute assignment, not a
  with-block). Confirmed in 2 sample rows. Deferred alongside the with-form fix's sibling
  case rather than bundled in, to keep this pass's diff auditable.
- **Constant-propagated `None` through a named variable**
  (`expected_output = None; assert result == expected_output` should be a nullity check,
  not a specific-value comparison). Only one instance in the sample; would require
  threading a third state set (`none_constants`) through `analyze_block` for a single
  observed case. Deferred.
- **`os.path.exists('hardcoded/literal/path')` with no variable reference to the SUT at
  all.** The AI auditor assumed this implies a side effect of the SUT, but there is zero
  syntactic evidence connecting the literal path to the focal call. Judged genuinely
  ambiguous; UNKNOWN is the correct conservative answer. Not fixed (by design, not by
  omission).
- **`result.options & ssl.OP_NO_TLSv1 & ssl.OP_NO_TLSv1_1`** (bitwise-AND expression on
  derived state). The existing code already has an explicit, deliberate rule
  (`compound_predicate_not_safely_classified`) for `BinOp` assertions on derived data,
  because a raw bitwise/arithmetic truthy check could pass for reasons unrelated to the
  intended bit-flag semantics. Judged as already-correct conservative design. Not
  fixed.
- **`some_other_function(solution, ...)` / `solution.convert_voc_voc_bbox(...)`** (calls to
  a helper function that merely takes an SUT instance as an argument, or a misspelled/
  hallucinated method name). Correctly UNKNOWN — passing an SUT-derived object as an
  argument to an unrelated function does not make that function's return value
  SUT-derived, and fuzzy-matching a misspelled method name to the real one would risk
  false positives elsewhere in the corpus. Not fixed.

## Tests

12 new tests added to `tests/test_step4_evaluation/test_oracle_analysis.py`, one per
confirmed fix (plus negative controls for the redirect-context and bogus-mock-attribute
rules, and a regression test proving the real `.called` attribute is unaffected). Full
suite:

```
pytest -q tests/test_step4_evaluation/test_oracle_analysis.py tests/test_step4_evaluation/test_sample_oracles_for_validation.py
```

Result: **98 passed** (86 pre-existing + 12 new). No pre-existing test was modified or
had its expected value changed.

Each fix was also spot-checked against its real originating corpus row (not just the
synthetic unit test) by re-running `classify_oracles` on the actual generated test source
for the exact `(generation_id, oracle_id)` pairs listed in the v3 disagreement table,
confirming the predicted class now matches the AI auditor's judgment for every confirmed
root cause, and confirming the deliberately-unfixed cases are unaffected.

## Corpus-level impact (v3 -> v4)

Same corpus (`downloaded_predictions/second_experiment/run_1`), same total site count —
this pass only reclassifies existing sites, it does not add or remove any.

| Class | v3 | v4 | delta |
|---|---:|---:|---:|
| TRIVIAL | 35 | 75 | +40 |
| WEAK | 2,354 | 2,398 | +44 |
| STRONG | 4,004 | 4,034 | +30 |
| UNKNOWN | 486 | 372 | -114 |
| Total | 6,879 | 6,879 | 0 |

Remaining UNKNOWN sites (372) by classification reason, largest first:
`comparison_without_sut_provenance` (193), `statically_failing_constant` (54, the
`assert False` fail-if-reached idiom — by design, see above),
`opaque_predicate_call` (42), `coarse_check_without_sut_provenance` (31),
`mock_contract_without_mock_provenance` (29, e.g. asserting on a mock name that was
never actually bound via `patch`/`Mock()` in the test — a generation defect, not a
classifier gap), plus single-digit tails.

## Artifacts produced (all new, non-overwriting)

- `step4_evaluation/oracle_analysis.py` — the 7 fixes above.
- `tests/test_step4_evaluation/test_oracle_analysis.py` — 12 new tests appended.
- `step4_evaluation/oracle_validation/oracle_manual_validation_sample_v4.csv`
- `step4_evaluation/oracle_validation/oracle_manual_validation_manifest_v4.json`
- `step4_evaluation/oracle_validation/oracle_manual_validation_blinded_v4.csv`
- `step4_evaluation/oracle_validation/oracle_manual_validation_blinded_v4_enriched.csv`
- `step4_evaluation/oracle_validation/CLASSIFIER_V4_CHANGELOG.md` (this file)

No v1/v2/v3 artifact was modified. No runtime/instrumentation code was touched. No
commits or pushes were made. `evaluate_results.py` and legacy result files were not
touched.

## What still blocks freeze

Real human review of `oracle_manual_validation_blinded_v4_enriched.csv` (250 rows). This
pass fixed every root cause it could confirm from source inspection and is a strict
improvement over v3, but "improved" is not "validated" — the paper cannot cite classifier
accuracy until a human (not an LLM in either the classifier-author or auditor role)
reviews the blinded sample.
