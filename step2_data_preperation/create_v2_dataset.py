"""
Function Extractor v2 — Phase 2

Scans source files (both the existing leaked real_world/ files AND newly cloned
unleaked repos) and produces a candidate pool of focal functions that pass all
v2 quality filters:

  - Has an English docstring
  - Cyclomatic complexity (Radon CC) >= MIN_CC (3)
  - 3 <= LOC <= 80
  - Not a dunder / test / deprecated / trivial getter
  - Focal function alone fits in <= MAX_FOCAL_TOKENS on all cohort tokenizers

Output: sources/v2_candidates.jsonl  (one JSON object per candidate function)

Usage:
    python step2_data_preperation/create_v2_dataset.py
    python step2_data_preperation/create_v2_dataset.py --no-token-check   # skip slow tokenizer load
    python step2_data_preperation/create_v2_dataset.py --input-dir path/to/pyfiles
"""

import argparse
import ast
import hashlib
import json
import logging
import sys
import textwrap
from pathlib import Path

from radon.complexity import cc_visit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources"
REPOS_DIR = SOURCES_DIR / "repos"
V2_REPOS_FILE = SOURCES_DIR / "v2_repos.json"
OUTPUT_FILE = SOURCES_DIR / "v2_candidates.jsonl"
LEAKED_REAL_WORLD_DIR = PROJECT_ROOT / "TestEval" / "data" / "real_world"

# Filter thresholds — must match design.yaml
MIN_CC = 3
MIN_LOC = 3
MAX_LOC = 80
MAX_FOCAL_TOKENS = 2000

# Models whose tokenizers we check (must match run_experiments.py MODELS_TO_RUN)
COHORT_MODEL_IDS = [
    "google/gemma-4-E4B-it",
    "Qwen/Qwen3.5-4B",
    "Qwen/Qwen3-4B-Thinking-2507",
    "mistralai/Ministral-3-3B-Reasoning-2512",
    "ibm-granite/granite-4.0-micro",
]

_TOKENIZERS: dict = {}   # model_id -> tokenizer (lazy-loaded)


def _load_tokenizers() -> None:
    try:
        from transformers import AutoTokenizer
    except ImportError:
        logging.error("transformers not installed. Run: pip install transformers")
        sys.exit(1)

    for model_id in COHORT_MODEL_IDS:
        logging.info(f"Loading tokenizer: {model_id}")
        try:
            tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            _TOKENIZERS[model_id] = tok
        except Exception as e:
            logging.warning(f"  Could not load tokenizer for {model_id}: {e}. Skipping.")


def _count_tokens(text: str) -> dict[str, int]:
    """Return token count per model for the given text."""
    if not _TOKENIZERS:
        return {}
    counts = {}
    for model_id, tok in _TOKENIZERS.items():
        try:
            counts[model_id] = len(tok.encode(text, add_special_tokens=False))
        except Exception:
            counts[model_id] = -1
    return counts


def _passes_token_budget(text: str) -> bool:
    """True if all loaded tokenizers agree that text fits in MAX_FOCAL_TOKENS."""
    if not _TOKENIZERS:
        return True  # skip check when tokenizers not loaded
    for model_id, tok in _TOKENIZERS.items():
        try:
            if len(tok.encode(text, add_special_tokens=False)) > MAX_FOCAL_TOKENS:
                return False
        except Exception:
            pass
    return True


def _is_excluded(name: str, source: str) -> bool:
    """Return True if the function should be filtered out."""
    # Dunder methods
    if name.startswith("__") and name.endswith("__"):
        return True
    # Test functions
    if name.startswith("test_") or name.startswith("Test"):
        return True
    # Deprecated markers
    lower = source.lower()
    if "deprecated" in lower or "@deprecated" in lower:
        return True
    # Trivial getter/setter patterns (single return or assignment body)
    stripped_lines = [l.strip() for l in source.splitlines() if l.strip() and not l.strip().startswith("#")]
    body_lines = [l for l in stripped_lines if not l.startswith("def ") and not l.startswith('"""') and not l.startswith("'''") and l != "..."]
    if len(body_lines) <= 1:
        return True
    return False


def _difficulty(cc: int) -> int:
    if cc <= 5:
        return 1   # Easy
    elif cc <= 10:
        return 2   # Medium
    return 3       # Hard


def _extract_target_lines(func_node: ast.FunctionDef, import_header_lines: int) -> list[int]:
    """Extract If/Return/Raise line numbers adjusted for the class Solution wrapper offset."""
    class_wrapper_offset = import_header_lines + 1  # imports + "class Solution:"
    targets = []
    for n in ast.walk(func_node):
        if isinstance(n, (ast.If, ast.Return, ast.Raise)):
            rel = n.lineno - func_node.lineno
            targets.append(rel + class_wrapper_offset + 1)
    return sorted(set(targets)) or [1]


def extract_from_file(
    py_file: Path,
    repo_name: str,
    commit_sha: str,
    commit_date: str,
    leaked: bool,
    domain: str,
) -> list[dict]:
    """Parse one .py file and return candidate function records."""
    try:
        source = py_file.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logging.warning(f"  Could not read {py_file}: {e}")
        return []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        logging.warning(f"  SyntaxError in {py_file.name}: {e}")
        return []

    lines = source.splitlines()

    # Collect module-level imports (future first)
    future_imports, regular_imports = [], []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            unparsed = ast.unparse(node)
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("__future__"):
                future_imports.append(unparsed)
            else:
                regular_imports.append(unparsed)
    import_header = "\n".join(future_imports + regular_imports)
    import_header_lines = len(import_header.splitlines()) if import_header else 0
    import_prefix = (import_header + "\n\n") if import_header else ""

    # Map each function node to its qualified name (Class.method, or bare name for
    # module-level functions) so that same-named methods in different classes in the
    # same file don't collide when hashed into task_num/id below.
    qualnames = {}
    def _record_qualnames(node, scope_parts):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualnames[id(child)] = ".".join(scope_parts + [child.name])
                _record_qualnames(child, scope_parts + [child.name])
            elif isinstance(child, ast.ClassDef):
                _record_qualnames(child, scope_parts + [child.name])
            else:
                _record_qualnames(child, scope_parts)
    _record_qualnames(tree, [])

    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.end_lineno is None:
            continue
        qualname = qualnames.get(id(node), node.name)

        # --- Docstring check ---
        docstring = ast.get_docstring(node)
        if not docstring:
            continue

        # --- Extract raw source ---
        func_lines = lines[node.lineno - 1: node.end_lineno]
        func_source = textwrap.dedent("\n".join(func_lines))
        loc = len([l for l in func_lines if l.strip()])

        # --- LOC filter ---
        if loc < MIN_LOC or loc > MAX_LOC:
            continue

        # --- Exclusion rules ---
        if _is_excluded(node.name, func_source):
            continue

        # --- Cyclomatic complexity ---
        try:
            cc_results = cc_visit(func_source)
            max_cc = max((c.complexity for c in cc_results), default=1)
        except Exception:
            max_cc = 1
        if max_cc < MIN_CC:
            continue

        # --- Build Solution-wrapped code (backward-compat with evaluate_results.py) ---
        # NOTE: self-presence must be checked via the AST arg list, not by string-matching
        # a single line. For multi-line signatures (each parameter on its own line), "self"
        # can appear on a line AFTER the "def {name}(" line; checking only that one line
        # wrongly concludes "no self" and inserts a duplicate "self" parameter, producing a
        # SyntaxError ("duplicate argument 'self'") when the wrapped code is later imported.
        already_has_self = bool(node.args.args) and node.args.args[0].arg == "self"
        wrapped_lines = func_source.splitlines()
        if not already_has_self:
            for i, ln in enumerate(wrapped_lines):
                if f"def {node.name}" in ln:
                    if f"def {node.name}():" in ln:
                        wrapped_lines[i] = ln.replace(f"def {node.name}():", f"def {node.name}(self):")
                    else:
                        wrapped_lines[i] = ln.replace(f"def {node.name}(", f"def {node.name}(self, ")
                    break
        wrapped = "class Solution:\n" + textwrap.indent("\n".join(wrapped_lines), "    ")
        python_solution = import_prefix + wrapped

        # --- Token budget check ---
        if not _passes_token_budget(func_source):
            logging.debug(f"  Token budget exceeded: {node.name} in {py_file.name}")
            continue

        focal_token_counts = _count_tokens(func_source)

        # --- Assemble record ---
        # Hash on qualname (not just node.name) so two same-named methods in different
        # classes of the same file get distinct task_num/id instead of colliding.
        uid = hashlib.md5(f"{repo_name}::{py_file.name}::{qualname}".encode()).hexdigest()[:12]
        task_num = int(hashlib.md5(f"{repo_name}_{py_file.stem}_{qualname}".encode()).hexdigest(), 16) % 1_000_000

        record = {
            "id": f"rwt2_{uid}",
            "task_num": task_num,
            "task_title": f"RealWorldV2::{py_file.stem}::{node.name}",
            "repo": repo_name,
            "commit_sha": commit_sha,
            "commit_date": commit_date,
            "license": "",                     # filled by package_v2_dataset.py
            "leaked": leaked,
            "domain": domain,
            "source_file": py_file.name,
            "func_name": node.name,
            "signature": f"def {node.name}({ast.unparse(node.args)})",
            "docstring": docstring,
            "focal_function": func_source,
            "python_solution": python_solution,  # backward-compat Solution wrapper
            "cyclomatic_complexity": max_cc,
            "difficulty": _difficulty(max_cc),
            "loc": loc,
            "focal_token_counts": focal_token_counts,
            # Fields filled by later phases:
            "dependency_level": None,          # Phase 3
            "context_card": None,              # Phase 4
            "has_failtopass": False,           # Phase 5
            "gold_test_path": None,            # Phase 5 (path only, not content)
            # Backward-compat harness fields:
            "blocks": [],
            "target_lines": _extract_target_lines(node, import_header_lines),
            "description": docstring,
        }
        candidates.append(record)

    return candidates


def scan_repo(repo_meta: dict) -> list[dict]:
    """Scan all .py files in a repo's local clone and return candidates."""
    repo_name = repo_meta["repo"]
    leaked = repo_meta.get("leaked", False)

    if leaked:
        src_dir = LEAKED_REAL_WORLD_DIR
        if not src_dir.exists():
            logging.warning(f"Leaked source dir missing: {src_dir}")
            return []
        # Only scan the specific file mapped to this repo entry
        local_file = repo_meta.get("local_file")
        if local_file:
            candidate = src_dir / local_file
            py_files = [candidate] if candidate.exists() else []
        else:
            # Fallback: scan all non-internal files (should not happen with correct metadata)
            py_files = [p for p in src_dir.glob("*.py") if not p.stem.startswith("our_")]
    else:
        # Use cloned repo
        clone_path = REPOS_DIR / repo_name.replace("/", "_")
        if not clone_path.exists():
            logging.warning(f"Clone missing for {repo_name}: {clone_path}")
            return []
        py_files = [p for p in clone_path.rglob("*.py")
                    if not any(part.startswith(".") for part in p.parts)
                    and "test" not in p.stem.lower()
                    and "setup" not in p.stem.lower()]

    candidates = []
    for py_file in py_files:
        extracted = extract_from_file(
            py_file=py_file,
            repo_name=repo_name,
            commit_sha=repo_meta.get("commit_sha", "unknown"),
            commit_date=repo_meta.get("commit_date", "unknown"),
            leaked=leaked,
            domain=repo_meta.get("domain", "unknown"),
        )
        candidates.extend(extracted)
        if extracted:
            logging.info(f"  {py_file.name}: {len(extracted)} candidates")

    return candidates


def main():
    parser = argparse.ArgumentParser(description="Extract v2 candidate functions from all repos")
    parser.add_argument("--no-token-check", action="store_true",
                        help="Skip tokenizer loading (faster, but no token budget enforcement)")
    parser.add_argument("--leaked-only", action="store_true",
                        help="Only process the leaked (existing) real_world files")
    args = parser.parse_args()

    if not args.no_token_check:
        logging.info("Loading cohort tokenizers (this may take a minute)...")
        _load_tokenizers()
    else:
        logging.info("Skipping tokenizer check (--no-token-check)")

    # Load repo metadata
    if not V2_REPOS_FILE.exists():
        logging.error(f"Repo metadata not found: {V2_REPOS_FILE}")
        logging.error("Run collect_sources_v2.py first.")
        sys.exit(1)

    repos = json.loads(V2_REPOS_FILE.read_text())
    if args.leaked_only:
        repos = [r for r in repos if r.get("leaked")]

    logging.info(f"Processing {len(repos)} repos...")

    all_candidates = []
    for repo_meta in repos:
        logging.info(f"=== {repo_meta['repo']} (leaked={repo_meta.get('leaked')}) ===")
        candidates = scan_repo(repo_meta)
        all_candidates.extend(candidates)
        logging.info(f"  Subtotal: {len(candidates)} candidates from this repo")

    logging.info(f"\nTotal candidates: {len(all_candidates)}")
    target = 300 * 3  # 3x headroom before QC
    if len(all_candidates) < target:
        logging.warning(f"Candidate pool {len(all_candidates)} is below 3x target ({target}). "
                        "Consider adding more repos in collect_sources_v2.py.")

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for rec in all_candidates:
            f.write(json.dumps(rec) + "\n")

    logging.info(f"Written to {OUTPUT_FILE}")

    # Summary
    leaked_n = sum(1 for r in all_candidates if r["leaked"])
    unleaked_n = len(all_candidates) - leaked_n
    by_diff = {1: 0, 2: 0, 3: 0}
    for r in all_candidates:
        by_diff[r["difficulty"]] = by_diff.get(r["difficulty"], 0) + 1

    print(f"\n{'='*55}")
    print(f"Candidates extracted:  {len(all_candidates)}")
    print(f"  Leaked:              {leaked_n}")
    print(f"  Unleaked:            {unleaked_n}")
    print(f"  Easy (CC 1-5):       {by_diff.get(1,0)}")
    print(f"  Medium (CC 6-10):    {by_diff.get(2,0)}")
    print(f"  Hard (CC >10):       {by_diff.get(3,0)}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
