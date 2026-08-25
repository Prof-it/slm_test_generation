"""
Small confirmation canary: compares Pynguin's default MUTATION_ANALYSIS
assertion-generation mode (used, unset, in every run so far) against SIMPLE
mode, on the same 5 audit tasks at 60s, to check whether switching modes for
fairness against the SLM baseline (which writes assertions blind to any
mutant set) meaningfully changes coverage/mutation-score outcomes -- i.e.
whether the choice is "free" (SIMPLE loses nothing) or a real tradeoff.

Run: python step3_modelling/pynguin_assertion_mode_check.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "step4_evaluation"))
from run_pynguin_v2 import load_tasks, prepare_importable_module  # noqa: E402

AUDIT_DIR = PROJECT_ROOT / "step4_evaluation" / "pynguin_assertion_mode_check"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

TASK_IDS = [229284, 28838, 619902, 889249, 363593]
MODES = ["MUTATION_ANALYSIS", "SIMPLE"]
SEED = 20260822
BUDGET = 60

OUTPUT_VARS = ",".join([
    "TargetModule", "SearchTime", "TotalTime", "AlgorithmIterations", "Goals",
    "FinalBranchCoverage", "FinalLineCoverage", "Assertions", "DeletedAssertions",
    "NumberOfCreatedMutants", "NumberOfKilledMutants", "MutationScore",
])


def run_one(task, mode):
    task_id = task["task_num"]
    raw_source = task["python_solution_full"]
    importable_source = prepare_importable_module(raw_source)

    work_dir = AUDIT_DIR / f"task{task_id}_{mode}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    (work_dir / "under_test.py").write_text(importable_source, encoding="utf-8")

    report_dir = work_dir / "pynguin-report"
    cmd = [
        "python", "-m", "pynguin",
        "--project-path", str(work_dir),
        "--output-path", str(work_dir),
        "--module-name", "under_test",
        "--algorithm", "DYNAMOSA",
        "--maximum-search-time", str(BUDGET),
        "--seed", str(SEED),
        "--assertion_generation", mode,
        "--report-dir", str(report_dir),
        "--statistics_backend", "CSV",
        "--output-variables", OUTPUT_VARS,
    ]
    os.environ["PYNGUIN_DANGER_AWARE"] = "true"
    try:
        proc = subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True,
                               timeout=BUDGET + 90)
    except subprocess.TimeoutExpired:
        return {"task_id": task_id, "mode": mode, "status": "TIMEOUT"}

    result = {"task_id": task_id, "mode": mode, "status": None}
    test_file = work_dir / "test_under_test.py"
    if test_file.exists():
        code = test_file.read_text(encoding="utf-8")
        result["status"] = "DONE"
        result["num_assert_statements"] = code.count("\n    assert ")
        result["test_char_len"] = len(code)
    else:
        result["status"] = "NO_CODE"

    stats_csv = report_dir / "statistics.csv"
    if stats_csv.exists():
        import csv
        with open(stats_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            result["stats"] = rows[0]

    shutil.rmtree(work_dir, ignore_errors=True)
    return result


def main():
    all_tasks = {t["task_num"]: t for t in load_tasks()}
    results = []
    for task_id in TASK_IDS:
        task = all_tasks[task_id]
        for mode in MODES:
            print(f"Running task {task_id} @ mode {mode} ...", flush=True)
            r = run_one(task, mode)
            results.append(r)
            print(f"  -> {r.get('status')}, num_asserts={r.get('num_assert_statements')}, stats={r.get('stats')}")

    out_path = AUDIT_DIR / "results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
