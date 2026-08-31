# Dependency-level review protocol

## Rater task

Independently assign exactly one dependency level to each focal function using the
`function_source` and its preserved imports in `dependency_context` in
`second_rater_sheet.csv`. Use the repository/commit/path identifiers in the manifest
when resolving project-local symbols. Do not consult `first_rater_labels.csv`, the
dataset's stored label, or aggregate results before submitting all ratings.

Use the highest dependency level required by any name the focal function references:

- **L0 — built-ins/local values only:** literals, parameters, local variables, and
  Python built-ins; no standard-library, third-party, same-class, or same-file helper.
- **L1 — standard library:** requires a Python standard-library module or symbol, but
  no L2/L3 dependency.
- **L2 — third party:** requires an installed non-standard-library package, but no
  same-class or same-file helper.
- **L3 — project-local context:** calls or accesses a helper, method, class, constant,
  or state defined elsewhere in the same class/file/project context. This level wins
  even when L1 or L2 dependencies are also present.
- **UNSURE:** the provided evidence was inspected but two or more substantive levels
  remain genuinely plausible. Explain the ambiguity. Do not guess from operational complexity:
  filesystem or network activity alone does not imply L3.
- **NOT_RATEABLE_MISSING_EVIDENCE:** required source evidence is absent or corrupted.
  This is an administrative exclusion, not a dependency label or disagreement.

Apply these implementation-aligned edge rules:

- Resolve aliases to the imported module (`import numpy as np` remains L2).
- Resolve relative imports against the repository/module location; a symbol defined
  in the project context is L3, not third party merely because the import is relative.
- Calls, attribute reads, imported constants/classes, decorators, default expressions,
  and runtime-used annotations count when the focal function depends on them.
- Nested calls use the deepest referenced dependency. Local variables and nested local
  functions do not increase the level unless their bodies reach an external dependency.
- `self.helper()`, `cls.helper()`, and same-class state defined outside the focal method
  are L3. Same-file module functions/classes/constants are also L3.
- When multiple types co-occur, choose the maximum: L3 > L2 > L1 > L0.

Record the label in `second_rater_label`, confidence as `high`, `medium`, or `low`, and
a short justification for every UNSURE, NOT_RATEABLE, or low-confidence decision.
Judge the evidence shown and linked by the manifest; do not search for either prior
label. All 30 rows now have recovered source evidence. If a row nevertheless cannot be
opened or verified, use NOT_RATEABLE_MISSING_EVIDENCE rather than UNSURE.

Before returning the file, confirm that all 30 rows have a response and that item IDs
and row order were not changed.
