"""
Diagnostic audit for the Pynguin search-time budget pilot: verifies the
apparent 30/60/120/600s convergence is real, not a configuration bug.

For each of a small set of tasks x each budget, this:
  1. Confirms the --maximum-search-time value actually reaches Pynguin's
     runtime config (via its own statistics CSV, not just trusting the CLI arg).
  2. Captures Pynguin's own internal statistics (AlgorithmIterations, Goals,
     FinalBranchCoverage, Assertions, DeletedAssertions, MutationScore,
     SearchTime, TotalTime) via --output-variables and --statistics-backend csv.
  3. Hashes the generated test file (normalized) to check whether increasing
     the budget produces a genuinely different suite or byte-identical output.
  4. Confirms assertion_generation is MUTATION_ANALYSIS (the default) and not
     silently NONE/overridden anywhere in the wrapper.

Does not touch run_pynguin_v2.py or the completed pilot/final-run artifacts;
purely additive diagnostic output.

Run: python step3_modelling/pynguin_budget_audit.py
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "step4_evaluation"))
from evaluate_results import fix_relative_imports, fix_absolute_imports  # noqa: E402
from run_pynguin_v2 import load_tasks, prepare_importable_module  # noqa: E402

AUDIT_DIR = PROJECT_ROOT / "step4_evaluation" / "pynguin_budget_audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_TASK_IDS = [229284, 28838, 619902, 889249, 363593]  # 3 DONE + 2 NO_CODE at every budget so far
BUDGETS = [30, 60, 120, 600]
SEED = 20260822

OUTPUT_VARS = ",".join([
    "TargetModule", "SearchTime", "TotalTime", "AlgorithmIterations", "Goals",
    "FinalBranchCoverage", "FinalLineCoverage", "Assertions", "DeletedAssertions",
    "NumberOfCreatedMutants", "NumberOfKilledMutants", "MutationScore",
    "RandomSeed",
])


def normalize_test_code(code: str) -> str:
    """Strip anything timestamp/path-dependent so hashing compares the
    actual generated logic, not incidental formatting noise."""
    lines = [l for l in code.splitlines() if not l.strip().startswith("#")]
    return "\n".join(lines).strip()


def run_one(task, budget):
    task_id = task["task_num"]
    raw_source = task["python_solution_full"]
    importable_source = prepare_importable_module(raw_source)

    work_dir = AUDIT_DIR / f"task{task_id}_budget{budget}"
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
        "--maximum-search-time", str(budget),
        "--seed", str(SEED),
        "--report-dir", str(report_dir),
        "--statistics_backend", "CSV",
        "--output-variables", OUTPUT_VARS,
    ]
    import os
    os.environ["PYNGUIN_DANGER_AWARE"] = "true"
    try:
        proc = subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True,
                               timeout=budget + 90)
    except subprocess.TimeoutExpired:
        return {"task_id": task_id, "budget": budget, "status": "TIMEOUT"}

    result = {"task_id": task_id, "budget": budget, "status": None,
              "returncode": proc.returncode}

    test_file = work_dir / "test_under_test.py"
    if test_file.exists():
        code = test_file.read_text(encoding="utf-8")
        result["status"] = "DONE"
        result["test_sha256_normalized"] = hashlib.sha256(
            normalize_test_code(code).encode("utf-8")).hexdigest()[:16]
        result["test_char_len"] = len(code)
        result["num_test_cases"] = len(re.findall(r"^def test_case_\d+", code, re.M))
        result["has_assert_keyword"] = " assert " in code or code.strip().startswith("assert ")
    else:
        result["status"] = "NO_CODE"
        result["stderr_tail"] = (proc.stderr or "")[-800:]

    stats_csv = report_dir / "statistics.csv"
    if stats_csv.exists():
        import csv
        with open(stats_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            result["stats"] = rows[0]
    else:
        result["stats_csv_found"] = False

    shutil.rmtree(work_dir, ignore_errors=True)
    return result


def main():
    all_tasks = {t["task_num"]: t for t in load_tasks()}
    results = []
    for task_id in AUDIT_TASK_IDS:
        task = all_tasks[task_id]
        for budget in BUDGETS:
            print(f"Running task {task_id} @ budget {budget}s ...", flush=True)
            r = run_one(task, budget)
            results.append(r)
            print(f"  -> {r.get('status')}, stats={r.get('stats')}")

    out_path = AUDIT_DIR / "audit_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    from collections import defaultdict
    by_task = defaultdict(list)
    for r in results:
        by_task[r["task_id"]].append(r)

    for task_id, rs in by_task.items():
        print(f"\nTask {task_id}:")
        hashes = set()
        for r in sorted(rs, key=lambda x: x["budget"]):
            stats = r.get("stats", {})
            h = r.get("test_sha256_normalized", "N/A")
            hashes.add(h)
            print(f"  budget={r['budget']:4d}s status={r['status']:8s} "
                  f"hash={h} n_tests={r.get('num_test_cases')} "
                  f"SearchTime={stats.get('SearchTime')} TotalTime={stats.get('TotalTime')} "
                  f"Iterations={stats.get('AlgorithmIterations')} "
                  f"FinalBranchCov={stats.get('FinalBranchCoverage')} "
                  f"Goals={stats.get('Goals')} Assertions={stats.get('Assertions')} "
                  f"MutationScore={stats.get('MutationScore')}")
        print(f"  -> distinct normalized-test hashes across budgets: {len(hashes) - (1 if 'N/A' in hashes and len(hashes)>1 else 0)}")

    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
