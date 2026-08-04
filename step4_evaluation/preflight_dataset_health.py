"""
preflight_dataset_health.py -- run this BEFORE any re-evaluation.

Adapted from a reviewer-proposed checklist item, wired to this repo's actual
dataset layout (TestEval/data/realworld-py-v2*.jsonl) and evaluation harness
(step4_evaluation/evaluate_results.py's fix_relative_imports/fix_absolute_imports).

Three jobs:
 1. Reproduce the importability audit as a permanent, reportable artefact with
    a per-error-class breakdown (does under_test.py import at all, independent
    of any model's generated test?).
 2. Answer the question the first version of this audit did NOT: are broken
    tasks distributed evenly across the recency pools? If they skew toward one
    pool, part of any historical-vs-recent contamination effect is a
    dataset-construction artefact, not evidence of pre-training exposure.
 3. Write dataset_health.json with a "broken_task_ids" list, which
    evaluate_results.py reads (load_known_harness_broken_ids) to tag each
    evaluated record with harness_broken_task=True/False for attribution.

Usage:
    python step4_evaluation/preflight_dataset_health.py
    python step4_evaluation/preflight_dataset_health.py --dataset TestEval/data/realworld-py-v2-tier-A.jsonl
"""

import argparse
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from scipy import stats as _stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "step4_evaluation"))
from evaluate_results import fix_absolute_imports, fix_relative_imports, COMMON_IMPORTS  # noqa: E402


def try_import(source: str) -> tuple[bool, str | None, str]:
    """Import the reconstructed under_test.py module in-process. Returns
    (ok, error_class, detail). Uses a unique module name per call and cleans
    up sys.path/sys.modules explicitly to avoid cross-call contamination."""
    tmp_dir = Path(tempfile.mkdtemp())
    (tmp_dir / "under_test.py").write_text(source, encoding="utf-8")
    sys.path.insert(0, str(tmp_dir))
    if "under_test" in sys.modules:
        del sys.modules["under_test"]
    try:
        mod = __import__("under_test")
        if not hasattr(mod, "Solution"):
            return False, "MissingSolutionAttr", "module imported but has no Solution class"
        return True, None, ""
    except Exception as e:  # noqa: BLE001
        return False, type(e).__name__, str(e)
    finally:
        sys.path.remove(str(tmp_dir))


def build_under_test_source(python_solution_full: str) -> str:
    lines = python_solution_full.splitlines()
    future_lines = [l for l in lines if l.strip().startswith("from __future__")]
    other_lines = [l for l in lines if not l.strip().startswith("from __future__")]
    future_block = "\n".join(future_lines) + "\n" if future_lines else ""
    remaining = fix_absolute_imports(fix_relative_imports("\n".join(other_lines)))
    return future_block + COMMON_IMPORTS + "\n" + remaining


def crosstab_report(rows, key, title):
    ok, bad = Counter(), Counter()
    for r in rows:
        (ok if r["importable"] else bad)[r.get(key)] += 1
    keys = sorted(set(ok) | set(bad), key=lambda x: (x is None, str(x)))
    print(f"\n{title}")
    print(f"  {'value':<16}{'total':>7}{'broken':>8}{'% broken':>10}")
    out = {}
    for k in keys:
        n = ok[k] + bad[k]
        pct = 100 * bad[k] / n if n else 0
        print(f"  {str(k):<16}{n:>7}{bad[k]:>8}{pct:>9.1f}%")
        out[str(k)] = {"total": n, "broken": bad[k], "pct_broken": round(pct, 2)}
    return out, ok, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2-tier-A.jsonl"))
    ap.add_argument("--out", default=str(PROJECT_ROOT / "step4_evaluation" / "dataset_health.json"))
    a = ap.parse_args()

    raw = [json.loads(l) for l in Path(a.dataset).read_text(encoding="utf-8").splitlines() if l.strip()]

    seen, dupes, unique = set(), [], []
    for r in raw:
        tn = str(r["task_num"])
        if tn in seen:
            dupes.append(tn)
        else:
            seen.add(tn)
            unique.append(r)
    print("=" * 68)
    print(f"loaded {len(raw)} rows | {len(unique)} unique task_num")
    if dupes:
        print(f"!! {len(dupes)} DUPLICATE task_num dropped: {sorted(set(dupes))}")
    print("=" * 68)

    rows = []
    for i, r in enumerate(unique, 1):
        src = build_under_test_source(r.get("python_solution_full", ""))
        ok, ecls, detail = try_import(src)
        rows.append({
            "task_id": str(r["task_num"]), "dep_level": r.get("dependency_level"),
            "recency": "historical" if r.get("leaked") else "recent",
            "repo": r.get("repo"), "importable": ok, "error_class": ecls, "detail": detail,
        })
        if i % 50 == 0:
            print(f"  checked {i}/{len(unique)}")

    n = len(rows)
    broken = [r for r in rows if not r["importable"]]
    print("\n" + "=" * 68)
    print(f"IMPORTABILITY: {n - len(broken)}/{n} OK, {len(broken)} broken ({100 * len(broken) / n:.1f}%)")
    print("=" * 68)

    print("\nBy error class:")
    ec = Counter(r["error_class"] for r in broken)
    for k, v in ec.most_common():
        print(f"  {k:<24}{v:>4}")

    lvl, _, _ = crosstab_report(rows, "dep_level", "By dependency level:")
    rec, ok_r, bad_r = crosstab_report(rows, "recency", "By RECENCY POOL:")

    print("\n" + "=" * 68)
    print("CONTAMINATION CONFOUND TEST")
    print("=" * 68)
    pools = [k for k in ("historical", "recent") if k in set(ok_r) | set(bad_r)]
    fisher = None
    if len(pools) == 2:
        table = [[bad_r[p], ok_r[p]] for p in pools]
        odds, p = _stats.fisher_exact(table)
        h_pct = 100 * bad_r["historical"] / max(1, bad_r["historical"] + ok_r["historical"])
        r_pct = 100 * bad_r["recent"] / max(1, bad_r["recent"] + ok_r["recent"])
        print(f"  broken rate historical : {h_pct:.1f}%")
        print(f"  broken rate recent     : {r_pct:.1f}%")
        print(f"  Fisher exact           : OR={odds:.3f}, p={p:.4f}")
        fisher = {"odds_ratio": odds, "p_value": p, "pct_broken_historical": h_pct, "pct_broken_recent": r_pct}
        if p < 0.05:
            worse = "recent" if r_pct > h_pct else "historical"
            print(f"\n  *** SIGNIFICANT IMBALANCE *** -- {worse} pool carries more guaranteed-failure tasks.")
        else:
            print("\n  No significant imbalance.")

    by_repo = defaultdict(lambda: [0, 0])
    for r in rows:
        by_repo[r["repo"]][0 if r["importable"] else 1] += 1
    hot = sorted(((k, v[1], v[0] + v[1]) for k, v in by_repo.items() if v[1]), key=lambda x: -x[1])[:10]
    if hot:
        print("\nMost-affected repositories:")
        for repo, b, tot in hot:
            print(f"  {str(repo):<40}{b:>3}/{tot}")

    payload = {
        "n_unique_tasks": n, "n_duplicates_dropped": len(dupes), "duplicates": sorted(set(dupes)),
        "n_broken": len(broken), "pct_broken": round(100 * len(broken) / n, 2),
        "by_error_class": dict(ec), "by_dep_level": lvl, "by_recency": rec,
        "contamination_confound_test": fisher,
        "broken_task_ids": sorted(r["task_id"] for r in broken),
        "rows": rows,
    }
    Path(a.out).write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
