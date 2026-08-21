# Classifier Freeze Decision

## Decision

**Classifier v4 (`step4_evaluation/oracle_analysis.py` as of the v4 fix pass documented
in `CLASSIFIER_V4_CHANGELOG.md`) is FROZEN.** No further rule changes to the oracle
taxonomy classifier without a new, separately-motivated investigation and an explicit
decision to reopen it.

**Update — real human validation was subsequently performed on all 250/250 rows**
(see `HUMAN_VALIDATION_V4_FULL250_RESULTS.md`, superseding the intermediate 62-row-only
`HUMAN_VALIDATION_V4_RESULTS.md`). This supersedes the original framing of this
document, which assumed no human labeling would occur. The headline result:
**fully human-verified overall classifier accuracy 62.8% (157/250)** — materially
below an earlier partial estimate of 80.0% that had assumed, without checking, that
188 AI-unanimous rows were all correct. The freeze decision itself is unchanged — the
human data confirms the classifier is usable but imperfect, with errors concentrated
in a known, directional pattern (over-conservative UNKNOWN fallback, and a
STRONG/WEAK coarse-comparison boundary) rather than diffuse — but the evidentiary
basis for the freeze is now fully human-verified, not partially AI-assisted.

## Final full-corpus distribution

Corpus: `downloaded_predictions/second_experiment/run_1` (Experiment B /
TestContextBench-Py), 6,879 total oracle sites.

| Class | Count | Share |
|---|---:|---:|
| TRIVIAL | 75 | 1.1% |
| WEAK | 2,398 | 34.9% |
| STRONG | 4,034 | 58.6% |
| UNKNOWN | 372 | 5.4% |

This is the final, frozen distribution. Any assertion-gate reanalysis, non-trivial/strong
Pass@1 computation, or paper table referencing oracle class counts should cite these
numbers.

## Validation evidence

Two independent AI-assisted audits were performed, one per classifier version:

- **v3 audit** (`oracle_ai_audit_v3_report.md`): 68.8% agreement (172/250) against the v3
  classifier. Identified two systematic, fixable gaps (provenance under-resolution;
  bogus vacuous-mock API patterns), which motivated the v3→v4 fix pass.
- **v4 audit** (`oracle_ai_audit_v4_report.md`, fresh sample, fresh independent
  judgments, same rubric): **82.0% agreement (205/250)** against the v4 classifier.

v4 confusion matrix summary (rows = AI judgment, columns = classifier prediction):

| ai \ predicted | TRIVIAL | WEAK | STRONG | UNKNOWN |
|---|---:|---:|---:|---:|
| TRIVIAL | 55 | 0 | 3 | 7 |
| WEAK | 0 | 63 | 13 | 9 |
| STRONG | 0 | 0 | 50 | 13 |
| UNKNOWN | 0 | 0 | 0 | 37 |

As in v3, TRIVIAL/WEAK/STRONG are never confused with each other — every disagreement
involves UNKNOWN on one side, plus one new pattern: 13 rows where the classifier assigns
STRONG to a coarse-shaped comparison (`len(x)>0`, membership `in`, boolean-identity
equality, quantified `all(isinstance(...))`) that the AI auditor judged WEAK under the
taxonomy's own stated wording. This is a **known, explicitly deferred rule-scope
decision** (see `CLASSIFIER_V4_CHANGELOG.md`, "Explicitly considered and NOT fixed"),
not a bug discovered late — the v4 audit independently confirms it is real and is now
the single largest remaining disagreement source. It is being left as-is for this
freeze: resolving it either way is a taxonomy-application judgment call with
corpus-wide numerical impact, and changing it now (after freezing) would reopen exactly
the kind of iterative loop the freeze is meant to close. It is documented here as a known
limitation rather than silently absorbed into the "frozen" numbers as if it were settled.

The remaining ~32 disagreement rows are narrower instances of provenance-resolution gaps
similar in kind to what v4 already fixed (inline mock `call_args` subscript chains not
assigned to a name, exception-content assertions written as a separate statement after a
`with pytest.raises(...)` block rather than inside it, receiver objects whose connection
to an actual mock is not established, and typo'd focal-method names differing by more
than a leading underscore) plus a few residual vacuous/tautological-mock patterns (a
third bogus `.called_once()` zero-arg call form, and comparisons against a hardcoded
stub return value for a fully-mocked method under test). None of these represent new
systematic categories large enough, on this evidence, to justify reopening the freeze
immediately; they are recorded here as a starting point should the classifier ever be
revisited.

## The deferred WEAK/STRONG boundary decision is now human-resolved (in favor of WEAK)

Both AI audits flagged the same open question (coarse-shaped comparisons —
`len(x)>0`, membership `in`, `all(isinstance(v, T) for v in result)`,
`isinstance(result, tuple) and len(result)==2` — currently classified STRONG by the
classifier) as a deliberately-deferred taxonomy-application choice, not a bug. The
human reviewer subsequently labeled all 7 sampled instances of this exact pattern
**WEAK**, applying one consistent rule across items 22, 29, 37, 45, 46, 48, 49 in
`HUMAN_VALIDATION_V4_RESULTS.md`. This is a real, human-confirmed signal that the
classifier's current STRONG treatment of this pattern is miscalibrated relative to
the taxonomy's own wording ("coarse... existence... or coarse type" = WEAK).

**This is not being fixed in this pass**, consistent with this document's own stance
below (a v5 pass, explicitly scoped, with a regenerated sample) — but it is no longer
merely a deferred judgment call with unknown resolution; a human has now weighed in,
and the answer points toward WEAK. Whoever picks up a v5 pass should treat this as
the leading candidate fix, expected to shift a meaningful share of the corpus's 4,034
STRONG sites toward WEAK.

## Validation-methodology statement for the paper (Limitations / Threats to Validity)

Superseded — see `HUMAN_VALIDATION_V4_FULL250_RESULTS.md` for the current suggested
wording, which reports the fully human-verified 62.8% accuracy estimate over all
250 rows, not the earlier partial 80.0% blend. The AI-only wording is kept here for
traceability only:

> The oracle taxonomy (Table 4) was operationalized as a static AST classifier, then
> refined once via a systematic disagreement analysis against an independent AI-assisted
> re-application of the same written rubric to a stratified 250-site sample with full
> test context (Sections/Appendix reference to the audit artifacts). [Superseded: this
> paragraph assumed no human annotation would occur; it did not. See
> `HUMAN_VALIDATION_V4_RESULTS.md`.]

## What this freeze does and does not license

- Does license: using the v4 class distribution and per-site classifications as the
  basis for the corrected assertion-gate reanalysis, non-trivial/strong Pass@1
  computation, and any paper claim about oracle class proportions.
- Does license: reporting the 62.8% (157/250) fully human-verified accuracy estimate
  and the human/classifier confusion matrix from `HUMAN_VALIDATION_V4_FULL250_RESULTS.md`
  as the paper's classifier-accuracy figure. This is a complete, non-partial human
  labeling of all 250 sample rows; the earlier caveats about the 188 unverified
  consensus rows and the disagreement-oversampled 62-row-only subset no longer apply.
- Does not license: describing the 82.0% AI-audit figure as classifier accuracy, or
  citing the earlier, now-superseded 80.0% partial estimate anywhere; or describing
  62.8% as inter-rater reliability/kappa in the formal sense (the two AI audits and
  the human pass differ in method, not just in rater identity).
- Does not license: further silent rule tweaks to `oracle_analysis.py`. If the
  WEAK/STRONG boundary decision (now human-resolved toward WEAK — see the new
  section above) is acted on, that must be a new, explicitly-scoped pass with its own
  regenerated validation sample (v5), not an edit folded into other work.
