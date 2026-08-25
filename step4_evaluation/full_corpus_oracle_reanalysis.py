"""Full-corpus isolated oracle re-evaluation pass.

Populates runtime-execution fields and computes the three corrected Pass@1
variants (execution / non-trivial / strong) using the frozen v4 classifier
and the validated instrumentation
(step4_evaluation/oracle_validation/RUNTIME_INSTRUMENTATION_PILOT_REPORT.md:
100/100 equivalence between original and instrumented execution, after 3
narrow fixes to _RECORDER_SOURCE). This module does not touch
evaluate_results.py, assertion_gate.py, gated_reanalysis.py, paper.tex, or
any legacy result file, and does not modify oracle_analysis.py's
classification logic.

Because the equivalence pilot already established, on real corpus suites,
that instrumented and original execution produce identical
status/pass-fail/exception-class outcomes (100/100 after fixes), this pass
runs ONLY the instrumented variant per suite (not both, unlike the pilot),
to make a corpus-scale run tractable. Coverage is not measured here (not
needed for oracle-execution classification or the three Pass@1 variants;
coverage/mutation are separate, already-existing pipelines that this pass
does not duplicate).

Usage:
    python full_corpus_oracle_reanalysis.py \
        --predictions-dir downloaded_predictions/second_experiment/run_1 \
        --experiment-tag experiment_b \
        --output-dir step4_evaluation/oracle_validation \
        --workers 10
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evaluate_results as er  # noqa: E402  (reused, not reimplemented)
from oracle_analysis import (  # noqa: E402
    OracleClass, classify_oracles, gate_outcomes, instrument_oracles, suite_category,
)

_MOCK_FS_ENV_RE = re.compile(
    r"""patch\(\s*["']builtins\.open["']
      | patch\(\s*["']open["']
      | patch\(\s*["']os\.environ["']
      | patch\.dict\(\s*os\.environ
      | monkeypatch\.setenv
      | monkeypatch\.setattr\(\s*os
      | monkeypatch\.setattr\(\s*["']os\.
      | mock_open\(
      | patch\(\s*["'][\w.]*\.open["']
      | os\.environ\[
      | os\.getenv\(
    """,
    re.VERBOSE,
)


def collect_suites(predictions_dir: Path) -> list[dict]:
    """Same suite granularity as evaluate_results.py: one row per (prediction
    file, task), all target-line tests combined into a single suite."""
    suites: list[dict] = []
    for path in sorted(predictions_dir.rglob("*.jsonl")):
        if path.name == "pynguin_results.jsonl":
            continue
        with path.open(encoding="utf-8", errors="ignore") as stream:
            for raw_line in stream:
                entry = er.clean_jsonl_line(raw_line)
                if not entry:
                    continue
                solution = (entry.get("python_solution_full") or entry.get("code")
                            or entry.get("python_solution") or "")
                if not solution:
                    continue
                func_name = entry.get("func_name", "solution")
                tests = entry.get("tests", {})
                test_list = list(tests.items()) if isinstance(tests, dict) else (
                    [(str(i), t) for i, t in enumerate(tests)] if isinstance(tests, list) else [])
                if not test_list:
                    continue
                combined = er._combine_tests_for_task(test_list, func_name)
                if not combined or not combined.strip():
                    continue
                if "test_case_0" in combined or "pymosa" in combined.lower():
                    continue  # Pynguin suites use a different harness path; out of scope
                suites.append({
                    "task_id": str(entry.get("task_num")),
                    "func_name": func_name,
                    "solution_code": solution,
                    "raw_test_code": combined,
                    "model": entry.get("model", path.stem),
                    "pipeline": "two-step" if path.name.startswith("linecov2_") else "single-step",
                    "tier": entry.get("tier", ""),
                    "dependency_level": entry.get("dependency_level", ""),
                    "source_file": str(path),
                })
    return suites


def _build_harness_source(suite: dict) -> tuple[str, str]:
    """Reproduce evaluate_results.py's exact non-Pynguin harness construction."""
    clean_test = er.strip_markdown(suite["raw_test_code"])
    clean_test = "\n".join(
        line for line in clean_test.splitlines()
        if not line.strip().startswith("from __future__")
    )
    clean_test = er._standardize_func_name(clean_test, f"test_{suite['func_name']}")

    solution_lines = suite["solution_code"].splitlines()
    future_lines = [l for l in solution_lines if l.strip().startswith("from __future__")]
    other_lines = [l for l in solution_lines if not l.strip().startswith("from __future__")]
    future_block = "\n".join(future_lines) + "\n" if future_lines else ""
    remaining_code = "\n".join(other_lines)
    remaining_code = er.fix_relative_imports(remaining_code)
    remaining_code = er.fix_absolute_imports(remaining_code)
    full_solution = future_block + er.COMMON_IMPORTS + "\n" + remaining_code

    harness = er.HARNESS_TEMPLATE.format(test_code=clean_test)
    return full_solution, harness


def _read_recorded_ids(env_file: Path) -> set[str]:
    if not env_file.exists():
        return set()
    ids = set()
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ids.add(json.loads(line)["oracle_id"])
        except Exception:
            pass
    return ids


def process_one_suite(suite: dict) -> dict:
    """Runs in a worker process. Builds harness, instruments, executes once
    (instrumented variant only -- see module docstring), classifies."""
    row: dict = {
        "task_id": suite["task_id"],
        "model": suite["model"],
        "pipeline": suite["pipeline"],
        "tier": suite["tier"],
        "dependency_level": suite["dependency_level"],
        "source_file": suite["source_file"],
        "mock_fs_env_flag": bool(_MOCK_FS_ENV_RE.search(suite["raw_test_code"])),
    }
    tmp_dir = None
    oracle_env_dir = None
    try:
        try:
            full_solution, harness_source = _build_harness_source(suite)
        except Exception as e:
            row["status"] = er.EvaluationResult.NO_CODE
            row["build_error"] = f"{type(e).__name__}: {e}"
            return row

        try:
            instrumented_source, sites = instrument_oracles(harness_source, sut_names={suite["func_name"]})
        except SyntaxError as e:
            row["status"] = er.EvaluationResult.SYNTAX_ERROR
            row["instrument_error"] = f"SyntaxError: {e}"
            row["n_oracle_sites"] = 0
            row["suite_passed"] = False
            row["suite_category"] = "no-executed-oracle"
            row["execution_success"] = False
            row["executed_nontrivial_gate"] = False
            row["executed_strong_gate"] = False
            return row

        row["n_oracle_sites"] = len(sites)
        row["n_trivial_sites"] = sum(1 for s in sites if s.oracle_class == OracleClass.TRIVIAL)
        row["n_weak_sites"] = sum(1 for s in sites if s.oracle_class == OracleClass.WEAK)
        row["n_strong_sites"] = sum(1 for s in sites if s.oracle_class == OracleClass.STRONG)
        row["n_unknown_sites"] = sum(1 for s in sites if s.oracle_class == OracleClass.UNKNOWN)

        tmp_dir = Path(tempfile.mkdtemp(prefix="fcra_"))
        oracle_env_dir = Path(tempfile.mkdtemp(prefix="fcra_env_"))
        oracle_env_file = oracle_env_dir / "executed.jsonl"

        (tmp_dir / "under_test.py").write_text(full_solution, encoding="utf-8")
        (tmp_dir / "test_generated.py").write_text(instrumented_source, encoding="utf-8")

        import os
        env = dict(os.environ)
        env["ORACLE_EXECUTION_FILE"] = str(oracle_env_file)

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_generated.py", "-v"],
                cwd=tmp_dir, capture_output=True, text=True, timeout=30, env=env,
            )
            status = er._determine_failure_status(proc)
            row["status"] = status
            if status != er.EvaluationResult.PASS:
                row["raw_exception_class"] = er._extract_exception_class(proc)
            n_collected, n_passed, n_skipped = er._parse_pytest_counts(proc.stdout)
            row["n_collected"], row["n_passed"], row["n_skipped"] = n_collected, n_passed, n_skipped
            row["timed_out"] = False
        except subprocess.TimeoutExpired:
            row["status"] = er.EvaluationResult.TIMEOUT
            row["timed_out"] = True

        suite_passed = row.get("status") == er.EvaluationResult.PASS
        row["suite_passed"] = suite_passed

        executed_ids = _read_recorded_ids(oracle_env_file)
        row["n_oracle_executions_recorded"] = len(executed_ids)
        row["suite_category"] = suite_category(sites, executed_ids)
        gates = gate_outcomes(suite_passed, sites, executed_ids)
        row["execution_success"] = gates["execution_success"]
        row["executed_nontrivial_gate"] = gates["executed_nontrivial_gate"]
        row["executed_strong_gate"] = gates["executed_strong_gate"]
        return row
    except Exception as e:
        row["status"] = "WORKER_ERROR"
        row["build_error"] = f"{type(e).__name__}: {e}"
        row.setdefault("suite_passed", False)
        row.setdefault("suite_category", "no-executed-oracle")
        row.setdefault("execution_success", False)
        row.setdefault("executed_nontrivial_gate", False)
        row.setdefault("executed_strong_gate", False)
        return row
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        if oracle_env_dir is not None:
            shutil.rmtree(oracle_env_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions-dir", type=Path, required=True)
    parser.add_argument("--experiment-tag", type=str, required=True,
                         help="Free-text tag (e.g. experiment_a, experiment_b) stamped into output filenames.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on suite count, for calibration runs.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.output_dir / f"full_corpus_reanalysis_results_{args.experiment_tag}.csv"
    if out_csv.exists():
        raise FileExistsError(f"Refusing to overwrite existing results: {out_csv}")

    print("Collecting candidate suites...", flush=True)
    suites = collect_suites(args.predictions_dir)
    print(f"Found {len(suites)} candidate suites (non-Pynguin).", flush=True)
    if args.limit:
        suites = suites[: args.limit]
        print(f"Limited to {len(suites)} suites for this run.", flush=True)

    t_start = time.time()
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one_suite, s): i for i, s in enumerate(suites)}
        done = 0
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            done += 1
            if done % 200 == 0 or done == len(suites):
                elapsed = time.time() - t_start
                print(f"[{done}/{len(suites)}] elapsed={elapsed:.0f}s "
                      f"rate={done/elapsed:.2f}/s", flush=True)

    elapsed = time.time() - t_start
    print(f"\nProcessed {len(rows)} suites in {elapsed:.1f}s ({len(rows)/elapsed:.2f}/s)", flush=True)

    seen: list[str] = []
    for r in rows:
        for k in r:
            if k not in seen:
                seen.append(k)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=seen, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_csv}")

    # Aggregate summary per model x pipeline
    cell_key = lambda r: (r["model"], r["pipeline"])  # noqa: E731
    cells: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        cells[cell_key(r)].append(r)

    summary_csv = args.output_dir / f"full_corpus_reanalysis_summary_{args.experiment_tag}.csv"
    if summary_csv.exists():
        raise FileExistsError(f"Refusing to overwrite existing summary: {summary_csv}")
    with summary_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "model", "pipeline", "n_suites",
            "execution_pass1_pct", "nontrivial_pass1_pct", "strong_pass1_pct",
            "no_executed_oracle", "trivial_only", "weak_only", "unknown_only", "strong_present",
        ])
        for (model, pipeline), group in sorted(cells.items()):
            n = len(group)
            exec_pct = 100 * sum(1 for r in group if r.get("execution_success")) / n
            nt_pct = 100 * sum(1 for r in group if r.get("executed_nontrivial_gate")) / n
            strong_pct = 100 * sum(1 for r in group if r.get("executed_strong_gate")) / n
            cat_counts = Counter(r.get("suite_category", "no-executed-oracle") for r in group)
            writer.writerow([
                model, pipeline, n,
                f"{exec_pct:.2f}", f"{nt_pct:.2f}", f"{strong_pct:.2f}",
                cat_counts.get("no-executed-oracle", 0), cat_counts.get("trivial-only", 0),
                cat_counts.get("weak-only", 0), cat_counts.get("unknown-only", 0),
                cat_counts.get("strong-present", 0),
            ])
    print(f"Wrote per-cell summary to {summary_csv}")

    overall_cat = Counter(r.get("suite_category", "no-executed-oracle") for r in rows)
    n = len(rows)
    print("\nOverall suite-category distribution:")
    for cat, count in overall_cat.most_common():
        print(f"  {cat}: {count} ({100*count/n:.1f}%)")
    exec_pct = 100 * sum(1 for r in rows if r.get("execution_success")) / n
    nt_pct = 100 * sum(1 for r in rows if r.get("executed_nontrivial_gate")) / n
    strong_pct = 100 * sum(1 for r in rows if r.get("executed_strong_gate")) / n
    print(f"\nOverall Execution Pass@1:   {exec_pct:.2f}%")
    print(f"Overall Non-trivial Pass@1: {nt_pct:.2f}%")
    print(f"Overall Strong Pass@1:      {strong_pct:.2f}%")


if __name__ == "__main__":
    main()
