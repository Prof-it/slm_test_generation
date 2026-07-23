"""
V2 Tier Dataset Preparer

Reads TestEval/data/realworld-py-v2.jsonl and emits three inference-ready
JSONL files — one per context tier:

  realworld-py-v2-tier-A.jsonl   — signature + docstring only
  realworld-py-v2-tier-B.jsonl   — A + dependency stubs
  realworld-py-v2-tier-C.jsonl   — B + mock/fixture hint

In each file:
  - python_solution  → replaced with the tier's context card text
    (this is what the model sees as "the code" when writing tests)
  - python_solution_full → the original full wrapped function is preserved
    under this key so evaluate_results.py can run tests against real code
  - tier              → "A", "B", or "C"
  - All other fields (task_num, func_name, target_lines, etc.) preserved

The inference scripts (generate_targetcov_hf.py) read python_solution as the
program context.  The evaluation scripts use python_solution_full for execution.
target_lines is set to [1] because the tier card has no meaningful line numbers
— effectively asking the model to write any test for the function.

Usage:
    python step2_data_preperation/prepare_v2_tier_datasets.py
"""

import json
import logging
import textwrap
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V2_JSONL = PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "TestEval" / "data"


def wrap_in_solution(tier_text: str, func_name: str) -> str:
    """
    Wrap the tier card in class Solution: so the model sees the same structure
    it will be tested against (evaluate_results.py always wraps in Solution).
    Also adds self to the function signature if not already present,
    matching what python_solution_full contains.
    """
    lines = tier_text.splitlines()
    for i, line in enumerate(lines):
        if f"def {func_name}(" in line and "(self" not in line:
            # Add self as first parameter
            if f"def {func_name}():" in line:
                lines[i] = line.replace(f"def {func_name}():", f"def {func_name}(self):")
            else:
                lines[i] = line.replace(f"def {func_name}(", f"def {func_name}(self, ")
            break
        elif f"def {func_name}(" in line:
            # Already has self — leave as-is
            break
    indented = textwrap.indent("\n".join(lines), "    ")
    return f"class Solution:\n{indented}"


def prepare_tier_datasets():
    if not V2_JSONL.exists():
        logging.error(f"v2 dataset not found: {V2_JSONL}")
        logging.error("Run step2_data_preperation/build_v2_pipeline.py first.")
        return

    records = [json.loads(l) for l in V2_JSONL.read_text().splitlines() if l.strip()]
    logging.info(f"Loaded {len(records)} records from {V2_JSONL.name}")

    for tier in ("A", "B", "C"):
        out_path = OUTPUT_DIR / f"realworld-py-v2-tier-{tier}.jsonl"
        written = 0
        skipped = 0

        with out_path.open("w", encoding="utf-8") as f:
            for rec in records:
                card = rec.get("context_card")
                if not card or tier not in card:
                    skipped += 1
                    continue

                tier_text = card[tier].get("text", "")
                if not tier_text:
                    skipped += 1
                    continue

                out = dict(rec)  # shallow copy — preserves all fields
                out["python_solution_full"] = rec.get("python_solution", "")  # keep original
                # Wrap tier card in class Solution: so model sees the same
                # structure that evaluate_results.py will run tests against.
                # This eliminates NameError from direct function calls.
                func_name = rec.get("func_name", "")
                out["python_solution"] = wrap_in_solution(tier_text, func_name)
                out["tier"] = tier
                out["target_lines"] = [2]  # line 2 is the def line inside class Solution
                f.write(json.dumps(out) + "\n")
                written += 1

        logging.info(f"Tier {tier}: {written} records written to {out_path.name}"
                     + (f" ({skipped} skipped — missing card)" if skipped else ""))

    logging.info("Done. Three tier JSONL files ready for inference.")


if __name__ == "__main__":
    prepare_tier_datasets()
