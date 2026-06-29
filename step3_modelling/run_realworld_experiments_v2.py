"""
RealWorldTests-Py v2 — Inference Runner

Runs all 5 SLMs across all 3 context tiers (A / B / C) on the v2 dataset.
For each combination the script calls the existing TestEval inference script
(generate_targetcov_hf.py) with the appropriate tier JSONL and system prompt.

Output layout (on GPU machine):
    /workspace/predictions/v2/
        tier_A/
            linecov_<model>_temp_0.0.jsonl
        tier_B/
            linecov_<model>_temp_0.0.jsonl
        tier_C/
            linecov_<model>_temp_0.0.jsonl

Prerequisites:
    python step2_data_preperation/prepare_v2_tier_datasets.py
    (generates TestEval/data/realworld-py-v2-tier-{A,B,C}.jsonl)

Usage:
    python step3_modelling/run_realworld_experiments_v2.py
    python step3_modelling/run_realworld_experiments_v2.py --quick-test   # 1 model, tier A only
    python step3_modelling/run_realworld_experiments_v2.py --tiers A B    # specific tiers
"""

import argparse
import logging
import os
import shutil
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Config ───────────────────────────────────────────────────────────────────

MODELS_TO_RUN = [
    "google/gemma-4-E4B-it",
    "Qwen/Qwen3.5-4B",
    "Qwen/Qwen3-4B-Thinking-2507",
    "mistralai/Ministral-3-3B-Reasoning-2512",
    "ibm-granite/granite-4.0-micro",
]

GLOBAL_TEMPERATURES = [0.0]
TIERS = ["A", "B", "C"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTEVAL_DIR = PROJECT_ROOT / "TestEval"
PREDICTIONS_BASE = "/workspace/predictions/v2"

TIER_DATASETS = {
    tier: TESTEVAL_DIR / "data" / f"realworld-py-v2-tier-{tier}.jsonl"
    for tier in TIERS
}

TIER_PROMPTS = {
    tier: TESTEVAL_DIR / "prompt" / f"system_v2_tier_{tier}.txt"
    for tier in TIERS
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def cleanup_disk_space():
    for path in ["/workspace/huggingface_cache/hub", "/root/.cache/huggingface/hub",
                 "/root/.cache/vllm"]:
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                os.makedirs(path, exist_ok=True)
            except Exception:
                pass
    os.system("sync")


def run_cmd(cmd: list[str]) -> None:
    logging.info(f"  $ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, text=True, encoding="utf-8", cwd=TESTEVAL_DIR)
    except subprocess.CalledProcessError as e:
        logging.error(f"  Command failed (exit {e.returncode}) — continuing")


def check_datasets(tiers: list[str]) -> bool:
    ok = True
    for tier in tiers:
        p = TIER_DATASETS[tier]
        if not p.exists():
            logging.error(f"Missing tier dataset: {p}")
            logging.error("Run: python step2_data_preperation/prepare_v2_tier_datasets.py")
            ok = False
    return ok


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run v2 tier inference for all SLMs")
    parser.add_argument("--quick-test", action="store_true",
                        help="One model, Tier A only, first task — smoke test")
    parser.add_argument("--tiers", nargs="+", choices=["A", "B", "C"], default=TIERS,
                        help="Which tiers to run (default: A B C)")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Override model list (default: all 5)")
    parser.add_argument("--temperature", type=float, default=None,
                        help="Override temperature (default: 0.0)")
    args = parser.parse_args()

    tiers   = ["A"] if args.quick_test else args.tiers
    models  = [MODELS_TO_RUN[0]] if args.quick_test else (args.models or MODELS_TO_RUN)
    temps   = [0.2] if args.quick_test else ([args.temperature] if args.temperature else GLOBAL_TEMPERATURES)

    logging.info("=== RealWorldTests-Py v2 Inference ===")
    logging.info(f"  Models:      {len(models)}")
    logging.info(f"  Tiers:       {tiers}")
    logging.info(f"  Temperatures:{temps}")
    logging.info(f"  Output:      {PREDICTIONS_BASE}")

    if not check_datasets(tiers):
        return

    for tier in tiers:
        dataset_path = TIER_DATASETS[tier]
        system_prompt = TIER_PROMPTS[tier]
        out_dir = os.path.join(PREDICTIONS_BASE, f"tier_{tier}")
        os.makedirs(out_dir, exist_ok=True)

        logging.info(f"\n{'='*60}")
        logging.info(f"TIER {tier} — dataset: {dataset_path.name}")
        logging.info(f"{'='*60}")

        for model in models:
            safe_name = model.split("/", 1)[1] if "/" in model else model
            # gemma uses bfloat16, everything else float16
            dtype = "bfloat16" if "gemma" in model.lower() else "float16"

            for temp in temps:
                out_file = os.path.join(out_dir, f"linecov_{safe_name}_temp_{temp}.jsonl")

                logging.info(f"\n  [{tier}] {safe_name}  T={temp}")

                cmd = [
                    "python", "generate_targetcov_hf.py",
                    "--dataset-path",   str(dataset_path),
                    "--model",          model,
                    "--covmode",        "line",
                    "--dtype",          dtype,
                    "--temperature",    str(temp),
                    "--seed",           "42",
                    "--max-tokens",     "8192",
                    "--max-model-len",  "16384",
                    "--max-num-seqs",   "4",
                    "--gen-timeout",    "480",
                    "--repetition-penalty", "1.15",
                    "--system-prompt",  str(system_prompt),
                    "--output-file",    out_file,
                ]

                if args.quick_test:
                    cmd.append("--quick-test")

                run_cmd(cmd)

            cleanup_disk_space()

    logging.info("\nInference complete.")
    logging.info(f"Predictions at: {PREDICTIONS_BASE}")
    logging.info("Next: python step4_evaluation/evaluate_results.py --input-dir "
                 f"{PREDICTIONS_BASE} --dataset TestEval/data/realworld-py-v2.jsonl")


if __name__ == "__main__":
    main()
