"""
Real World Experiment Runner

Runs inference for the Real World benchmark using pre-generated dataset files
(realworld-py.jsonl and realworld-py-all.jsonl). Executes both One-Step (line
coverage) and Two-Step (CoT) generation scripts for each model.

Usage:
    python step3_modelling/run_real_world_experiments_inference.py
"""
import argparse
import logging
import os
from pathlib import Path
import shutil
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

MODELS_TO_RUN = [
    "google/gemma-3-4b-it",
    "cyankiwi/Ministral-3-8B-Instruct-2512-AWQ-8bit",
    "mistralai/Ministral-3-3B-Reasoning-2512",
    "ibm-granite/granite-4.0-micro",
    "Qwen/Qwen3-4B-Instruct-2507",
]

GLOBAL_TEMPERATURES = [0.0]

PROJECT_ROOT = Path(__file__).resolve().parent
if PROJECT_ROOT.name in ["step3_modelling", "step4_evaluation"]:
    PROJECT_ROOT = PROJECT_ROOT.parent

TESTEVAL_DIR = PROJECT_ROOT / "TestEval"
PREDICTIONS_PATH = "/workspace/predictions" 

# Pre-existing Datasets (Must exist)
DATASET_BASE = TESTEVAL_DIR / "data" / "realworld-py.jsonl"
DATASET_ALL = TESTEVAL_DIR / "data" / "realworld-py-all.jsonl"

# Real-world system prompts (with mocking guidance)
SYSTEM_PROMPT_ONESTEP = TESTEVAL_DIR / "prompt" / "system_realworld.txt"
SYSTEM_PROMPT_TWOSTEP = TESTEVAL_DIR / "prompt" / "system_exec_realworld.txt"


def cleanup_disk_space():
    """
    Aggressively cleans up HuggingFace cache directories to free up space
    during extensive model runs.
    """
    # Only delete HuggingFace hub if you are really low on space.
    paths = ["/workspace/huggingface_cache/hub", "/root/.cache/huggingface/hub"] 
    
    for p in paths:
        if os.path.exists(p):
            try: shutil.rmtree(p); os.makedirs(p, exist_ok=True)
            except: pass
    os.system("sync")

def run_experiment(command):
    """Execute a command via subprocess in the TESTEVAL_DIR."""
    try: subprocess.run(command, check=True, text=True, encoding='utf-8', cwd=TESTEVAL_DIR)
    except: pass

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--quick-test", action="store_true")
    parser.add_argument("--passes", type=int, default=1)
    args = parser.parse_args()

    if not DATASET_BASE.exists() or not DATASET_ALL.exists():
        logging.error("CRITICAL ERROR: Real World Dataset files not found!")
        logging.error(f"Missing: {DATASET_BASE}")
        logging.error(f"Missing: {DATASET_ALL}")
        logging.error("Please run 'step2_data_preperation/create_realworld_dataset.py' first to generate these files.")
        return

    logging.info("Datasets verified. Starting inference pipeline...")

    if args.quick_test:
        models = [MODELS_TO_RUN[0]]
        temps = [0.2]
        runs = ["run_1"]
    else:
        models = MODELS_TO_RUN
        temps = GLOBAL_TEMPERATURES
        runs = [f"run_{i+1}" for i in range(args.passes)]
    
    BASE_SEED = 42

    for i, run_id in enumerate(runs):
        seed = BASE_SEED + i
        out_dir = os.path.join(PREDICTIONS_PATH, run_id)
        os.makedirs(out_dir, exist_ok=True)
        
        for model in models:
            safe_name = model.split("/", 1)[1] if "/" in model else model
            dtype = "bfloat16" if "gemma-3" in model.lower() else "float16"

            for temp in temps:
                # Pass full paths ensure the subprocess finds the file regardless of where it's running from
                
                # Command 1: Line Coverage
                cmd_l = ["python", "generate_targetcov_hf.py",
                         "--dataset-path", str(DATASET_BASE),
                         "--model", model, "--covmode", "line", "--dtype", dtype,
                         "--temperature", str(temp), "--seed", str(seed),
                         "--max-tokens", "4096", "--max-model-len", "8192",
                         "--system-prompt", str(SYSTEM_PROMPT_ONESTEP),
                         "--output-file", os.path.join(out_dir, f"linecov_{safe_name}_temp_{temp}.jsonl")]

                # Command 2: CoT Coverage
                cmd_c = ["python", "gen_linecov_cot_hf.py",
                         "--dataset-path", str(DATASET_ALL),
                         "--model", model, "--temperature", str(temp), "--seed", str(seed),
                         "--dtype", dtype,
                         "--max-tokens", "4096", "--max-model-len", "8192",
                         "--system-prompt", str(SYSTEM_PROMPT_TWOSTEP),
                         "--output-file", os.path.join(out_dir, f"linecov2_{safe_name}_temp_{temp}.jsonl")]
                
                if args.quick_test: 
                    cmd_l.append("--quick-test")
                    cmd_c.append("--quick-test")

                logging.info(f"Running: {' '.join(cmd_l)}")
                run_experiment(cmd_l)
                
                logging.info(f"Running: {' '.join(cmd_c)}")
                run_experiment(cmd_c)
            
            cleanup_disk_space()

if __name__ == "__main__":
    main()