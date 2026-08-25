# TestContextBench-Py Datasheet Verification

## Status: complete — two discrepancies found, not yet fixed in paper.tex

Every factual row of the datasheet (`Table~\ref{tab:tcb_datasheet}`,
`paper.tex` ~L433-452) checked directly against the dataset-construction code
and the released dataset file
(`TestEval/data/realworld-py-v2.jsonl`, 300 records).

## Confirmed accurate

| Claim | Verified against | Result |
|---|---|---|
| 300 unique functions, 75/level x 4 levels | `TestEval/data/realworld-py-v2.jsonl` | Exact: `{L0:75, L1:75, L2:75, L3:75}` |
| Per-repo cap 15 / 5% | `package_v2_dataset.py:145,276` (`max_per_repo=15` default) + dataset file | Exact: max observed per-repo count in the released file is 15 |
| CC >= 3 | `create_v2_dataset.py:47` (`MIN_CC = 3`, candidates rejected only when `max_cc < MIN_CC`) | Matches; confirms the earlier `>=` vs `>` resolution |
| 3-80 LOC | `create_v2_dataset.py:48-49,215` (`MIN_LOC=3`, `MAX_LOC=80`) | Exact match |
| Recency cutoff 2026-06-10 | `collect_sources_v2.py:42` (`CUTOFF_DATE = "2026-06-10"`) | Exact match, used consistently for both the GitHub search queries and the leaked-pool `commit_date` tag |
| Target 75/level | `package_v2_dataset.py:50` (`TARGET_PER_LEVEL = 75`) | Matches |
| Dependency-level definitions (L0 builtins / L1 stdlib / L2 third-party / L3 same-file) | `paper.tex` prose vs. `create_v2_dataset.py`/classifier logic | Matches described resolution order (deepest category wins) |

## Discrepancies found

### 1. "English docstring" is not an enforced criterion — only "has a docstring"

`paper.tex` Table `tab:tcb_datasheet` and the inclusion-criteria prose both
state the dataset requires "a natural-language English docstring." The actual
filter in `create_v2_dataset.py:204-207` is:

```python
docstring = ast.get_docstring(node)
if not docstring:
    continue
```

This checks *presence* of a docstring only — there is no language detection
anywhere in the pipeline (`create_v2_dataset.py`, `package_v2_dataset.py`,
`collect_sources_v2.py` all searched, no `langdetect`/`isascii`/similar).
In practice this is very likely fine, since source repos were collected via
GitHub-search queries scoped to English-topic tags and `language:python`, and
a manual spot-check would likely find the residual non-English docstring rate
near zero — but as literally written, the paper claims an enforced criterion
that the code does not implement. Either add a real language check, or soften
the wording to "a non-empty docstring (informally, in practice English, given
the English-topic-scoped source search; not independently verified by
language ID)."

### 2. Licensing claim does not hold for the 60/300 (20%) leaked-pool tasks

`paper.tex` states: *"Only repositories with OSI-approved licenses included;
license metadata retained per task."* This is true for the 240 freshly
collected tasks (`license` in `{mit, apache-2.0}` in the released dataset —
`collect_sources_v2.py:151-152,177` filters explicitly to
`license_key in ("mit", "apache-2.0")`), but **not** for the 60 tasks drawn
from the pre-existing "leaked" TestEval real-world pool
(`collect_sources_v2.py:117-134`, `collect_leaked()`), whose `license` field
is hard-coded to the literal placeholder string `"varies"`
(`collect_sources_v2.py:128`), not a verified OSI-approved license per task.

Confirmed directly in the released dataset:

```
Counter({'mit': 225, 'varies': 60, 'apache-2.0': 15})
```

60/300 = 20% of the benchmark carries an unverified license placeholder, not
an OSI-approved license confirmed per task. This is a real gap between the
paper's blanket licensing claim and what the pipeline actually checked for
the leaked-pool subset (which is the same subset TestEval itself already
draws from, so it may be inheriting TestEval's own licensing posture rather
than lacking one entirely — but the paper does not currently say that, and
`"varies"` as recorded is not itself evidence of OSI compliance).

**Two ways to close this, your call:**
- (a) Actually check the license of each of the 60 leaked-pool source repos
  (they're already cloned locally under `sources/repos/`) and replace the
  `"varies"` placeholder with the real per-repo license, same as the other
  240; report the true post-check numbers in the datasheet.
- (b) Soften the datasheet claim to something like: "Repositories in the
  freshly collected pool (240/300, 80%) were filtered to OSI-approved
  MIT/Apache-2.0 licenses at collection time; the remaining 60/300 (20%)
  were drawn from TestEval's pre-existing real-world pool and inherit
  TestEval's own licensing treatment rather than being independently
  re-verified here."

I did not choose between these or edit `paper.tex` — this is a factual/scope
call, not a mechanical fix.

## Not independently re-verified (out of scope for this pass)

- Whether the specific MIT/Apache-2.0 license string recorded for each of the
  240 non-leaked tasks matches the actual `LICENSE` file in the corresponding
  cloned repo (spot-checkable via `sources/repos/*/LICENSE*`, not exhaustively
  redone here).
- Reproducibility of the GitHub Search API query results themselves (subject
  to API/index drift over time; the released `.jsonl` is the frozen
  snapshot, which is what matters for reproducibility of *this paper's*
  results, not of re-running the collection query today).
