"""
Review-response statistics for the journal manuscript (Tier-B re-analyses).

Computes, WITHOUT any new generation, from evaluation_results/second_experiment:
  - per-config Pass@1 with task-level bootstrap 95% CI            (Codex #8)
  - conditional mutation vs UNCONDITIONAL fault-detection utility (Codex #2)
  - xfail prevalence among passing suites                         (Codex #3)
  - wall-clock seconds per accepted (passing) suite               (Codex #16)
  - Pass@1 broken down by dependency level L0-L3                  (Codex #9/RQ3)
  - Pass@1 broken down by leaked vs proxy-unleaked                (Codex #4)
  - mean focal prompt-token count per tier                        (Codex #10)
  - has_failtopass availability                                   (Codex #13)
  - full 30-config table (LaTeX longtable for the appendix)       (Codex #22)

Run: python step4_evaluation/review_response_stats.py
"""
import json, glob, os, statistics, random
from collections import defaultdict

random.seed(20260723)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC = os.path.join(ROOT, "evaluation_results", "second_experiment", "run_1")
DATA = os.path.join(ROOT, "TestEval", "data")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mutation_subset_v2_ids.json"), encoding="utf-8") as _f:
    MUTATION_SUBSET_EXPB = set(str(x) for x in json.load(_f))

MODELS = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
          "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]
PREFIX = {"linecov": "Single-call", "linecov2": "Two-stage"}
TIERS = ["A", "B", "C"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def deduplicate_tasks(records):
    """Keep the first record for each task_num.

    RealWorldTests-Py v2 contains one exact duplicate input row (task 316020).
    Treating both rows as independent would violate the N=1-per-task design.
    """
    seen = set()
    unique = []
    for record in records:
        task_num = str(record.get("task_num"))
        if task_num in seen:
            continue
        seen.add(task_num)
        unique.append(record)
    return unique


def bootstrap_ci(bools, n=2000):
    if not bools:
        return (0.0, 0.0)
    N = len(bools)
    means = []
    for _ in range(n):
        s = sum(bools[random.randrange(N)] for _ in range(N))
        means.append(100.0 * s / N)
    means.sort()
    return (means[int(0.025 * n)], means[int(0.975 * n)])


# ---- dataset join tables: task_num -> {dep_level, leaked} per tier -------------
meta = {}
tier_focal_tokens = defaultdict(list)
failtopass_vals = set()
for t in TIERS:
    for row in load_jsonl(os.path.join(DATA, f"realworld-py-v2-tier-{t}.jsonl")):
        tn = str(row["task_num"])
        meta[(t, tn)] = {"dep": row.get("dependency_level", "?"),
                         "leaked": str(row.get("leaked", "?"))}
        failtopass_vals.add(str(row.get("has_failtopass", "?")))
        # tier context size: length of the tier-specific context_card (chars, proxy for tokens)
        cc = row.get("context_card", "")
        tier_focal_tokens[t].append(len(str(cc)))

rows = []  # full-table rows
print("=" * 100)
print("PER-CONFIG STATISTICS (second experiment, N=1 run, T=0.0)")
print("=" * 100)
hdr = f"{'Model':26s} {'Mode':8s} {'Tier':4s} {'N':>4s} {'Pass@1':>7s} {'95% CI':>15s} {'cMut':>6s} {'uMut':>6s} {'xfail%':>7s} {'s/pass':>7s}"
print(hdr)
for m in MODELS:
    for pfx, mode in PREFIX.items():
        for t in TIERS:
            path = os.path.join(SEC, f"tier_{t}", f"{pfx}_{m}_temp_0.0_evaluated.jsonl")
            if not os.path.exists(path):
                continue
            recs = deduplicate_tasks(load_jsonl(path))
            N = len(recs)
            passed = [r for r in recs if r.get("status") == "Pass"]
            bools = [1 if r.get("status") == "Pass" else 0 for r in recs]
            p1 = 100.0 * len(passed) / N if N else 0
            lo, hi = bootstrap_ci(bools)
            muts = [r["mutation_score"] for r in passed
                    if r.get("mutation_score") is not None]
            cmut = statistics.mean(muts) if muts else 0.0   # conditional (already %)
            # unconditional over the mutation sample (fail/missing-in-sample = 0),
            # NOT over all N=300: tasks outside the Cochran subset were never
            # eligible for a mutation score, and dividing by N conflated "never
            # sampled" with "sampled, scored zero", deflating uMut by N/|subset|.
            in_sample = [r for r in recs if str(r.get("task_num")) in MUTATION_SUBSET_EXPB]
            n_sample = len(in_sample)
            sample_muts = [(r["mutation_score"] if r.get("mutation_score") is not None else 0.0)
                           for r in in_sample]
            umut = (sum(sample_muts) / n_sample) if n_sample else 0.0
            xf = sum(1 for r in passed if r.get("has_xfail_tests"))
            xfp = 100.0 * xf / len(passed) if passed else 0.0
            # xfail-excluded Pass@1: count as pass only if no xfail tests present
            p1_noxf = 100.0 * sum(1 for r in passed if not r.get("has_xfail_tests")) / N if N else 0.0
            durs = []
            for r in passed:
                perf = r.get("performance") or {}
                if "duration_seconds" in perf:            # One-Step schema
                    durs.append(perf.get("duration_seconds", 0))
                else:                                      # Two-Step schema
                    durs.append(perf.get("duration_conditions_sec", 0) +
                                perf.get("duration_tests_sec", 0))
            spp = statistics.mean(durs) if durs else 0.0
            # dependency-level & leaked breakdown
            byd = defaultdict(lambda: [0, 0]); byl = defaultdict(lambda: [0, 0])
            for r in recs:
                info = meta.get((t, str(r.get("task_num"))))
                ok = 1 if r.get("status") == "Pass" else 0
                if info:
                    byd[info["dep"]][0] += ok; byd[info["dep"]][1] += 1
                    byl[info["leaked"]][0] += ok; byl[info["leaked"]][1] += 1
            rows.append(dict(m=m, mode=mode, t=t, N=N, p1=p1, lo=lo, hi=hi,
                             cmut=cmut, umut=umut, nmut=len(muts), npass=len(passed),
                             xfp=xfp, p1_noxf=p1_noxf, spp=spp,
                             byd=dict(byd), byl=dict(byl)))
            print(f"{m:26s} {mode:8s} {t:4s} {N:4d} {p1:6.2f}% [{lo:5.1f},{hi:5.1f}] "
                  f"{cmut:5.1f} {umut:5.1f} {xfp:6.1f} {p1_noxf:6.2f} {spp:6.2f}")

# ---- aggregate dependency-level and leaked/unleaked (pooled over configs) -------
print("\n" + "=" * 100)
print("POOLED Pass@1 by DEPENDENCY LEVEL (all 30 configs)")
agg_d = defaultdict(lambda: [0, 0]); agg_l = defaultdict(lambda: [0, 0])
for r in rows:
    for k, (ok, n) in r["byd"].items():
        agg_d[k][0] += ok; agg_d[k][1] += n
    for k, (ok, n) in r["byl"].items():
        agg_l[k][0] += ok; agg_l[k][1] += n
for k in sorted(agg_d):
    ok, n = agg_d[k]; print(f"  {k}: {100*ok/n:5.2f}%  (n={n})")
print("POOLED Pass@1 by LEAKED (proxy):")
for k in sorted(agg_l):
    ok, n = agg_l[k]; print(f"  leaked={k}: {100*ok/n:5.2f}%  (n={n})")

# ---- token counts per tier -----------------------------------------------------
print("\nMEAN context_card size per tier (characters, proxy for prompt length):")
for t in TIERS:
    vals = tier_focal_tokens[t]
    if vals:
        print(f"  Tier {t}: {statistics.mean(vals):8.0f} chars  (n={len(vals)})")
print(f"\nhas_failtopass distinct values across dataset: {failtopass_vals}")

# ---- LaTeX longtable of all 30 configs -----------------------------------------
out = os.path.join(ROOT, "paper", "v2", "full_config_table.tex")
rows_sorted = sorted(rows, key=lambda r: -r["p1"])
with open(out, "w", encoding="utf-8") as fh:
    fh.write("% Auto-generated by step4_evaluation/review_response_stats.py\n")
    fh.write("\\begingroup\n\\scriptsize\n\\setlength{\\tabcolsep}{2pt}\n")
    fh.write("\\begin{longtable}{@{}p{0.24\\textwidth}p{0.10\\textwidth}cccccc@{}}\n")
    fh.write("\\toprule\n")
    fh.write("Model & Mode & Tier & Pass@1 & 95\\% CI & cMut & uMut & m/pass \\\\\n\\midrule\n\\endhead\n")
    for r in rows_sorted:
        fh.write(f"{r['m'].replace('_','-')} & {r['mode']} & {r['t']} & "
                 f"{r['p1']:.1f}\\% & [{r['lo']:.1f}, {r['hi']:.1f}] & "
                 f"{r['cmut']:.1f}\\% & {r['umut']:.1f}\\% & {r['nmut']}/{r['npass']} \\\\\n")
    fh.write("\\botrule\n\\end{longtable}\n\\endgroup\n")
print(f"\nWrote LaTeX full-config table -> {out}")
