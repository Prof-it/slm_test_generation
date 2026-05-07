"""
LLM-as-Judge Unit Test Quality Evaluation

Double-blind, double-pass pairwise evaluation of LLM-generated unit tests using
Claude as judge. Mitigates position bias by swapping A/B order between passes.

Scoring: 4 criteria × 1-5 Likert (max 20 per pass, 40 total). Equal weighting.
Null-test veto: if Assertions = 1, total score = 1 regardless of other criteria.

Bias detection:
- Position bias: Pass1 winner = A (pos1), Pass2 winner = B (pos1 after swap) -> Invalid
- Stochastic noise: passes disagree AND score variance > 4.0 -> Stochastic_Noise
- Clean judgment: A wins both OR B wins both

Usage:
    python step3_modelling/llm_as_judge.py --predictions_dir TestEval/predictions_realworld_1 --eval_dir evaluation_results_realworld_1 --evaluation_group full_factorial --output_dir TestEval/predictions_judgellm
"""

import argparse
import json
import os
import logging
import glob
import time
import itertools
import hashlib
import pandas as pd
from tqdm import tqdm
import anthropic
from anthropic import RateLimitError, APIError
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()


LOG_FILE = os.path.join(os.path.dirname(__file__), 'llm_as_judge_logs.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


DEFAULT_MODEL = "claude-sonnet-4-6" 
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# T=0.1 allows slight variance to test if the reasoning is robust.
JUDGE_TEMPERATURE = 0.1 

# Pricing dollar
PRICE_INPUT_PER_M = 3.00
PRICE_OUTPUT_PER_M = 15.00

if not ANTHROPIC_API_KEY:
    raise ValueError("Please set the ANTHROPIC_API_KEY environment variable.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL_NAME = DEFAULT_MODEL

TIE_THRESHOLD = 2.0  # 5% deviation on 40-point double-pass scale

SYSTEM_PROMPT = """You are a Senior QA Engineer evaluating unit test quality.
Analyze the test design step-by-step against the criteria.

IMPORTANT GUIDELINES:
1. REASONING FIRST: You must output textual reasoning BEFORE assigning scores.
2. PARADIGM AGNOSTIC: Accept different valid testing styles (e.g., Mocking vs. State Verification).
3. CRITICALITY: A test that asserts nothing is worthless, regardless of code cleanliness.

Output strictly valid JSON."""

EVALUATION_TEMPLATE = """
[PROBLEM DESCRIPTION]
{docstring}

[FOCAL METHOD]
```python
{focal_code}
```

[TEST OPTION A]
```python
{code_a}
```

[TEST OPTION B]
```python
{code_b}
```

[EVALUATION CRITERIA - Score each 1-5 points]

1. ROBUSTNESS (Edge cases, boundary values):
   - 5: Excellent - Comprehensive coverage (Empty, None, Negative, Type errors, Boundary limits, multiple edge cases)
   - 4: Good - Multiple edge cases covered with some depth
   - 3: Acceptable - Basic edge cases or happy path with some variation
   - 2: Poor - Only happy path tested with standard valid inputs
   - 1: Very Poor - Minimal/No coverage, missing critical test cases

2. ASSERTION STRENGTH (Verification quality):
   - 5: Excellent - Strong, specific assertions (Exact values, states, specific exception types with messages)
   - 4: Good - Specific assertions covering key behaviors
   - 3: Acceptable - Basic assertions that verify correctness
   - 2: Poor - Weak/Generic (Asserts type only, or 'is not None')
   - 1: Very Poor - Trivial/None (assert True, or no meaningful assertions)

3. READABILITY (Code clarity):
   - 5: Excellent - Professional (Clear naming, AAA pattern, proper setup, well-documented)
   - 4: Good - Clean structure with clear intent
   - 3: Acceptable - Understandable but could be clearer
   - 2: Poor - Messy or unclear structure
   - 1: Very Poor - Obfuscated/Confusing, hard to understand

4. CONCISENESS (Efficiency):
   - 5: Excellent - Highly efficient (Minimal code, no redundancy, elegant)
   - 4: Good - Efficient with minimal unnecessary code
   - 3: Acceptable - Some unnecessary code but functional
   - 2: Poor - Notable redundancy or verbosity
   - 1: Very Poor - Bloated (Excessive redundancy, dead code, unnecessary complexity)

[OUTPUT FORMAT] Return ONLY this JSON:
{{
  "analysis_test_a": "Step-by-step analysis of A...",
  "analysis_test_b": "Step-by-step analysis of B...",
  "comparison_text": "Textual comparison...",
  "test_a_scores": [Robustness, Assertions, Readability, Conciseness],
  "test_b_scores": [Robustness, Assertions, Readability, Conciseness]
}}
"""

class ThreadSafeWriter:
    """Thread-safe file writer for parallel API calls."""
    def __init__(self, filepath):
        self.filepath = filepath
        self.lock = threading.Lock()

    def write(self, data):
        """Write JSON data to file in thread-safe manner."""
        with self.lock:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data) + "\n")

def stable_hash(text):
    """
    Creates a stable hash that persists across Python sessions.

    Python's built-in hash() is salted for security and changes between restarts.
    This breaks cache persistence. Used MD5 for stable, deterministic hashing.

    Args:
        text: String to hash
    Returns:
        Hexadecimal hash string (first 16 chars for brevity)
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]

def clean_and_parse_json(response_text):
    """Attempts to extract and repair JSON from LLM output."""
    # Try direct parsing
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    def fix_escape_sequences(text):
        """Fix Python-style escape sequences that are invalid in JSON."""
        import re
        # Replace \xHH (hex escape) with a safe placeholder
        # These appear in the LLM's analysis when describing test code strings
        text = re.sub(r'\\x[0-9a-fA-F]{2}', '<hex>', text)

        # Also fix any other invalid escape sequences
        # Valid JSON escapes are: \" \\ \/ \b \f \n \r \t \uXXXX
        # Replace any \<char> where <char> is not a valid JSON escape
        # Keep the backslash but double it to make it literal
        def replace_invalid_escape(match):
            escaped_char = match.group(1)
            # Valid single-char escapes in JSON
            if escaped_char in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't']:
                return match.group(0)  # Keep as-is
            # Unicode escape
            if escaped_char == 'u':
                return match.group(0)  # Keep as-is
            # Invalid escape - double the backslash to make it literal
            return '\\\\' + escaped_char

        text = re.sub(r'\\(.)', replace_invalid_escape, text)
        return text

    # Strategy 1: Extract from ```json markers (most reliable for our case)
    # Look for ```json followed by content, then ```
    # Use negative lookahead to get the LAST ```
    if '```json' in response_text:
        # Find the ```json marker
        json_start = response_text.find('```json')
        if json_start != -1:
            # Start after ```json and any whitespace
            content_start = json_start + 7  # len('```json')
            # Skip leading whitespace/newlines
            while content_start < len(response_text) and response_text[content_start] in ' \t\n\r':
                content_start += 1

            # Find the LAST ``` marker
            last_backticks = response_text.rfind('```', content_start)
            if last_backticks != -1:
                text_content = response_text[content_start:last_backticks].strip()

                # Fix invalid escape sequences before parsing
                text_content = fix_escape_sequences(text_content)

                try:
                    result = json.loads(text_content)
                    # Success - no need to log verbosely
                    return result
                except json.JSONDecodeError as e:
                    # Only log and save on failure
                    logger.warning(f"Strategy 1: Extracted {len(text_content)} chars from ```json block")
                    logger.warning(f"Extracted starts: {text_content[:80]}...")
                    logger.warning(f"Extracted ends: ...{text_content[-80:]}")
                    logger.warning(f"Strategy 1 FAILED: JSON parse error: {e} at position {e.pos if hasattr(e, 'pos') else 'unknown'}")

                    # Save extracted content to debug file
                    debug_dir = os.path.dirname(LOG_FILE)
                    extracted_file = os.path.join(debug_dir, 'strategy1_extracted.json')
                    try:
                        with open(extracted_file, 'w', encoding='utf-8') as f:
                            f.write(text_content)
                        logger.warning(f"Saved Strategy 1 extracted content to {extracted_file}")
                    except Exception as e2:
                        logger.warning(f"Could not save extracted content: {e2}")

    # Strategy 2: Extract JSON object with balanced braces
    # Find first { and match balanced braces
    first_brace = response_text.find('{')
    if first_brace != -1:
        brace_count = 0
        in_string = False
        escape_next = False

        for i in range(first_brace, len(response_text)):
            char = response_text[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found matching closing brace
                        text_content = response_text[first_brace:i+1]

                        text_content = fix_escape_sequences(text_content)

                        try:
                            result = json.loads(text_content)
                            # Success - no need to log verbosely
                            return result
                        except json.JSONDecodeError as e:
                            # Only log and save on failure
                            logger.warning(f"Strategy 2: Extracted {len(text_content)} chars with balanced braces")
                            logger.warning(f"Strategy 2 FAILED: JSON parse error: {e} at position {e.pos if hasattr(e, 'pos') else 'unknown'}")

                            # Save extracted content to debug file
                            debug_dir = os.path.dirname(LOG_FILE)
                            extracted_file = os.path.join(debug_dir, 'strategy2_extracted.json')
                            try:
                                with open(extracted_file, 'w', encoding='utf-8') as f:
                                    f.write(text_content)
                                logger.warning(f"Saved Strategy 2 extracted content to {extracted_file}")
                            except Exception as e2:
                                logger.warning(f"Could not save extracted content: {e2}")
                        break

    logger.error("ALL STRATEGIES FAILED: Could not extract valid JSON")
    return None

def call_claude_judge(prompt, retries=3):
    """Call LLM with granular error handling and JSON validation."""
    required_keys = ["test_a_scores", "test_b_scores"]
    last_failure_reason = "Unknown"

    for attempt in range(retries):
        try:
            # Rate limiting buffer (reduced for parallel execution - concurrency controlled by ThreadPoolExecutor)
            time.sleep(0.1)

            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=8192,
                temperature=JUDGE_TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Check for truncation (incomplete response)
            stop_reason = response.stop_reason
            if stop_reason == "max_tokens":
                last_failure_reason = f"Response truncated (hit max_tokens limit). Response length: {len(response_text)} chars"
                logger.warning(f"{last_failure_reason} (Attempt {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt * 2)
                continue

            result = clean_and_parse_json(response_text)

            if result:
                # Validate Keys
                if all(k in result for k in required_keys):
                    return result
                else:
                    last_failure_reason = f"Missing keys: expected {required_keys}, got {list(result.keys())}"
                    logger.warning(f"{last_failure_reason} (Attempt {attempt + 1}/{retries})")
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt * 2)  # Exponential backoff for JSON issues
            else:
                # Check if response ends abruptly (likely truncated)
                ends_cleanly = response_text.rstrip().endswith(('```', '}', ']'))
                # Show both start and end for better debugging
                start_text = response_text[:100] if len(response_text) > 100 else response_text
                end_text = response_text[-100:] if len(response_text) > 100 else response_text
                last_failure_reason = f"JSON parsing failed. Response length: {len(response_text)} chars, ends_cleanly: {ends_cleanly}, starts: {start_text}... ends: ...{end_text}"
                logger.warning(f"{last_failure_reason} (Attempt {attempt + 1}/{retries})")
                # Save full response to debug file for inspection
                if attempt == retries - 1:
                    debug_file = os.path.join(os.path.dirname(LOG_FILE), 'failed_json_response.txt')
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    logger.error(f"Saved full failed response to {debug_file} for debugging")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt * 2)  # Exponential backoff for JSON issues

        except RateLimitError as e:
            last_failure_reason = f"Rate Limit: {e}"
            wait_time = 2 ** attempt * 10
            logger.warning(f"Rate Limit Hit. Waiting {wait_time}s... (Attempt {attempt + 1}/{retries})")
            time.sleep(wait_time)

        except APIError as e:
            last_failure_reason = f"API Error: {e}"
            wait_time = 2 ** attempt * 5
            logger.warning(f"Anthropic API Error: {e}. Waiting {wait_time}s... (Attempt {attempt + 1}/{retries})")
            time.sleep(wait_time)

        except Exception as e:
            last_failure_reason = f"Unexpected Error: {e}"
            logger.error(f"Unexpected Error: {e} (Attempt {attempt + 1}/{retries})")
            if attempt == retries - 1: return None
            time.sleep(5)

    logger.error(f"Failed to get valid response after {retries} retries. Last failure: {last_failure_reason}")
    return None

def calculate_weighted_score(raw_scores):
    """Sum criterion scores (Robustness, Assertions, Readability, Conciseness) 1-5 each.

    Null-test veto: if Assertions = 1, returns 1.0 regardless of other scores.
    Max score: 20.0 per pass.
    """
    if len(raw_scores) < 4:
        raw_scores = raw_scores + [1] * (4 - len(raw_scores))  # Default to 1 (Very Poor) for missing scores

    robustness, assertions, readability, conciseness = raw_scores[0], raw_scores[1], raw_scores[2], raw_scores[3]

    if assertions == 1:
        return 1.0

    return robustness + assertions + readability + conciseness

def judge_pair_double_pass(task_id, focal_code, docstring, model_a_name, code_a, model_b_name, code_b):
    """Performs Double-Pass Evaluation with Python-side Weighted Math."""

    # PASS 1: A vs B
    prompt_1 = EVALUATION_TEMPLATE.format(
        docstring=docstring, focal_code=focal_code, code_a=code_a, code_b=code_b
    )
    result_1 = call_claude_judge(prompt_1)
    if not result_1: return None

    # PASS 2: B vs A
    prompt_2 = EVALUATION_TEMPLATE.format(
        docstring=docstring, focal_code=focal_code, code_a=code_b, code_b=code_a
    )
    result_2 = call_claude_judge(prompt_2)
    if not result_2: return None

    # Extracting scores
    scores_1_pos1 = result_1.get("test_a_scores", [1,1,1,1]) # Model A (default to 1 = Very Poor)
    scores_1_pos2 = result_1.get("test_b_scores", [1,1,1,1]) # Model B

    scores_2_pos1 = result_2.get("test_a_scores", [1,1,1,1]) # Model B (Swapped)
    scores_2_pos2 = result_2.get("test_b_scores", [1,1,1,1]) # Model A (Swapped)

    wa_1 = calculate_weighted_score(scores_1_pos1)
    wa_2 = calculate_weighted_score(scores_2_pos2)
    model_a_total = wa_1 + wa_2

    wb_1 = calculate_weighted_score(scores_1_pos2)
    wb_2 = calculate_weighted_score(scores_2_pos1)
    model_b_total = wb_1 + wb_2

    # Determine winner for each pass
    pass1_winner = "A" if (wa_1 - wb_1) > TIE_THRESHOLD else ("B" if (wb_1 - wa_1) > TIE_THRESHOLD else "Tie")
    pass2_winner = "A" if (wa_2 - wb_2) > TIE_THRESHOLD else ("B" if (wb_2 - wa_2) > TIE_THRESHOLD else "Tie")

    bias_status = "None"

    # Calculate score variance between passes for noise detection
    score_variance_a = abs(wa_1 - wa_2)
    score_variance_b = abs(wb_1 - wb_2)
    max_score_variance = max(score_variance_a, score_variance_b)

    # Position 1 bias: A wins pass1 (A in pos1), B wins pass2 (B in pos1 after swap)
    if pass1_winner == "A" and pass2_winner == "B":
        bias_status = "Position_Bias_First"

    # Position 2 bias (rare): B wins pass1 (B in pos2), A wins pass2 (A in pos2 after swap)
    elif pass1_winner == "B" and pass2_winner == "A":
        bias_status = "Position_Bias_Second"

    # Stochastic Noise: Disagreement without positional pattern
    # High variance in scores between passes indicates unreliable judgment
    elif pass1_winner != pass2_winner and max_score_variance > 4.0:  # >4 points difference on 20-point scale
        bias_status = "Stochastic_Noise"

    # If A wins both times OR B wins both times, that's consistent judgment (not bias)
    # Small disagreements (Tie vs narrow win) are acceptable and handled by averaging

    # The winner
    score_diff = abs(model_a_total - model_b_total)
    final_winner = "Tie"
    
    if bias_status != "None":
        final_winner = "Invalid_Bias"
    elif score_diff > TIE_THRESHOLD:
        final_winner = "A" if model_a_total > model_b_total else "B"

    return {
        "task_id": task_id,
        "model_a": model_a_name,
        "model_b": model_b_name,
        "bias_status": bias_status,
        "final_winner_model": final_winner,
        "model_a_total_score": model_a_total,
        "model_b_total_score": model_b_total,
        "score_diff": score_diff,
        # Reliability metrics for noise detection
        "score_variance_a": score_variance_a,
        "score_variance_b": score_variance_b,
        "max_score_variance": max_score_variance,
        "pass1_winner": pass1_winner,
        "pass2_winner": pass2_winner,
        # Raw criterion scores for transparency and post-hoc analysis
        "model_a_scores_pass1": scores_1_pos1,  # [robustness, assertions, readability, conciseness]
        "model_a_scores_pass2": scores_2_pos2,
        "model_b_scores_pass1": scores_1_pos2,
        "model_b_scores_pass2": scores_2_pos1,
        # Reasoning and code for validation
        "reasoning_pass_full": result_1.get("comparison_text", ""),
        "code_a": code_a,
        "code_b": code_b,
        "focal_code": focal_code,
        "docstring": docstring
    }

def select_evaluation_groups():
    """Returns Dict of {group_name: [(pattern, config_name), ...]}"""
    return {
        "best_configs": [
            ("pynguin_results.jsonl", "Pynguin (Baseline)"),
            ("linecov2_Qwen3-4B-Instruct*_temp_1.0.jsonl", "Qwen3-4B-Instruct Two-Shot CoT T=1.0"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_0.0.jsonl", "Ministral-3-8B-Instruct Two-Shot CoT T=0.0"),
            ("linecov2_granite-4.0-micro_temp_0.2.jsonl", "granite-4.0-micro Two-Shot CoT T=0.2"),
            ("linecov_Ministral-3-3B-Reasoning*_temp_0.8.jsonl", "Ministral-3-3B-Reasoning One-Shot T=0.8"),
            ("linecov_gemma-3-4b-it_temp_0.2.jsonl", "gemma-3-4b-it One-Shot T=0.2"),
        ],
        "temperature_ablation": [
            ("linecov2_Qwen3-4B-Instruct*_temp_0.0.jsonl", "Qwen3-4B-Instruct Two-Shot CoT T=0.0"),
            ("linecov2_Qwen3-4B-Instruct*_temp_0.8.jsonl", "Qwen3-4B-Instruct Two-Shot CoT T=0.8"),
            ("linecov2_Qwen3-4B-Instruct*_temp_1.0.jsonl", "Qwen3-4B-Instruct Two-Shot CoT T=1.0"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_0.0.jsonl", "Ministral-3-8B-Instruct Two-Shot CoT T=0.0"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_0.8.jsonl", "Ministral-3-8B-Instruct Two-Shot CoT T=0.8"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_1.0.jsonl", "Ministral-3-8B-Instruct Two-Shot CoT T=1.0"),
        ],
        "prompting_ablation": [
            ("linecov_Qwen3-4B-Instruct*_temp_1.0.jsonl", "Qwen3-4B-Instruct One-Shot T=1.0"),
            ("linecov2_Qwen3-4B-Instruct*_temp_1.0.jsonl", "Qwen3-4B-Instruct Two-Shot CoT T=1.0"),
            ("linecov_Ministral-3-8B-Instruct*_temp_0.0.jsonl", "Ministral-3-8B-Instruct One-Shot T=0.0"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_0.0.jsonl", "Ministral-3-8B-Instruct Two-Shot CoT T=0.0"),
        ],
        # All 5 architectures × 3 temps × 2 prompts + 1 baseline = 31 configs
        "full_factorial": [
            # Dense 4B (Qwen3)
            ("linecov_Qwen3-4B-Instruct*_temp_0.0.jsonl", "Qwen3-4B-Instruct One-Shot T=0.0"),
            ("linecov_Qwen3-4B-Instruct*_temp_0.8.jsonl", "Qwen3-4B-Instruct One-Shot T=0.8"),
            ("linecov_Qwen3-4B-Instruct*_temp_1.0.jsonl", "Qwen3-4B-Instruct One-Shot T=1.0"),
            ("linecov2_Qwen3-4B-Instruct*_temp_0.0.jsonl", "Qwen3-4B-Instruct Two-Shot T=0.0"),
            ("linecov2_Qwen3-4B-Instruct*_temp_0.8.jsonl", "Qwen3-4B-Instruct Two-Shot T=0.8"),
            ("linecov2_Qwen3-4B-Instruct*_temp_1.0.jsonl", "Qwen3-4B-Instruct Two-Shot T=1.0"),

            # Quantized 8B (Ministral-8B AWQ)
            ("linecov_Ministral-3-8B-Instruct*_temp_0.0.jsonl", "Ministral-3-8B-Instruct One-Shot T=0.0"),
            ("linecov_Ministral-3-8B-Instruct*_temp_0.8.jsonl", "Ministral-3-8B-Instruct One-Shot T=0.8"),
            ("linecov_Ministral-3-8B-Instruct*_temp_1.0.jsonl", "Ministral-3-8B-Instruct One-Shot T=1.0"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_0.0.jsonl", "Ministral-3-8B-Instruct Two-Shot T=0.0"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_0.8.jsonl", "Ministral-3-8B-Instruct Two-Shot T=0.8"),
            ("linecov2_Ministral-3-8B-Instruct*_temp_1.0.jsonl", "Ministral-3-8B-Instruct Two-Shot T=1.0"),

            # Mamba Hybrid (granite)
            ("linecov_granite-4.0-micro_temp_0.0.jsonl", "granite-4.0-micro One-Shot T=0.0"),
            ("linecov_granite-4.0-micro_temp_0.8.jsonl", "granite-4.0-micro One-Shot T=0.8"),
            ("linecov_granite-4.0-micro_temp_1.0.jsonl", "granite-4.0-micro One-Shot T=1.0"),
            ("linecov2_granite-4.0-micro_temp_0.0.jsonl", "granite-4.0-micro Two-Shot T=0.0"),
            ("linecov2_granite-4.0-micro_temp_0.8.jsonl", "granite-4.0-micro Two-Shot T=0.8"),
            ("linecov2_granite-4.0-micro_temp_1.0.jsonl", "granite-4.0-micro Two-Shot T=1.0"),

            # Reasoning (Ministral-3B with Internal CoT)
            ("linecov_Ministral-3-3B-Reasoning*_temp_0.0.jsonl", "Ministral-3-3B-Reasoning One-Shot T=0.0"),
            ("linecov_Ministral-3-3B-Reasoning*_temp_0.8.jsonl", "Ministral-3-3B-Reasoning One-Shot T=0.8"),
            ("linecov_Ministral-3-3B-Reasoning*_temp_1.0.jsonl", "Ministral-3-3B-Reasoning One-Shot T=1.0"),
            ("linecov2_Ministral-3-3B-Reasoning*_temp_0.0.jsonl", "Ministral-3-3B-Reasoning Two-Shot T=0.0"),
            ("linecov2_Ministral-3-3B-Reasoning*_temp_0.8.jsonl", "Ministral-3-3B-Reasoning Two-Shot T=0.8"),
            ("linecov2_Ministral-3-3B-Reasoning*_temp_1.0.jsonl", "Ministral-3-3B-Reasoning Two-Shot T=1.0"),

            # Dense 4B (gemma)
            ("linecov_gemma-3-4b-it_temp_0.0.jsonl", "gemma-3-4b-it One-Shot T=0.0"),
            ("linecov_gemma-3-4b-it_temp_0.8.jsonl", "gemma-3-4b-it One-Shot T=0.8"),
            ("linecov_gemma-3-4b-it_temp_1.0.jsonl", "gemma-3-4b-it One-Shot T=1.0"),
            ("linecov2_gemma-3-4b-it_temp_0.0.jsonl", "gemma-3-4b-it Two-Shot T=0.0"),
            ("linecov2_gemma-3-4b-it_temp_0.8.jsonl", "gemma-3-4b-it Two-Shot T=0.8"),
            ("linecov2_gemma-3-4b-it_temp_1.0.jsonl", "gemma-3-4b-it Two-Shot T=1.0"),

            # Baseline
            ("pynguin_results.jsonl", "Pynguin (Baseline)"),
        ]
    }

def load_data(base_dir, evaluation_group="best_configs", eval_dir=None):
    """Load predictions and join with evaluation results, returning only status=Pass tests.

    Two-stage loading:
    1. Predictions from base_dir/run_1/*.jsonl (test code)
    2. Evaluation results from eval_dir/run_1/*_evaluated.jsonl (status)

    Returns (tasks, focal_methods, docstrings, pass_rate_stats).
    """
    groups = select_evaluation_groups()
    if evaluation_group not in groups:
        raise ValueError(f"Unknown group: {evaluation_group}")

    selected_models = groups[evaluation_group]
    tasks = {}
    focal_methods = {}
    docstrings = {}
    pass_rate_stats = {}

    logger.info(f"Loading data for group: {evaluation_group}...")
    logger.info(f"Eval dir override: {eval_dir if eval_dir else '(none - using heuristic)'}")

    if eval_dir:
        eval_base_dir = eval_dir
    elif "predictions" in base_dir.lower():
        # Heuristic: Remove any TestEval/ prefix and replace predictions with evaluation_results
        base_cleaned = base_dir.split(os.sep)[-1] if os.sep in base_dir else base_dir
        if "predictions_realworld" in base_cleaned:
            eval_base_dir = "evaluation_results_realworld"
        elif "predictions_initial" in base_cleaned:
            eval_base_dir = "evaluation_results_initial"
        else:
            eval_base_dir = base_dir.replace("predictions", "evaluation_results")
    else:
        eval_base_dir = base_dir

    for pattern, friendly_name in selected_models:
        pred_search_path = os.path.join(base_dir, "run_1", pattern)
        pred_files = glob.glob(pred_search_path)

        eval_pattern = pattern.replace('.jsonl', '_evaluated.jsonl')
        eval_search_path = os.path.join(eval_base_dir, "run_1", eval_pattern)
        eval_files = glob.glob(eval_search_path)

        if not pred_files:
            logger.warning(f"No prediction files found for {friendly_name}: {pred_search_path}")
            continue

        if not eval_files:
            logger.warning(f"No evaluation files found for {friendly_name}: {eval_search_path}")
            logger.warning(f"Skipping Pass filter for this model (will load all tests)")
            # Fall back to loading without status filter
            eval_files = None

        status_lookup = {}
        if eval_files:
            for eval_filepath in eval_files:
                with open(eval_filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            task_num = str(d.get('task_num', ''))
                            status_lookup[task_num] = d.get('status', 'Unknown')
                        except Exception:
                            continue

        pass_count = 0
        total_count = 0

        for pred_filepath in pred_files:
            with open(pred_filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        total_count += 1

                        tid = str(d.get('task_num', d.get('task_id', '')))
                        if not tid: continue

                        # Filter by Pass status (if evaluation results available)
                        if status_lookup:
                            status = status_lookup.get(tid, 'Unknown')
                            if status != "Pass":
                                continue

                        pass_count += 1

                        # Extract test code
                        tests_obj = d.get('tests', {})
                        test_code = ""
                        if isinstance(tests_obj, dict):
                            for k, v in tests_obj.items():
                                if isinstance(v, dict):
                                    test_code = v.get('test_code', '')
                                else:
                                    test_code = v
                                break

                        if not test_code or not test_code.strip(): continue

                        if tid not in tasks: tasks[tid] = {}
                        tasks[tid][friendly_name] = test_code

                        if tid not in focal_methods:
                            focal_methods[tid] = d.get('code') or d.get('python_solution', '')

                        if tid not in docstrings:
                            docstrings[tid] = (d.get('prompt') or d.get('docstring') or "No docstring.")

                    except Exception:
                        continue

        # Record pass rate statistics
        pass_rate = (pass_count / total_count * 100) if total_count > 0 else 0
        pass_rate_stats[friendly_name] = {
            'pass_count': pass_count,
            'total_count': total_count,
            'pass_rate': pass_rate
        }
        logger.info(f"{friendly_name}: {pass_count}/{total_count} passing ({pass_rate:.1f}%)")

    logger.info(f"Loaded {len(tasks)} tasks with passing tests across all models.")
    return tasks, focal_methods, docstrings, pass_rate_stats

# Sampling strategy
def perform_stratified_sampling(df, output_dir, group_name, n_per_stratum=10, seed=42):
    """Samples from Ties, Marginal Wins, and Clear Wins for human validation."""
    valid = df[df['bias_status'] == 'None'].copy()
    if valid.empty: return

    def classify_diff(row):
        d = row['score_diff']
        if d <= TIE_THRESHOLD: return 'Tie'  # <= 2.0 for 1-5 scale
        if d <= 8.0: return 'Marginal'  # Adjusted for 1-5 scale (was 4.0 for 0-2 scale)
        return 'Clear'
    
    valid['stratum'] = valid.apply(classify_diff, axis=1)
    sampled_rows = []
    
    logger.info(f"Sampling for human validation ({group_name})...")
    for stratum in ['Tie', 'Marginal', 'Clear']:
        subset = valid[valid['stratum'] == stratum]
        count = min(len(subset), n_per_stratum)
        if count > 0:
            sampled_rows.append(subset.sample(n=count, random_state=seed))

    if sampled_rows:
        final_sample = pd.concat(sampled_rows).sample(frac=1, random_state=seed)
        path = os.path.join(output_dir, f"stratified_human_eval_{group_name}.csv")
        cols = ['task_id', 'stratum', 'score_diff', 'model_a', 'model_b',
                'model_a_total_score', 'model_b_total_score',
                'docstring', 'focal_code', 'code_a', 'code_b', 'reasoning_pass_full']
        final_sample[cols].to_csv(path, index=False)
        logger.info(f"Saved human sample to {path}")

def load_global_comparison_cache(output_dir):
    """Load all previously completed comparisons from ALL group files for deduplication."""
    cache = {}  # key: comparison_key -> value: decision result

    # Search for all pairwise_judgements_*.jsonl files in output directory
    cache_files = glob.glob(os.path.join(output_dir, "pairwise_judgements_*.jsonl"))

    for cache_file in cache_files:
        with open(cache_file, 'r') as f:
            for line in f:
                try:
                    result = json.loads(line)
                    # Create unique key based on task_id, model names, AND the actual code being compared
                    # This ensures we can reuse comparisons across groups if they compare the same code
                    # Use stable_hash instead of hash() for persistence across Python sessions
                    code_hash = stable_hash(result['code_a'] + result['code_b'])
                    comparison_key = f"{result['task_id']}||{result['model_a']}||{result['model_b']}||{code_hash}"
                    cache[comparison_key] = result
                except:
                    continue

    logger.info(f"Loaded {len(cache)} comparisons from global cache across all groups")
    return cache

def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge Evaluation System")
    parser.add_argument("--predictions_dir", type=str, default="TestEval/predictions_realworld")
    parser.add_argument("--eval_dir", type=str, default=None,
                        help="Path to evaluation results directory (e.g. evaluation_results_realworld_1). "
                             "Overrides auto-detection. Required for correct Pass-status filtering.")
    parser.add_argument("--output_dir", type=str, default="TestEval/predictions_judgellm")
    parser.add_argument("--evaluation_group", type=str, default="best_configs",
                        choices=["best_configs", "temperature_ablation", "prompting_ablation", "full_factorial", "all"])
    parser.add_argument("--human_sample_size", type=int, default=10)
    parser.add_argument("--task_sample_size", type=int, default=None, help="Pilot study: sample N tasks")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use_cache", action="store_true", default=True,
                        help="Reuse comparisons from other groups (default: True)")
    parser.add_argument("--no_cache", action="store_true",
                        help="Disable cache and re-evaluate all comparisons")
    parser.add_argument("--max_workers", type=int, default=5,
                        help="Max parallel API requests (default: 5). Anthropic handles concurrency well.")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load global cache once before processing any groups
    global_cache = {}
    if args.use_cache and not args.no_cache:
        logger.info("Loading global comparison cache to reuse evaluations across groups...")
        global_cache = load_global_comparison_cache(args.output_dir)
    else:
        logger.info("Cache disabled - will re-evaluate all comparisons")

    # Determine groups to run
    if args.evaluation_group == "all":
        groups_to_run = ["best_configs", "temperature_ablation", "prompting_ablation"]
    else:
        groups_to_run = [args.evaluation_group]

    for group_name in groups_to_run:
        logger.info("\n" + "=" * 60)
        logger.info(f"STARTING EVALUATION: {group_name}")
        logger.info("=" * 60)

        # 1. Load Data (with pass rate statistics)
        tasks, focal_methods, docstrings, pass_rate_stats = load_data(args.predictions_dir, evaluation_group=group_name, eval_dir=args.eval_dir)

        # Optional: Pilot Sampling
        if args.task_sample_size and args.task_sample_size < len(tasks):
            import random
            random.seed(args.seed)
            sampled_ids = random.sample(list(tasks.keys()), args.task_sample_size)
            tasks = {tid: tasks[tid] for tid in sampled_ids}
            logger.info(f"PILOT MODE: Sampled {len(tasks)} tasks.")

        OUTPUT_FILE = os.path.join(args.output_dir, f"pairwise_judgements_{group_name}.jsonl")
        STATS_FILE = os.path.join(args.output_dir, f"evaluation_statistics_{group_name}.json")

        # Load existing results from THIS group's file for resume functionality
        local_completed = {}
        if os.path.exists(OUTPUT_FILE):
            logger.info(f"Found existing results file for {group_name}. Loading completed comparisons...")
            with open(OUTPUT_FILE, 'r') as f:
                for line in f:
                    try:
                        result = json.loads(line)
                        # Create unique key for each comparison including code hash
                        code_hash = stable_hash(result['code_a'] + result['code_b'])
                        comparison_key = f"{result['task_id']}||{result['model_a']}||{result['model_b']}||{code_hash}"
                        local_completed[comparison_key] = result
                    except:
                        continue
            logger.info(f"Loaded {len(local_completed)} completed comparisons from {group_name}.")

        # Merge global cache with local results (local takes precedence)
        available_cache = {**global_cache, **local_completed}
        logger.info(f"Total available cached comparisons: {len(available_cache)} (global: {len(global_cache)}, local: {len(local_completed)})")

        # Cost Estimation
        total_pairs = sum((len(m)*(len(m)-1))//2 for m in tasks.values() if len(m)>=2)
        total_calls = total_pairs * 2 # Double pass
        
        # Heuristic: 1 char ~= 0.25 tokens. 
        # Avg input context per call ~= Focal(300) + Doc(100) + CodeA(200) + CodeB(200) + Prompt(500) = 1300 chars
        est_input_tokens = total_calls * 1500  # Conservative estimate
        est_output_tokens = total_calls * 400  # Reasoning + JSON

        est_cost = ((est_input_tokens/1_000_000) * PRICE_INPUT_PER_M) + \
                   ((est_output_tokens/1_000_000) * PRICE_OUTPUT_PER_M)

        logger.info(f"--- COST ESTIMATION ({group_name}) ---")
        logger.info(f"Pairs: {total_pairs} | API Calls: {total_calls} (Double-Pass)")
        logger.info(f"Est. Cost: ${est_cost:.2f} (Input: ~{est_input_tokens} toks, Output: ~{est_output_tokens} toks)")
        logger.info("-------------------------------------")
        
        # Evaluation Loop with Parallel Processing
        cache_hits = 0
        new_comparisons = 0
        reused_from_other_groups = 0

        # Thread-safe writer for parallel execution
        writer = ThreadSafeWriter(OUTPUT_FILE)

        # Build list of all comparisons to perform
        comparison_jobs = []
        for task_id, models in tasks.items():
            if len(models) < 2: continue
            focal = focal_methods.get(task_id, "")
            doc = docstrings.get(task_id, "")

            # Important Selection Bias Mitigation
            # Only compare models that BOTH have passing tests for this task.
            pairs = list(itertools.combinations(models.keys(), 2))

            for m1, m2 in pairs:
                code_a = models[m1]
                code_b = models[m2]
                code_hash = stable_hash(code_a + code_b)
                comparison_key = f"{task_id}||{m1}||{m2}||{code_hash}"

                # Check if cached
                if comparison_key in available_cache:
                    cached_result = available_cache[comparison_key]
                    cache_hits += 1

                    # Write to this group's file if from another group
                    if comparison_key not in local_completed:
                        reused_from_other_groups += 1
                        writer.write(cached_result)
                    continue

                # Add to job queue for parallel processing
                comparison_jobs.append({
                    'task_id': task_id,
                    'focal': focal,
                    'doc': doc,
                    'm1': m1,
                    'code_a': code_a,
                    'm2': m2,
                    'code_b': code_b,
                    'comparison_key': comparison_key
                })

        logger.info(f"Cache hits: {cache_hits} | New comparisons to perform: {len(comparison_jobs)}")

        # Parallel execution
        if comparison_jobs:
            def evaluate_comparison(job):
                """Worker function for parallel evaluation."""
                try:
                    decision = judge_pair_double_pass(
                        job['task_id'], job['focal'], job['doc'],
                        job['m1'], job['code_a'], job['m2'], job['code_b']
                    )
                    return (job['comparison_key'], decision)
                except Exception as e:
                    logger.error(f"Failed to evaluate {job['comparison_key']}: {e}")
                    return (job['comparison_key'], None)

            # Use ThreadPoolExecutor for parallel API calls
            with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                # Submit all jobs
                futures = {executor.submit(evaluate_comparison, job): job for job in comparison_jobs}

                # Process results as they complete
                for future in tqdm(as_completed(futures), total=len(comparison_jobs), desc=f"Evaluating {group_name}"):
                    comparison_key, decision = future.result()
                    if decision:
                        new_comparisons += 1
                        # Thread-safe write to disk
                        writer.write(decision)
                        # Add to cache to prevent duplicates
                        available_cache[comparison_key] = decision
                    else:
                        logger.warning(f"Skipping failed comparison: {comparison_key}")

        logger.info(f"Evaluation complete for {group_name}:")
        logger.info(f"  - New comparisons: {new_comparisons}")
        logger.info(f"  - Reused from other groups: {reused_from_other_groups}")
        logger.info(f"  - Already in this group: {cache_hits - reused_from_other_groups}")
        logger.info(f"  - Total skipped (cached): {cache_hits}")

        # Statistics & Sampling
        # Load ALL results from file (including previously completed ones) for complete statistics
        all_results = []
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r') as f:
                for line in f:
                    try:
                        all_results.append(json.loads(line))
                    except:
                        continue

        if all_results:
            df = pd.DataFrame(all_results)
            
            bias_counts = df['bias_status'].value_counts().to_dict()
            winner_dist = df['final_winner_model'].value_counts().to_dict()
            
            # Win Matrix
            valid_df = df[df['bias_status'] == 'None']
            win_matrix = {}
            for _, row in valid_df.iterrows():
                w, ma, mb = row['final_winner_model'], row['model_a'], row['model_b']
                for m in [ma, mb]: win_matrix.setdefault(m, 0)
                if w == "A": win_matrix[ma] += 1
                elif w == "B": win_matrix[mb] += 1

            # TIE_THRESHOLD Sensitivity Analysis
            # Calculate tie percentage to validate threshold appropriateness
            tie_count = winner_dist.get('Tie', 0)
            tie_percentage = (tie_count / len(valid_df) * 100) if len(valid_df) > 0 else 0

            # Calculate score distribution for threshold recommendation
            score_diffs = valid_df['score_diff'].describe().to_dict()

            stats = {
                "total_comparisons": len(df),
                "bias_analysis": bias_counts,
                "winner_distribution": winner_dist,
                "win_counts": win_matrix,
                "tie_threshold_analysis": {
                    "current_threshold": TIE_THRESHOLD,
                    "tie_percentage": round(tie_percentage, 2),
                    "tie_count": tie_count,
                    "valid_comparisons": len(valid_df),
                    "score_diff_stats": {k: round(v, 2) for k, v in score_diffs.items() if k != 'count'},
                    "recommendation": (
                        "INCREASE threshold (too many ties)" if tie_percentage > 40 else
                        "DECREASE threshold (too few ties)" if tie_percentage < 10 else
                        "Threshold appears reasonable"
                    )
                },
                "est_cost_usd": est_cost,
                "pass_rate_statistics": pass_rate_stats
            }

            with open(STATS_FILE, 'w') as f: json.dump(stats, f, indent=2)

            # Log BIAS & NOISE analysis
            logger.info("\n" + "=" * 60)
            logger.info("JUDGMENT RELIABILITY ANALYSIS")
            logger.info("=" * 60)
            logger.info(f"Total Comparisons: {len(df)}")
            logger.info(f"Bias Status Breakdown:")
            for status, count in bias_counts.items():
                percentage = (count / len(df) * 100) if len(df) > 0 else 0
                logger.info(f"  - {status}: {count} ({percentage:.1f}%)")

            # Stochastic noise warning
            noise_count = bias_counts.get('Stochastic_Noise', 0)
            if noise_count > len(df) * 0.05:  # >5% noise is concerning
                logger.warning(f"⚠️  HIGH STOCHASTIC NOISE: {noise_count} comparisons ({noise_count/len(df)*100:.1f}%)")
                logger.warning(f"⚠️  Judge is inconsistent between passes (not position-dependent)")
                logger.warning(f"⚠️  Consider: lower temperature, clearer prompt, or different model")
            else:
                logger.info(f"✓ Low noise level: {noise_count} stochastic disagreements ({noise_count/len(df)*100:.1f}%)")
            logger.info("=" * 60 + "\n")

            # Log TIE_THRESHOLD analysis
            logger.info("=" * 60)
            logger.info("TIE THRESHOLD SENSITIVITY ANALYSIS")
            logger.info("=" * 60)
            logger.info(f"Current Threshold: {TIE_THRESHOLD}")
            logger.info(f"Tie Rate: {tie_percentage:.1f}% ({tie_count}/{len(valid_df)} comparisons)")
            logger.info(f"Score Diff - Median: {score_diffs.get('50%', 0):.2f}, Mean: {score_diffs.get('mean', 0):.2f}")
            threshold_rec = stats['tie_threshold_analysis']['recommendation']
            if "INCREASE" in threshold_rec:
                logger.warning(f"⚠️  {threshold_rec}")
                logger.warning(f"⚠️  Consider TIE_THRESHOLD = 3.0 or 4.0 to reduce ties")
            elif "DECREASE" in threshold_rec:
                logger.warning(f"⚠️  {threshold_rec}")
                logger.warning(f"⚠️  Consider TIE_THRESHOLD = 1.0 or 1.5 to allow more ties")
            else:
                logger.info(f"✓ {threshold_rec} (10-40% ties is acceptable)")
            logger.info("=" * 60 + "\n")

            # Log pass rate warning if significant imbalance
            logger.info("=" * 60)
            logger.info("PASS RATE ANALYSIS (Selection Bias Check)")
            logger.info("=" * 60)
            pass_counts = [s['pass_count'] for s in pass_rate_stats.values()]
            if pass_counts:
                min_pass = min(pass_counts)
                max_pass = max(pass_counts)
                if max_pass > 0 and (max_pass - min_pass) / max_pass > 0.3:
                    logger.warning(f"⚠️  SELECTION BIAS DETECTED: Pass count range {min_pass}-{max_pass}")
                    logger.warning(f"⚠️  Models with more passing tests may appear better due to larger sample size")
                    logger.warning(f"⚠️  Recommendation: Report pass rate alongside quality scores")
                else:
                    logger.info(f"✓ Pass counts well-balanced: {min_pass}-{max_pass} (acceptable range)")
            logger.info("=" * 60 + "\n")
            
            perform_stratified_sampling(
                df, args.output_dir, group_name, 
                n_per_stratum=args.human_sample_size, seed=args.seed
            )
    
    # Merge human samples if "all" was selected
    if args.evaluation_group == "all":
        logger.info("Merging human validation samples from all groups...")
        all_samples = []
        for grp in groups_to_run:
            f = os.path.join(args.output_dir, f"stratified_human_eval_{grp}.csv")
            if os.path.exists(f): all_samples.append(pd.read_csv(f))
        
        if all_samples:
            merged = pd.concat(all_samples, ignore_index=True)
            merged.to_csv(os.path.join(args.output_dir, "stratified_human_eval_ALL_GROUPS.csv"), index=False)
            logger.info("Saved merged human evaluation file.")

if __name__ == "__main__":
    main()