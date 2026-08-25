"""
Builds scratch, filtered copies of all 30 second-experiment prediction files
containing ONLY the 14 repaired tasks (13 NameError extraction defects + the
one fix_relative_imports harness-bug task, 916895), for re-scoring under the
now-corrected reference modules / harness.

Does NOT modify downloaded_predictions/ (the frozen, original SLM generation
record) at all -- reads it, filters+patches in memory, writes to a new
scratch directory. The 13 NameError tasks get python_solution_full replaced
with the same repaired value already patched into TestEval/data/*.jsonl
(step2_data_preperation/repair_extraction_defects_2026.py); task 916895 is
copied unchanged (its python_solution_full was always correct -- only the
evaluation harness's fix_relative_imports had a bug, now fixed at the
function level).

Usage:
    python step2_data_preperation/build_repair_rescoring_subset.py
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRED_GLOB = PROJECT_ROOT / "downloaded_predictions" / "second_experiment" / "run_1"
OUT_DIR = PROJECT_ROOT / "step4_evaluation" / "_extraction_repair_rescoring_predictions"

REPAIRED_TASK_IDS = {
    "363593", "896053", "25953", "162266", "51723", "119665", "872607",
    "718898", "990106", "432562", "234352", "235598", "577470",  # NameError repairs
    "916895",  # fix_relative_imports harness-bug fix, no dataset patch needed
}

REPAIR_AUDIT = json.loads(
    (PROJECT_ROOT / "step4_evaluation" / "oracle_validation" / "EXTRACTION_REPAIR_AUDIT.json").read_text()
)
NAME_ERROR_TASK_IDS = {a["task_id"] for a in REPAIR_AUDIT if a["importable"]}


def main():
    # Pull the repaired python_solution_full straight from the now-patched
    # dataset file (single source of truth, avoids duplicating the snippets).
    repaired_full = {}
    with open(PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            tid = str(row.get("task_num"))
            if tid in NAME_ERROR_TASK_IDS:
                repaired_full[tid] = row["python_solution_full"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_files = 0
    n_rows_total = 0
    for src in sorted(PRED_GLOB.rglob("*.jsonl")):
        rel = src.relative_to(PRED_GLOB)
        dst = OUT_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        rows_out = []
        with open(src, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                tid = str(row.get("task_num"))
                if tid not in REPAIRED_TASK_IDS:
                    continue
                if tid in repaired_full:
                    row["python_solution_full"] = repaired_full[tid]
                rows_out.append(row)
        with open(dst, "w", encoding="utf-8") as f:
            for row in rows_out:
                f.write(json.dumps(row) + "\n")
        n_files += 1
        n_rows_total += len(rows_out)

    print(f"Wrote {n_files} filtered prediction files ({n_rows_total} rows total, "
          f"expected {n_files * len(REPAIRED_TASK_IDS)}) to {OUT_DIR}")


if __name__ == "__main__":
    main()
