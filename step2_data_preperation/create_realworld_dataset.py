"""
Real World Dataset Creator

This script generates the 'Real World' benchmark dataset by parsing raw Python files.
It performs the following steps:
1.  **Code Analysis**: Calculates McCabe cyclomatic complexity (Radon) for difficulty classification.
2.  **Block Extraction**: Identifies target lines (If/Else blocks) for coverage targets.
3.  **Instrumentation**: Injects logging (optional) and wraps code in a LeetCode-style `Solution` class.
4.  **Balancing**: Caps functions per source file and stratifies by difficulty to produce a balanced dataset.
5.  **Serialization**: Saves the processed tasks to .jsonl files compatible with the TestEval harness.

Usage:
    python step2_data_preperation/create_realworld_dataset.py
    python step2_data_preperation/create_realworld_dataset.py --target-count 50
    python step2_data_preperation/create_realworld_dataset.py --target-count 50 --max-per-file 8
"""

import argparse
import ast
import hashlib
import math
import logging
import json
import random
import textwrap
from collections import defaultdict
from pathlib import Path
from radon.complexity import cc_visit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = PROJECT_ROOT / "TestEval" / "data" / "real_world"
DEFAULT_OUTPUT_BASE = PROJECT_ROOT / "TestEval" / "data" / "realworld-py.jsonl"
DEFAULT_OUTPUT_ALL = PROJECT_ROOT / "TestEval" / "data" / "realworld-py-all.jsonl"

DIFFICULTY_LABELS = {1: "Easy", 2: "Medium", 3: "Hard"}


def analyze_code(source_code: str):
    """
    Assigns difficulty (1=Easy, 2=Medium, 3=Hard) using McCabe cyclomatic
    complexity (Radon cc_visit, max over all blocks).
    Standard thresholds: CC 1-5 -> Easy, 6-10 -> Medium, >10 -> Hard.
    Returns (difficulty_level, max_cc) for sorting purposes.
    """
    try:
        cc_results = cc_visit(source_code)
        if not cc_results:
            return 1, 1

        max_cc = max(c.complexity for c in cc_results)

        if max_cc <= 5:
            return 1, max_cc
        elif max_cc <= 10:
            return 2, max_cc
        else:
            return 3, max_cc
    except Exception as e:
        logging.warning(f"Error analyzing difficulty: {e}")
        return 2, 1


class BlockExtractor(ast.NodeVisitor):
    """
    Extracts conditional blocks (If/Else) to serve as coverage targets.
    """
    def __init__(self, func_lineno):
        self.blocks = []
        self.func_lineno = func_lineno
        self.current_depth = 0

    def generic_visit(self, node):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            self.current_depth += 1

            if isinstance(node, ast.If):
                # Deterministic difficulty based on nesting
                if self.current_depth <= 1: block_diff = 0
                elif self.current_depth == 2: block_diff = 1
                else: block_diff = 2

                # Calculate relative start/end lines
                try:
                    end_lineno = node.body[-1].lineno
                except (IndexError, AttributeError):
                    end_lineno = node.lineno

                self.blocks.append({
                    "type": "if",
                    "start": node.lineno - self.func_lineno + 1,
                    "end": end_lineno - self.func_lineno + 1,
                    "difficulty": block_diff,
                    "eg_cov_prob": -1.0
                })

                # Handle Else/Elif
                if node.orelse:
                     first_else_node = node.orelse[0]
                     # If it's an 'elif', AST treats it as nested If; we skip marking it as 'else' here
                     if not isinstance(first_else_node, ast.If):
                         try:
                             else_end = node.orelse[-1].lineno
                         except:
                             else_end = first_else_node.lineno

                         self.blocks.append({
                            "type": "else",
                            "start": first_else_node.lineno - self.func_lineno + 1,
                            "end": else_end - self.func_lineno + 1,
                            "difficulty": block_diff,
                            "eg_cov_prob": -1.0
                        })

            super().generic_visit(node)
            self.current_depth -= 1
        else:
            super().generic_visit(node)


class CodeInstrumenter(ast.NodeTransformer):
    """Injects logging statements for execution path tracing."""
    def __init__(self):
        self.counter = 0

    def _create_log_node(self, msg):
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='log_function', ctx=ast.Load()),
                args=[ast.Constant(value=msg)],
                keywords=[]
            )
        )

    def visit_For(self, node):
        self.counter += 1
        msg = f"LOOP #{self.counter}: Entered for loop at line {node.lineno}\\n"
        # Insert log at the start of the loop body
        node.body.insert(0, self._create_log_node(msg))
        self.generic_visit(node)
        return node

    def visit_While(self, node):
        self.counter += 1
        msg = f"LOOP #{self.counter}: Entered while loop at line {node.lineno}\\n"
        node.body.insert(0, self._create_log_node(msg))
        self.generic_visit(node)
        return node

    def visit_If(self, node):
        self.counter += 1
        msg_if = f"BRANCH #{self.counter}: Covered if branch at line {node.lineno}\\n"
        node.body.insert(0, self._create_log_node(msg_if))

        if node.orelse and not (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)):
            self.counter += 1
            msg_else = f"BRANCH #{self.counter}: Covered else branch\\n"
            node.orelse.insert(0, self._create_log_node(msg_else))

        self.generic_visit(node)
        return node


class CodeAnalyzer:
    """
    Main processor: parses source files, identifies functions, wraps them in
    the Solution class, and extracts metadata.
    """
    def __init__(self, file_path):
        self.file_path = file_path
        with open(file_path, 'r', encoding='utf-8') as f:
            self.source = f.read()
        try:
            self.tree = ast.parse(self.source)
        except SyntaxError:
            self.tree = None
        self.lines = self.source.splitlines()

    def instrument_code(self, source_code, func_name):
        try:
            tree = ast.parse(source_code)
            instrumenter = CodeInstrumenter()
            tree = instrumenter.visit(tree)
            ast.fix_missing_locations(tree)
            log_helper = f"""\ndef log_function(info_str):\n    with open("test_logs/{func_name}.log", "a") as file:\n        file.write(info_str)\n"""
            return ast.unparse(tree) + log_helper
        except Exception:
            return source_code

    def extract_tasks(self):
        if not self.tree: return []
        tasks = []

        # Extract module-level imports, ensuring __future__ imports come first since Python requires __future__ before all other statements
        future_imports = []
        regular_imports = []
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                unparsed = ast.unparse(node)
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("__future__"):
                    future_imports.append(unparsed)
                else:
                    regular_imports.append(unparsed)
        all_imports = future_imports + regular_imports
        import_header = "\n".join(all_imports) + "\n\n"

        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"): continue

                # Extract raw source of the function
                if node.end_lineno:
                    func_source = textwrap.dedent("\n".join(self.lines[node.lineno-1 : node.end_lineno]))
                else:
                    continue # Python < 3.8 compat or error

                if len(func_source.splitlines()) < 3: continue

                # Formatting for LeetCode Style "class Solution"
                def_line_index = -1
                lines = func_source.splitlines()
                for idx, line in enumerate(lines):
                    if f"def {node.name}" in line:
                        def_line_index = idx
                        break

                # Add 'self' to arguments
                if def_line_index != -1:
                    def_line = lines[def_line_index]
                    if "():" in def_line:
                        lines[def_line_index] = def_line.replace("():", "(self):")
                    else:
                        lines[def_line_index] = def_line.replace(f"def {node.name}(", f"def {node.name}(self, ")
                    func_source_with_self = "\n".join(lines)
                else:
                    func_source_with_self = func_source

                # Wrap code to Solution class for TestEval harness
                wrapped_code = "class Solution:\n" + textwrap.indent(func_source_with_self, "    ")
                final_code_for_dataset = import_header + wrapped_code

                # Analyze Difficulty
                difficulty_level, complexity_score = analyze_code(func_source)

                # Extract Blocks
                block_visitor = BlockExtractor(node.lineno)
                block_visitor.visit(node)
                blocks_data = block_visitor.blocks

                # Identify Target Lines (Adjust for wrapper offset)
                targets = []
                class_wrapper_offset = len(import_header.splitlines()) + 1 # imports + class def

                for n in ast.walk(node):
                    if isinstance(n, (ast.If, ast.Return, ast.Raise)):
                        rel_line = n.lineno - node.lineno
                        targets.append(rel_line + class_wrapper_offset + 1)

                desc = ast.get_docstring(node) or f"Implement {node.name}."
                num_lines = len(func_source.splitlines())

                task_base = {
                    "task_num": int(hashlib.md5(f"{self.file_path.stem}_{node.name}".encode()).hexdigest(), 16) % 100000,
                    "task_title": f"RealWorld::{self.file_path.name}::{node.name}",
                    "difficulty": difficulty_level,
                    "complexity_score": complexity_score,
                    "num_lines": num_lines,
                    "source_file": self.file_path.name,
                    "func_name": node.name,
                    "description": desc,
                    "python_solution": final_code_for_dataset,
                    "blocks": blocks_data,
                    "target_lines": sorted(list(set(targets))) if targets else [1]
                }

                task_all = task_base.copy()
                task_all["python_solution_instrumented"] = self.instrument_code(func_source, node.name)
                task_all["sampled_paths"] = []
                task_all["sampled_condition_paths"] = []

                # Attach metadata used for balancing (not written to JSONL)
                meta = {
                    "source_file": self.file_path.name,
                    "complexity_score": complexity_score,
                    "num_lines": num_lines,
                }

                tasks.append((task_base, task_all, meta))

        return tasks


def balance_dataset(all_tasks, target_count=None, max_per_file=10, seed=42):
    """
    Automated stratified random sampling to eliminate manual selection bias.

    Strategy (two-phase, reproducible):
    1. Per-file random cap: shuffle each source file's tasks with a fixed seed,
       then take the first min(n, max_per_file) at random. This prevents any
       single file from dominating while removing the previous complexity-ranking
       bias (picking only the "most interesting" functions by CC).
    2. Proportional stratified sample: if a target_count is given, allocate
       slots to each difficulty tier proportional to its share in the post-cap
       pool, then sample randomly within each tier. Allocation is data-driven,
       not a fixed 40/30/30 split.

    Reproducibility: all randomness is sourced from a single seeded RNG so the
    dataset composition is fully deterministic for a given seed.
    """
    rng = random.Random(seed)

    by_file = defaultdict(list)
    for task in all_tasks:
        by_file[task[2]["source_file"]].append(task)

    num_files = len(by_file)
    logging.info(f"Balancing: {len(all_tasks)} total functions from {num_files} files "
                 f"(max {max_per_file}/file, seed={seed})")

    # Phase 1: per-file random cap
    pool = []
    for _, file_tasks in sorted(by_file.items()):
        rng.shuffle(file_tasks)
        pool.extend(file_tasks[:max_per_file])

    logging.info(f"After per-file cap: {len(pool)} candidates")

    if target_count is None or len(pool) <= target_count:
        return pool

    # Phase 2: proportional stratified random sample
    by_diff = defaultdict(list)
    for task in pool:
        by_diff[task[0]["difficulty"]].append(task)

    total_pool = len(pool)
    selected = []
    allocated = 0
    tiers = sorted(by_diff.keys())

    for i, diff in enumerate(tiers):
        tier_tasks = list(by_diff[diff])
        rng.shuffle(tier_tasks)
        if i < len(tiers) - 1:
            n = round(target_count * len(tier_tasks) / total_pool)
        else:
            # Last tier absorbs rounding remainder to hit target_count exactly
            n = target_count - allocated
        n = max(0, min(n, len(tier_tasks)))
        selected.extend(tier_tasks[:n])
        allocated += n
        logging.info(f"  Difficulty {diff}: pool {len(tier_tasks)} -> selected {n}")

    return selected


def print_summary(all_tasks, selected_tasks):
    """Prints a formatted summary table of the dataset composition."""

    # Before balancing
    by_file_all = defaultdict(list)
    for t in all_tasks:
        by_file_all[t[2]["source_file"]].append(t)

    # After balancing
    by_file_sel = defaultdict(list)
    for t in selected_tasks:
        by_file_sel[t[2]["source_file"]].append(t)

    print("\n" + "=" * 90)
    print("DATASET COMPOSITION SUMMARY")
    print("=" * 90)

    # Per-file table
    header = f"{'Source File':<35} {'Total':>5} {'Selected':>8} {'Easy':>5} {'Med':>5} {'Hard':>5} {'Avg Lines':>9}"
    print(header)
    print("-" * 90)

    total_all = 0
    total_sel = 0
    total_easy = 0
    total_med = 0
    total_hard = 0

    for filename in sorted(set(list(by_file_all.keys()) + list(by_file_sel.keys()))):
        all_count = len(by_file_all.get(filename, []))
        sel_tasks = by_file_sel.get(filename, [])
        sel_count = len(sel_tasks)

        easy = sum(1 for t in sel_tasks if t[0]["difficulty"] == 1)
        med = sum(1 for t in sel_tasks if t[0]["difficulty"] == 2)
        hard = sum(1 for t in sel_tasks if t[0]["difficulty"] == 3)
        avg_lines = sum(t[2]["num_lines"] for t in sel_tasks) / sel_count if sel_count else 0

        total_all += all_count
        total_sel += sel_count
        total_easy += easy
        total_med += med
        total_hard += hard

        print(f"{filename:<35} {all_count:>5} {sel_count:>8} {easy:>5} {med:>5} {hard:>5} {avg_lines:>9.1f}")

    print("-" * 90)
    print(f"{'TOTAL':<35} {total_all:>5} {total_sel:>8} {total_easy:>5} {total_med:>5} {total_hard:>5}")
    print()

    # Difficulty distribution
    print("Difficulty Distribution:")
    for label_id, label in DIFFICULTY_LABELS.items():
        count = sum(1 for t in selected_tasks if t[0]["difficulty"] == label_id)
        pct = (count / total_sel * 100) if total_sel else 0
        bar = "#" * int(pct / 2)
        print(f"  {label:<8} {count:>3} ({pct:>5.1f}%)  {bar}")
    print("=" * 90)


def generate_datasets(input_dir: Path, output_base: Path, output_all: Path,
                      target_count=None, max_per_file=10, seed=42):
    if not input_dir.exists():
        logging.error(f"Input directory not found: {input_dir}")
        return False

    logging.info(f"Scanning for Python files in: {input_dir}")
    all_tasks = []

    files = list(input_dir.glob("*.py"))
    logging.info(f"Found {len(files)} files.")

    for py_file in files:
        logging.info(f"Processing {py_file.name}...")
        try:
            analyzer = CodeAnalyzer(py_file)
            extracted = analyzer.extract_tasks()
            logging.info(f"  -> Extracted {len(extracted)} tasks.")
            all_tasks.extend(extracted)
        except Exception as e:
            logging.error(f"Failed to process {py_file.name}: {e}")

    if not all_tasks:
        logging.warning("No tasks extracted. Check input files.")
        return False

    selected = balance_dataset(all_tasks, target_count, max_per_file, seed)

    print_summary(all_tasks, selected)

    output_base.parent.mkdir(parents=True, exist_ok=True)

    logging.info(f"Writing {len(selected)} tasks to {output_base}")
    with open(output_base, "w", encoding="utf-8") as f:
        for task in selected:
            f.write(json.dumps(task[0]) + "\n")

    logging.info(f"Writing enriched tasks to {output_all}")
    with open(output_all, "w", encoding="utf-8") as f:
        for task in selected:
            f.write(json.dumps(task[1]) + "\n")

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Real World JSONL Dataset from Python files.")
    parser.add_argument("--input-dir", type=str, default=str(DEFAULT_INPUT_DIR), help="Directory containing .py source files")
    parser.add_argument("--output-base", type=str, default=str(DEFAULT_OUTPUT_BASE), help="Output path for base JSONL")
    parser.add_argument("--output-all", type=str, default=str(DEFAULT_OUTPUT_ALL), help="Output path for enriched JSONL")
    parser.add_argument("--target-count", type=int, default=None,
                        help="Target N after stratified sampling. Omit to take all valid functions (recommended for publication).")
    parser.add_argument("--max-per-file", type=int, default=10,
                        help="Max functions sampled per source file (prevents single-domain over-representation, default=10).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible stratified sampling (default=42).")

    args = parser.parse_args()

    success = generate_datasets(
        Path(args.input_dir), Path(args.output_base), Path(args.output_all),
        target_count=args.target_count, max_per_file=args.max_per_file, seed=args.seed
    )
    if success:
        print("\n[SUCCESS] Dataset generation complete.")
    else:
        print("\n[FAILURE] Could not generate datasets.")
