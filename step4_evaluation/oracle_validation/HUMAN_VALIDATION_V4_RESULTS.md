# Human Validation of the v4 Oracle Classifier — Disagreement Subset

## What this is

This is the first genuine human-labeled validation data produced for the oracle
taxonomy classifier. It supersedes the "no human labeling will be performed"
framing in `CLASSIFIER_FREEZE_DECISION.md` for the rows it covers.

**Scope: 62 of 250 rows in the v4 blinded sample** — specifically, every row where
the three independent judging methods (the static classifier's `predicted_class`,
the first AI-assisted audit `oracle_ai_audit_v4_report.md`, and a second independent
AI labeling pass `oracle_manual_validation_blinded_v4_enriched_ai_labeled.csv`) did
**not** all agree. This is not a uniform random sample of the 250 — it is
deliberately oversampled for difficulty/disagreement. The other 188 rows, where all
three methods already agreed, were not separately human-checked.

The human reviewer read each row blind to all three methods' predictions (working
directly from `oracle_source` + `enclosing_test_source` + `focal_function` in
`oracle_manual_validation_blinded_v4_enriched.csv`), applying the same paper-Table-4
taxonomy used throughout this project.

## Headline result

Estimated overall classifier accuracy, combining the 188 AI-consensus rows
(assumed correct — **not independently human-verified**, a real limitation) with
the 62 human-labeled disagreement rows:

**(188 + 12) / 250 = 80.0%**

This is the first accuracy figure in this project traceable to human judgment
rather than AI self-checking, and should replace prior "no accuracy can be
reported" language in the paper's Limitations section, **with the above caveat
about the 188 unverified consensus rows stated alongside it.**

## Agreement with each source, on the 62-row disagreement subset

| Compared to human | Agreement |
|---|---:|
| Classifier `predicted_class` | 12/62 (19.4%) |
| AI audit v4 (`oracle_ai_audit_v4_report.md`) | 32/62 (51.6%) |
| Second AI labeling pass (`..._ai_labeled.csv`) | 26/62 (41.9%) |

**Do not read the classifier's 19.4% as its overall accuracy.** This subset is
selected *because* the classifier's prediction was disputed by at least one other
method, so by construction it excludes every case where the classifier was already
correct-and-agreed-upon. The 80.0% blended estimate above is the appropriate
headline number, not this raw subset agreement rate.

## Human label distribution on this subset

| Class | Count |
|---|---:|
| STRONG | 25 |
| TRIVIAL | 21 |
| WEAK | 14 |
| UNKNOWN | 2 |

## Human vs. classifier confusion matrix (62 rows; rows = human, columns = classifier)

| human \ classifier | TRIVIAL | WEAK | STRONG | UNKNOWN |
|---|---:|---:|---:|---:|
| **TRIVIAL** | 3 | 0 | 3 | 15 |
| **WEAK** | 0 | 0 | 8 | 6 |
| **STRONG** | 0 | 1 | 7 | 17 |
| **UNKNOWN** | 0 | 0 | 0 | 2 |

## Key finding: the classifier's UNKNOWN fallback is substantially over-cautious

Of the 40 rows (out of 62) where the classifier predicted UNKNOWN, a human reader
with full test context resolved **38 (95%)** to a real class (15 TRIVIAL, 6 WEAK,
17 STRONG) and agreed UNKNOWN was correct in only **2 (5%)**. This is now
human-confirmed, not merely AI-audit-suspected: the classifier's provenance
resolution remains the dominant source of residual error even after the v3→v4 fix
pass, specifically in the direction of excess conservatism (false UNKNOWN) rather
than misclassification between TRIVIAL/WEAK/STRONG.

Secondary finding: outside the UNKNOWN column, the classifier also mislabeled 3
TRIVIAL cases as STRONG, 1 WEAK case as STRONG, and 8 WEAK cases as STRONG — i.e.
there is a real, human-confirmed tendency for the classifier to over-credit
specificity in a way not limited to the "coarse-comprehension" pattern
(`len(x)>0`, membership, `all(isinstance(...))`) already flagged as a known,
deliberately-deferred boundary decision in `CLASSIFIER_V4_CHANGELOG.md`. (Several
of the 8 WEAK→STRONG cases in this matrix *are* that exact deferred pattern, per
the reviewer's own "pattern rule" applied to items 22/29/37/45/46/48/49 in the
labeling session — this is the deferred decision being empirically confirmed by a
human, not a new independent finding.)

## Methodological caveats

- Per-class precision/recall computed **only on this 62-row subset** would be
  structurally biased (e.g. WEAK precision measures to 0.0 here, because by
  construction any classifier-WEAK-and-human-agreed row was excluded from the
  subset) and is intentionally **not reported** in this document as a classifier
  metric. Do not compute or cite per-class P/R from this subset alone.
- The 188 "AI-consensus" rows folded into the 80.0% headline estimate were not
  independently human-checked. If time allows a future pass, spot-checking a
  random sample of those 188 (rather than only the disagreement set) would let
  the 80.0% figure be reported as measured rather than partly assumed.
- This is still not a full independent random-sample human validation of all 250
  rows. It is a targeted, disagreement-oversampled validation, which is well
  suited to *diagnosing* classifier weaknesses (as the UNKNOWN-fallback finding
  above demonstrates) but should be described precisely as such in the paper, not
  rounded up to "the classifier was validated against a random human-labeled
  sample."

## Suggested paper wording (Limitations / Threats to Validity), replacing the
prior AI-only framing

> A human reviewer labeled every oracle site in the 250-site validation sample
> (Section/Appendix reference) where the static classifier's prediction was
> disputed by at least one of two independent AI-assisted re-applications of the
> same written taxonomy (62 of 250 sites; the remaining 188 sites had unanimous
> agreement across all three methods and were not separately human-verified).
> Against this human ground truth, the classifier agreed on 12 of 62 disputed
> sites; combined with the assumed-correct consensus sites, this yields an
> estimated overall accuracy of 80.0% (200/250). The dominant error mode,
> confirmed by human review, is over-conservative fallback to the UNKNOWN class
> rather than misclassification among trivial/weak/strong (of 40 classifier-UNKNOWN
> disputed sites, a human resolved 38 to a definite class); reported non-trivial
> and strong-oracle gate figures should therefore be read as a conservative lower
> bound with respect to sites currently classified UNKNOWN.

## Files

- `oracle_manual_validation_v4_human_vs_all.csv` — all 62 rows with human, classifier,
  and both AI-audit labels side by side, for inspection.
- `oracle_manual_validation_blinded_v4_enriched.csv` — the source-of-truth file;
  `manual_class`/`manual_sut_dependent`/`manual_notes` filled in for these 62 rows,
  blank for the other 188 (not overwritten or fabricated).
