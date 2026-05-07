"""
Mutation Testing Subset Generator

Selects a stratified random 20% sample per difficulty tier (Easy/Medium/Hard) for
computationally expensive mutation testing. Outputs a JSON file with the selected task IDs.

Usage:
    python create_mutation_subset.py
    python create_mutation_subset.py --data TestEval/data/realworld-py.jsonl --output step4_evaluation/mutation_subset_ids_realworld.json
"""

import json
import random
import argparse
import pandas as pd
from pathlib import Path

# Config
SEED = 42
SAMPLE_RATE_DEFAULT = 0.20

def create_subset(data_path, output_path, sample_rate=SAMPLE_RATE_DEFAULT):
    """Stratified sample by difficulty tier and export selected task IDs."""
    random.seed(SEED)

    if not data_path.exists():
        print(f"Error: Could not find data at {data_path}")
        return

    with open(data_path, 'r') as f:
        data = [json.loads(line) for line in f]

    df = pd.DataFrame(data)

    df['difficulty'] = pd.to_numeric(df['difficulty'], errors='coerce').fillna(-1).astype(int)
    df['task_num'] = df['task_num'].astype(str)

    subset_ids = []
    print(f"Dataset: {data_path}")
    print(f"Total Population: {len(df)}")
    print(f"Distribution: {df['difficulty'].value_counts().to_dict()}")

    # 1: Easy, 2: Medium, 3: Hard
    for diff in [1, 2, 3]:
        strata = df[df['difficulty'] == diff]
        total_in_strata = len(strata)

        # Calculate 20%, ensuring at least 1 if the strata isn't empty
        n_sample = int(total_in_strata * sample_rate)
        if n_sample == 0 and total_in_strata > 0:
            n_sample = 1

        sampled = strata.sample(n=n_sample, random_state=SEED)
        subset_ids.extend(sampled['task_num'].tolist())

        print(f"  Difficulty {diff}: Found {total_in_strata} -> Selected {len(sampled)}")

    # Save
    with open(output_path, 'w') as f:
        json.dump(subset_ids, f)

    print(f"\nSaved {len(subset_ids)} task IDs to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mutation Testing Subset Generator")
    parser.add_argument("--data", type=str, default="TestEval/data/leetcode-py.jsonl",
                        help="Path to the JSONL dataset")
    parser.add_argument("--output", type=str, default="step4_evaluation/mutation_subset_ids.json",
                        help="Path for the output JSON file")
    parser.add_argument("--sample-rate", type=float, default=SAMPLE_RATE_DEFAULT,
                        help="Fraction of tasks to sample per difficulty tier (default: 0.20)")
    args = parser.parse_args()
    create_subset(Path(args.data), Path(args.output), args.sample_rate)