"""
Pynguin baseline runner for the v2 dataset (TestContextBench-Py, 300 tasks).

Rewritten from the old step3_modelling/run_real_world_experiments_pynguin.py
(preserved untouched), which targeted the v1 dataset and its own hand-maintained
MODULE_PATH_MAP import-rewriting hack. That approach doesn't generalize to v2's
300 tasks pulled from ~50+ repositories.

Instead this reuses evaluate_results.py's own fix_relative_imports /
fix_absolute_imports (imported, not reimplemented) to prepare an importable
`under_test.py` module for Pynguin to instrument -- the exact same import-fixing
logic the LLM evaluation harness applies at test-execution time. This keeps
Pynguin and the LLM pipelines on a genuinely common evaluator: evaluate_results.py
already has first-class Pynguin support (detects "test_case_0"/"pymosa" in
generated test code, tracks xfail prevalence via has_xfail_tests/num_xfail_tests,
preserves markers) -- see evaluate_results.py's `is_pynguin` branch. This script
only needs to produce a predictions-shaped .jsonl; no custom evaluation logic.

One nuance: the module fed to Pynguin for *generation* must already import
cleanly (Pynguin executes it to build call graphs), so this script applies
fix_relative_imports/fix_absolute_imports itself before writing under_test.py
for Pynguin. But the *predictions file* written out stores the ORIGINAL,
unfixed python_solution_full (matching what real LLM prediction files contain),
so evaluate_results.py applies the identical fix step at evaluation time for
both Pynguin and LLM suites -- apples to apples.

Run (pilot):
    python step3_modelling/run_pynguin_v2.py --pilot 20 --search-time 60 --seed 20260822
Run (final, after pilot review):
    python step3_modelling/run_pynguin_v2.py --search-time <chosen> --seeds <n> --base-seed 42
"""
import argparse
import json
import logging
import os
import signal
import psutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "step4_evaluation"))
from evaluate_results import fix_relative_imports, fix_absolute_imports  # noqa: E402


def _run_with_psutil_killtree(cmd, cwd, timeout):
    """Like evaluate_results.py's _run_with_killtree, but walks the actual OS
    process tree via psutil instead of relying on process-group membership.

    _run_with_killtree's os.killpg() approach failed against Pynguin
    specifically: Pynguin's own internal `multiprocess`-based worker isolation
    appears to put its forked worker into a distinct session/process group
    (likely for its own crash-containment purposes), so killpg(getpgid(direct
    child)) never reaches it -- observed twice in production as a 3+ hour
    stall where the direct child sat mostly idle (~1s accumulated CPU over
    hours) while a grandchild kept ~80-100% CPU with no way to signal it via
    the process-group path. Walking psutil's parent/child PID tree (which
    reflects the OS's real process ancestry, independent of which process
    group/session a descendant later joined) reaches it directly.
    """
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            parent = psutil.Process(proc.pid)
            descendants = parent.children(recursive=True)
            for child in descendants:
                try:
                    child.send_signal(signal.SIGKILL)
                except psutil.NoSuchProcess:
                    pass
        except psutil.NoSuchProcess:
            pass
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        raise

# One representative prediction file has python_solution_full/target_lines/func_name
# for all 300 v2 tasks -- these fields are identical across every model/pipeline/tier
# for a given task_num, since they describe the ground-truth reference module, not
# the LLM's generation.
SOURCE_PREDICTIONS_FILE = (
    PROJECT_ROOT / "downloaded_predictions" / "second_experiment" / "run_1"
    / "tier_A" / "linecov_Qwen3.5-4B_temp_0.0.jsonl"
)

ALGORITHM = "DYNAMOSA"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def load_tasks():
    tasks = []
    with open(SOURCE_PREDICTIONS_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            tasks.append({
                "task_num": r["task_num"],
                "task_title": r.get("task_title", ""),
                "func_name": r.get("func_name", "solution"),
                "python_solution_full": r["python_solution_full"],
                "target_lines": r.get("target_lines", []),
            })
    return tasks


def prepare_importable_module(raw_source: str) -> str:
    """Same transform evaluate_results.py applies before writing under_test.py:
    separate __future__ imports, then fix relative + absolute imports."""
    lines = raw_source.splitlines()
    future_lines = [l for l in lines if l.strip().startswith("from __future__")]
    other_lines = [l for l in lines if not l.strip().startswith("from __future__")]
    future_block = "\n".join(future_lines) + "\n" if future_lines else ""
    remaining = "\n".join(other_lines)
    remaining = fix_relative_imports(remaining)
    remaining = fix_absolute_imports(remaining)
    return future_block + remaining


def run_pynguin_for_task(task: dict, seed: int, search_time: int, python_exec: str,
                          assertion_generation: str = "SIMPLE") -> dict:
    task_id = task["task_num"]
    raw_source = task["python_solution_full"]
    importable_source = prepare_importable_module(raw_source)

    start_time = time.time()
    generated_code = ""
    status = "NO_CODE"

    with tempfile.TemporaryDirectory(prefix=f"pynguin_{task_id}_") as temp_dir:
        temp_path = Path(temp_dir)
        module_name = "under_test"
        source_file = temp_path / f"{module_name}.py"
        source_file.write_text(importable_source, encoding="utf-8")

        cmd = [
            python_exec, "-m", "pynguin",
            "--project-path", str(temp_path),
            "--output-path", str(temp_path),
            "--module-name", module_name,
            "--algorithm", ALGORITHM,
            "--maximum-search-time", str(search_time),
            "--seed", str(seed),
            "--assertion_generation", assertion_generation,
        ]
        os.environ["PYNGUIN_DANGER_AWARE"] = "true"

        try:
            proc = _run_with_psutil_killtree(cmd, cwd=str(temp_path), timeout=search_time + 60)
            expected_test_file = temp_path / f"test_{module_name}.py"
            if expected_test_file.exists():
                generated_code = expected_test_file.read_text(encoding="utf-8")
                status = "DONE"
            else:
                error_msg = proc.stderr or proc.stdout or "Unknown/Silent Crash"
                logging.warning(f"Pynguin CRASH for Task {task_id}: {error_msg[-500:]}")
                status = "NO_CODE"
        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
            logging.warning(f"Task {task_id} Timed Out.")
        except Exception as e:
            logging.error(f"Pynguin execution failed for task {task_id}: {e}")
            status = "ERROR"

    duration = time.time() - start_time

    tests_map = {}
    if status == "DONE" and generated_code.strip():
        for line in task.get("target_lines", []):
            tests_map[str(line)] = {"test_code": generated_code, "generated_tokens": None}

    return {
        "task_num": task_id,
        "task_title": task.get("task_title", ""),
        "func_name": task.get("func_name", "solution"),
        "python_solution_full": raw_source,  # unfixed, matching real prediction files
        "model": "Pynguin-DynaMOSA",
        "temperature": 0.0,
        "pynguin_status": status,
        "pynguin_seed": seed,
        "pynguin_search_time": search_time,
        "pynguin_assertion_generation": assertion_generation,
        "tests": tests_map,
        "timed_out": status == "TIMEOUT",
        "performance_batch": {"duration_seconds": round(duration, 4)},
    }


def main():
    parser = argparse.ArgumentParser(description="Pynguin baseline runner (v2 dataset)")
    parser.add_argument("--pilot", type=int, default=None, help="Run only the first N tasks (pilot mode)")
    parser.add_argument("--search-time", type=int, required=True, help="Pynguin --maximum-search-time in seconds")
    parser.add_argument("--seeds", type=int, default=1, help="Number of seed replicates to run")
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--assertion-generation", type=str, default="SIMPLE",
                         help="Pynguin --assertion_generation mode (default SIMPLE, not Pynguin's own "
                              "default MUTATION_ANALYSIS -- see PIPELINE_FIX_PLAN.md for why: SIMPLE "
                              "produces comparable-or-more assertions at zero measured coverage cost, "
                              "and is fair against the SLM baseline which writes assertions blind to "
                              "any mutant set, unlike MUTATION_ANALYSIS which optimizes against "
                              "Pynguin's own internal mutants.")
    parser.add_argument("--python-exec", type=str, default=sys.executable,
                         help="Python executable with pynguin installed (must be <3.11)")
    args = parser.parse_args()

    tasks = load_tasks()
    if args.pilot:
        tasks = tasks[: args.pilot]
    logging.info(f"Loaded {len(tasks)} tasks.")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for seed_idx in range(args.seeds):
        seed = args.base_seed + seed_idx
        out_file = out_dir / f"pynguin_seed{seed}.jsonl"

        completed_ids = set()
        if out_file.exists():
            with open(out_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        completed_ids.add(json.loads(line)["task_num"])
                    except Exception:
                        pass
            logging.info(f"Resuming seed {seed}: {len(completed_ids)} tasks already done.")

        with open(out_file, "a", encoding="utf-8") as f_out:
            for i, task in enumerate(tasks):
                if task["task_num"] in completed_ids:
                    continue
                result = run_pynguin_for_task(task, seed, args.search_time, args.python_exec,
                                               assertion_generation=args.assertion_generation)
                f_out.write(json.dumps(result) + "\n")
                f_out.flush()
                if (i + 1) % 10 == 0:
                    logging.info(f"  seed {seed}: {i + 1}/{len(tasks)} done")

    logging.info("All seeds complete.")


if __name__ == "__main__":
    main()
