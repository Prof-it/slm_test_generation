"""
Mutation Testing Subset Generator

Selects a stratified sample using Cochran's formula for finite populations.
Cochran: n = z^2 * p * q / e^2, with finite-population correction n' = n / (1 + (n-1)/N).
For z=1.96 (95% CI), p=0.5 (worst case), e=0.10 (10% margin), N=210 -> n=67.

Distributes the target n proportionally across difficulty tiers (Easy/Medium/Hard).

Usage:
    python create_mutation_subset.py
    python create_mutation_subset.py --data TestEval/data/realworld-py.jsonl --output step4_evaluation/mutation_subset_ids_realworld.json
"""

import json
import math
import random
import argparse
import pandas as pd
from pathlib import Path

SEED = 42
# Cochran formula constants (95% CI, p=0.5 worst case, e=0.10)
_Z, _P, _E = 1.96, 0.5, 0.10


def cochran_n(population_size: int, z: float = _Z, p: float = _P, e: float = _E) -> int:
    """Return minimum sample size for finite population using Cochran's formula."""
    n0 = (z ** 2 * p * (1 - p)) / (e ** 2)
    n = n0 / (1 + (n0 - 1) / population_size)
    return math.ceil(n)


def create_subset(data_path, output_path, cochran_target: int = 0):
    """Stratified sample by difficulty tier using Cochran's formula and export selected task IDs."""
    random.seed(SEED)

    if not data_path.exists():
        print(f"Error: Could not find data at {data_path}")
        return

    with open(data_path, 'r') as f:
        data = [json.loads(line) for line in f]

    df = pd.DataFrame(data)
    df['difficulty'] = pd.to_numeric(df['difficulty'], errors='coerce').fillna(-1).astype(int)
    df['task_num'] = df['task_num'].astype(str)

    total_population = len(df)
    target_n = cochran_target if cochran_target > 0 else cochran_n(total_population)

    print(f"Dataset: {data_path}")
    print(f"Total Population N: {total_population}")
    print(f"Cochran target n (95% CI, e=0.10): {cochran_n(total_population)} -> using {target_n}")
    print(f"Distribution: {df['difficulty'].value_counts().to_dict()}")

    subset_ids = []
    allocated = 0

    tiers = [1, 2, 3]  # Easy, Medium, Hard
    strata_sizes = {d: len(df[df['difficulty'] == d]) for d in tiers}
    total_stratified = sum(strata_sizes.values())

    for i, diff in enumerate(tiers):
        strata = df[df['difficulty'] == diff]
        total_in_strata = strata_sizes[diff]
        if total_in_strata == 0:
            continue

        # Proportional allocation; last tier absorbs rounding remainder
        if i < len(tiers) - 1:
            n_sample = round(target_n * total_in_strata / total_stratified)
        else:
            n_sample = target_n - allocated

        n_sample = max(1, min(n_sample, total_in_strata))
        sampled = strata.sample(n=n_sample, random_state=SEED)
        subset_ids.extend(sampled['task_num'].tolist())
        allocated += n_sample

        print(f"  Difficulty {diff}: Population {total_in_strata} -> Selected {n_sample}")

    with open(output_path, 'w') as f:
        json.dump(subset_ids, f)

    print(f"\nSaved {len(subset_ids)} task IDs to {output_path}")
    print(f"Sample covers {len(subset_ids)/total_population*100:.1f}% of population "
          f"(Cochran: 95% CI, e=0.10).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mutation Testing Subset Generator (Cochran formula)")
    parser.add_argument("--data", type=str, default="TestEval/data/leetcode-py.jsonl",
                        help="Path to the JSONL dataset")
    parser.add_argument("--output", type=str, default="step4_evaluation/mutation_subset_ids.json",
                        help="Path for the output JSON file")
    parser.add_argument("--cochran-n", type=int, default=0,
                        help="Override Cochran target n (0 = auto-compute from population)")
    args = parser.parse_args()
    create_subset(Path(args.data), Path(args.output), cochran_target=args.cochran_n)