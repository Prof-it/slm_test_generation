"""
Taxonomy/optimism aggregations for the Methods/Results sections.
  - Full status taxonomy counts (both experiments)
  - Vacuous-pass overlap (Pass status AND all_skipped_vacuous_pass)
  - Per-model/pipeline assertion optimism: execution-gated Pass@1 minus
    assertion-gated Pass@1 (i.e. Pass suites that lack a detectable assertion)
  - Best config per experiment, Wilson 95% CI
  - Exp B failure counts by raw_exception_class x dependency_level x pipeline

Run: python step4_evaluation/taxonomy_optimism.py
"""
import json, os, math, sys, glob
from pathlib import Path
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "step4_evaluation"))
from evaluate_results import _combine_tests_for_task, strip_markdown  # noqa: E402
from assertion_gate import has_detectable_assertion  # noqa: E402

SEC = os.path.join(ROOT, "evaluation_results", "second_experiment", "run_1")
FIRST = os.path.join(ROOT, "evaluation_results", "first_experiment", "run_1")
PRED_A = os.path.join(ROOT, "downloaded_predictions", "first_experiment", "run_1")
PRED_B = os.path.join(ROOT, "downloaded_predictions", "second_experiment", "run_1")
DATA = os.path.join(ROOT, "TestEval", "data")

MODELS = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
          "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]
PREFIX = {"linecov": "Single-call", "linecov2": "Two-stage"}
TIERS = ["A", "B", "C"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((center - half) / denom, (center + half) / denom)


def assertion_flags_for_file(pred_path, evaluated_recs):
    """Return {task_num: has_assertion_bool} for Pass-status tasks in a prediction file."""
    pass_ids = {str(r["task_num"]) for r in evaluated_recs if r.get("status") == "Pass"}
    flags = {}
    for line in open(pred_path, encoding="utf-8"):
        if not line.strip():
            continue
        entry = json.loads(line)
        tn = str(entry.get("task_num"))
        if tn not in pass_ids:
            continue
        tests = entry.get("tests")
        if not tests:
            flags[tn] = False
            continue
        test_list = list(tests.items()) if isinstance(tests, dict) else [(str(i), t) for i, t in enumerate(tests)]
        func_name = entry.get("func_name", "solution")
        combined = _combine_tests_for_task(test_list, func_name)
        source = strip_markdown(combined)
        if not source.strip():
            flags[tn] = False
            continue
        ok, _kind = has_detectable_assertion(source)
        flags[tn] = ok
    return flags


# ============================================================================
print("=" * 90)
print("1. FULL STATUS TAXONOMY (both experiments)")
print("=" * 90)
for label, path in [("Exp A", os.path.join(FIRST, "*.jsonl")),
                     ("Exp B", os.path.join(SEC, "tier_*", "*.jsonl"))]:
    statuses = defaultdict(int)
    for f in glob.glob(path):
        for r in load_jsonl(f):
            statuses[r.get("status")] += 1
    total = sum(statuses.values())
    print(f"\n{label} (N={total}):")
    for s, c in sorted(statuses.items(), key=lambda kv: -kv[1]):
        print(f"  {s:16s} {c:5d}  ({100*c/total:5.2f}%)")

# ============================================================================
print("\n" + "=" * 90)
print("2. VACUOUS-PASS OVERLAP (status==Pass AND all_skipped_vacuous_pass)")
print("=" * 90)
for label, path in [("Exp A", os.path.join(FIRST, "*.jsonl")),
                     ("Exp B", os.path.join(SEC, "tier_*", "*.jsonl"))]:
    n_pass = n_vac = 0
    for f in glob.glob(path):
        for r in load_jsonl(f):
            if r.get("status") == "Pass":
                n_pass += 1
                if r.get("all_skipped_vacuous_pass"):
                    n_vac += 1
    print(f"{label}: {n_vac}/{n_pass} Pass suites are vacuous ({100*n_vac/n_pass:.2f}%)" if n_pass else f"{label}: n/a")

# ============================================================================
print("\n" + "=" * 90)
print("3. PER-MODEL/PIPELINE ASSERTION OPTIMISM (execution-gated - assertion-gated Pass@1)")
print("=" * 90)

def assertion_optimism(models, prefixes, pred_dir, eval_dir, tiers=None):
    rows = []
    for m in models:
        for pfx, mode in prefixes.items():
            if tiers:
                all_recs = []
                pass_ids_all = set()
                asrt_pass_all = set()
                for t in tiers:
                    ep = os.path.join(eval_dir, f"tier_{t}", f"{pfx}_{m}_temp_0.0_evaluated.jsonl")
                    pp = os.path.join(pred_dir, f"tier_{t}", f"{pfx}_{m}_temp_0.0.jsonl")
                    if not os.path.exists(ep) or not os.path.exists(pp):
                        continue
                    recs = load_jsonl(ep)
                    all_recs.extend(recs)
                    flags = assertion_flags_for_file(pp, recs)
                    for tn, ok in flags.items():
                        pass_ids_all.add(tn)
                        if ok:
                            asrt_pass_all.add(tn)
                N = len(all_recs)
                n_exec_pass = sum(1 for r in all_recs if r.get("status") == "Pass")
            else:
                ep = os.path.join(eval_dir, f"{pfx}_{m}_temp_0.0_evaluated.jsonl")
                pp = os.path.join(pred_dir, f"{pfx}_{m}_temp_0.0.jsonl")
                if not os.path.exists(ep) or not os.path.exists(pp):
                    continue
                recs = load_jsonl(ep)
                N = len(recs)
                n_exec_pass = sum(1 for r in recs if r.get("status") == "Pass")
                flags = assertion_flags_for_file(pp, recs)
                pass_ids_all = set(flags.keys())
                asrt_pass_all = {tn for tn, ok in flags.items() if ok}
            exec_p1 = 100.0 * n_exec_pass / N if N else float("nan")
            asrt_p1 = 100.0 * len(asrt_pass_all) / N if N else float("nan")
            gap = exec_p1 - asrt_p1
            rows.append(dict(m=m, mode=mode, N=N, exec_p1=exec_p1, asrt_p1=asrt_p1, gap=gap))
            print(f"  {m:26s} {mode:10s} N={N:4d}  exec-Pass@1={exec_p1:6.2f}%  "
                  f"assertion-Pass@1={asrt_p1:6.2f}%  optimism-gap={gap:5.2f}pp")
    return rows

print("\n-- Exp A --")
rows_a = assertion_optimism(MODELS, PREFIX, PRED_A, FIRST, tiers=None)
print("\n-- Exp B (pooled over tiers) --")
rows_b = assertion_optimism(MODELS, PREFIX, PRED_B, SEC, tiers=TIERS)

for label, rows in [("Exp A", rows_a), ("Exp B", rows_b)]:
    sc_gaps = [r["gap"] for r in rows if r["mode"] == "Single-call"]
    ts_gaps = [r["gap"] for r in rows if r["mode"] == "Two-stage"]
    print(f"\n{label} mean optimism gap: Single-call={sum(sc_gaps)/len(sc_gaps):.2f}pp  "
          f"Two-stage={sum(ts_gaps)/len(ts_gaps):.2f}pp")

# ============================================================================
print("\n" + "=" * 90)
print("4. BEST CONFIG PER EXPERIMENT, Wilson 95% CI (execution-gated Pass@1)")
print("=" * 90)
for label, rows in [("Exp A", rows_a), ("Exp B", rows_b)]:
    best = max(rows, key=lambda r: r["exec_p1"])
    k = round(best["exec_p1"] / 100.0 * best["N"])
    lo, hi = wilson_ci(k, best["N"])
    print(f"{label} best config: {best['m']} / {best['mode']}  "
          f"Pass@1={best['exec_p1']:.2f}%  Wilson 95% CI=[{100*lo:.2f}%, {100*hi:.2f}%]  (k={k}, n={best['N']})")

# ============================================================================
print("\n" + "=" * 90)
print("5. Exp B failure counts by raw_exception_class x dependency_level x pipeline")
print("=" * 90)
dep_level = {}
for t in TIERS:
    for row in load_jsonl(os.path.join(DATA, f"realworld-py-v2-tier-{t}.jsonl")):
        dep_level[str(row["task_num"])] = row.get("dependency_level", "?")

fail_counts = defaultdict(int)
for m in MODELS:
    for pfx, mode in PREFIX.items():
        for t in TIERS:
            path = os.path.join(SEC, f"tier_{t}", f"{pfx}_{m}_temp_0.0_evaluated.jsonl")
            if not os.path.exists(path):
                continue
            for r in load_jsonl(path):
                if r.get("status") != "Runtime Error":
                    continue
                if r.get("harness_broken_task"):
                    continue
                tn = str(r.get("task_num"))
                lvl = dep_level.get(tn, "?")
                exc = r.get("raw_exception_class") or "None"
                fail_counts[(exc, lvl, mode)] += 1

print(f"{'exception_class':30s} {'level':6s} {'pipeline':12s} {'count':>6s}")
for (exc, lvl, mode), c in sorted(fail_counts.items(), key=lambda kv: -kv[1])[:40]:
    print(f"{exc:30s} {lvl:6s} {mode:12s} {c:6d}")

out = {"fail_counts": [{"exc": k[0], "level": k[1], "pipeline": k[2], "count": v}
                        for k, v in fail_counts.items()]}
with open(os.path.join(ROOT, "step4_evaluation", "taxonomy_optimism_output.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("\nwrote step4_evaluation/taxonomy_optimism_output.json")
