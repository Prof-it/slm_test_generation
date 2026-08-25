"""Runtime-instrumentation equivalence pilot.

Answers one question: does wrapping oracle sites with __record_oracle_execution__
(oracle_analysis.instrument_oracles) change what a suite does, compared to running
the same suite unmodified?

This is an ISOLATED, read-only-with-respect-to-production path. It reuses
evaluate_results.py's own harness-construction and execution helpers (imported,
not reimplemented) so the pilot's "original" run is byte-for-byte the same
methodology as production, then adds a second "instrumented" run for comparison.
It does not write to evaluation_results/, does not call evaluate_results.main(),
and never touches assertion_gate.py / gated_reanalysis.py / paper.tex.

Usage:
    python runtime_instrumentation_pilot.py \
        --predictions-dir downloaded_predictions/second_experiment/run_1 \
        --output-dir step4_evaluation/oracle_validation \
        --sample-size 50 --seed 20260822
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evaluate_results as er  # noqa: E402  (reused, not reimplemented, see module docstring)
from oracle_analysis import instrument_oracles  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Suite-level heuristic flags for the "pay particular attention to" categories the
# project owner named. Regex-based and intentionally coarse -- this only decides
# which rows get called out for manual attention in the report, it does not gate
# execution or change any outcome.
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


def _stratify_key(entry: dict, path: Path) -> tuple:
    tier = next((p.removeprefix("tier_") for p in path.parts if p.startswith("tier_")), "")
    pipeline = "two-step" if path.name.startswith("linecov2_") else "single-step"
    return (entry.get("dependency_level", ""), tier, pipeline)


def collect_suites(predictions_dir: Path) -> list[dict]:
    """One row per (prediction file, task) -- matching evaluate_results.py's own
    suite granularity, where all target-line tests for a task are combined into
    a single suite. This is coarser than the oracle-validation sampler's
    per-target generation_id."""
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
                    continue  # Pynguin suites use a different harness path; out of scope for this pilot
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


def stratified_sample(suites: list[dict], size: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for s in suites:
        groups[(s["dependency_level"], s["tier"], s["pipeline"])].append(s)
    for g in groups.values():
        rng.shuffle(g)
    selected: list[dict] = []
    keys = sorted(groups)
    while len(selected) < min(size, len(suites)):
        progressed = False
        for key in keys:
            if groups[key] and len(selected) < size:
                selected.append(groups[key].pop())
                progressed = True
        if not progressed:
            break
    rng.shuffle(selected)
    return selected


def _build_harness_source(suite: dict) -> tuple[str, str]:
    """Reproduce evaluate_results.py's exact non-Pynguin harness construction.
    Returns (full_solution, harness_source)."""
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


def _run_pytest(tmp_dir: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "test_generated.py", "-v"],
        cwd=tmp_dir, capture_output=True, text=True, timeout=timeout,
    )


def _run_coverage(tmp_dir: Path, timeout: int = 15) -> float:
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "--cov=under_test", "--cov-report=json:coverage.json",
             "test_generated.py"],
            cwd=tmp_dir, capture_output=True, timeout=timeout,
        )
        cov_path = tmp_dir / "coverage.json"
        if cov_path.exists():
            with open(cov_path) as f:
                return json.load(f)["totals"]["percent_covered"]
    except Exception:
        pass
    return 0.0


def _execute_variant(full_solution: str, harness_source: str, oracle_env_file: Path | None,
                      label: str) -> dict:
    """Runs one variant (original or instrumented) through the exact production
    execution path (subprocess pytest -v, then --cov if not a crash outcome) in
    its own isolated temp dir, exactly like evaluate_results.evaluate_single_test_worker."""
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"pilot_{label}_"))
    out: dict = {
        "status": er.EvaluationResult.NO_CODE, "coverage": 0.0,
        "n_collected": None, "n_passed": None, "n_skipped": None,
        "raw_exception_class": None, "all_skipped_vacuous_pass": False,
        "timed_out": False, "collection_error": False,
    }
    try:
        (tmp_dir / "under_test.py").write_text(full_solution, encoding="utf-8")
        (tmp_dir / "test_generated.py").write_text(harness_source, encoding="utf-8")

        env = None
        if oracle_env_file is not None:
            import os
            env = dict(os.environ)
            env["ORACLE_EXECUTION_FILE"] = str(oracle_env_file)

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_generated.py", "-v"],
                cwd=tmp_dir, capture_output=True, text=True, timeout=30, env=env,
            )
            out["status"] = er._determine_failure_status(proc)
            if out["status"] != er.EvaluationResult.PASS:
                out["raw_exception_class"] = er._extract_exception_class(proc)
            out["collection_error"] = "ERROR collecting" in proc.stdout or "INTERNALERROR" in (proc.stdout + proc.stderr)
            n_collected, n_passed, n_skipped = er._parse_pytest_counts(proc.stdout)
            out["n_collected"], out["n_passed"], out["n_skipped"] = n_collected, n_passed, n_skipped
            if out["status"] == er.EvaluationResult.PASS and n_collected and n_skipped and n_skipped >= n_collected:
                out["all_skipped_vacuous_pass"] = True
            out["_stdout_tail"] = proc.stdout[-1500:]
            out["_stderr_tail"] = proc.stderr[-1500:]
        except subprocess.TimeoutExpired:
            out["status"] = er.EvaluationResult.TIMEOUT
            out["timed_out"] = True

        if out["status"] not in (er.EvaluationResult.TIMEOUT, er.EvaluationResult.SYNTAX_ERROR,
                                  er.EvaluationResult.NO_CODE):
            out["coverage"] = _run_coverage(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return out


def _read_recorded_ids(env_file: Path) -> list[str]:
    if not env_file.exists():
        return []
    ids = []
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ids.append(json.loads(line)["oracle_id"])
        except Exception:
            pass
    return ids


def run_pilot(suites: list[dict]) -> list[dict]:
    rows = []
    for i, suite in enumerate(suites, 1):
        row: dict = {
            "pilot_index": i,
            "task_id": suite["task_id"],
            "model": suite["model"],
            "pipeline": suite["pipeline"],
            "tier": suite["tier"],
            "dependency_level": suite["dependency_level"],
            "source_file": suite["source_file"],
            "mock_fs_env_flag": bool(_MOCK_FS_ENV_RE.search(suite["raw_test_code"])),
        }
        print(f"[{i}/{len(suites)}] task {suite['task_id']} ({suite['model']}, {suite['pipeline']}, "
              f"tier {suite['tier']}, {suite['dependency_level']})", flush=True)

        try:
            full_solution, harness_source = _build_harness_source(suite)
        except Exception as e:
            row["build_error"] = f"{type(e).__name__}: {e}"
            rows.append(row)
            continue

        t0 = time.time()
        orig = _execute_variant(full_solution, harness_source, oracle_env_file=None, label="orig")
        row["orig_status"] = orig["status"]
        row["orig_n_collected"] = orig["n_collected"]
        row["orig_n_passed"] = orig["n_passed"]
        row["orig_n_skipped"] = orig["n_skipped"]
        row["orig_exception_class"] = orig["raw_exception_class"]
        row["orig_coverage"] = orig["coverage"]
        row["orig_vacuous_pass"] = orig["all_skipped_vacuous_pass"]
        row["orig_timed_out"] = orig["timed_out"]

        # Attempt instrumentation. A syntax-parse failure here is not itself a
        # divergence -- the original run would already be SYNTAX_ERROR/collection
        # failure in that case (both variants agree it's broken), so record and
        # skip instrumentation cleanly rather than crash the pilot.
        try:
            instrumented_source, sites = instrument_oracles(harness_source, sut_names={suite["func_name"]})
            row["instrument_error"] = None
            row["n_oracle_sites"] = len(sites)
        except SyntaxError as e:
            row["instrument_error"] = f"SyntaxError: {e}"
            row["n_oracle_sites"] = None
            instrumented_source = None

        if instrumented_source is not None:
            oracle_env_file = Path(tempfile.mkdtemp(prefix="pilot_oracle_env_")) / "executed.jsonl"
            instr = _execute_variant(full_solution, instrumented_source, oracle_env_file=oracle_env_file,
                                      label="instr")
            recorded_ids = _read_recorded_ids(oracle_env_file)
            shutil.rmtree(oracle_env_file.parent, ignore_errors=True)

            row["instr_status"] = instr["status"]
            row["instr_n_collected"] = instr["n_collected"]
            row["instr_n_passed"] = instr["n_passed"]
            row["instr_n_skipped"] = instr["n_skipped"]
            row["instr_exception_class"] = instr["raw_exception_class"]
            row["instr_coverage"] = instr["coverage"]
            row["instr_vacuous_pass"] = instr["all_skipped_vacuous_pass"]
            row["instr_timed_out"] = instr["timed_out"]
            row["n_oracle_executions_recorded"] = len(recorded_ids)
            row["n_unique_oracle_ids_recorded"] = len(set(recorded_ids))

            divergences = []
            if row["orig_status"] != row["instr_status"]:
                divergences.append(f"status {row['orig_status']!r} != {row['instr_status']!r}")
            if row["orig_n_collected"] != row["instr_n_collected"]:
                divergences.append(f"n_collected {row['orig_n_collected']!r} != {row['instr_n_collected']!r}")
            if row["orig_n_passed"] != row["instr_n_passed"]:
                divergences.append(f"n_passed {row['orig_n_passed']!r} != {row['instr_n_passed']!r}")
            if row["orig_n_skipped"] != row["instr_n_skipped"]:
                divergences.append(f"n_skipped {row['orig_n_skipped']!r} != {row['instr_n_skipped']!r}")
            if row["orig_exception_class"] != row["instr_exception_class"]:
                divergences.append(f"exception_class {row['orig_exception_class']!r} != {row['instr_exception_class']!r}")
            if abs((row["orig_coverage"] or 0.0) - (row["instr_coverage"] or 0.0)) > 0.01:
                divergences.append(f"coverage {row['orig_coverage']!r} != {row['instr_coverage']!r}")
            if row["orig_vacuous_pass"] != row["instr_vacuous_pass"]:
                divergences.append("all_skipped_vacuous_pass differs")

            row["equivalent"] = not divergences
            row["divergence_reason"] = "; ".join(divergences) if divergences else ""
            if row["mock_fs_env_flag"] and divergences:
                row["divergence_reason"] += " [SUITE MOCKS FS/ENV -- see report]"
        else:
            row["equivalent"] = None  # not applicable: could not build instrumented variant
            row["divergence_reason"] = "instrumentation not attempted (source failed to AST-parse)"

        row["wall_seconds"] = round(time.time() - t0, 2)
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260822)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.output_dir / "runtime_pilot_results.csv"
    if out_csv.exists():
        raise FileExistsError(f"Refusing to overwrite existing pilot results: {out_csv}")

    print("Collecting candidate suites...", flush=True)
    suites = collect_suites(args.predictions_dir)
    print(f"Found {len(suites)} candidate suites (non-Pynguin).", flush=True)

    sample = stratified_sample(suites, args.sample_size, args.seed)
    print(f"Sampled {len(sample)} suites for the pilot (seed={args.seed}).", flush=True)

    rows = run_pilot(sample)

    fieldnames = [k for k in rows[0].keys() if not k.startswith("_")] if rows else []
    # union of all keys across rows, in first-seen order, minus private fields
    seen = []
    for r in rows:
        for k in r:
            if not k.startswith("_") and k not in seen:
                seen.append(k)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=seen, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    n_applicable = sum(1 for r in rows if r["equivalent"] is not None)
    n_equivalent = sum(1 for r in rows if r["equivalent"] is True)
    print(f"\nWrote {len(rows)} rows to {out_csv}")
    print(f"Equivalence rate (of {n_applicable} suites where instrumentation was applicable): "
          f"{n_equivalent}/{n_applicable} = {n_equivalent / n_applicable:.1%}" if n_applicable else "n/a")


if __name__ == "__main__":
    main()
