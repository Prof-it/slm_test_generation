# Human Validation of the v4 Oracle Classifier — Full 250-Site Sample

## Status: complete. Supersedes `HUMAN_VALIDATION_V4_RESULTS.md`'s 62-row-only estimate.

This closes the last open item from the classifier-validation Limitations bullet in
`paper.tex`: **all 250 sites in the v4 blinded sample now have real human labels**,
not just the 62-site AI-disagreement subset. The other 188 rows (three-way AI
consensus: classifier + two independent AI audits) were previously *assumed* correct
and reported as such, explicitly caveated as "not independently human-verified."
That assumption has now been tested directly.

Labeling was done blind (working only from `oracle_source` + `enclosing_test_source`
+ `focal_function`, no AI/classifier prediction visible), using the same paper-Table-4
taxonomy and an interactive tool built for the purpose (self-contained HTML,
localStorage-backed, taxonomy reference embedded). Output merged with the existing
62-row human file (`oracle_manual_validation_v4_human_vs_all.csv`) and the classifier's
own predictions (`oracle_manual_validation_sample_v4.csv`, joined by row position after
verifying the two files are row-order-aligned: `lineno`/`col_offset`/`task_id` match
positionally for all 250 rows) into
`oracle_manual_validation_v4_FULL250_human_vs_all.csv`.

## Headline result: 62.8% (157/250) sample agreement, not the previously reported 80.0% — and not corpus-wide accuracy either

The paper's prior figure, 80.0% (200/250), blended the 62-row human-labeled subset
with the assumption that all 188 AI-consensus rows were correct. That assumption was
wrong for a meaningful fraction of them: of the 188 previously-unverified rows, the
classifier agrees with the human label on only 145 (77.1%), not 188 (100%, the implicit
assumption). The fully human-verified agreement over all 250 sample sites is:

**157 / 250 = 62.8%**

This is the honest number and should replace 80.0% everywhere it appears in the paper.
It is materially lower, and should not be averaged with the earlier estimate or
otherwise softened.

**Important correction to how this number should be described.** 62.8% is unweighted
agreement on the 250-site *validation sample*, not an estimate of corpus-wide
classifier accuracy, and should not be described as the latter. The sample's
classifier-predicted class balance (66 STRONG=26.4%, 55 TRIVIAL=22.0%, 66 UNKNOWN=26.4%,
63 WEAK=25.2%) is not proportional to the true corpus balance (4,034 STRONG=58.6%,
75 TRIVIAL=1.1%, 372 UNKNOWN=5.4%, 2,398 WEAK=34.9%, over 6,879 sites): STRONG is
roughly 2.2x more prevalent in the corpus than in the sample (58.6% vs. 26.4%), while
TRIVIAL and UNKNOWN are roughly 20x and 5x more prevalent in the sample than in the
corpus, respectively (WEAK is closer, 34.9% vs. 25.2%, about 1.4x).
Reweighting each predicted class's sample agreement rate (STRONG 69.7%, TRIVIAL 100%,
UNKNOWN 9.1%, WEAK 79.4%) by its corpus prevalence gives an approximate corpus-weighted
agreement of **~70%**. This is reported as an approximate point estimate only — no
stratified-sampling variance/CI estimator was computed for it — not as a replacement
headline number.

**Gate-specific precision/recall is more informative than either aggregate figure**,
since the paper's reported quantities are the gates themselves:

| Gate | Precision | Recall |
|---|---:|---:|
| Non-trivial (predicted WEAK or STRONG vs. human WEAK or STRONG) | 94.6% | 79.7% |
| Strong (predicted STRONG vs. human STRONG) | 69.7% | 57.5% |

The non-trivial gate is reliable enough to support reading Non-trivial Pass@1
throughout the paper as a genuinely conservative lower bound (very few false
positives; the ~20% of true non-trivial sites it misses are recovered as UNKNOWN, not
wrongly excluded as TRIVIAL — consistent with the error-mode finding below). The
strong gate is materially weaker (69.7% precision, 57.5% recall) and Strong Pass@1
figures should be presented as exploratory and classifier-sensitive, not with the
same confidence as the Non-trivial figures.

## Agreement with each source, full 250-row sample

| Compared to human | Agreement |
|---|---:|
| Classifier `predicted_class` | 157/250 (62.8%) |
| First AI audit (`oracle_ai_audit_v4_report.md`) | 177/250 (70.8%) |
| Second AI audit (Codex-labeled) | 171/250 (68.4%) |

Both AI audits also over-estimated their own reliability when only checked against each
other / the classifier (82.0% three-way agreement reported in `CLASSIFIER_FREEZE_DECISION.md`)
rather than against genuine human judgment — all three methods agree with each other
considerably more than any of them agrees with a human, which is exactly the blind spot
"AI-assisted validation of AI-assisted validation" cannot see on its own.

## Human label distribution, full 250 rows

| Class | Count |
|---|---:|
| TRIVIAL | 88 |
| STRONG | 80 |
| WEAK | 73 |
| UNKNOWN | 9 |

## Confusion matrix (rows = human, columns = classifier), full 250

| human \ classifier | STRONG | TRIVIAL | UNKNOWN | WEAK |
|---|---:|---:|---:|---:|
| STRONG | 46 | 0 | 22 | 12 |
| TRIVIAL | 3 | 55 | 29 | 1 |
| UNKNOWN | 3 | 0 | 6 | 0 |
| WEAK | 14 | 0 | 9 | 50 |

## Error decomposition: the dominant failure mode is confirmed, at full scale, to be over-conservative UNKNOWN fallback

Of the 93 total disagreements between the classifier and the human label:

- **60 (64.5%)** are the classifier predicting `UNKNOWN` while the human resolved the
  site to a definite class (STRONG, WEAK, or TRIVIAL). **All 60 (100%)** of these are
  human-resolved to a definite class — none of them turned out to genuinely be
  irresolvable. This is stronger and more decisive confirmation of the pattern already
  reported from the 62-row sample (there: 38/40, 95%; now: 60/60, 100%, at more than
  double the disputed-UNKNOWN count).
- **3 (3.2%)** are the reverse (classifier predicts a definite class, human says
  UNKNOWN) — a much smaller, asymmetric error direction.
- **30 (32.3%)** are genuine cross-confusion among the three quality classes, not
  involving UNKNOWN at all. This is overwhelmingly concentrated in one boundary:
  **STRONG vs. WEAK, 26 of 30 (87%)** of all non-UNKNOWN confusion, split 12
  human-STRONG/classifier-WEAK and 14 human-WEAK/classifier-STRONG. This directly
  matches the already-documented open judgement call in `paper.tex` (coarse-shaped
  comparisons over derived collections — `len(x)>0`, membership tests, quantified type
  checks — where the classifier defaults to STRONG and the human/AI reviews have
  repeatedly favoured WEAK). TRIVIAL is essentially never confused with STRONG or WEAK
  in either direction (4 of 250 rows total), so the taxonomy's TRIVIAL boundary is not
  where the classifier's real accuracy problem lives.

## What this changes and does not change

- **Does not change**: any already-reported Pass@1, Non-trivial Pass@1, Strong Pass@1,
  mutation, RQ2/RQ3, or Pynguin figure. All of those come from applying the *frozen*
  classifier to the 6,879-site corpus; this validation sample measures how much to
  trust that classifier's output, it does not re-run the classifier or change what it
  output on any corpus site.
- **Does change**: the confidence the paper can honestly claim in the classifier's
  output, and how that confidence should be attributed across the two gates it
  actually reports. 62.8% sample agreement (~70% corpus-weighted, approximately),
  with errors concentrated in a known, directionally understood pattern
  (over-predicting UNKNOWN, essentially never wrongly promoting a weak/trivial oracle
  to STRONG or vice versa outside the specific STRONG/WEAK coarse-comparison
  boundary), is a materially different, more honest claim than 80.0%, and should
  replace it in the classifier-validation paragraph, the Limitations section's
  "62/250 disagreement-only" bullet (now resolved, not a limitation), and any other
  citation of the 80.0% figure. The gate-specific precision/recall split (94.6%/79.7%
  non-trivial vs. 69.7%/57.5% strong) means Non-trivial Pass@1 and Strong Pass@1
  should not be presented with equal confidence: the former is a defensible
  conservative lower bound, the latter should be flagged as exploratory.
