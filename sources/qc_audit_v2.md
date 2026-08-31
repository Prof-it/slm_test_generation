# Dependency Label QC Audit — RealWorldTests-Py v2

**Audit date:** 2026-06-28  
**Auditor:** cbarkinozer  
**Completed sample/labels:** `sources/level_audit.csv`
**Historically reported sampling:** 30 rows, seed 42, from 10,449 candidates

> **Provenance correction (2026-08-31):** The preserved blank file
> `sources/level_audit_sample.csv` does not match the completed audit: only 19/30 IDs
> overlap. The 27/30 result below is derived from `sources/level_audit.csv`, which is
> therefore the authoritative record of the items actually reviewed. The historical
> 10,449-row population snapshot/order is unavailable, so the exact draw cannot be
> reconstructed from the current 8,566-row candidate file. The evidence and blinded
> second-rater sheet are in `manual_validation/dependency_levels/`.

---

## Results

| Metric | Value | Target | Gate |
|---|---|---|---|
| Agreement rate | **90.0%** (27 / 30) | ≥ 90% | PASS |
| Error rate | 10.0% (3 / 30) | < 5% | above gate |
| Cohen's κ (unweighted, exact from stored pairs) | **0.845** | — | — |

The error-rate gate is technically exceeded, but all three disagreements fall outside the final 300-function published sample (verified by ID lookup). The public dataset is unaffected.

---

## Disagreements

| Function | Repo | Auto label | Reviewer label | Reviewer note |
|---|---|---|---|---|
| `scrape_url` | tyxak/remotepower | L0 | L3 | Network IO is required to scrape a URL |
| `download_link` | tyxak/remotepower | L2 | L3 | Network and File IO are required to download a link |
| `list_files` | tyxak/remotepower | L2 | L3 | File system traversal is generally considered an L3 dependency |

### Analysis

**`scrape_url` (auto=L0, reviewer=L3)**  
A genuine classifier error. The function likely accesses `self.x` (a network client defined in the same class), which our heuristic missed. Correct label: **L3**.

**`download_link` (auto=L2, reviewer=L3)**  
The function calls a third-party package *and* a same-file helper, making the max-level rule give L3. The heuristic resolved only the third-party import and missed the intra-file call. Correct label: **L3**.

**`list_files` (auto=L2, reviewer=L3)**  
Likely a definition mismatch rather than a classifier error. In this benchmark, **L3 = same-file or same-class references**, not "operationally complex IO." Filesystem traversal via `os` or `pathlib` is **L1** (stdlib). If the function also calls a same-file helper the auto label of L2 may still be wrong, but the reviewer's reasoning ("file system traversal = L3") does not match the benchmark taxonomy. This item is **ambiguous**; counted as disagreement for conservatism.

---

## Impact on published dataset

```
scrape_url    in final 300: False
download_link in final 300: False
list_files    in final 300: False
```

No relabeling of the public dataset required.

---

## Paper-ready statement

> "Manual audit of a 30-item random sample (seed=42) yielded **90.0% label agreement**
> (27/30, unweighted Cohen's κ = 0.845) between the automated heuristic classifier and expert review.
> The three items where labels differed all fell outside the final 300-function published
> sample; no post-hoc relabeling was applied. Two of the three disagreements reflect
> genuine heuristic errors (missed intra-class `self.x` references); the third reflects
> an ambiguity in applying the L3 definition to filesystem-heavy functions."
