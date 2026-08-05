"""
Robustness checks on the Exp A vs Exp B Spearman(Pass@1, uMut) divergence.
1. Absolute mutant counts (killed/total) per pooled model x pipeline cell, Exp B.
2. Bootstrap 95% CI on rho itself (n=10 cells), both experiments.
3. Fisher r-to-z test: is rho_A=0.842 significantly different from rho_B=-0.006?

Run: python step4_evaluation/rho_robustness_check.py
"""
import json, os, random
from collections import defaultdict
from scipy.stats import spearmanr
import numpy as np

random.seed(20260804)
np.random.seed(20260804)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC = os.path.join(ROOT, "evaluation_results", "second_experiment", "run_1")
FIRST = os.path.join(ROOT, "evaluation_results", "first_experiment", "run_1")

with open(os.path.join(ROOT, "step4_evaluation", "mutation_subset_v2_ids.json"), encoding="utf-8") as f:
    SUBSET_B = set(str(x) for x in json.load(f))
with open(os.path.join(ROOT, "step4_evaluation", "mutation_subset_ids.json"), encoding="utf-8") as f:
    SUBSET_A = set(str(x) for x in json.load(f))

MODELS_B = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
            "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]
PREFIX_B = {"linecov": "Single-call", "linecov2": "Two-stage"}
TIERS_B = ["A", "B", "C"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


# ---------- Exp B: pooled model x pipeline (10 cells), with mutant counts -------
print("=" * 100)
print("EXP B -- pooled model x pipeline (10 cells): Pass@1, uMut, killed/total mutants")
print("=" * 100)
cellsB = []
for m in MODELS_B:
    for pfx, mode in PREFIX_B.items():
        all_recs = []
        for t in TIERS_B:
            path = os.path.join(SEC, f"tier_{t}", f"{pfx}_{m}_temp_0.0_evaluated.jsonl")
            if not os.path.exists(path):
                print(f"  MISSING FILE: {path}")
                continue
            all_recs.extend(load_jsonl(path))
        N = len(all_recs)
        passed = sum(1 for r in all_recs if r.get("status") == "Pass")
        p1 = 100.0 * passed / N if N else float("nan")
        in_sample = [r for r in all_recs if str(r.get("task_num")) in SUBSET_B]
        n_sample = len(in_sample)
        sample_muts = [(r["mutation_score"] if r.get("mutation_score") is not None else 0.0)
                       for r in in_sample]
        umut = (sum(sample_muts) / n_sample) if n_sample else float("nan")
        killed = sum((r.get("mutation_stats") or {}).get("killed", 0) for r in in_sample
                     if r.get("mutation_stats"))
        total = sum((r.get("mutation_stats") or {}).get("total", 0) for r in in_sample
                    if r.get("mutation_stats"))
        n_scored = sum(1 for r in in_sample if r.get("mutation_score") is not None)
        cellsB.append(dict(m=m, mode=mode, N=N, p1=p1, umut=umut,
                            n_sample=n_sample, n_scored=n_scored,
                            killed=killed, total=total))
        print(f"  {m:26s} {mode:10s}  N={N:3d}  Pass@1={p1:6.2f}%  uMut={umut:5.2f}%  "
              f"n_sample={n_sample:3d}  n_scored(passed&mutated)={n_scored:3d}  "
              f"killed/total={killed}/{total}")

pass1_B = [c["p1"] for c in cellsB]
umut_B = [c["umut"] for c in cellsB]
rho_B, p_B = spearmanr(pass1_B, umut_B)
print(f"\nSpearman(Pass@1, uMut) Exp B pooled (n=10): rho={rho_B:.4f}  p={p_B:.4f}")

# ---------- Exp A: pooled model x pipeline (10 cells) for parity ----------------
print("\n" + "=" * 100)
print("EXP A -- pooled model x pipeline (10 cells): Pass@1, uMut")
print("=" * 100)
MODELS_A = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
            "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]
PREFIX_A = {"linecov": "Single-call", "linecov2": "Two-stage"}

cellsA = []
for m in MODELS_A:
    for pfx, mode in PREFIX_A.items():
        path = os.path.join(FIRST, f"{pfx}_{m}_temp_0.0_evaluated.jsonl")
        if not os.path.exists(path):
            print(f"  MISSING FILE: {path}")
            continue
        recs = load_jsonl(path)
        N = len(recs)
        passed = sum(1 for r in recs if r.get("status") == "Pass")
        p1 = 100.0 * passed / N if N else float("nan")
        in_sample = [r for r in recs if str(r.get("task_num")) in SUBSET_A]
        n_sample = len(in_sample)
        sample_muts = [(r["mutation_score"] if r.get("mutation_score") is not None else 0.0)
                       for r in in_sample]
        umut = (sum(sample_muts) / n_sample) if n_sample else float("nan")
        killed = sum((r.get("mutation_stats") or {}).get("killed", 0) for r in in_sample
                     if r.get("mutation_stats"))
        total = sum((r.get("mutation_stats") or {}).get("total", 0) for r in in_sample
                    if r.get("mutation_stats"))
        n_scored = sum(1 for r in in_sample if r.get("mutation_score") is not None)
        cellsA.append(dict(m=m, mode=mode, N=N, p1=p1, umut=umut,
                            n_sample=n_sample, n_scored=n_scored,
                            killed=killed, total=total))
        print(f"  {m:26s} {mode:10s}  N={N:3d}  Pass@1={p1:6.2f}%  uMut={umut:5.2f}%  "
              f"n_sample={n_sample:3d}  n_scored(passed&mutated)={n_scored:3d}  "
              f"killed/total={killed}/{total}")

pass1_A = [c["p1"] for c in cellsA]
umut_A = [c["umut"] for c in cellsA]
rho_A, p_A = spearmanr(pass1_A, umut_A)
print(f"\nSpearman(Pass@1, uMut) Exp A pooled (n=10): rho={rho_A:.4f}  p={p_A:.4f}")

# =================================================================================
# CHECK 2: bootstrap 95% CI on rho itself, resampling CELLS (n=10) with replacement
# =================================================================================
def bootstrap_rho_ci(x, y, n_boot=10000):
    x = np.array(x); y = np.array(y)
    n = len(x)
    boots = []
    for _ in range(n_boot):
        idx = np.random.randint(0, n, n)
        xb, yb = x[idx], y[idx]
        if np.std(xb) == 0 or np.std(yb) == 0:
            continue
        r, _ = spearmanr(xb, yb)
        if not np.isnan(r):
            boots.append(r)
    boots.sort()
    lo = boots[int(0.025 * len(boots))]
    hi = boots[int(0.975 * len(boots))]
    return lo, hi, len(boots)

lo_A, hi_A, nb_A = bootstrap_rho_ci(pass1_A, umut_A)
lo_B, hi_B, nb_B = bootstrap_rho_ci(pass1_B, umut_B)
print("\n" + "=" * 100)
print("CHECK 2: bootstrap 95% CI on rho (resampling 10 cells w/ replacement, 10000 draws)")
print("=" * 100)
print(f"  Exp A: rho={rho_A:.3f}  95% CI [{lo_A:.3f}, {hi_A:.3f}]  (n_valid_boots={nb_A})")
print(f"  Exp B: rho={rho_B:.3f}  95% CI [{lo_B:.3f}, {hi_B:.3f}]  (n_valid_boots={nb_B})")

# =================================================================================
# CHECK 3: Fisher r-to-z test comparing the two independent correlations
# =================================================================================
def fisher_r_to_z_test(r1, n1, r2, n2):
    z1 = np.arctanh(r1)
    z2 = np.arctanh(r2)
    se = np.sqrt(1.0 / (n1 - 3) + 1.0 / (n2 - 3))
    z = (z1 - z2) / se
    from scipy.stats import norm
    p = 2 * (1 - norm.cdf(abs(z)))
    return z, p

z_stat, p_fisher = fisher_r_to_z_test(rho_A, 10, rho_B, 10)
print("\n" + "=" * 100)
print("CHECK 3: Fisher r-to-z test, rho_A vs rho_B (n=10 each)")
print("=" * 100)
print(f"  z = {z_stat:.3f}   p = {p_fisher:.4f}")
if p_fisher > 0.05:
    print("  --> NOT significantly different at alpha=0.05. Cannot claim the relationship")
    print("      differs between Exp A and Exp B on this evidence alone.")
else:
    print("  --> Significantly different at alpha=0.05.")
