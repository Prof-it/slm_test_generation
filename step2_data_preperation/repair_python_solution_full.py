"""
Targeted repair for the 25 tasks whose stored python_solution_full has the
duplicate-'self' SyntaxError bug (fixed at the source in create_v2_dataset.py,
but the already-built dataset JSONLs still carry the old, broken value).

Re-locates each task's original function in its cloned source repo
(sources/repos/) and re-extracts python_solution_full using the SAME logic as
create_v2_dataset.py's fixed AST-based self-check, then patches just that one
field in-place across all four dataset files. Nothing else about the task
(context_card, dependency_level, leaked, etc.) is touched.

Usage:
    python step2_data_preperation/repair_python_solution_full.py --dry-run
    python step2_data_preperation/repair_python_solution_full.py
"""

import argparse
import ast
import json
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources" / "repos"
DATASET_FILES = [
    PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl",
    PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2-tier-A.jsonl",
    PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2-tier-B.jsonl",
    PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2-tier-C.jsonl",
]

BROKEN_IDS_FILE = Path(__file__).resolve().parent.parent / "step4_evaluation" / "rq_reanalysis_output" / "broken_by_category.json"


def build_python_solution_full(func_source_lines: list[str], func_name: str, import_prefix: str, node: ast.AST) -> str:
    """Mirrors create_v2_dataset.py's fixed wrapping logic exactly."""
    already_has_self = bool(node.args.args) and node.args.args[0].arg == "self"
    wrapped_lines = list(func_source_lines)
    if not already_has_self:
        for i, ln in enumerate(wrapped_lines):
            if f"def {func_name}" in ln:
                if f"def {func_name}():" in ln:
                    wrapped_lines[i] = ln.replace(f"def {func_name}():", f"def {func_name}(self):")
                else:
                    wrapped_lines[i] = ln.replace(f"def {func_name}(", f"def {func_name}(self, ")
                break
    wrapped = "class Solution:\n" + textwrap.indent("\n".join(wrapped_lines), "    ")
    return import_prefix + wrapped


def find_source_file(repo_dir_name: str, source_file: str) -> Path | None:
    repo_dir = SOURCES_DIR / repo_dir_name
    if not repo_dir.exists():
        return None
    matches = list(repo_dir.rglob(source_file))
    return matches[0] if len(matches) == 1 else (matches if matches else None)


def extract_import_prefix(tree: ast.Module) -> str:
    """Collect EVERY top-level import statement in the module (not just a
    contiguous leading block) -- mirrors create_v2_dataset.py's logic exactly
    (lines 168-179), which walks tree.body for ast.Import/ImportFrom nodes
    anywhere at module level, __future__ imports first."""
    future_imports, regular_imports = [], []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            unparsed = ast.unparse(node)
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("__future__"):
                future_imports.append(unparsed)
            else:
                regular_imports.append(unparsed)
    import_header = "\n".join(future_imports + regular_imports)
    return (import_header + "\n\n") if import_header else ""


def repair_task(row: dict) -> str | None:
    """Returns the corrected python_solution_full, or None if the function
    couldn't be re-located (caller should leave the task untouched and flag it)."""
    repo = row["repo"]
    repo_dir_name = repo.replace("/", "_")
    source_file = row.get("source_file", "")
    func_name = row["func_name"]

    candidate = find_source_file(repo_dir_name, source_file)
    if candidate is None:
        print(f"  !! source file not found: {repo_dir_name}/{source_file}")
        return None
    if isinstance(candidate, list):
        # Multiple files with this basename -- disambiguate by matching func_name + docstring.
        found = None
        for c in candidate:
            text = c.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                    doc = ast.get_docstring(node) or ""
                    if row.get("docstring", "").strip()[:60] in doc:
                        found = (c, text, node)
                        break
            if found:
                break
        if not found:
            print(f"  !! ambiguous source file, could not disambiguate: {repo_dir_name}/{source_file}")
            return None
        path, text, node = found
    else:
        path = candidate
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            print(f"  !! source file has a syntax error itself: {path} ({e})")
            return None
        node = None
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name:
                doc = ast.get_docstring(n) or ""
                if row.get("docstring", "").strip()[:60] in doc:
                    node = n
                    break
        if node is None:
            print(f"  !! function {func_name} not found (or docstring mismatch) in {path}")
            return None

    lines = text.splitlines()
    func_lines = lines[node.lineno - 1: node.end_lineno]
    func_source = textwrap.dedent("\n".join(func_lines))
    tree = ast.parse(text)
    import_prefix = extract_import_prefix(tree)

    return build_python_solution_full(func_source.splitlines(), func_name, import_prefix, node)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Report what would change without writing files")
    args = ap.parse_args()

    broken_by_cat = json.load(open(BROKEN_IDS_FILE))
    target_ids = set(broken_by_cat.get("SyntaxError", []))
    print(f"Repairing {len(target_ids)} tasks: {sorted(target_ids)}\n")

    # Use the base dataset file to look up repo/source_file/func_name/docstring once.
    base_records = {}
    for line in (PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        base_records[str(rec["task_num"])] = rec

    repaired = {}
    failed = []
    for tn in sorted(target_ids):
        row = base_records.get(tn)
        if row is None:
            failed.append(tn)
            continue
        print(f"Task {tn} ({row['repo']} :: {row['func_name']})")
        fixed = repair_task(row)
        if fixed is None:
            failed.append(tn)
        else:
            repaired[tn] = fixed
            print(f"  OK -- regenerated python_solution_full ({len(fixed)} chars)")

    print(f"\nRepaired: {len(repaired)}  |  Failed to relocate: {len(failed)} {failed}")

    if args.dry_run:
        print("\n--dry-run set: no files written.")
        return

    for dpath in DATASET_FILES:
        lines = dpath.read_text(encoding="utf-8").splitlines()
        n_patched = 0
        out_lines = []
        for line in lines:
            if not line.strip():
                out_lines.append(line)
                continue
            rec = json.loads(line)
            tn = str(rec.get("task_num"))
            if tn in repaired:
                rec["python_solution_full"] = repaired[tn]
                n_patched += 1
            out_lines.append(json.dumps(rec))
        dpath.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"Patched {n_patched} records in {dpath.name}")


if __name__ == "__main__":
    main()
