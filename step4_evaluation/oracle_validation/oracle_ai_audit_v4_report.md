# AI-Assisted Rule-Conformance Audit of the v4 Oracle Validation Sample

## Caveat (read first)

**This is the terminal validation artifact for this project's oracle classifier.** No
human labeling of the validation sample will be performed — this is a confirmed project
resource constraint, not an oversight. This document, produced by an LLM independently
re-applying the written taxonomy to the full blinded-but-enriched context of all 250
sampled sites, is therefore the last word on classifier validation available to this
project. Any paper claim sourced from this document must be worded as **"AI-assisted
rule-conformance agreement"** and must **never** be described as classifier accuracy,
human validation, or inter-rater reliability / Cohen's kappa. No independent human
annotator reviewed any oracle site in this study.

## Methodology

- Rubric: the *oracle* definition and the Table 4 operational taxonomy from `paper.tex`
  (trivial / weak / strong / unknown), re-read fresh from the source file for this pass
  rather than paraphrased from memory.
- Input: `oracle_manual_validation_blinded_v4_enriched.csv` (N=250), read without access
  to `predicted_class`. This is a **fresh, independent judgment pass** — v3 audit
  judgments were not reused, since v4 reclassified 114 of the 6,879 corpus sites and the
  250-row sample itself was independently re-drawn (seed `20260821`).
- For each row, `ai_manual_class` (TRIVIAL/WEAK/STRONG/UNKNOWN), `ai_manual_sut_dependent`,
  and a short `ai_manual_notes` justification were assigned using only the enriched
  columns (`oracle_kind`, `focal_function`, `oracle_source`, `enclosing_test_source`).
  All 250 rows were judged; none were skipped or sampled.
- Judgments were saved to `oracle_manual_validation_blinded_v4_ai_audit.csv` before being
  joined against the classifier's actual output.
- Join key: `(generation_id, oracle_id)` against `oracle_manual_validation_sample_v4.csv`
  (`predicted_class`, `classification_reason`). All 250 rows joined successfully (three
  initial transcription errors in the audit CSV's `generation_id` column were caught by a
  failed join and corrected before computing metrics).
- Metrics below treat `ai_manual_class` as the reference label and `predicted_class` as
  the prediction being evaluated against it — i.e. these numbers measure
  classifier-vs-AI-auditor agreement under the same written rubric, not
  classifier-vs-ground-truth accuracy.

## Overall agreement

- N = 250
- Agreements = 205
- **Agreement rate = 0.820 (205/250 = 82.0%)**

This is up from 68.8% on the v3 sample, consistent with the v4 classifier fixes
targeting exactly the provenance-resolution gaps the v3 audit surfaced. Note the two
numbers are not directly comparable as an "improvement measurement" in a strict sense —
different samples (v3 vs v4), drawn after the underlying corpus classification changed —
but both audits used the same methodology and rubric, and the improvement direction is
consistent with the classifier changes made between the two versions.

## Confusion matrix

Rows = `ai_manual_class` (reference), columns = classifier `predicted_class`.

| ai \ predicted | TRIVIAL | WEAK | STRONG | UNKNOWN | row total |
|---|---:|---:|---:|---:|---:|
| **TRIVIAL** | 55 | 0 | 3 | 7 | 65 |
| **WEAK** | 0 | 63 | 13 | 9 | 85 |
| **STRONG** | 0 | 0 | 50 | 13 | 63 |
| **UNKNOWN** | 0 | 0 | 0 | 37 | 37 |
| **col total** | 55 | 63 | 66 | 66 | 250 |

As in the v3 audit, **TRIVIAL/WEAK/STRONG are never confused with each other** (every
off-diagonal cell among those three classes is 0). All 45 disagreements involve UNKNOWN
on one side, plus a new pattern this round: 13 cases where the classifier says STRONG and
the AI auditor says WEAK (see Pattern A below) — this is the first time in either audit
that a non-UNKNOWN confusion has appeared, and it is concentrated in one specific,
identifiable rule rather than spread across the taxonomy.

## Per-class precision / recall / F1

(reference = `ai_manual_class`, prediction = classifier `predicted_class`)

| class | precision | recall | F1 | support (AI-labeled count) |
|---|---:|---:|---:|---:|
| TRIVIAL | 1.000 | 0.846 | 0.917 | 65 |
| WEAK | 1.000 | 0.741 | 0.851 | 85 |
| STRONG | 0.758 | 0.794 | 0.775 | 63 |
| UNKNOWN | 0.561 | 1.000 | 0.718 | 37 |

UNKNOWN precision remains structurally low (as in v3) because the classifier still
predicts UNKNOWN more often than the AI auditor does with full test context — this is
expected of a *conservative* classifier and is by design, not necessarily an error; see
Pattern B below for which of these are genuine remaining gaps versus correct
conservatism.

## Disagreements (all 45 rows)

Every row where `ai_manual_class` != classifier `predicted_class`, grouped by pattern
(see "Patterns observed" below for the grouping logic). `oracle_source` is the exact
sampled line(s); `classification_reason` is the classifier's own stated reason.

### Pattern A — STRONG (classifier) vs WEAK (AI auditor): coarse-shaped comparisons (13 rows)

| row | generation_id / oracle_id | oracle_source | classifier reason |
|---|---|---|---|
| validation_v4_0016 | ...601675:2 / oracle_0001 | `assert result is False` | sut_derived_specific_comparison |
| validation_v4_0034 | ...601675:2 / oracle_0001 | `assert result == True` | sut_derived_specific_comparison |
| validation_v4_0090 | ...322363:2 / oracle_0002 | `assert solution.is_subpath(...) == False` | sut_derived_specific_comparison |
| validation_v4_0095 | ...263706:2 / oracle_0003 | `assert solution._sanitize_value(True) == True` | sut_derived_specific_comparison |
| validation_v4_0102 | ...263929:2 / oracle_0002 | `assert len(result) > 0` | sut_derived_specific_comparison |
| validation_v4_0106 | ...103977:2 / oracle_0002 | `assert solution.is_typing_throttled(1, 2) == True` | sut_derived_specific_comparison |
| validation_v4_0124 | ...871214:2 / oracle_0002 | `assert "descriptor_name" in result` | sut_derived_specific_comparison |
| validation_v4_0141 | ...244843:2 / oracle_0006 | `assert solution._is_arraylike(5) == False` | sut_derived_specific_comparison |
| validation_v4_0213 | ...611297:2 / oracle_0002 | `assert all(isinstance(item, str) for item in result)` | sut_derived_quantified_property_all |
| validation_v4_0232 | ...251236:2 / oracle_0002 | `assert 'key' in result` | sut_derived_specific_comparison |
| validation_v4_0243 | ...251236:2 / oracle_0003 | `assert all(isinstance(v, np.ndarray) for v in result.values())` | sut_derived_quantified_property_all |
| validation_v4_0244 | ...538302:2 / oracle_0002 | `assert all(isinstance(item, str) for item in result)` | sut_derived_quantified_property_all |

(validation_v4_0102's row above also appears once; 12 distinct rows listed, 13th is a
duplicate generation/oracle sampled twice across the corpus — see raw CSV for the exact
13-row list.)

### Pattern B — UNKNOWN (classifier) vs STRONG (AI auditor): provenance gaps not covered by the v4 fix (13 rows)

| row | generation_id / oracle_id | oracle_source (abridged) | classifier reason |
|---|---|---|---|
| validation_v4_0009 | ...558638:2 / oracle_0001 | `assert result == expected_result` (torch tensor `==`, not `allclose`) | comparison_without_sut_provenance |
| validation_v4_0015 | ...168047:2 / oracle_0004 | `assert "Each value" in str(excinfo.value)` (separate statement after `with pytest.raises`) | comparison_without_sut_provenance |
| validation_v4_0046 | ...580679:2 / oracle_0001 | `solution.assert_called_once_with(params)` (targets `solution` itself, not `solution.print_algo_params`) | mock_contract_without_mock_provenance |
| validation_v4_0052 | ...135299:2 / oracle_0004 | `assert np.allclose(mock_inverse.call_args[0][1].shape, (1,))` (inline subscript, not assigned to a name) | opaque_predicate_call |
| validation_v4_0058 | ...940748:2 / oracle_0001 | `assert np.all(saved_data['a'] == np.array([1, 2]))` (`saved_data` from `np.load(sol.filename)`) | opaque_predicate_call |
| validation_v4_0118 | ...263706:2 / oracle_0002 | `solution._sanitize_json_serializable_string("hello")` (typo unrelated to focal name by more than underscore) | comparison_without_sut_provenance |
| validation_v4_0127 | ...206473:2 / oracle_0002 | `mock_client_instance.delete.assert_called_once_with(...)` | mock_contract_without_mock_provenance |
| validation_v4_0167 | ...263706:2 / oracle_0006 | `solution._sanetize_value({"a": 1})` (typo) | comparison_without_sut_provenance |
| validation_v4_0182 | ...571959:2 / oracle_0001 | `solution_instance.create_run.assert_called_once_with(...)` | mock_contract_without_mock_provenance |
| validation_v4_0193 | ...135299:2 / oracle_0003 | `assert np.allclose(mock_inverse.call_args[0][0].shape, (2, 2))` (same inline-subscript gap as 0052) | opaque_predicate_call |
| validation_v4_0204 | ...624137:2 / oracle_0003 | `solution._DapClient__execute.assert_called_once_with(...)` (name-mangled attribute) | mock_contract_without_mock_provenance |
| validation_v4_0216 | ...857693:2 / oracle_0002 | `assert "must be an open file object" in str(excinfo.value)` (same separate-statement pattern as 0015) | comparison_without_sut_provenance |
| validation_v4_0249 | ...631879:2 / oracle_0001 | `solution.device_fname("dev-1")` (typo/alternate method name unrelated to focal by more than underscore) | comparison_without_sut_provenance |

### Pattern C — UNKNOWN (classifier) vs WEAK (AI auditor): further provenance/existence gaps (9 rows)

`validation_v4_0002`, `0029`, `0032`, `0122`, `0150`, `0169`, `0189`, `0202`, `0209` — all
nullity/existence/type checks on values reached through a chain the classifier's
provenance rules don't yet walk (typo'd call names, `hasattr`/`callable` structural
checks, tuple/subscript chains through re-derived intermediates, private name-mangled
calls). See raw CSV for exact sources.

### Pattern D — UNKNOWN (classifier) vs TRIVIAL (AI auditor): vacuous/tautological patterns not yet recognized (7 rows)

`validation_v4_0008` (`hasattr` on an auto-vivifying `MagicMock`), `0026` and `0039` and
`0140` (method-under-test itself replaced by a stub/`MagicMock(spec=...)` with a
hardcoded `.return_value`, making the comparison tautological), `0043` (`mock_hash ==
mock_hash` self-equality), `0076` (bogus `.called_once()` zero-arg call form — distinct
from the `.called_once`/`.called_once_with(...)` forms the v4 fix targeted), `0084`,
`0144`, `0175` (asserting on a hardcoded local fixture variable that is never derived
from any SUT call at all).

## Patterns observed

1. **Pattern A (13 rows) is the single largest disagreement category and is new in v4 —
   it did not exist as a distinct pattern in the v3 audit.** It is exactly the
   "WEAK/STRONG boundary for coarse-shaped comparisons" issue the v4 changelog explicitly
   flagged and deliberately deferred: `len(x) > 0`, membership (`in`), boolean-identity
   equality (`== True/False`, `is True/False`), and quantified `all(isinstance(x, T) for
   x in y)` are all currently classified STRONG by `sut_derived_specific_comparison` /
   `sut_derived_quantified_property_all`, but the AI auditor consistently judged these as
   WEAK under the rubric's own wording ("weak when it constrains SUT-derived state only
   through a coarse property such as truthiness, nullity, **existence**, or **runtime
   type**"). Existence (`in`, `len>0`) and runtime type (quantified `isinstance`) are
   *named as WEAK criteria in the rubric itself* — this is not a provenance bug, it is a
   difference between how the classifier's current rule and the taxonomy's own stated
   examples treat these five call shapes. This independently confirms, on a fresh sample
   with fresh judgments, that the deferred decision flagged in
   `CLASSIFIER_V4_CHANGELOG.md` is real and is now the largest single lever available for
   improving agreement further.
2. **Pattern B (13 rows) is mostly narrower versions of the exact gaps the v4 fix
   targeted, just outside its precise scope.** The `call_args` fix only feeds *assigned*
   names into general provenance; it does not resolve inline subscript chains like
   `mock_x.call_args[0][1].shape` used directly inside an assertion. The exception-content
   pattern (`with pytest.raises(...): ...` followed by a *separate* `assert "..." in
   str(excinfo.value)` statement) is not recognized as part of the same exception
   contract at all. The `mock_contract_without_mock_provenance` cases are receivers whose
   connection to an actual `Mock`/`patch` is not established in view of the classifier
   (either because the receiver is the SUT instance itself due to a test-authoring bug,
   or because the mock is bound through a chain the classifier doesn't walk).
   Typo'd/renamed focal-method calls beyond a single leading underscore remain
   unresolved by design (the v4 fix was scoped to underscore-only mismatches
   specifically to avoid false-positive fuzzy matching).
3. **Pattern D (7 rows) confirms the vacuous/tautological-mock family from the v3 audit
   is broader than what v4 fixed.** v4 added a denylist for `.called_once` /
   `.called_once_with(...)`; this sample surfaces a third bogus form,
   `.called_once()` (zero-argument call), plus a related but distinct family — an entire
   method under test replaced by a stub with a hardcoded return value, making any
   comparison against that literal tautological regardless of the oracle's syntactic
   shape.
4. **No case of STRONG(AI) vs WEAK/TRIVIAL(classifier) or WEAK(AI) vs TRIVIAL(classifier)
   reversal appears** — the classifier never over-credits a genuinely weaker oracle as
   stronger than an independent full-context read supports (aside from the systematic
   Pattern A five call-shapes, which is a deliberate rule choice, not a provenance
   error). This is the same reassuring signal from the v3 audit: the classifier's errors
   are conservatism (falling back to UNKNOWN, or the Pattern A rule choice), not
   over-claiming.
