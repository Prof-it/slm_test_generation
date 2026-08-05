"""
RQ3: Pass@1 by dependency level (L0-L3), post-correction, execution-gated
and assertion-gated, pooled across all 30 Exp B configs (all models,
pipelines, tiers). Wilson 95% CI on both.

Run: python step4_evaluation/rq3_dependency_level.py
"""
import json, math, sys, glob
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "step4_evaluation"))
from evaluate_results import _combine_tests_for_task, strip_markdown  # noqa: E402
from assertion_gate import has_detectable_assertion  # noqa: E402

SEC = ROOT / "evaluation_results" / "second_experiment" / "run_1"
PRED_B_GLOB = str(ROOT / "downloaded_predictions" / "second_experiment" / "run_1" / "tier_*" / "*.jsonl")
DATA = ROOT / "TestEval" / "data"

MODELS = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
          "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]
PREFIX = {"linecov": "Single-call", "linecov2": "Two-stage"}
TIERS = ["A", "B", "C"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    denom = 1 + z ** 2 / n
    center = p + z ** 2 / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))
    lo = (center - half) / denom
    hi = (center + half) / denom
    return (p * 100, lo * 100, hi * 100)


dep_level = {}
for t in TIERS:
    for row in load_jsonl(DATA / f"realworld-py-v2-tier-{t}.jsonl"):
        dep_level[str(row["task_num"])] = row.get("dependency_level", "?")

pred_b_files = {Path(f).parent.name + "/" + Path(f).stem: f for f in glob.glob(PRED_B_GLOB)}


def assertion_pass_ids(pred_path, pass_ids):
    out = set()
    for line in open(pred_path, encoding="utf-8"):
        if not line.strip():
            continue
        entry = json.loads(line)
        tn = str(entry.get("task_num"))
        if tn not in pass_ids:
            continue
        tests = entry.get("tests")
        if not tests:
            continue
        test_list = list(tests.items()) if isinstance(tests, dict) else [(str(i), t) for i, t in enumerate(tests)]
        func_name = entry.get("func_name", "solution")
        combined = _combine_tests_for_task(test_list, func_name)
        source = strip_markdown(combined)
        if not source.strip():
            continue
        ok, _kind = has_detectable_assertion(source)
        if ok:
            out.add(tn)
    return out


counts = defaultdict(lambda: {"n": 0, "exec_pass": 0, "gated_pass": 0})

for m in MODELS:
    for pfx, mode in PREFIX.items():
        for t in TIERS:
            path = SEC / f"tier_{t}" / f"{pfx}_{m}_temp_0.0_evaluated.jsonl"
            if not path.exists():
                continue
            recs = load_jsonl(path)
            pass_ids = {str(r["task_num"]) for r in recs if r.get("status") == "Pass"}
            pred_path = pred_b_files.get(f"tier_{t}/{pfx}_{m}_temp_0.0")
            gated_ids = assertion_pass_ids(pred_path, pass_ids) if pred_path else set()
            for r in recs:
                tn = str(r["task_num"])
                lvl = dep_level.get(tn, "?")
                counts[lvl]["n"] += 1
                if r.get("status") == "Pass":
                    counts[lvl]["exec_pass"] += 1
                    if tn in gated_ids:
                        counts[lvl]["gated_pass"] += 1

print("=" * 90)
print("RQ3: Pass@1 by dependency level, pooled over all 30 configs (N=2250/level)")
print("=" * 90)
print(f"{'Level':6s} {'N':>5s} {'exec Pass@1':>14s} {'95% CI':>16s} {'gated Pass@1':>14s} {'95% CI':>16s}")
for lvl in ["L0", "L1", "L2", "L3"]:
    c = counts[lvl]
    n = c["n"]
    pe, lo_e, hi_e = wilson_ci(c["exec_pass"], n)
    pg, lo_g, hi_g = wilson_ci(c["gated_pass"], n)
    print(f"{lvl:6s} {n:5d} {pe:12.2f}%  [{lo_e:5.2f},{hi_e:5.2f}] {pg:12.2f}%  [{lo_g:5.2f},{hi_g:5.2f}]")
