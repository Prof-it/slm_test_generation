import argparse
import ast
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import json

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "TestEval"))

# Default Directories
DEFAULT_PREDICTIONS_DIR = PROJECT_ROOT / "TestEval" / "predictions"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "evaluation_results"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COMMON_IMPORTS = """
import math
import collections
import itertools
import functools
import heapq
import bisect
import re
import unittest
from typing import *
"""

HARNESS_TEMPLATE = """
import pytest
import sys
import unittest
from typing import *
import math
import collections
import itertools
import functools
import heapq
import bisect
import re
from under_test import Solution

# --- Model Generated Code ---
{test_code}
"""

class EvaluationResult:
    PASS = "Pass"
    ASSERTION_ERROR = "Assertion Error"
    SYNTAX_ERROR = "Pytest Error"
    RUNTIME_ERROR = "Runtime Error"
    TIMEOUT = "Timeout"
    NO_CODE = "No Code"

def parse_arguments():
    parser = argparse.ArgumentParser(description="Master Evaluation Driver")
    
    # Input / Output Controls
    parser.add_argument("--input-file", type=str, help="Specific file to run.")
    parser.add_argument("--input-dir", type=str, help="Specific directory to scan for .jsonl files (recursive). Overrides default predictions dir.")
    parser.add_argument("--output-dir", type=str, help="Custom output directory for results. Defaults to 'evaluation_results'.")
    
    # Execution Controls
    parser.add_argument("--limit", type=int, default=None, help="Limit tasks per file")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel processes")
    
    # Mutation Controls
    parser.add_argument("--run-mutation", action="store_true", help="Enable mutation testing for all passing tests.")
    parser.add_argument("--mutation-subset", type=str, help="Path to JSON file containing specific task_nums to mutate (overrides --run-mutation for selection).")
    parser.add_argument("--mutation-timeout", type=int, default=600, help="Timeout in seconds for mutation analysis per task (Default: 600s).")
    
    return parser.parse_args()

def clean_jsonl_line(line):
    line = line.strip()
    if not line: return None
    try: return json.loads(line)
    except: 
        try: return json.loads(line + "}")
        except: return None

def strip_markdown(code: str) -> str:
    if not isinstance(code, str): return ""
    if "</think>" in code:
        code = code.split("</think>")[-1].strip()
    if "<think>" in code: 
        code = re.sub(r'<think>.*', '', code, flags=re.DOTALL).strip()

    pattern_py = r"```python\s*(.*?)(?:```|$)"
    match_py = re.search(pattern_py, code, re.DOTALL | re.IGNORECASE)
    if match_py: return match_py.group(1).strip()

    pattern_gen = r"```\s*(.*?)(?:```|$)"
    match_gen = re.search(pattern_gen, code, re.DOTALL)
    if match_gen: return match_gen.group(1).strip()

    return code.strip().strip("`")

def _standardize_func_name(code, required_name):
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name != required_name:
                    node.name = required_name
                break
        return ast.unparse(tree)
    except Exception:
        return code

def check_for_assertions(source_code):
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert): return True
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                        if node.func.attr.startswith('assert'): return True
        return False
    except: return False

def _determine_failure_status(proc: subprocess.CompletedProcess) -> str:
    output = proc.stdout + "\n" + proc.stderr
    if proc.returncode == 0: return EvaluationResult.PASS
    if "SyntaxError" in output or "IndentationError" in output: return EvaluationResult.SYNTAX_ERROR
    if "AssertionError" in output: return EvaluationResult.ASSERTION_ERROR
    if "ModuleNotFoundError" in output or "ImportError" in output: return EvaluationResult.RUNTIME_ERROR
    if "INTERNALERROR" in output: return EvaluationResult.SYNTAX_ERROR
    return EvaluationResult.RUNTIME_ERROR

def run_cosmic_ray_analysis(source_code_str: str, test_code_str: str, per_test_timeout: int = 10, overall_timeout: int = 600) -> dict:
    result_dict = {
        "mutation_score": 0.0, "total_mutants": 0, "killed_mutants": 0,
        "survived_mutants": 0, "log": "", "error": None
    }
    tmpdir = tempfile.mkdtemp(prefix="cosmic_ray_")
    
    try:
        work_dir = Path(tmpdir)
        
        # 1. Write Files
        (work_dir / "under_test.py").write_text(source_code_str, encoding='utf-8')
        (work_dir / "test_mutation.py").write_text(test_code_str, encoding='utf-8')
        
        # 2. Config Construction
        python_exec = sys.executable.replace("\\", "/") 

        config_content = f"""
[cosmic-ray]
module-path = "under_test.py"
timeout = {float(per_test_timeout)}
excluded-modules = []
test-command = "{python_exec} -m pytest test_mutation.py"

[cosmic-ray.distributor]
name = "local"
"""
        (work_dir / "cr-config.toml").write_text(config_content, encoding='utf-8')

        # 3. Initialization
        init_proc = subprocess.run(
            [sys.executable, "-m", "cosmic_ray.cli", "init", "cr-config.toml", "session.sqlite"],
            cwd=work_dir, capture_output=True, text=True, timeout=60
        )
        if init_proc.returncode != 0:
            raise RuntimeError(f"Init failed (Code {init_proc.returncode}): {init_proc.stderr}")

        # 4. Execution
        exec_proc = subprocess.run(
            [sys.executable, "-m", "cosmic_ray.cli", "exec", "cr-config.toml", "session.sqlite"],
            cwd=work_dir, capture_output=True, text=True, timeout=overall_timeout
        )

        # 5. Reporting
        report_proc = subprocess.run(
            [sys.executable, "-m", "cosmic_ray.cli", "dump", "session.sqlite"],
            cwd=work_dir, capture_output=True, text=True, timeout=30
        )
        if report_proc.returncode != 0:
            pass

        # Flatten lists and parse safely
        raw_output = report_proc.stdout.strip()
        mutants = []
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, list): mutants.extend(item)
                    else: mutants.append(item)
            elif isinstance(parsed, dict):
                mutants.append(parsed)
        except json.JSONDecodeError:
            for line in raw_output.splitlines():
                if line.strip():
                    try: 
                        obj = json.loads(line)
                        if isinstance(obj, list): mutants.extend(obj)
                        else: mutants.append(obj)
                    except: pass 

        total = len(mutants)
        killed = 0
        
        for m in mutants:
            if not isinstance(m, dict): continue
            test_outcome = m.get('test_outcome')
            if isinstance(test_outcome, dict):
                if test_outcome.get('outcome') == 'killed': killed += 1
            elif isinstance(test_outcome, str):
                if test_outcome == 'killed': killed += 1

        survived = total - killed
        score = 0.0
        if total > 0:
            score = (killed / total) * 100.0
            
        result_dict.update({
            "mutation_score": score,
            "total_mutants": total,
            "killed_mutants": killed,
            "survived_mutants": survived
        })

    except subprocess.TimeoutExpired:
        result_dict["error"] = "Timeout during mutation analysis"
    except Exception as e:
        result_dict["error"] = str(e)
    finally:
        try: shutil.rmtree(tmpdir, ignore_errors=True)
        except: pass 

    return result_dict

def evaluate_single_test_worker(task_data):
    task_id = task_data['task_id']
    func_name = task_data['func_name']
    solution_code = task_data['solution_code']
    raw_test_code = task_data['raw_test_code']
    do_mutation = task_data.get('mutation_enabled', False)
    mutation_timeout = task_data.get('mutation_timeout', 600)

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"eval_{task_id}_"))
    result = {
        "status": EvaluationResult.NO_CODE, 
        "coverage": 0.0, 
        "has_assertions": False,
        "mutation_score": None,
        "mutation_stats": None,
        "mutation_error": None 
    }
    log_entry = None 
    
    try:
        clean_test = strip_markdown(raw_test_code)
        clean_test = _standardize_func_name(clean_test, f"test_{func_name}")
        
        if not clean_test or not clean_test.strip(): return result, None

        result["has_assertions"] = check_for_assertions(clean_test)
        
        full_solution = COMMON_IMPORTS + "\n" + solution_code
        (tmp_dir / "under_test.py").write_text(full_solution, encoding='utf-8')
        
        harness = HARNESS_TEMPLATE.format(test_code=clean_test)
        exec_script = harness + f"\ntest_{func_name}()"
        (tmp_dir / "test_generated.py").write_text(exec_script, encoding='utf-8')
        
        proc = None
        output_str = ""
        
        # 1. Execution
        try:
            proc = subprocess.run(
                [sys.executable, "test_generated.py"], 
                cwd=tmp_dir, capture_output=True, text=True, timeout=10
            )
            result["status"] = _determine_failure_status(proc)
            output_str = proc.stdout + "\n" + proc.stderr
        except subprocess.TimeoutExpired:
            result["status"] = EvaluationResult.TIMEOUT
            output_str = "TIMEOUT (10s limit)"

        # 2. Coverage & Mutation
        if result["status"] == EvaluationResult.PASS:
            (tmp_dir / "test_generated.py").write_text(harness, encoding='utf-8')
            try:
                subprocess.run(["pytest", "--cov=under_test", "--cov-report=json:coverage.json", "test_generated.py"], 
                               cwd=tmp_dir, capture_output=True, timeout=15)
                if (tmp_dir / "coverage.json").exists():
                    with open(tmp_dir / "coverage.json") as f:
                        cov_data = json.load(f)
                        result["coverage"] = cov_data["totals"]["percent_covered"]
            except: pass

            if result["coverage"] > 0 and do_mutation:
                full_test_harness = harness + f"\ntest_{func_name}()"
                
                mutation_res = run_cosmic_ray_analysis(
                    source_code_str=full_solution,
                    test_code_str=full_test_harness,
                    per_test_timeout=10, 
                    overall_timeout=mutation_timeout 
                )
                
                result["mutation_score"] = mutation_res["mutation_score"]
                result["mutation_stats"] = {
                    "total": mutation_res["total_mutants"],
                    "killed": mutation_res["killed_mutants"],
                    "survived": mutation_res["survived_mutants"]
                }
                if mutation_res["error"]:
                    result["mutation_error"] = mutation_res["error"]
                    log_entry = {
                        "task_id": task_id,
                        "status": "Mutation Error", 
                        "code": clean_test,
                        "output": f"Error: {mutation_res['error']}"
                    }

        if result["status"] != EvaluationResult.PASS:
            log_entry = {
                "task_id": task_id,
                "status": result["status"],
                "code": clean_test,
                "output": output_str
            }

    finally:
        try: shutil.rmtree(tmp_dir, ignore_errors=True)
        except: pass
        
    return result, log_entry

def process_file(input_path, output_path, args):
    logger.info(f"Processing {input_path} -> {output_path}")
    log_path = output_path.with_suffix(".md")
    
    use_subset = False
    mutation_target_ids = set()
    
    if args.mutation_subset:
        try:
            with open(args.mutation_subset, 'r') as f:
                mutation_target_ids = set(str(x) for x in json.load(f))
            use_subset = True
            logger.info(f"Loaded {len(mutation_target_ids)} tasks for mutation testing.")
        except Exception as e:
            logger.error(f"Failed to load mutation subset: {e}")
            return
    elif args.run_mutation:
        logger.info("Mutation testing ENABLED for all passing tasks.")

    data = []
    try:
        with open(input_path, 'r', errors='ignore') as f:
            for line in f:
                cleaned = clean_jsonl_line(line)
                if cleaned: data.append(cleaned)
    except Exception as e:
        logger.error(f"Could not read {input_path}: {e}")
        return

    if args.limit: data = data[:args.limit]
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_f_handle = open(output_path, 'w', encoding='utf-8')
    log_f_handle = open(log_path, 'w', encoding='utf-8')
    log_f_handle.write(f"# FAILURE LOG: {input_path.name}\n\n")

    tasks = []
    
    for i, entry in enumerate(data):
        task_num = str(entry.get('task_num', f"task_{i}"))
        solution = entry.get('code') or entry.get('python_solution') or ""
        
        if not solution:
            out_f_handle.write(json.dumps({"task_num": task_num, "status": EvaluationResult.NO_CODE}) + "\n")
            continue

        func_name = entry.get('func_name', 'solution')
        perf_data = entry.get('performance_batch', {})
        timed_out = entry.get('timed_out', False)
        tests = entry.get('tests', {})
        
        test_list = []
        if isinstance(tests, dict): test_list = list(tests.items())
        elif isinstance(tests, list): test_list = [(str(ix), t) for ix, t in enumerate(tests)]

        if not test_list:
            status = EvaluationResult.TIMEOUT if timed_out else EvaluationResult.NO_CODE
            res = {"task_num": task_num, "status": status, "performance": perf_data}
            out_f_handle.write(json.dumps(res) + "\n")
            continue
            
        should_mutate = False
        if use_subset:
            should_mutate = task_num in mutation_target_ids
        elif args.run_mutation:
            should_mutate = True

        for tid, val in test_list:
            code = val.get("test_code", "") if isinstance(val, dict) else str(val)
            worker_payload = {
                'task_id': f"{task_num}_{tid}",
                'func_name': func_name,
                'solution_code': solution,
                'raw_test_code': code,
                'mutation_enabled': should_mutate,
                'mutation_timeout': args.mutation_timeout
            }
            meta = {'task_num': task_num, 'target_line': tid, 'performance': perf_data}
            tasks.append((worker_payload, meta))

    total_tasks = len(tasks)
    print(f"Executing {total_tasks} evaluations with {args.workers} workers...")
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(evaluate_single_test_worker, task[0]): task[1] for task in tasks}
        count = 0
        for future in as_completed(futures):
            meta = futures[future]
            count += 1
            try:
                result, log_entry = future.result()
                final_res = result.copy()
                final_res.update(meta)
                out_f_handle.write(json.dumps(final_res) + "\n")
                out_f_handle.flush() 
                if log_entry: _write_log_entry(log_f_handle, log_entry)
                if count % 50 == 0: print(f"\rProgress: {count}/{total_tasks} finished", end="", flush=True)
            except Exception as e:
                logger.error(f"Worker crashed: {e}")

    out_f_handle.close()
    log_f_handle.close()
    print("\nDone.")

def _write_log_entry(log_file, entry):
    report = [
        f"## TASK: {entry['task_id']}",
        f"**STATUS:** {entry['status']}",
        "",
        "### Output",
        "```text",
        entry['output'].strip(),
        "```",
        "",
        "### Code",
        "```python",
        entry['code'].strip(),
        "```",
        "---"
    ]
    log_file.write("\n".join(report))
    log_file.flush()

def main():
    args = parse_arguments()
    
    # 1. Determine Results Directory
    results_dir = Path(args.output_dir) if args.output_dir else DEFAULT_RESULTS_DIR
    results_dir.mkdir(exist_ok=True, parents=True)
    
    # 2. Determine Predictions Directory (Source)
    predictions_dir = Path(args.input_dir) if args.input_dir else DEFAULT_PREDICTIONS_DIR

    files_to_process = []
    
    if args.input_file:
        # Case A: Single File
        in_path = Path(args.input_file).resolve()
        out_name = f"{in_path.stem}_evaluated.jsonl"
        
        # Try to keep relative folder structure if input is inside predictions dir
        try:
            rel_path = in_path.relative_to(predictions_dir.resolve())
            out_path = results_dir / rel_path.parent / out_name
        except ValueError:
            # Fallback: flatten structure
            out_path = results_dir / out_name
            
        files_to_process.append((in_path, out_path))
    else:
        # Case B: Recursive Scan
        logger.info(f"Scanning {predictions_dir} recursively...")
        candidates = predictions_dir.rglob("*.jsonl")
        
        for input_f in candidates:
            if not input_f.is_file(): continue
            # Maintain folder structure in output
            try:
                rel_path = input_f.relative_to(predictions_dir)
                out_path = results_dir / rel_path.parent / f"{input_f.stem}_evaluated.jsonl"
            except ValueError:
                # Should not happen if globbing from predictions_dir
                out_path = results_dir / f"{input_f.stem}_evaluated.jsonl"
                
            files_to_process.append((input_f, out_path))

    for in_f, out_f in files_to_process:
        if out_f.exists():
            print(f"Skipping {in_f.name} (Exists)")
            continue
        process_file(in_f, out_f, args)

if __name__ == "__main__":
    main()