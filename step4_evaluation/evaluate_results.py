"""
Master Evaluation Driver

Validates LLM-generated Python unit tests. For each prediction file, runs pytest
in an isolated temp dir, measures statement coverage, and optionally runs cosmic-ray
mutation testing. Supports resuming interrupted runs and parallel workers.

Usage:
    python evaluate_results.py --input-dir /path/to/predictions --output-dir evaluation_results --run-mutation
    python evaluate_results.py --input-dir /path/to/predictions --output-dir evaluation_results --mutation-subset step4_evaluation/mutation_subset_ids.json
"""

import argparse
import ast
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "TestEval"))

# Regex to match relative imports: from .foo import bar  /  from ..pkg import baz
_RELATIVE_IMPORT_RE = re.compile(r'^(\s*)from\s+(\.+\w*)\s+import\s+(.+)$')

# Stdlib module names for filtering absolute-import wrapping
import sys as _sys
_STDLIB_MODULES = getattr(_sys, 'stdlib_module_names', set())

def fix_absolute_imports(code: str) -> str:
    """Wrap non-stdlib absolute imports in try/except MagicMock fallback.

    When under_test.py is executed standalone (without the source repo's
    virtualenv), absolute imports like ``import datachain`` or
    ``from pandera import X`` raise ImportError and prevent the module from
    loading at all.  Wrapping them lets under_test.py load cleanly; the
    model-generated test is then responsible for mocking what it needs.
    """
    import ast as _ast
    out = []
    for line in code.splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        # Absolute `import foo` or `import foo.bar`
        if stripped.startswith('import ') and not stripped.startswith('import .'):
            try:
                stmts = _ast.parse(stripped).body
            except SyntaxError:
                out.append(line)
                continue
            if stmts and isinstance(stmts[0], _ast.Import):
                top_mods = [alias.name.split('.')[0] for alias in stmts[0].names]
                if any(m not in _STDLIB_MODULES and m not in ('__future__',) for m in top_mods):
                    names = [alias.asname or alias.name.split('.')[0] for alias in stmts[0].names]
                    out.append(f"{indent}try:")
                    out.append(f"{indent}    {stripped}")
                    out.append(f"{indent}except (ImportError, ModuleNotFoundError):")
                    out.append(f"{indent}    from unittest.mock import MagicMock as _MagicMock")
                    for name in names:
                        out.append(f"{indent}    {name} = _MagicMock()")
                    continue

        # Absolute `from foo import bar` (non-relative)
        if stripped.startswith('from ') and not stripped.startswith('from .'):
            try:
                stmts = _ast.parse(stripped).body
            except SyntaxError:
                out.append(line)
                continue
            if stmts and isinstance(stmts[0], _ast.ImportFrom):
                mod = (stmts[0].module or '').split('.')[0]
                if mod and mod not in _STDLIB_MODULES and mod not in ('__future__',):
                    names = [alias.asname or alias.name for alias in stmts[0].names]
                    out.append(f"{indent}try:")
                    out.append(f"{indent}    {stripped}")
                    out.append(f"{indent}except (ImportError, ModuleNotFoundError):")
                    out.append(f"{indent}    from unittest.mock import MagicMock as _MagicMock")
                    for name in names:
                        out.append(f"{indent}    {name} = _MagicMock()")
                    continue

        out.append(line)
    return '\n'.join(out)

def fix_relative_imports(code: str) -> str:
    """Convert relative imports to try/except with MagicMock fallback.

    Relative imports (e.g. ``from .broker import get_broker``) fail when the
    module is executed as a standalone file.  This wraps each such import in a
    try/except that falls back to assigning MagicMock() to every imported name,
    allowing the rest of the module to load.
    """
    out = []
    for line in code.splitlines():
        m = _RELATIVE_IMPORT_RE.match(line)
        if m:
            indent, _module, names_str = m.group(1), m.group(2), m.group(3)
            # Parse imported names, respecting "X as Y" aliases
            names = []
            for part in names_str.split(','):
                part = part.strip()
                if not part:
                    continue
                if ' as ' in part:
                    names.append(part.split(' as ')[-1].strip())
                else:
                    names.append(part.strip())
            out.append(f"{indent}try:")
            out.append(f"{indent}    {line.strip()}")
            out.append(f"{indent}except (ImportError, SystemError):")
            out.append(f"{indent}    from unittest.mock import MagicMock as _MagicMock")
            for name in names:
                out.append(f"{indent}    {name} = _MagicMock()")
        else:
            out.append(line)
    return '\n'.join(out)

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
from unittest.mock import patch, MagicMock
import pytest
import sys
import os
import unittest
from typing import *
import math
import collections
import itertools
import functools
import heapq
import bisect
import re
import datetime
import json
import time
import copy
import io
import hashlib
import logging

# Flexible import — wrapped so third-party import failures in
# under_test.py don't prevent the test file from loading at all.
try:
    from under_test import Solution
except (ImportError, Exception):
    pass # Function might be standalone

try:
    from under_test import *
except (ImportError, Exception):
    pass # under_test may have unresolvable third-party imports

# --- Model Generated Code ---
{test_code}
"""

class EvaluationResult:
    """
    Standardized constants representing the outcome of a specific test execution.
    """
    PASS = "Pass"
    ASSERTION_ERROR = "Assertion Error"
    SYNTAX_ERROR = "Pytest Error"
    RUNTIME_ERROR = "Runtime Error"
    TIMEOUT = "Timeout"
    NO_CODE = "No Code"

def parse_arguments():
    """
    Parses command-line arguments for the evaluation driver.
    """
    parser = argparse.ArgumentParser(description="Master Evaluation Driver")
    
    # Input / Output Controls
    parser.add_argument("--input-file", type=str, help="Specific file to run.")
    parser.add_argument("--input-dir", type=str, help="Specific directory to scan for .jsonl files (recursive). Overrides default predictions dir.")
    parser.add_argument("--output-dir", type=str, help="Custom output directory for results. Defaults to 'evaluation_results'.")
    
    # Execution Controls
    parser.add_argument("--limit", type=int, default=None, help="Limit tasks per file")
    parser.add_argument("--workers", type=int, default=12, help="Number of parallel processes")
    
    # Mutation Controls
    parser.add_argument("--run-mutation", action="store_true", help="Enable mutation testing for all passing tests.")
    parser.add_argument("--mutation-subset", type=str, help="Path to JSON file containing specific task_nums to mutate (overrides --run-mutation for selection).")
    parser.add_argument("--mutation-timeout", type=int, default=300, help="Timeout in seconds for mutation analysis per task (Default: 300s).")
    
    return parser.parse_args()

def clean_jsonl_line(line):
    """
    Attempts to parse a JSON line, with fallback logic for truncated JSON
    (common in interrupted LLM generations).
    """
    line = line.strip()
    if not line: return None
    try: return json.loads(line)
    except: 
        try: return json.loads(line + "}")
        except: return None

def strip_markdown(code: str) -> str:
    """
    Sanitizes LLM output by removing:
    1. Chain-of-Thought traces (<think> tags).
    2. Markdown code fences (```python).
    3. Conversational filler before the code starts.
    """
    if not isinstance(code, str): return ""
    
    # 1. Remove Thinking Blocks
    if "</think>" in code:
        code = code.split("</think>")[-1].strip()
    if "<think>" in code: 
        code = re.sub(r'<think>.*', '', code, flags=re.DOTALL).strip()

    # 2. Extract Markdown Blocks (High Precision)
    # Match ```python ... ``` ignoring case — only if content is non-empty
    pattern_py = r"```python\s*(.*?)(?:```|$)"
    match_py = re.search(pattern_py, code, re.DOTALL | re.IGNORECASE)
    if match_py and match_py.group(1).strip():
        return match_py.group(1).strip()

    # Match generic ``` ... ``` — only if content is non-empty
    pattern_gen = r"```\s*(.*?)(?:```|$)"
    match_gen = re.search(pattern_gen, code, re.DOTALL)
    if match_gen and match_gen.group(1).strip():
        return match_gen.group(1).strip()

    # 3. Fallback: Heuristic Extraction (Chatter Removal)
    # If no markdown, look for the first line starting with common Python keywords.
    lines = code.split('\n')
    keywords = ["def ", "class ", "import ", "from ", "@"]
    
    start_index = -1
    for i, line in enumerate(lines):
        clean_line = line.strip()
        # Check if line starts with a keyword (and isn't a comment)
        if any(clean_line.startswith(k) for k in keywords):
            start_index = i
            break
            
    if start_index != -1:
        # Rejoin from the first valid line of code, strip any trailing fence
        result = "\n".join(lines[start_index:]).strip()
        result = re.sub(r'\n```\w*\s*$', '', result).strip()
        result = re.sub(r'```\w*\s*$', '', result).strip()
        return result

    # 4. Last Resort: clean backticks and whitespace
    return code.strip().strip("`")


def _standardize_func_name(code, required_name):
    """
    Parses the AST to find the best candidate for the test functions.
    1. If a function is already named correctly, return code.
    2. If ANY function starts with 'test', TRUST THE LLM. Pytest will find it.
       (Renaming in this case is dangerous as it might rename a helper instead).
    3. If no 'test' functions exist, find a function with Assertions and rename it.
    4. Last resort: Rename the last defined function.
    """
    try:
        tree = ast.parse(code)
        
        # Get all function definitions
        candidates = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        
        if not candidates:
            return code

        chosen_node = None

        # Helper: Count 'assert' statements inside a function node
        def count_asserts(node):
            return sum(1 for child in ast.walk(node) if isinstance(child, ast.Assert))

        # 1. Exact Match Check (Optimization)
        for node in candidates:
            if node.name == required_name:
                return code # No need to rename, it's already correct

        # 2. Look for functions starting with 'test'
        test_prefix_funcs = [f for f in candidates if f.name.lower().startswith("test")]
        
        if test_prefix_funcs:
            # If the LLM generated a 'test_' function, pytest will find it automatically.
            # We do NOT rename here, as we might accidentally rename a helper function.
            return code

        # 3. If no 'test' name, look for ANY function with assertions
        if not chosen_node:
            assert_funcs = [f for f in candidates if count_asserts(f) > 0]
            if assert_funcs:
                # Sort by number of asserts, descending
                assert_funcs.sort(key=lambda f: (count_asserts(f), f.lineno), reverse=True)
                chosen_node = assert_funcs[0]

        # 4. Fallback: The LAST function defined
        if not chosen_node:
            chosen_node = candidates[-1]

        # Apply the rename
        chosen_node.name = required_name
        
        return ast.unparse(tree)
        
    except Exception:
        # If AST parsing fails (syntax error in generated code), return raw code
        return code


def _combine_tests_for_task(test_list, func_name):
    """Combine all target_line tests for a task into a single test suite.

    For Pynguin: entries are identical suites, return the first.
    For SLMs: strip markdown, rename test functions per target_line, concatenate.
    """
    if not test_list:
        return ""

    # Get first non-empty code to check if Pynguin
    first_code = ""
    for _, val in test_list:
        c = val.get("test_code", "") if isinstance(val, dict) else str(val)
        if c and c.strip():
            first_code = c
            break

    if not first_code:
        return ""

    # Pynguin detection: all entries are identical suites, return first
    if "test_case_0" in first_code or "pymosa" in first_code.lower():
        return first_code

    # SLM: combine individual tests with renamed functions
    combined_parts = []

    for tid, val in test_list:
        code = val.get("test_code", "") if isinstance(val, dict) else str(val)
        if not code or not code.strip():
            continue

        code = strip_markdown(code)
        if not code or not code.strip():
            continue

        # Strip __future__ (harness prepends its own imports)
        code = "\n".join(
            line for line in code.splitlines()
            if not line.strip().startswith("from __future__")
        )
        if not code.strip():
            continue

        # Rename test functions to avoid collisions across target lines
        try:
            tree = ast.parse(code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

            if funcs:
                test_funcs = [f for f in funcs if f.name.lower().startswith("test")]
                if test_funcs:
                    for f in test_funcs:
                        f.name = f"{f.name}_line{tid}"
                else:
                    # No test_ function — rename last function to be discoverable
                    funcs[-1].name = f"test_line{tid}"
                code = ast.unparse(tree)
            else:
                # No functions at all — wrap in a test function
                indented = "\n".join(f"    {line}" for line in code.splitlines())
                code = f"def test_line{tid}():\n{indented}"
        except SyntaxError:
            # AST parse failed — skip this piece entirely to avoid poisoning
            # the combined file. One broken test should not kill all others.
            logger.warning(f"Skipping test piece for line {tid} (SyntaxError in generated code)")
            continue

        combined_parts.append(code)

    return "\n\n".join(combined_parts)


def check_for_assertions(source_code):
    """
    Static analysis check to verify if the test code actually contains assertions.
    Prevents "False Positives" where a test passes simply because it did nothing.
    """
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

def count_xfail_tests(source_code):
    """
    Count the number of @pytest.mark.xfail decorated test functions.
    Returns tuple: (has_xfail, num_xfail)
    """
    try:
        num_xfail = 0
        if '@pytest.mark.xfail' in source_code:
            # Count occurrences (rough estimate)
            num_xfail = source_code.count('@pytest.mark.xfail')
        return (num_xfail > 0, num_xfail)
    except:
        return (False, 0)

def _determine_failure_status(proc: subprocess.CompletedProcess) -> str:
    """
    Maps subprocess output and return codes to an EvaluationResult constant.
    Distinguishes between Syntax Errors, Assertion Errors, and Runtime Crashes.
    """
    output = proc.stdout + "\n" + proc.stderr
    if proc.returncode == 0: return EvaluationResult.PASS
    if "SyntaxError" in output or "IndentationError" in output: return EvaluationResult.SYNTAX_ERROR
    if "AssertionError" in output: return EvaluationResult.ASSERTION_ERROR
    if "ModuleNotFoundError" in output or "ImportError" in output: return EvaluationResult.RUNTIME_ERROR
    if "INTERNALERROR" in output: return EvaluationResult.SYNTAX_ERROR
    return EvaluationResult.RUNTIME_ERROR

def _run_with_killtree(cmd, cwd, timeout):
    """Like subprocess.run(cmd, timeout=timeout) but kills the whole process tree
    on timeout, not just the immediate child. cosmic-ray exec spawns pytest as a
    grandchild process; Popen.kill()/proc.kill() (what subprocess.run's timeout
    handling uses) only terminates the immediate child on Windows, leaving the
    pytest grandchild running. With 12 parallel workers those orphans pile up and
    starve CPU for everyone else, which cascades into more timeouts.
    """
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=creationflags
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass
        raise

def run_cosmic_ray_analysis(source_code_str: str, test_code_str: str, per_test_timeout: int = 10, overall_timeout: int = 3600) -> dict:
    """
    Executes mutation testing using `cosmic-ray`.

    Workflow:
    1. Creates a temporary directory.
    2. Writes the solution and test files.
    3. Configures cosmic-ray (TOML).
    4. Initializes the mutation session.
    5. Executes the mutation session (handling timeouts gracefully).
    6. Dumps statistics to calculate the mutation score.
    """
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
        # Use current Python executable (cosmic-ray and pytest must be in this environment)
        python_exec = sys.executable.replace("\\", "/")

        # Create cosmic-ray config (no max-workers - local distributor runs serially)
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
            [python_exec, "-m", "cosmic_ray.cli", "init", "cr-config.toml", "session.sqlite"],
            cwd=work_dir, capture_output=True, text=True, timeout=60
        )
        if init_proc.returncode != 0:
            raise RuntimeError(f"Init failed (Code {init_proc.returncode}): {init_proc.stderr}")

        # 4. Execution
        exec_timed_out = False
        try:
            # We process ALL pending mutations in one call (not a loop).
            # We catch timeout specifically here so we can still report partial results.
            exec_proc = _run_with_killtree(
                [python_exec, "-m", "cosmic_ray.cli", "exec", "cr-config.toml", "session.sqlite"],
                cwd=work_dir, timeout=overall_timeout
            )
            if exec_proc.returncode != 0:
                print(f"  [DEBUG] cosmic-ray exec failed: {exec_proc.returncode}")
                if exec_proc.stderr: print(f"  [DEBUG] stderr: {exec_proc.stderr[:300]}")

        except subprocess.TimeoutExpired:
            exec_timed_out = True
            print(f"  [DEBUG] cosmic-ray exec timed out after {overall_timeout}s. Dumping partial results.")

        # 5. Reporting
        # We run dump even if exec failed/timed out to capture whatever work was finished
        dump_timed_out = False
        try:
            report_proc = _run_with_killtree(
                [python_exec, "-m", "cosmic_ray.cli", "dump", "session.sqlite"],
                cwd=work_dir, timeout=120
            )
            if report_proc.returncode != 0:
                pass
        except subprocess.TimeoutExpired:
            dump_timed_out = True
            result_dict["error"] = "cosmic-ray dump timed out after 120s — mutation results unavailable"
            return result_dict

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
        survived = 0
        incompetent = 0
        timeout_mutants = 0
        pending = 0
        unknown = 0

        for m in mutants:
            if not isinstance(m, dict): continue
            test_outcome = m.get('test_outcome')
            
            # Extract outcome value
            outcome_value = None
            if isinstance(test_outcome, dict):
                outcome_value = test_outcome.get('outcome')
            elif isinstance(test_outcome, str):
                outcome_value = test_outcome

            # Count by type
            if outcome_value == 'killed':
                killed += 1
            elif outcome_value == 'survived':
                survived += 1
            elif outcome_value == 'incompetent':
                incompetent += 1
            elif outcome_value == 'timeout':
                timeout_mutants += 1
            elif outcome_value == 'pending':
                pending += 1
            else:
                unknown += 1

        # Mutation Score Calculation 
        # killed = good, survived + unknown = bad, incompetent + timeout = excluded (invalid mutants)
        effective_survived = survived + unknown
        valid_mutants = killed + effective_survived
        score = 0.0
        if valid_mutants > 0:
            score = (killed / valid_mutants) * 100.0

        mutation_warning = None
        if exec_timed_out:
            mutation_warning = f"Partial results: execution timed out after {overall_timeout}s"
        elif total > 0 and (total - (killed + effective_survived + incompetent + timeout_mutants)) > 0:
            mutation_warning = "Partial results: some mutants remained pending"

        result_dict.update({
            "mutation_score": score,
            "total_mutants": total,
            "killed_mutants": killed,
            "survived_mutants": effective_survived  # includes unknown as survived
        })

        if mutation_warning:
            result_dict["mutation_warning"] = mutation_warning

    except Exception as e:
        result_dict["error"] = str(e)
    finally:
        try: shutil.rmtree(tmpdir, ignore_errors=True)
        except: pass 

    return result_dict

def evaluate_single_test_worker(task_data):
    """
    Worker function executed in a separate process.

    1. Writes the solution code and test harness to an isolated temp directory.
    2. Runs the test via `pytest`.
    3. If passing: runs `pytest-cov` for coverage data.
    4. If passing + coverage > 0 + mutation enabled: runs `run_cosmic_ray_analysis`.
    """
    task_id = task_data['task_id']
    func_name = task_data['func_name']
    solution_code = task_data['solution_code']
    raw_test_code = task_data['raw_test_code']
    do_mutation = task_data.get('mutation_enabled', False)
    mutation_timeout = task_data.get('mutation_timeout', 300)

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"eval_{task_id}_"))
    result = {
        "status": EvaluationResult.NO_CODE,
        "coverage": 0.0,
        "has_assertions": False,
        "has_xfail_tests": False,  
        "num_xfail_tests": 0,      
        "mutation_score": None,
        "mutation_stats": None,
        "mutation_error": None,
        "mutation_timeout": False  
    }
    log_entry = None 
    
    try:
        clean_test = strip_markdown(raw_test_code)
        # Strip __future__ imports from generated test code — test harness templates
        # prepend their own imports, and __future__ appearing after those causes SyntaxError.
        clean_test = "\n".join(
            line for line in clean_test.splitlines()
            if not line.strip().startswith("from __future__")
        )

        is_pynguin = "test_case_0" in clean_test or "pymosa" in clean_test.lower()
        
        # Separate __future__ imports from solution code so they always appear
        # first in the file (Python requires __future__ before all other statements).
        solution_lines = solution_code.splitlines()
        future_lines = []
        other_lines = []
        for line in solution_lines:
            if line.strip().startswith("from __future__"):
                future_lines.append(line)
            else:
                other_lines.append(line)

        future_block = "\n".join(future_lines) + "\n" if future_lines else ""
        remaining_code = "\n".join(other_lines)
        # Convert relative imports (from .xxx import yyy) to try/except with
        # Wrap both relative AND absolute third-party imports so under_test.py
        # loads cleanly without the source repo's virtualenv installed.
        remaining_code = fix_relative_imports(remaining_code)
        remaining_code = fix_absolute_imports(remaining_code)
        full_solution = future_block + COMMON_IMPORTS + "\n" + remaining_code
        (tmp_dir / "under_test.py").write_text(full_solution, encoding='utf-8')

        if is_pynguin:
            # STRATEGY FOR PYNGUIN
            # Do not rename functions (keeps test_case_0, test_case_1, etc.)
            # Do not enforce 'Solution' import and use pytest to run all generated cases

            if not clean_test or not clean_test.strip(): return result, None

            result["has_assertions"] = check_for_assertions(clean_test)

            # Track xfail tests for Pynguin
            has_xfail, num_xfail = count_xfail_tests(clean_test)
            result["has_xfail_tests"] = has_xfail
            result["num_xfail_tests"] = num_xfail

            harness = f"""
import pytest
import sys
import os
import datetime
import json
import time
import copy
import io
import hashlib
import logging
from unittest.mock import MagicMock, patch

# Add current dir to path so imports work
sys.path.insert(0, os.getcwd())

# --- Pynguin Generated Code ---
{clean_test}
"""
            (tmp_dir / "test_generated.py").write_text(harness, encoding='utf-8')
            
            # Execution
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "test_generated.py", "-v"],
                    cwd=tmp_dir, capture_output=True, text=True, timeout=30
                )
                result["status"] = _determine_failure_status(proc)
                output_str = proc.stdout + "\n" + proc.stderr
            except subprocess.TimeoutExpired:
                result["status"] = EvaluationResult.TIMEOUT
                output_str = "TIMEOUT (30s limit)"

            # Coverage: ungated — measure for all non-crash outcomes
            if result["status"] not in (EvaluationResult.TIMEOUT, EvaluationResult.SYNTAX_ERROR, EvaluationResult.NO_CODE):
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pytest", "--cov=under_test", "--cov-report=json:coverage.json", "test_generated.py"],
                        cwd=tmp_dir, capture_output=True, timeout=15
                    )
                    if (tmp_dir / "coverage.json").exists():
                        with open(tmp_dir / "coverage.json") as f:
                            cov_data = json.load(f)
                            result["coverage"] = cov_data["totals"]["percent_covered"]
                except: pass

            # Mutation: still gated on PASS
            if result["status"] == EvaluationResult.PASS and result["coverage"] > 0 and do_mutation:
                mutation_res = run_cosmic_ray_analysis(
                    source_code_str=full_solution,
                    test_code_str=harness,
                    per_test_timeout=30,
                    overall_timeout=mutation_timeout
                )
                result["mutation_score"] = mutation_res["mutation_score"]
                result["mutation_stats"] = {
                    "total": mutation_res["total_mutants"],
                    "killed": mutation_res["killed_mutants"],
                    "survived": mutation_res["survived_mutants"]
                }
                if mutation_res.get("mutation_warning"):
                    result["mutation_timeout"] = True

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

        else:
            # TestEval logic
            clean_test = _standardize_func_name(clean_test, f"test_{func_name}")

            if not clean_test or not clean_test.strip(): return result, None

            result["has_assertions"] = check_for_assertions(clean_test)

            harness = HARNESS_TEMPLATE.format(test_code=clean_test)
            (tmp_dir / "test_generated.py").write_text(harness, encoding='utf-8')

            # Execution
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "test_generated.py", "-v"],
                    cwd=tmp_dir, capture_output=True, text=True, timeout=30
                )
                result["status"] = _determine_failure_status(proc)
                output_str = proc.stdout + "\n" + proc.stderr
            except subprocess.TimeoutExpired:
                result["status"] = EvaluationResult.TIMEOUT
                output_str = "TIMEOUT (30s limit)"

            # Coverage: ungated — measure for all non-crash outcomes
            if result["status"] not in (EvaluationResult.TIMEOUT, EvaluationResult.SYNTAX_ERROR, EvaluationResult.NO_CODE):
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pytest", "--cov=under_test", "--cov-report=json:coverage.json", "test_generated.py"],
                        cwd=tmp_dir, capture_output=True, timeout=15
                    )
                    if (tmp_dir / "coverage.json").exists():
                        with open(tmp_dir / "coverage.json") as f:
                            cov_data = json.load(f)
                            result["coverage"] = cov_data["totals"]["percent_covered"]
                except: pass

            # Mutation: still gated on PASS
            if result["status"] == EvaluationResult.PASS and result["coverage"] > 0 and do_mutation:
                mutation_res = run_cosmic_ray_analysis(
                    source_code_str=full_solution,
                    test_code_str=harness,
                    per_test_timeout=30,
                    overall_timeout=mutation_timeout
                )

                result["mutation_score"] = mutation_res["mutation_score"]
                result["mutation_stats"] = {
                    "total": mutation_res["total_mutants"],
                    "killed": mutation_res["killed_mutants"],
                    "survived": mutation_res["survived_mutants"]
                }
                if mutation_res.get("mutation_warning"):
                     result["mutation_timeout"] = True

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
    """
    Orchestrates the evaluation of a single prediction file (.jsonl).
    """
    logger.info(f"Processing {input_path} -> {output_path}")
    log_path = output_path.with_suffix(".md")
    
    # Resume logic
    completed_ids = set()
    if output_path.exists():
        logger.info("Output file exists. Scanning for completed tasks...")
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        t_num = str(data.get('task_num', ''))
                        completed_ids.add(t_num)
                    except: pass
            logger.info(f"Resuming: Found {len(completed_ids)} completed tasks.")
        except Exception as e:
            logger.warning(f"Failed to read existing output file: {e}. Might start fresh or duplicate.")

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
    
    out_f_handle = open(output_path, 'a', encoding='utf-8')
    log_f_handle = open(log_path, 'a', encoding='utf-8')
    
    if not output_path.exists() or output_path.stat().st_size == 0:
        log_f_handle.write(f"# FAILURE LOG: {input_path.name}\n\n")

    tasks = []
    
    for i, entry in enumerate(data):
        task_num = str(entry.get('task_num', f"task_{i}"))
        # python_solution_full is set by prepare_v2_tier_datasets.py so that
        # evaluation always runs against the real function, not the tier card stub.
        solution = entry.get('python_solution_full') or entry.get('code') or entry.get('python_solution') or ""

        if not solution:
            if task_num not in completed_ids:
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
            if task_num not in completed_ids:
                status = EvaluationResult.TIMEOUT if timed_out else EvaluationResult.NO_CODE
                res = {"task_num": task_num, "status": status, "performance": perf_data}
                out_f_handle.write(json.dumps(res) + "\n")
            continue

        if task_num in completed_ids:
            continue

        # Combine all target_line tests into a single test suite per task
        combined_code = _combine_tests_for_task(test_list, func_name)

        should_mutate = False
        if use_subset:
            should_mutate = task_num in mutation_target_ids
        elif args.run_mutation:
            should_mutate = True

        worker_payload = {
            'task_id': task_num,
            'func_name': func_name,
            'solution_code': solution,
            'raw_test_code': combined_code,
            'mutation_enabled': should_mutate,
            'mutation_timeout': args.mutation_timeout
        }
        meta = {'task_num': task_num, 'performance': perf_data}
        tasks.append((worker_payload, meta))

    total_tasks = len(tasks)
    if total_tasks == 0:
        logger.info("All tasks in file already completed.")
    else:
        print(f"Executing {total_tasks} remaining evaluations with {args.workers} workers...")
        
        executor = ProcessPoolExecutor(max_workers=args.workers)
        try:
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
        except KeyboardInterrupt:
            print("\nInterrupted. Cancelling pending tasks and terminating worker processes...")
            for f in futures:
                f.cancel()
            # cancel_futures requires Python 3.9+; worker processes (and the
            # cosmic-ray/pytest grandchildren they spawned) are force-killed so
            # nothing keeps running in the background after we exit.
            for p in list(getattr(executor, "_processes", {}).values()):
                try: p.kill()
                except Exception: pass
            executor.shutdown(wait=False, cancel_futures=True)
            out_f_handle.close()
            log_f_handle.close()
            raise
        else:
            executor.shutdown(wait=True)

    out_f_handle.close()
    log_f_handle.close()
    print("\nDone.")

def _write_log_entry(log_file, entry):
    """Formats and appends a failure log entry to the markdown log file."""
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

class _DebouncedSigint:
    """Swallows a single Ctrl+C / CTRL_C_EVENT and only lets it through as a real
    KeyboardInterrupt if a second one arrives within `window` seconds.

    Multi-hour mutation-testing runs are vulnerable to a single stray SIGINT
    (a control character in pasted text, another process sharing the console
    broadcasting CTRL_C_EVENT, etc.) killing hours of work. Requiring a
    deliberate double press matches common CLI conventions and protects
    against that without ignoring a genuine cancel request.
    """
    def __init__(self, window=3.0):
        self.window = window
        self.last_time = None
        self._orig_handler = None

    def __enter__(self):
        self._orig_handler = signal.signal(signal.SIGINT, self._handle)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        signal.signal(signal.SIGINT, self._orig_handler)

    def _handle(self, signum, frame):
        now = time.monotonic()
        if self.last_time is not None and (now - self.last_time) <= self.window:
            self.last_time = None
            raise KeyboardInterrupt()
        self.last_time = now
        print(f"\n[!] Ctrl+C received. Press it again within {self.window:.0f}s to "
              f"actually stop the run (guards against a single stray interrupt).",
              flush=True)

def main():
    """
    Main entry point.
    """
    args = parse_arguments()
    
    results_dir = Path(args.output_dir) if args.output_dir else DEFAULT_RESULTS_DIR
    results_dir.mkdir(exist_ok=True, parents=True)

    predictions_dir = Path(args.input_dir) if args.input_dir else DEFAULT_PREDICTIONS_DIR

    files_to_process = []
    
    if args.input_file:
        in_path = Path(args.input_file).resolve()
        out_name = f"{in_path.stem}_evaluated.jsonl"
        try:
            rel_path = in_path.relative_to(predictions_dir.resolve())
            out_path = results_dir / rel_path.parent / out_name
        except ValueError:
            out_path = results_dir / out_name
        files_to_process.append((in_path, out_path))
    else:
        logger.info(f"Scanning {predictions_dir} recursively...")
        candidates = predictions_dir.rglob("*.jsonl")
        for input_f in candidates:
            if not input_f.is_file(): continue
            try:
                rel_path = input_f.relative_to(predictions_dir)
                out_path = results_dir / rel_path.parent / f"{input_f.stem}_evaluated.jsonl"
            except ValueError:
                out_path = results_dir / f"{input_f.stem}_evaluated.jsonl"
            files_to_process.append((input_f, out_path))
    with _DebouncedSigint():
        for in_f, out_f in files_to_process:
            process_file(in_f, out_f, args)


if __name__ == "__main__":
    main()