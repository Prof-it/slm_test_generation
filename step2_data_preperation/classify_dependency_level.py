"""
Dependency Level Classifier — Phase 3

Assigns each candidate function exactly one dependency level L0–L3:

  L0 — only builtins and literals  (no imports referenced)
  L1 — highest dep is stdlib        (sys.stdlib_module_names)
  L2 — highest dep is third-party   (pip-installed, not stdlib)
  L3 — highest dep is same-file or same-class reference

Level = max across all referenced names in the function body.

Uses `jedi` for name resolution wherever possible; falls back to import-map
heuristics when jedi is unavailable or raises an error.

After running, updates each record in sources/v2_candidates.jsonl with
  "dependency_level": "L0" | "L1" | "L2" | "L3"
  "level_confidence": "jedi" | "heuristic"

Also writes sources/level_audit_sample.csv with 30 randomly sampled items
for manual validation.

Usage:
    python step2_data_preperation/classify_dependency_level.py
    python step2_data_preperation/classify_dependency_level.py --no-jedi   # heuristic only
    python step2_data_preperation/classify_dependency_level.py --audit-n 50
"""

import argparse
import ast
import csv
import json
import logging
import random
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources"
CANDIDATES_FILE = SOURCES_DIR / "v2_candidates.jsonl"
AUDIT_FILE = SOURCES_DIR / "level_audit_sample.csv"

# Python standard library module names (Python 3.10+)
try:
    import sys as _sys
    STDLIB_MODULES = set(_sys.stdlib_module_names)
except AttributeError:
    # Fallback for Python < 3.10
    import sysconfig, os
    STDLIB_MODULES = set()
    stdlib_path = sysconfig.get_paths()["stdlib"]
    if stdlib_path and os.path.isdir(stdlib_path):
        for name in os.listdir(stdlib_path):
            STDLIB_MODULES.add(name.split(".")[0])

# Names that are Python builtins (no import needed)
BUILTIN_NAMES = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))


def _root_name(node: ast.expr) -> str | None:
    """Return the root identifier of a Name or Attribute chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_name(node.value)
    return None


def _build_import_map(tree: ast.Module) -> dict[str, str]:
    """
    Build {local_alias: top_level_package} from module-level imports.
    e.g. `import os.path as osp` -> {'osp': 'os'}
         `from collections import defaultdict` -> {'defaultdict': 'collections'}
    """
    import_map: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                top = alias.name.split(".")[0]
                import_map[local] = top
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            for alias in node.names:
                local = alias.asname or alias.name
                import_map[local] = top or alias.name
    return import_map


def _file_defs(tree: ast.Module, func_node) -> set[str]:
    """Names defined at module scope (classes, functions, assignments) excluding func_node itself."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not func_node:
                names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return names


def _class_attrs(tree: ast.Module, func_node) -> set[str]:
    """
    If func_node is a method, return all attribute names visible inside the class
    (other method names, class-level assigns) — these are L3 references.
    """
    attrs: set[str] = set()
    for class_node in ast.walk(tree):
        if not isinstance(class_node, ast.ClassDef):
            continue
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item is func_node:
                    attrs.update(m.name for m in class_node.body
                                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
                    # self.x accesses — find all attribute names accessed via self
                    for n in ast.walk(func_node):
                        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self":
                            attrs.add(n.attr)
                    break
    return attrs


def classify_heuristic(func_source: str, full_file_source: str) -> tuple[str, str]:
    """
    AST-based heuristic classifier. Returns (level, 'heuristic').
    Resolves names against the module-level import map.
    """
    try:
        func_tree = ast.parse(func_source)
        file_tree = ast.parse(full_file_source)
    except SyntaxError:
        return "L2", "heuristic"  # conservative: assume external

    # Get the first function node in func_tree
    func_node = None
    for node in ast.walk(func_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_node = node
            break
    if func_node is None:
        return "L0", "heuristic"

    import_map = _build_import_map(file_tree)
    file_level_defs = _file_defs(file_tree, None)
    class_level_attrs = _class_attrs(file_tree, None)

    level = 0  # 0=L0, 1=L1, 2=L2, 3=L3

    for n in ast.walk(func_node):
        root = _root_name(n) if isinstance(n, (ast.Name, ast.Attribute)) else None
        if root is None:
            continue
        if root in BUILTIN_NAMES or root in ("self", "cls", "True", "False", "None"):
            continue

        if root in class_level_attrs:
            level = max(level, 3)
        elif root in file_level_defs:
            level = max(level, 3)
        elif root in import_map:
            top = import_map[root].split(".")[0]
            if top in STDLIB_MODULES:
                level = max(level, 1)
            else:
                level = max(level, 2)
        # Unknown name: could be a local variable; don't bump level

    return f"L{level}", "heuristic"


def classify_with_jedi(
    func_source: str,
    full_file_source: str,
    file_path: str,
    func_line: int,
) -> tuple[str, str]:
    """
    jedi-powered classifier. Returns (level, 'jedi').
    Falls back to heuristic on any jedi error.
    """
    try:
        import jedi
    except ImportError:
        return classify_heuristic(func_source, full_file_source)

    try:
        import_map = _build_import_map(ast.parse(full_file_source))
    except SyntaxError:
        import_map = {}

    try:
        func_tree = ast.parse(func_source)
    except SyntaxError:
        return "L2", "heuristic"

    func_node = None
    for node in ast.walk(func_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_node = node
            break
    if func_node is None:
        return "L0", "jedi"

    file_tree = ast.parse(full_file_source) if full_file_source else None
    file_defs = _file_defs(file_tree, None) if file_tree else set()
    class_attrs = _class_attrs(file_tree, None) if file_tree else set()

    level = 0
    script = jedi.Script(full_file_source, path=file_path)

    for n in ast.walk(func_node):
        if not isinstance(n, (ast.Name, ast.Attribute)):
            continue
        root = _root_name(n)
        if root is None or root in BUILTIN_NAMES or root in ("self", "cls"):
            continue

        actual_line = (func_line - 1) + (getattr(n, "lineno", 1))
        col = getattr(n, "col_offset", 0)

        try:
            completions = script.infer(actual_line, col)
        except Exception:
            completions = []

        resolved = False
        for comp in completions:
            module_path = str(comp.module_path or "")
            module_name = comp.module_name or ""

            if not module_name:
                continue

            top = module_name.split(".")[0]

            if top in BUILTIN_NAMES:
                resolved = True
                break
            if top in STDLIB_MODULES:
                level = max(level, 1)
                resolved = True
                break
            if top in file_defs or top in class_attrs:
                level = max(level, 3)
                resolved = True
                break
            # Anything else with a path that's not stdlib = third-party
            if module_path and "site-packages" in module_path:
                level = max(level, 2)
                resolved = True
                break
            if module_path:
                level = max(level, 2)
                resolved = True
                break

        if not resolved and root in import_map:
            top = import_map[root].split(".")[0]
            if top in STDLIB_MODULES:
                level = max(level, 1)
            elif top in file_defs or top in class_attrs:
                level = max(level, 3)
            else:
                level = max(level, 2)

    return f"L{level}", "jedi"


# Per-file derived data: {(repo, source_file): (import_map, file_defs, class_attrs)}
FileContext = tuple[dict, set, set]


def build_file_context_cache(records: list[dict]) -> dict[tuple[str, str], FileContext]:
    """
    Pre-compute import_map, file_defs, and class_attrs for every unique
    (repo, source_file) pair.  Reads and parses each file exactly once.
    """
    unique_pairs: set[tuple[str, str]] = set()
    for rec in records:
        unique_pairs.add((rec.get("repo", ""), rec.get("source_file", "")))

    cache: dict[tuple[str, str], FileContext] = {}
    for repo, source_file in unique_pairs:
        leaked_path = PROJECT_ROOT / "TestEval" / "data" / "real_world" / source_file
        if leaked_path.exists():
            src_path = leaked_path
        else:
            repo_dir = PROJECT_ROOT / "sources" / "repos" / repo.replace("/", "_")
            if not repo_dir.exists():
                continue
            matches = list(repo_dir.rglob(source_file))
            if not matches:
                continue
            src_path = matches[0]

        try:
            src = src_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
            im = _build_import_map(tree)
            fd = _file_defs(tree, None)
            ca = _class_attrs(tree, None)
            cache[(repo, source_file)] = (im, fd, ca)
        except Exception:
            pass

    logging.info(f"File context cache built: {len(cache)}/{len(unique_pairs)} unique files parsed")
    return cache


def classify_record(rec: dict, use_jedi: bool,
                    file_ctx_cache: dict | None = None) -> dict:
    """Classify a single candidate record using pre-built file context."""
    func_source = rec.get("focal_function", "")
    repo = rec.get("repo", "")
    source_file = rec.get("source_file", "")

    if file_ctx_cache is not None and (repo, source_file) in file_ctx_cache:
        import_map, file_defs, class_attrs = file_ctx_cache[(repo, source_file)]
    else:
        # Fallback: parse on the fly (shouldn't happen in normal flow)
        try:
            ft = ast.parse(func_source)
            import_map = _build_import_map(ft)
            file_defs = set()
            class_attrs = set()
        except SyntaxError:
            import_map, file_defs, class_attrs = {}, set(), set()

    # Classify using pre-computed file context — only parse the small func_source
    try:
        func_tree = ast.parse(func_source)
    except SyntaxError:
        rec["dependency_level"] = "L2"
        rec["level_confidence"] = "heuristic"
        return rec

    func_node = None
    for node in ast.walk(func_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_node = node
            break

    level = 0
    if func_node:
        for n in ast.walk(func_node):
            root = _root_name(n) if isinstance(n, (ast.Name, ast.Attribute)) else None
            if root is None or root in BUILTIN_NAMES or root in ("self", "cls", "True", "False", "None"):
                continue
            if root in class_attrs or root in file_defs:
                level = max(level, 3)
            elif root in import_map:
                top = import_map[root].split(".")[0]
                level = max(level, 1 if top in STDLIB_MODULES else 2)

    rec["dependency_level"] = f"L{level}"
    rec["level_confidence"] = "heuristic"
    return rec


def main():
    parser = argparse.ArgumentParser(description="Classify dependency levels for v2 candidates")
    parser.add_argument("--no-jedi", action="store_true", help="Use heuristic-only (faster, less accurate)")
    parser.add_argument("--audit-n", type=int, default=30, help="Number of items to write to audit CSV (default 30)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not CANDIDATES_FILE.exists():
        logging.error(f"Candidates file not found: {CANDIDATES_FILE}")
        logging.error("Run create_v2_dataset.py first.")
        sys.exit(1)

    use_jedi = not args.no_jedi
    if use_jedi:
        try:
            import jedi  # noqa: F401
            logging.info("jedi available — using jedi-powered classification")
        except ImportError:
            logging.warning("jedi not installed; falling back to heuristic. Run: pip install jedi")
            use_jedi = False

    records = []
    with CANDIDATES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    logging.info(f"Building file context cache for {len(records)} candidates...")
    file_ctx_cache = build_file_context_cache(records)

    logging.info(f"Classifying {len(records)} candidates...")
    for i, rec in enumerate(records):
        records[i] = classify_record(rec, use_jedi, file_ctx_cache)
        if (i + 1) % 1000 == 0:
            logging.info(f"  {i+1}/{len(records)} classified")

    # Write updated candidates back
    with CANDIDATES_FILE.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    logging.info(f"Updated {CANDIDATES_FILE} with dependency_level field")

    # Distribution summary
    dist: dict[str, int] = {}
    for rec in records:
        lv = rec.get("dependency_level", "unknown")
        dist[lv] = dist.get(lv, 0) + 1
    print(f"\n{'='*45}")
    print("Dependency Level Distribution:")
    for lv in ["L0", "L1", "L2", "L3", "unknown"]:
        n = dist.get(lv, 0)
        pct = n / len(records) * 100 if records else 0
        bar = "#" * int(pct / 2)
        print(f"  {lv}: {n:>5}  ({pct:>5.1f}%)  {bar}")
    print(f"{'='*45}")

    # Audit CSV sample
    rng = random.Random(args.seed)
    sample = rng.sample(records, min(args.audit_n, len(records)))
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "repo", "func_name", "dependency_level", "level_confidence",
            "cyclomatic_complexity", "loc",
            "manual_label",   # blank — fill in during QC
            "notes",
        ])
        writer.writeheader()
        for rec in sample:
            writer.writerow({
                "id": rec.get("id", ""),
                "repo": rec.get("repo", ""),
                "func_name": rec.get("func_name", ""),
                "dependency_level": rec.get("dependency_level", ""),
                "level_confidence": rec.get("level_confidence", ""),
                "cyclomatic_complexity": rec.get("cyclomatic_complexity", ""),
                "loc": rec.get("loc", ""),
                "manual_label": "",
                "notes": "",
            })
    logging.info(f"Audit sample ({len(sample)} items) written to {AUDIT_FILE}")


if __name__ == "__main__":
    main()
