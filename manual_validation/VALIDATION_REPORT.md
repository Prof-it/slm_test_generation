# Manual-validation reproducibility report

## Dependency-level validation

- Reported source population at original review: 10,449 candidates.
- Current candidate population: 8,566 rows (hash recorded in the manifest).
- Completed first-rater sample: 30 rows; declared seed 42.
- Preserved blank-sample overlap: 19/30.
- Evidence reconciliation: 19 preserved-sample matches, 5 completed-audit rows found
  in the current candidate file, and 6 completed-audit rows recovered exactly from
  audit-era nested-repository Git objects. Evidence available: 30/30.
- Reproducibility status: evidence and reviewed row set are preserved; the original
  10,449-row population snapshot/order is not, so the original draw cannot be replayed.
- Agreement rule: unweighted Cohen's kappa and raw agreement over paired substantive
  L0/L1/L2/L3 ratings only. Missing, NOT_RATEABLE, and genuine UNSURE responses are
  counted and reported as exclusions. Agreement uses original independent labels
  before adjudication.
- Historical automated-label versus first-rater result: 27/30 raw agreement (0.900),
  exact unweighted Cohen's kappa 0.8451. This supersedes the earlier approximate 0.87.

## Oracle-site validation

- Source population: 6,879 statically identified oracle sites.
- Sample: 250, seed 20260821.
- Sampling: deterministic round-robin strata over predicted class, pipeline, and tier.
- Exclusions before sampling: Pynguin result files, empty generated tests, and generated
  tests that could not be parsed.
- Evidence: sampled oracle source, enclosing generated test, focal function name,
  stable generation/task/oracle identifiers, locations, and content hashes.
- Reproducibility status: exact sample, input predictions, script, seed, manifest, and
  first-rater labels are preserved.
- Agreement rule: unweighted Cohen's kappa and raw agreement over paired substantive
  TRIVIAL/WEAK/STRONG/UNKNOWN ratings. Administrative non-rateable rows and genuine
  uncertainty are separately reported and excluded. Agreement precedes adjudication.

After second rating, retain the returned sheet unchanged, run
`calculate_agreement.py` with `--json-output`, and fill the separate adjudication sheet
without modifying either rater's labels.
