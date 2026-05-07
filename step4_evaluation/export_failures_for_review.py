"""
Export Failing Test Cases as CSV for Manual Human Review

This script extracts failing test cases from evaluated results and exports them
as CSV files designed for a human researcher to open in Google Sheets and
manually categorize each failure. The goal is qualitative root-cause analysis:
identifying recurring patterns (e.g. "hallucinated API", "missing import"),
assessing proximity to success, and building mechanistic explanations for
why specific models fail on specific tasks.

Sampling strategy:
    - TestEval (initial & temperature): Stratified random sample of 50 failures,
      weighted toward top/mid/low-performing models for balanced coverage.
    - Real-World dataset: ALL unique failures exported (small enough for full review).

Output CSV columns include the generated test code, error output, auto-detected
patterns, and empty columns for the reviewer to fill in: root_cause_category,
specific_issue, proximity_to_success, recurring_pattern, and notes.

Usage:
    python step4_evaluation/export_failures_for_review.py
"""

import json
import logging
import random
import csv
from pathlib import Path
from collections import defaultdict
import re

logger = logging.getLogger(__name__)

# Configuration
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Sampling strategy for TestEval INITIAL (all 11 SLMs + Pynguin, 20 samples each)
TESTEVAL_INITIAL_SAMPLE_CONFIG = {
    "granite-4.0-micro": 20,
    "Qwen3-4B-Instruct-2507": 20,
    "Qwen3-4B-Thinking-2507": 20,
    "Qwen3-8B-AWQ": 20,
    "gemma-3-4b-it": 20,
    "Llama-3.2-3B-Instruct": 20,
    "Meta-Llama-3.1-8B-Instruct-AWQ-INT4": 20,
    "Ministral-3-3B-Instruct-2512": 20,
    "Ministral-3-3B-Reasoning-2512": 20,
    "Ministral-3-8B-Instruct-2512-AWQ-4bit": 20,
    "Ministral-3-8B-Instruct-2512-AWQ-8bit": 20,
    "pynguin_results": 20,
}

REALWORLD_SAMPLE_CONFIG = {
    "granite-4.0-micro": 20,
    "Qwen3-4B-Instruct-2507": 20,
    "gemma-3-4b-it": 20,
    "Ministral-3-3B-Reasoning-2512": 20,
    "Ministral-3-8B-Instruct-2512-AWQ-8bit": 20,
    "pynguin_results": 10,
}

# Sampling strategy for TestEval TEMPERATURE (all 5 models from that experiment)
TESTEVAL_TEMP_SAMPLE_CONFIG = {
    "granite-4.0-micro": 10,                     # Top performer
    "Qwen3-4B-Instruct-2507": 10,                # Mid-tier (note: different name in temp)
    "gemma-3-4b-it": 10,                         # Mid-tier
    "Ministral-3-3B-Reasoning-2512": 10,         # Reasoning model
    "Ministral-3-8B-Instruct-2512-AWQ-8bit": 10, # 8B quantized
}

# Failure modes mapping
FAILURE_MODES = {
    "Assertion Error": "Assertion",
    "Runtime Error": "Runtime",
    "Pytest Error": "Syntax",
    "Syntax Error": "Syntax",
    "Compile Error": "Syntax",
    "No Code": "NoCode",
    "Timeout": "Timeout",
    "Pass": "Pass"
}

# Root cause categories for manual analysis
ROOT_CAUSE_CATEGORIES = [
    "Missing imports",
    "Hallucinated APIs",
    "Incorrect assertion logic",
    "Type mismatches",
    "Off-by-one errors",
    "Context overflow",
    "Wrong test structure",
    "Edge case handling",
    "Other"
]


def extract_test_code_from_markdown(md_content, task_id):
    """Extract test code for a specific task from markdown failure log."""
    # Pattern: ## TASK: {task_num}_{target_line}
    pattern = rf"## TASK: {re.escape(task_id)}\s*\n.*?### Code\s*\n```python\n(.*?)```"
    match = re.search(pattern, md_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def extract_error_output_from_markdown(md_content, task_id):
    """Extract pytest error output for a specific task."""
    pattern = rf"## TASK: {re.escape(task_id)}\s*\n\*\*STATUS:\*\* (.*?)\n\n### Output\s*\n```text\n(.*?)```"
    match = re.search(pattern, md_content, re.DOTALL)
    if match:
        status = match.group(1).strip()
        output = match.group(2).strip()
        # Truncate very long outputs
        if len(output) > 2000:
            output = output[:1000] + "\n... [TRUNCATED] ...\n" + output[-500:]
        return status, output
    return None, None


def load_evaluation_results(eval_jsonl_path):
    """Load evaluation results from JSONL file."""
    results = []
    with open(eval_jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def load_predictions(pred_jsonl_path):
    """Load predictions with test code from JSONL file."""
    predictions = {}
    with open(pred_jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                task_num = str(data.get('task_num', ''))
                predictions[task_num] = data
    return predictions


def get_test_code_from_prediction(predictions, task_num, target_line):
    """Extract test code from prediction data.

    When target_line is None (e.g. initial_1 eval results have no per-line
    breakdown), fall back to the first available test in the task's tests dict.
    """
    task_num = str(task_num)

    if task_num not in predictions:
        return None

    task_data = predictions[task_num]
    tests = task_data.get('tests', {})

    # Try exact match first; fall back to first available test when target_line
    # is None or not found (initial_1 evals have target_line=None).
    target_line_str = str(target_line) if target_line is not None else None
    if target_line_str and target_line_str in tests:
        test_info = tests[target_line_str]
    elif tests:
        test_info = next(iter(tests.values()))
    else:
        return None

    if isinstance(test_info, dict):
        code = test_info.get('test_code', '')
    else:
        code = str(test_info)

    # Clean markdown code blocks
    code = re.sub(r'^```python\s*\n?', '', code)
    code = re.sub(r'\n?```$', '', code)
    return code.strip()


def analyze_failure_pattern(test_code, error_output, status):
    """Preliminary automatic pattern detection."""
    patterns = []

    if not test_code:
        return ["No code generated"]

    code_lower = test_code.lower()
    error_lower = (error_output or "").lower()

    # Import issues
    if "modulenotfounderror" in error_lower or "importerror" in error_lower:
        patterns.append("Import error")
    if "no module named" in error_lower:
        patterns.append("Missing module")

    # API hallucinations
    if "attributeerror" in error_lower and "has no attribute" in error_lower:
        patterns.append("Possible API hallucination")
    if "typeerror" in error_lower and "argument" in error_lower:
        patterns.append("Wrong function signature")

    # Assertion issues
    if "assertionerror" in error_lower:
        if "assert" in error_lower and "==" in error_lower:
            patterns.append("Value mismatch")
        if "none" in error_lower:
            patterns.append("Unexpected None")

    # Syntax issues
    if "syntaxerror" in error_lower or "indentationerror" in error_lower:
        patterns.append("Syntax/Indentation error")

    # Type issues
    if "typeerror" in error_lower:
        patterns.append("Type mismatch")

    # Index/Key errors
    if "indexerror" in error_lower:
        patterns.append("Index out of bounds")
    if "keyerror" in error_lower:
        patterns.append("Key not found")

    # Context overflow indicators
    if test_code and len(test_code) < 50:
        patterns.append("Possibly truncated")
    if test_code and not test_code.strip().startswith("def ") and not test_code.strip().startswith("import"):
        patterns.append("Incomplete test structure")

    return patterns if patterns else ["Needs manual review"]


def sample_failures_for_model(eval_dir, pred_dir, model_name, n_samples, run_num=1):
    """
    Collect and randomly sample failing test cases for a model, ensuring
    minimum coverage across different failure modes.

    If the total number of failures is <= n_samples, all failures are returned.
    Otherwise, failures are grouped by failure_mode and a roughly equal number
    is sampled from each mode (at least one per mode). Any remaining slots are
    filled by random sampling from the remaining failures.

    The resulting sample is randomized and biased toward failure-mode diversity,
    not proportional to the original failure distribution. Intended for manual
    qualitative analysis.
    """

    # Find evaluation files for this model
    eval_path = Path(eval_dir) / f"run_{run_num}"
    pred_path = Path(pred_dir) / f"run_{run_num}"

    # Look for files matching the model
    eval_files = list(eval_path.glob(f"*{model_name}*_evaluated.jsonl"))

    if not eval_files:
        # Try partial match
        eval_files = list(eval_path.glob("*_evaluated.jsonl"))
        eval_files = [f for f in eval_files if model_name.lower().replace("-", "").replace("_", "")
                      in f.name.lower().replace("-", "").replace("_", "")]

    # NoCode failures have no test code or error output to analyse — exclude them
    # so all sample slots go to real execution failures (Assertion, Runtime, Timeout).
    EXCLUDE_MODES = {"NoCode"}

    all_failures = []

    for eval_file in eval_files:
        # Load evaluation results
        results = load_evaluation_results(eval_file)

        # Find corresponding prediction file
        pred_filename = eval_file.name.replace("_evaluated.jsonl", ".jsonl")
        pred_file = pred_path / pred_filename

        predictions = {}
        if pred_file.exists():
            predictions = load_predictions(pred_file)

        # Load markdown for detailed error info
        md_file = eval_file.with_suffix('.md')
        md_content = ""
        if md_file.exists():
            md_content = md_file.read_text(encoding='utf-8', errors='ignore')

        # Collect failures
        for result in results:
            status = result.get('status', '')
            if status != 'Pass':
                failure_mode = FAILURE_MODES.get(status, status)
                if failure_mode in EXCLUDE_MODES:
                    continue

                task_num = result.get('task_num', '')
                target_line = result.get('target_line')  # None in initial_1

                # Markdown key: initial_1 uses "## TASK: {task_num}" with no
                # target_line; other datasets use "{task_num}_{target_line}".
                md_key = str(task_num) if target_line is None else f"{task_num}_{target_line}"
                task_id = md_key

                # Get test code
                test_code = get_test_code_from_prediction(predictions, task_num, target_line)

                # Get error output from markdown
                _, error_output = extract_error_output_from_markdown(md_content, md_key)

                # Extract config from filename
                config_match = re.search(r'temp_(\d+\.?\d*)', eval_file.name)
                temp = config_match.group(1) if config_match else "unknown"

                mode_match = re.search(r'(linecov2?|mutcov)', eval_file.name)
                mode = "Two-Step" if mode_match and "2" in mode_match.group(1) else "One-Step"

                # Skip entries where no test code could be retrieved
                if not test_code:
                    continue

                failure_info = {
                    'model': model_name,
                    'config': f"{mode}, T={temp}",
                    'task_id': task_id,
                    'task_num': task_num,
                    'target_line': target_line,
                    'failure_mode': failure_mode,
                    'raw_status': status,
                    'test_code': test_code,
                    'error_output': error_output or "[No output found]",
                    'auto_patterns': analyze_failure_pattern(test_code, error_output, status),
                    'source_file': eval_file.name,
                    'coverage': result.get('coverage', 0),
                    'mutation_score': result.get('mutation_score', None)
                }
                all_failures.append(failure_info)

    # Sample failures stratified by failure mode
    if len(all_failures) <= n_samples:
        return all_failures

    # Group failures by failure mode
    by_mode = defaultdict(list)
    for f in all_failures:
        by_mode[f['failure_mode']].append(f)

    sampled = []
    samples_per_mode = max(1, n_samples // len(by_mode))

    for mode, failures in by_mode.items():
        n_take = min(len(failures), samples_per_mode)
        sampled.extend(random.sample(failures, n_take))

    # Fill remaining quota
    remaining = [f for f in all_failures if f not in sampled]
    if len(sampled) < n_samples and remaining:
        additional = min(n_samples - len(sampled), len(remaining))
        sampled.extend(random.sample(remaining, additional))

    return sampled[:n_samples]


def get_all_realworld_failures(eval_dir, pred_dir, run_num=1, deduplicate=True):
    """
    Get failures from real-world dataset for comprehensive analysis.

    Args:
        eval_dir: Evaluation results directory
        pred_dir: Predictions directory
        run_num: Run number to analyze
        deduplicate: If True, keep only one failure per (model, task_num) to avoid
                     counting the same test multiple times across target_lines
    """
    all_failures = []
    seen_tests = set()  # (model, task_num) pairs

    eval_path = Path(eval_dir) / f"run_{run_num}"
    pred_path = Path(pred_dir) / f"run_{run_num}"

    eval_files = list(eval_path.glob("*_evaluated.jsonl"))

    for eval_file in eval_files:
        # Extract model name from filename
        name_parts = eval_file.stem.replace("_evaluated", "").split("_")
        # Find model name (between linecov and temp)
        model_name = "_".join([p for p in name_parts if p not in ["linecov", "linecov2", "temp"] and not p.replace(".", "").isdigit()])

        results = load_evaluation_results(eval_file)

        pred_filename = eval_file.name.replace("_evaluated.jsonl", ".jsonl")
        pred_file = pred_path / pred_filename

        predictions = {}
        if pred_file.exists():
            predictions = load_predictions(pred_file)

        md_file = eval_file.with_suffix('.md')
        md_content = ""
        if md_file.exists():
            md_content = md_file.read_text(encoding='utf-8', errors='ignore')

        for result in results:
            status = result.get('status', '')
            if status != 'Pass':
                task_num = result.get('task_num', '')
                target_line = result.get('target_line', '')
                task_id = f"{task_num}_{target_line}"

                # Deduplication: only keep first failure per (model, task_num)
                dedup_key = (model_name, task_num)
                if deduplicate and dedup_key in seen_tests:
                    continue
                seen_tests.add(dedup_key)

                test_code = get_test_code_from_prediction(predictions, task_num, target_line)
                _, error_output = extract_error_output_from_markdown(md_content, task_id)

                config_match = re.search(r'temp_(\d+\.?\d*)', eval_file.name)
                temp = config_match.group(1) if config_match else "unknown"

                mode_match = re.search(r'(linecov2?|mutcov)', eval_file.name)
                mode = "Two-Step" if mode_match and "2" in mode_match.group(1) else "One-Step"

                failure_info = {
                    'model': model_name,
                    'config': f"{mode}, T={temp}",
                    'task_id': task_id,
                    'task_num': task_num,
                    'target_line': target_line,
                    'failure_mode': FAILURE_MODES.get(status, status),
                    'raw_status': status,
                    'test_code': test_code or "[No code found]",
                    'error_output': error_output or "[No output found]",
                    'auto_patterns': analyze_failure_pattern(test_code, error_output, status),
                    'source_file': eval_file.name,
                    'coverage': result.get('coverage', 0),
                    'mutation_score': result.get('mutation_score', None)
                }
                all_failures.append(failure_info)

    return all_failures


def write_analysis_csv(failures, output_path, include_manual_columns=True):
    """Write failures to CSV with columns for manual analysis."""
    if not failures:
        logger.info(f"No failures to write to {output_path}")
        return

    fieldnames = [
        'id',
        'model',
        'config',
        'task_id',
        'failure_mode',
        'auto_detected_patterns',
        'test_code',
        'error_output_summary',
    ]

    if include_manual_columns:
        fieldnames.extend([
            # Manual analysis columns
            'root_cause_category',
            'specific_issue',
            'proximity_to_success',  # High/Medium/Low
            'recurring_pattern',     # Yes/No
            'notes'
        ])

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for i, failure in enumerate(failures, 1):
            # Truncate long fields for CSV readability
            test_code = failure['test_code']
            if len(test_code) > 1500:
                test_code = test_code[:750] + "\n... [TRUNCATED] ...\n" + test_code[-500:]

            # Keep END of error output (contains actual error message)
            # Also prefix with ' to prevent Google Sheets formula interpretation
            error_summary = failure['error_output']
            if len(error_summary) > 1000:
                # Keep last 800 chars (actual error) + first 150 chars (context)
                error_summary = error_summary[:150] + "\n... [TRUNCATED - showing end] ...\n" + error_summary[-800:]

            # Prefix with single quote to force text mode in Google Sheets
            # This prevents cells starting with = or - being interpreted as formulas
            def escape_for_sheets(text):
                """Prefix with ' if text could be interpreted as formula."""
                if text and len(text) > 0:
                    first_char = text.strip()[0] if text.strip() else ''
                    if first_char in ('=', '+', '-', '@'):
                        return "'" + text
                return text

            row = {
                'id': i,
                'model': failure['model'],
                'config': failure['config'],
                'task_id': failure['task_id'],
                'failure_mode': failure['failure_mode'],
                'auto_detected_patterns': "; ".join(failure['auto_patterns']),
                'test_code': escape_for_sheets(test_code),
                'error_output_summary': escape_for_sheets(error_summary),
            }

            if include_manual_columns:
                row.update({
                    'root_cause_category': '',
                    'specific_issue': '',
                    'proximity_to_success': '',
                    'recurring_pattern': '',
                    'notes': ''
                })

            writer.writerow(row)

    logger.info(f"Written {len(failures)} failures to {output_path}")


def write_detailed_analysis_report(failures, output_path):
    """Write a detailed markdown report for easier manual review."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Error Analysis Report for Manual Review\n\n")
        f.write("## Instructions\n\n")
        f.write("For each failure below, analyze and record:\n")
        f.write("1. **Root Cause Category**: " + ", ".join(ROOT_CAUSE_CATEGORIES) + "\n")
        f.write("2. **Proximity to Success**: Would a minor fix allow the test to pass? (High/Medium/Low)\n")
        f.write("3. **Recurring Pattern**: Is this error pattern seen in other failures?\n\n")
        f.write("---\n\n")

        # Group by model for easier analysis
        by_model = defaultdict(list)
        for f_info in failures:
            by_model[f_info['model']].append(f_info)

        for model, model_failures in by_model.items():
            f.write(f"# Model: {model}\n\n")
            f.write(f"Total failures in sample: {len(model_failures)}\n\n")

            # Summary by failure mode
            mode_counts = defaultdict(int)
            for mf in model_failures:
                mode_counts[mf['failure_mode']] += 1

            f.write("### Failure Mode Distribution\n")
            for mode, count in sorted(mode_counts.items(), key=lambda x: -x[1]):
                f.write(f"- {mode}: {count}\n")
            f.write("\n---\n\n")

            for i, failure in enumerate(model_failures, 1):
                f.write(f"## Failure {i}: {failure['task_id']}\n\n")
                f.write(f"**Config**: {failure['config']}\n\n")
                f.write(f"**Failure Mode**: {failure['failure_mode']}\n\n")
                f.write(f"**Auto-detected Patterns**: {', '.join(failure['auto_patterns'])}\n\n")

                f.write("### Generated Test Code\n")
                f.write("```python\n")
                f.write(failure['test_code'][:2000])
                if len(failure['test_code']) > 2000:
                    f.write("\n# ... [TRUNCATED] ...")
                f.write("\n```\n\n")

                f.write("### Error Output\n")
                f.write("```\n")
                error_out = failure['error_output'][:1500]
                f.write(error_out)
                if len(failure['error_output']) > 1500:
                    f.write("\n... [TRUNCATED] ...")
                f.write("\n```\n\n")

                f.write("### Manual Analysis (Fill in)\n")
                f.write("- **Root Cause**: \n")
                f.write("- **Specific Issue**: \n")
                f.write("- **Proximity to Success**: [High/Medium/Low]\n")
                f.write("- **Recurring Pattern**: [Yes/No]\n")
                f.write("- **Notes**: \n\n")
                f.write("---\n\n")

    logger.info(f"Written detailed report to {output_path}")


def collect_samples_for_config(eval_dir, pred_dir, sample_config):
    """Collect stratified failure samples across models per a sampling config."""
    all_samples = []
    for model_name, n_samples in sample_config.items():
        samples = sample_failures_for_model(eval_dir, pred_dir, model_name, n_samples)
        logger.info(f"  {model_name}: requested {n_samples}, got {len(samples)}")
        all_samples.extend(samples)
    return all_samples


def safe_write_csv(failures, output_path):
    """Write CSV only if file does not exist or has no filled manual annotations."""
    output_path = Path(output_path)
    if output_path.exists():
        with open(output_path, encoding='utf-8') as f:
            existing = list(csv.DictReader(f))
        filled = sum(1 for r in existing if r.get('root_cause_category', '').strip())
        if filled > 0:
            logger.warning(
                f"SKIPPED writing {output_path.name} — {filled} rows already have manual annotations. "
                f"Delete or rename the file first if you want to re-export."
            )
            return
    write_analysis_csv(failures, output_path)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    base_path = Path(__file__).parent.parent
    output_dir = base_path / "step4_evaluation" / "error_analysis_output"
    output_dir.mkdir(exist_ok=True)

    # TestEval Initial Pass-1 (greedy, T=0.0) — ~8 samples per model, all 11 models
    initial_1_samples = collect_samples_for_config(
        base_path / "evaluation_results_initial_1",
        base_path / "TestEval" / "predictions_initial_1",
        TESTEVAL_INITIAL_SAMPLE_CONFIG,
    )
    safe_write_csv(initial_1_samples, output_dir / "initial_1_failure_analysis.csv")
    logger.info(f"Exported {len(initial_1_samples)} initial_1 failures to {output_dir}/")

    realworld_1_samples = collect_samples_for_config(
        base_path / "evaluation_results_realworld_1",
        base_path / "TestEval" / "predictions_realworld_1",
        REALWORLD_SAMPLE_CONFIG,
    )
    safe_write_csv(realworld_1_samples, output_dir / "realworld_1_failure_analysis.csv")
    logger.info(f"Exported {len(realworld_1_samples)} realworld_1 failures to {output_dir}/")


if __name__ == "__main__":
    main()
