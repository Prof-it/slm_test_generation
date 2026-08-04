"""
Refreshes dataset-derived fields embedded in already-generated prediction
files (python_solution_full, python_solution, context_card, dependency_level,
leaked, etc.) from the CURRENT dataset JSONLs, without touching the model's
actual output fields (tests, performance_batch, model, temperature).

Why this is needed: predictions were saved with a full copy of that task's
dataset row at inference time. Repairing TestEval/data/realworld-py-v2*.jsonl
(e.g. the duplicate-'self' fix) does NOT retroactively update predictions
already on disk -- evaluate_results.py reads whatever's embedded in the
prediction file, so without this refresh the re-evaluation would silently
keep testing against the old, broken python_solution_full.

Usage:
    python step4_evaluation/refresh_prediction_dataset_fields.py --dry-run
    python step4_evaluation/refresh_prediction_dataset_fields.py
"""

import argparse
import glob
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Fields that come from the dataset construction pipeline, not from the model.
# Only these get overwritten; everything else in each prediction record (the
# model's actual generated output and its metadata) is left untouched.
DATASET_FIELDS = [
    "python_solution_full", "python_solution", "context_card", "signature",
    "docstring", "focal_function", "dependency_level", "leaked", "cyclomatic_complexity",
    "loc", "func_name", "target_lines", "source_file", "commit_sha", "commit_date",
    "license", "domain", "has_failtopass", "description",
]

TIER_DATASET_FILES = {
    "A": PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2-tier-A.jsonl",
    "B": PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2-tier-B.jsonl",
    "C": PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2-tier-C.jsonl",
}

PREDICTIONS_GLOB = str(PROJECT_ROOT / "downloaded_predictions" / "second_experiment" / "run_1" / "tier_*" / "*.jsonl")


def load_dataset_by_task(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        out[str(rec["task_num"])] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tier_data = {tier: load_dataset_by_task(path) for tier, path in TIER_DATASET_FILES.items()}

    files = sorted(glob.glob(PREDICTIONS_GLOB))
    if not files:
        raise RuntimeError(f"No prediction files found matching {PREDICTIONS_GLOB}")

    total_patched = 0
    for f in files:
        fpath = Path(f)
        tier = fpath.parent.name.replace("tier_", "")
        if tier not in tier_data:
            print(f"  !! skipping {f}: unknown tier {tier!r}")
            continue
        ds_by_task = tier_data[tier]

        lines = fpath.read_text(encoding="utf-8").splitlines()
        out_lines = []
        n_patched_this_file = 0
        n_missing = 0
        for line in lines:
            if not line.strip():
                out_lines.append(line)
                continue
            entry = json.loads(line)
            tn = str(entry.get("task_num"))
            ds_row = ds_by_task.get(tn)
            if ds_row is None:
                n_missing += 1
                out_lines.append(line)
                continue
            changed = False
            for field in DATASET_FIELDS:
                if field in ds_row and entry.get(field) != ds_row[field]:
                    entry[field] = ds_row[field]
                    changed = True
            if changed:
                n_patched_this_file += 1
            out_lines.append(json.dumps(entry))

        total_patched += n_patched_this_file
        msg = f"{fpath.relative_to(PROJECT_ROOT)}: {n_patched_this_file} records refreshed"
        if n_missing:
            msg += f", {n_missing} task_nums not found in tier {tier} dataset"
        print(msg)

        if not args.dry_run:
            fpath.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print(f"\nTotal records refreshed: {total_patched}" + (" (dry-run, nothing written)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
