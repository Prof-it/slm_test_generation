# Manual validation and second-rater package

This directory makes the two single-rater validations used by the study independently
inspectable. Give a second rater only each task's `PROTOCOL.md` and
`second_rater_sheet.csv`. Do **not** provide `first_rater_labels.csv` until rating is
complete.

## Packages

1. [`dependency_levels/`](dependency_levels/) — 30 functions classified as L0–L3.
2. [`oracle_classes/`](oracle_classes/) — 250 generated-test oracle sites classified
   as TRIVIAL, WEAK, STRONG, or UNKNOWN.

Each package contains a protocol, a blinded evidence-and-response CSV, the separated
first-rater labels, and a machine-readable provenance manifest. Rebuild deterministic
views with:

```bash
python manual_validation/build_review_packages.py
```

The builder may regenerate blank templates, but it fails closed if any second-rater or
adjudication response cell is populated. It will never silently erase partial or
completed human work. Preserve returned rating files under version control before any
subsequent package maintenance.

After the second rater fills a sheet, calculate agreement with:

```bash
# For both files with comma
python manual_validation/calculate_agreement.py dependency_levels

# If both files use "#,##" as delimiter
python manual_validation/calculate_agreement.py dependency_levels --delimiter "#,##"

# If your first rater file uses comma, and your second rater file uses "#,##"
python manual_validation/calculate_agreement.py dependency_levels \
  --first-delimiter "," --second-delimiter "#,##" \
  --second-rater-file manual_validation/dependency_levels/second_rater_result.csv
```

The script reports complete, non-uncertain pairs only. Report the rated denominator,
raw agreement, and unweighted Cohen's kappa; retain disagreements for adjudication but
do not silently replace either rater's independent labels.

### Example output:
Original sample: 30
Rateable paired observations: 30
Excluded missing second-rater rating: 0
Excluded NOT_RATEABLE: 0
Excluded genuine UNSURE: 0
Raw agreement: 0.600 (18/30)
Cohen's kappa (unweighted): 0.287

## Provenance caveat

The oracle sample is exactly reproducible from the recorded population, code, and seed.
The dependency audit has a legacy sample-draw mismatch: `sources/level_audit_sample.csv`
and completed `sources/level_audit.csv` overlap on 19/30 IDs. Of the other 11 completed
rows, five remain in `v2_candidates.jsonl`; six were recovered from audit-era Git
objects in the preserved nested repositories and verified by stable ID, nonblank LOC,
and content hash. Thus all 30 completed-audit items are rateable, but the historical
population snapshot/order that generated those 30 is not preserved. See
`dependency_levels/sample_manifest.csv` for the item-by-item reconciliation.

`UNSURE` means substantive ambiguity after inspecting evidence.
`NOT_RATEABLE_MISSING_EVIDENCE` is a separate administrative status. Neither enters
kappa. Adjudication must be stored separately and never replace either independent
rater column; agreement is always calculated before adjudication.
