"""
Master Experiment Runner

Generates unit tests using a predefined list of Small Language Models (SLMs).
Performs sequential runs (passes) to ensure statistical significance for Pass@1 metrics.
"""
import argparse
import subprocess
import os
import logging
import time
import shutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

MODELS_TO_RUN = [

    # Gemma
    "google/gemma-4-E4B-it",

    # Qwen Family - keeping the reasoning/thinking variants, dropping the plain Instruct ones
    "Qwen/Qwen3.5-4B", # Defaults to thinking mode, run as-is (no --disable-thinking)
    #"Qwen/Qwen3-4B-Instruct-2507", # Dropped: keeping only the Thinking variant below
    "Qwen/Qwen3-4B-Thinking-2507",
    #"Qwen/Qwen3-8B-AWQ"

    # Mistral Family - keeping the reasoning variant, dropping the plain Instruct one
    #"cyankiwi/Ministral-3-8B-Instruct-2512-AWQ-8bit",
    #"cyankiwi/Ministral-3-8B-Instruct-2512-AWQ-4bit",
    #"mistralai/Ministral-3-3B-Instruct-2512", # Dropped: keeping only the Reasoning variant below
    "mistralai/Ministral-3-3B-Reasoning-2512",

    # IBM Granite
    "ibm-granite/granite-4.0-micro",

    # Meta Llama Family
    #"meta-llama/Llama-3.2-3B-Instruct",
    #"hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4",
]

GLOBAL_TEMPERATURES = [0.0]
TESTEVAL_PATH = "./TestEval"
# For RunPod/Docker environment
PREDICTIONS_PATH = "/workspace/predictions" 

def cleanup_disk_space():
    """
    Deletes HuggingFace cache and vLLM compilation cache to free up space 
    between model runs.
    """
    paths_to_clear = [
        "/workspace/huggingface_cache/hub", # Where the heavy model weights are
        "/root/.cache/vllm",                # vLLM compilation cache (can get huge)
        "/root/.cache/huggingface/hub"      # Fallback default location
    ]

    for path in paths_to_clear:
        if os.path.exists(path):
            try:
                logging.info(f"Removing contents of: {path}")
                shutil.rmtree(path)
                # Re-create the empty directory structure so tools don't crash
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                logging.warning(f"Error cleaning {path}: {e}")
        else:
            logging.debug(f"Path not found (skipping): {path}")
    
    # Run a system sync to ensure OS registers freed space
    os.system("sync")

def run_experiment(command):
    """
    Executes a command and waits for it to complete.
    """
    try:
        output_file_index = command.index("--output-file") + 1
        experiment_name = os.path.basename(command[output_file_index])
    except (ValueError, IndexError):
        experiment_name = "unknown_experiment"

    logging.info(f"Starting/Resuming: {experiment_name}")

    try:
        subprocess.run(
            command, 
            check=True, 
            text=True, 
            encoding='utf-8', 
            cwd=TESTEVAL_PATH
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"Experiment '{experiment_name}' failed with exit code {e.returncode}.")
    except FileNotFoundError:
        logging.error(f"Command not found: {command[0]}.")


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Run SLM benchmark experiments.")
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="Run only 1 run, 1 model, 1 temp for pipeline verification."
    )
    parser.add_argument("--passes", type=int, default=1, help="Number of sequential passes (runs) to perform.")
    return parser.parse_args()


def main():
    """Main function to orchestrate all experiments sequentially."""
    args = parse_args()
    
    if args.quick_test:
        logging.info("Quick test mode: 1 model, 1 temperature, 1 run.")
        target_temperatures = [0.2]
        models_to_process = [MODELS_TO_RUN[0]]
        run_ids = ["run_1"]
    else:
        logging.info(f"Full benchmark mode ({args.passes} passes).")
        target_temperatures = GLOBAL_TEMPERATURES
        models_to_process = MODELS_TO_RUN
        run_ids = [f"run_{i+1}" for i in range(args.passes)]

    total_start_time = time.time()

    BASE_SEED = 42

    for i, run_id in enumerate(run_ids):
        # Run 1 uses 42, Run 2 uses 43, Run 3 uses 44
        current_run_seed = BASE_SEED + i

        logging.info(f"Starting batch: {run_id}")

        run_output_dir_abs = os.path.join(PREDICTIONS_PATH, run_id)
        os.makedirs(run_output_dir_abs, exist_ok=True)

        # Instead of building a list of all commands, we execute them per model
        # so we can delete the model immediately after it is used.
        
        count = 1
        total_exps = len(models_to_process) * len(target_temperatures) * 2

        for model in models_to_process:
            # Clean model name for filenames (replace / with -)
            if "/" in model:
                model_safe_name = model.split("/", 1)[1]
            else:
                model_safe_name = model
            
            current_dtype = "float16"
            # Gemma 3 requires bfloat16. Others work fine with float16.
            if "gemma-3" in model.lower():
                current_dtype = "bfloat16"
                logging.info(f"Detected Gemma 3. Forcing dtype to {current_dtype}")


            for temp in target_temperatures:
                
                # 1. Line Coverage Command
                final_linecov_name = f"linecov_{model_safe_name}_temp_{temp}.jsonl"
                full_output_path_line = os.path.join(run_output_dir_abs, final_linecov_name)
                
                command_linecov = [
                    "python", "generate_targetcov_hf.py",
                    "--model", model,
                    "--covmode", "line",
                    "--dtype", current_dtype,
                    "--temperature", str(temp),
                    "--seed", str(current_run_seed),
                    "--max-tokens", "8192",
                    "--max-model-len", "16384",
                    "--max-num-seqs", "4",
                    "--gen-timeout", "480",
                    "--repetition-penalty", "1.15",
                    "--output-file", full_output_path_line
                ]

                # 2. Chain-of-Thought (CoT) Command
                final_cot_name = f"linecov2_{model_safe_name}_temp_{temp}.jsonl"
                full_output_path_cot = os.path.join(run_output_dir_abs, final_cot_name)

                command_cot = [
                    "python", "gen_linecov_cot_hf.py",
                    "--model", model,
                    "--temperature", str(temp),
                    "--seed", str(current_run_seed),
                    "--dtype", current_dtype,
                    "--max-tokens", "8192",
                    "--max-model-len", "16384",
                    "--max-num-seqs", "4",
                    "--gen-timeout", "480",
                    "--repetition-penalty", "1.15",
                    "--output-file", full_output_path_cot
                ]
                
                if args.quick_test:
                    command_linecov.append("--quick-test")
                    command_cot.append("--quick-test")
                
                # Execute Line Coverage
                logging.info(f"[{run_id}] Step {count}/{total_exps} (Part A)")
                run_experiment(command_linecov)
                
                # Execute CoT
                logging.info(f"[{run_id}] Step {count}/{total_exps} (Part B)")
                run_experiment(command_cot)
                
                count += 1

            cleanup_disk_space()

    total_duration = time.time() - total_start_time
    logging.info(f"All {args.passes} benchmark runs completed in {total_duration:.2f}s.")

if __name__ == "__main__":
    main()