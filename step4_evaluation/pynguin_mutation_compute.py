import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ids = set(json.load(open(ROOT / "step4_evaluation" / "mutation_subset_v2_ids.json")))

seed_files = {
    42: ROOT / "evaluation_results" / "pynguin_simple_mutation" / "pynguin_seed42_evaluated.jsonl",
    43: ROOT / "evaluation_results" / "pynguin_simple_mutation" / "pynguin_seed43_evaluated.jsonl",
}

all_subset_recs = []
per_seed = {}

for seed, path in seed_files.items():
    with open(path, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]
    sub = [r for r in recs if str(r["task_num"]) in ids]
    assert len(sub) == 73, f"seed {seed}: expected 73, got {len(sub)}"
    per_seed[seed] = sub
    all_subset_recs.extend(sub)

nonzero = [r for r in all_subset_recs if r.get("mutation_stats") and r["mutation_stats"].get("total", 0) > 0]
print(f"Sanity check: {len(nonzero)} / {len(all_subset_recs)} subset records have mutation_stats.total > 0")
if not nonzero:
    print("ALL ZERO -- something is still wrong. Sample error fields:")
    errs = [r.get("mutation_error") for r in all_subset_recs if r.get("mutation_error")]
    for e in errs[:5]:
        print(" -", e)
    raise SystemExit(1)

def compute(records, label):
    n = len(records)
    passed_scored = [r["mutation_score"] for r in records if r.get("status") == "Pass" and r.get("mutation_score") is not None]
    cmut = sum(passed_scored) / len(passed_scored) if passed_scored else float("nan")
    umut_vals = [(r["mutation_score"] if r.get("mutation_score") is not None else 0.0) for r in records]
    umut = sum(umut_vals) / n
    print(f"{label}: n={n}, n_pass_scored={len(passed_scored)}, cMut={cmut:.2f}%, uMut={umut:.2f}%")
    return cmut, umut

print()
for seed in [42, 43]:
    compute(per_seed[seed], f"Seed {seed}")

print()
cmut_pooled, umut_pooled = compute(all_subset_recs, "Pooled (both seeds)")

# also report mutant/kill totals for transparency
total_mutants = sum(r["mutation_stats"]["total"] for r in all_subset_recs if r.get("mutation_stats"))
total_killed = sum(r["mutation_stats"]["killed"] for r in all_subset_recs if r.get("mutation_stats"))
n_with_mutants = sum(1 for r in all_subset_recs if r.get("mutation_stats") and r["mutation_stats"]["total"] > 0)
print(f"\nTotal mutants across pooled subset: {total_mutants}, killed: {total_killed}")
print(f"Records with total>0 mutants: {n_with_mutants} / {len(all_subset_recs)}")

with open(ROOT / "step4_evaluation" / "_pynguin_mutation_numbers.json", "w") as f:
    json.dump({
        "n_pooled": len(all_subset_recs),
        "cmut_pooled_pct": round(cmut_pooled, 2),
        "umut_pooled_pct": round(umut_pooled, 2),
        "total_mutants": total_mutants,
        "total_killed": total_killed,
        "n_with_mutants": n_with_mutants,
    }, f, indent=1)
