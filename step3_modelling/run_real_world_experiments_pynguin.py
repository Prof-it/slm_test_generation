"""
Pynguin Baseline Runner

Uses the Pynguin automated test generation tool (DynaMOSA algorithm) to generate
regression test suites for the Real World dataset. Mimics the SLM output format
for direct comparison in the evaluation step.
"""
import sys
import os
import logging
import argparse
import subprocess
import time
import json
import re
import tempfile
from pathlib import Path
from tqdm import tqdm


# This simulates the libraries existing so Pynguin doesn't crash on import
from unittest.mock import MagicMock
sys.modules["vllm"] = MagicMock()
sys.modules["accelerate"] = MagicMock()
sys.modules["deepspeed"] = MagicMock()
sys.modules["triton"] = MagicMock()


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTEVAL_DIR = PROJECT_ROOT / "TestEval"
DATA_PATH = TESTEVAL_DIR / "data" / "realworld-py.jsonl"
OUTPUT_DIR = TESTEVAL_DIR / "predictions_testeval_pynguin"

# Pynguin Configuration
# DYNAMOSA is the default and generally best performing algorithm according to the paper
ALGORITHM = "DYNAMOSA" 
# 120 seconds per task to be comparable with SLM inference time (usually 30-90s)
MAX_SEARCH_TIME = 120 

# Maps source filenames to their full installed module paths.
# Used to rewrite relative imports (e.g., "from .broker import get_broker")
# into absolute imports (e.g., "from dramatiq.broker import get_broker")
# so Pynguin can import the standalone solution_pkg.py without errors.
MODULE_PATH_MAP = {
    "apscheduler_expressions.py": "apscheduler.triggers.cron.expressions",
    "dramatiq_message.py": "dramatiq.message",
    "encode__utils.py": "httpx._utils",
    "humanize_time.py": "humanize.time",
    "requests_utils.py": "requests.utils",
    "scrapy_url.py": "scrapy.utils.url",
    "pandas_numeric.py": "pandas.core.tools.numeric",
    "pandas_common.py": "pandas.io.common",
    "pytorch_utils.py": "torch.nn.modules.utils",
    "transformers_activations.py": "transformers.activations",
    "vllm_hashing.py": "vllm.utils.hashing",
    "scikit_validation.py": "sklearn.utils.validation",
    "our_evaluate_results.py": None,
    "our_run_experiments.py": None,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def rewrite_relative_imports(source_code, task_title):
    """Rewrite relative imports to absolute imports using the module path map.

    Pynguin writes source code to a standalone file (solution_pkg.py) which has
    no parent package. Relative imports like `from .broker import get_broker`
    fail with ImportError. This rewrites them to absolute imports so the installed
    packages resolve correctly.
    """
    # Extract filename from task_title: "RealWorld::filename.py::func_name"
    parts = task_title.split("::")
    if len(parts) < 2:
        return source_code

    filename = parts[1]
    module_path = MODULE_PATH_MAP.get(filename)
    if not module_path:
        return source_code

    module_parts = module_path.split(".")

    def replace_relative_import(match):
        dots = match.group(1)
        rest = match.group(2)
        num_dots = len(dots)

        if num_dots >= len(module_parts):
            return match.group(0)  # Can't resolve, leave as-is

        prefix = ".".join(module_parts[:-num_dots])
        if rest.startswith("import "):
            # "from . import certs" -> "from requests import certs"
            return f"from {prefix} {rest}"
        else:
            # "from .broker import x" -> "from dramatiq.broker import x"
            return f"from {prefix}.{rest}"

    # Match: from (dots) [optional-whitespace] (optional-module-name import names)
    # The \s* after dots handles "from . import x" (space between dot and import)
    pattern = r"from\s+(\.+)\s*((?:\w[\w.]*\s+)?import\s+.+)"
    return re.sub(pattern, replace_relative_import, source_code)


def parse_args():
    parser = argparse.ArgumentParser(description="Run Pynguin Baseline Experiments")
    parser.add_argument("--passes", type=int, default=10, help="Number of passes to run")
    parser.add_argument("--quick-test", action="store_true", help="Run only first 2 tasks for debugging")
    return parser.parse_args()

def check_pynguin_availability():
    """Ensures Pynguin is installed and runnable."""
    try:
        # Run help and capture output
        result = subprocess.run(
            [sys.executable, "-m", "pynguin", "--help"], 
            capture_output=True, 
            text=True,  # Ensure output is string, not bytes
            check=True
        )
    except subprocess.CalledProcessError as e:
        logging.error("Pynguin execution failed!")
        logging.error(f"Return Code: {e.returncode}")
        logging.error(f"Standard Error Output:\n{e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        logging.error("Python interpreter not found.")
        sys.exit(1)

def run_pynguin_for_task(task, seed):
    """
    Sets up a temp environment, writes the code, runs Pynguin, and extracts the test.
    """
    task_id = task['task_num']
    func_name = task['func_name']
    task_title = task.get('task_title', '')
    source_code = task['python_solution']

    # Rewrite relative imports to absolute so the standalone file can import them
    source_code = rewrite_relative_imports(source_code, task_title)

    # Pynguin needs a module name. We'll use 'solution_pkg'
    module_name = "solution_pkg"

    start_time = time.time()
    generated_code = ""
    status = "NO_CODE"
    
    with tempfile.TemporaryDirectory(prefix=f"pynguin_{task_id}_") as temp_dir:
        temp_path = Path(temp_dir)
        
        source_file = temp_path / f"{module_name}.py"
        try:
            source_file.write_text(source_code, encoding="utf-8")
        except Exception as e:
            logging.error(f"Failed to write source code for task {task_id}: {e}")
            return None

        # Prepare Pynguin command. Pynguin outputs to the 'pynguin-results' folder inside output_path by default
        cmd = [
            sys.executable, "-m", "pynguin",
            "--project-path", str(temp_path),
            "--output-path", str(temp_path),
            "--module-name", module_name,
            "--algorithm", ALGORITHM,
            "--maximum-search-time", str(MAX_SEARCH_TIME),
            "--seed", str(seed),
            "--verbose" 
        ]

        # Pynguin requires this env var to acknowledge executing arbitrary code
        env = os.environ.copy()
        env["PYNGUIN_DANGER_AWARE"] = "true"

        try:
            proc = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=MAX_SEARCH_TIME + 30 # Grace period for startup/shutdown
            )
            
            # Harvest results, Pynguin generates: test_{module_name}.py
            expected_test_file = temp_path / f"test_{module_name}.py"
            
            if expected_test_file.exists():
                generated_code = expected_test_file.read_text(encoding="utf-8")
                status = "DONE"
            else:
                logging.warning(f"Pynguin CRASH for Task {task_id}.")
                error_msg = proc.stderr
                if not error_msg: error_msg = proc.stdout  # Sometimes Pynguin prints errors to stdout
                logging.warning(f"Reason: {error_msg[-500:] if error_msg else 'Unknown/Silent Crash'}")
                with open("pynguin_crash_log.txt", "a", encoding="utf-8") as err_log:
                    err_log.write(f"\n{'='*20} TASK {task_id} CRASH {'='*20}\n")
                    err_log.write(error_msg if error_msg else "No output captured.")
                    err_log.write("\n")
                
                status = "NO_CODE"

        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
            logging.warning(f"Task {task_id} Timed Out.")
        except Exception as e:
            logging.error(f"Pynguin execution failed for task {task_id}: {e}")
            status = "ERROR"

    duration = time.time() - start_time
    
    approx_tokens = int(len(generated_code) / 4)
    tps = approx_tokens / duration if duration > 0 else 0
    
    tests_map = {}
    if status == "DONE":
        # Modify the generated code to import from 'under_test' instead of 'solution_pkg'
        # This matches the harness expectation in our_evaluate_results.py
        generated_code = generated_code.replace(f"import {module_name} as module_0", "import under_test as module_0")
        generated_code = generated_code.replace(f"import {module_name}", "import under_test")
        
        target_lines = task.get('target_lines', [])
        for line in target_lines:
            tests_map[str(line)] = {
                "test_code": generated_code,
                "generated_tokens": approx_tokens
            }
            
    return {
        "task_num": task_id,
        "task_title": task.get('task_title', 'Unknown'),
        "code": source_code,
        "model": "Pynguin-DynaMOSA",
        "temperature": 0.0, # Not applicable, but keeps schema compatible
        "status": "Pass" if status == "DONE" else status, # Using 'Pass' to mean generation succeeded
        "tests": tests_map,
        "timed_out": status == "TIMEOUT",
        "performance_batch": {
            "duration_seconds": round(duration, 4),
            "total_generated_tokens": approx_tokens, # Not applicable, but keeps schema compatible
            "tokens_per_second": round(tps, 2) # Not applicable, but keeps schema compatible
        }
    }

def main():
    args = parse_args()
    check_pynguin_availability()
    
    if not DATA_PATH.exists():
        logging.error(f"Data file not found at: {DATA_PATH}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Loading data from {DATA_PATH}...")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        dataset = [json.loads(line) for line in f]
    
    if args.quick_test:
        logging.info("Quick test mode: running only 2 tasks.")
        dataset = dataset[:2]

    total_start_time = time.time()
    BASE_SEED = 42

    for i in range(args.passes):
        run_id = f"run_{i+1}"
        current_seed = BASE_SEED + i
        
        output_file = OUTPUT_DIR / f"{run_id}" / "pynguin_results.jsonl"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"=== Starting {run_id.upper()} (Seed: {current_seed}) ===")
        
        completed_ids = set()
        if output_file.exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try: completed_ids.add(json.loads(line)['task_num'])
                    except: pass
            logging.info(f"Resuming {run_id}: {len(completed_ids)} tasks already done.")

        with open(output_file, 'a', encoding='utf-8') as f_out:
            for task in tqdm(dataset, desc=f"Processing {run_id}"):
                if task['task_num'] in completed_ids:
                    continue
                
                result = run_pynguin_for_task(task, current_seed)
                
                if result:
                    f_out.write(json.dumps(result) + "\n")
                    f_out.flush()

    total_duration = time.time() - total_start_time
    logging.info(f"All {args.passes} Pynguin runs completed in {total_duration:.2f}s.")
    logging.info(f"Results saved to: {OUTPUT_DIR}")
    
    if os.path.exists("pynguin_crash_log.txt"):
        logging.warning("!!! ERRORS DETECTED !!! Check 'pynguin_crash_log.txt' to see why Pynguin failed.")

if __name__ == "__main__":
    main()