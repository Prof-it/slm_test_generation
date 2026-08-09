"""
L0 model-attributable RuntimeError rate: among L0 (builtins/literals-only)
dependency-level tasks, what fraction of MODEL outputs raised a Runtime Error,
after stripping the 18 harness_broken_task cases (golden-solution-itself-fails
tasks, a dataset defect not attributable to the model)?

Run: python step4_evaluation/l0_runtime_error_rate.py
"""
import json, os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC = os.path.join(ROOT, "evaluation_results", "second_experiment", "run_1")
DATA = os.path.join(ROOT, "TestEval", "data")

MODELS = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
          "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]
PREFIX = {"linecov": "Single-call", "linecov2": "Two-stage"}
TIERS = ["A", "B", "C"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


# task_num -> dependency_level, from dataset (level is tier-independent, same task set per tier)
dep_level = {}
for t in TIERS:
    for row in load_jsonl(os.path.join(DATA, f"realworld-py-v2-tier-{t}.jsonl")):
        dep_level[str(row["task_num"])] = row.get("dependency_level", "?")

# ---- pooled across all 30 configs, RuntimeError rate by dep level, with/without harness-broken strip
counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # counts[strip_mode][level] = [n_re, n_total]
raw_exc_at_l0 = defaultdict(int)
per_config_l0 = []

for m in MODELS:
    for pfx, mode in PREFIX.items():
        for t in TIERS:
            path = os.path.join(SEC, f"tier_{t}", f"{pfx}_{m}_temp_0.0_evaluated.jsonl")
            if not os.path.exists(path):
                continue
            recs = load_jsonl(path)
            l0_re = 0
            l0_total_stripped = 0
            for r in recs:
                tn = str(r.get("task_num"))
                lvl = dep_level.get(tn, "?")
                broken = bool(r.get("harness_broken_task"))
                is_re = r.get("status") == "Runtime Error"

                # unstripped (includes harness-broken tasks)
                counts["unstripped"][lvl][1] += 1
                if is_re:
                    counts["unstripped"][lvl][0] += 1

                # stripped (excludes harness-broken tasks -- model-attributable only)
                if not broken:
                    counts["stripped"][lvl][1] += 1
                    if is_re:
                        counts["stripped"][lvl][0] += 1
                        if lvl == "L0":
                            raw_exc_at_l0[r.get("raw_exception_class") or "None"] += 1

                if lvl == "L0" and not broken:
                    l0_total_stripped += 1
                    if is_re:
                        l0_re += 1
            per_config_l0.append(dict(m=m, mode=mode, t=t, n=l0_total_stripped, re=l0_re))

print("=" * 90)
print("RuntimeError rate by dependency level, pooled over all 30 configs (900 obs/level unstripped)")
print("=" * 90)
for mode_label, key in [("UNSTRIPPED (includes 18 harness-broken tasks x 30 configs = 540 obs)", "unstripped"),
                         ("STRIPPED (harness_broken_task excluded -- model-attributable only)", "stripped")]:
    print(f"\n-- {mode_label} --")
    for lvl in ["L0", "L1", "L2", "L3", "?"]:
        n_re, n_tot = counts[key][lvl]
        if n_tot == 0:
            continue
        print(f"  {lvl}: {n_re:4d} / {n_tot:4d} = {100*n_re/n_tot:5.2f}%")

print("\n" + "=" * 90)
print("L0 model-attributable RuntimeError: raw_exception_class breakdown")
print("=" * 90)
for k, v in sorted(raw_exc_at_l0.items(), key=lambda kv: -kv[1]):
    print(f"  {k}: {v}")

print("\n" + "=" * 90)
print("L0 model-attributable RuntimeError rate per config (30 rows)")
print("=" * 90)
for row in per_config_l0:
    pct = 100 * row["re"] / row["n"] if row["n"] else float("nan")
    print(f"  {row['m']:26s} {row['mode']:10s} Tier {row['t']}: {row['re']:3d}/{row['n']:3d} = {pct:5.2f}%")
