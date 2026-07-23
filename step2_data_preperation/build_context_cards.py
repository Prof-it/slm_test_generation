"""
Context Card Builder — Phase 4

Builds three strictly nested context cards (A ⊂ B ⊂ C) for each candidate
function, all within the 6 500-token hard cap.

  Tier A — focal signature + docstring only
  Tier B — A + dependency stubs (signature + ellipsis, NO body)
  Tier C — B + mock/fixture hint comment

Token counts are recorded per cohort tokenizer.  If Tier C exceeds the cap,
the least-referenced dependency stubs are dropped one by one until it fits,
and the trims are logged to cards/trim_log.jsonl.

Output:
  - Writes "context_card" field back into sources/v2_candidates.jsonl
  - cards/v2_cards.jsonl   (one record per function, cards + token counts)
  - cards/trim_log.jsonl   (one record per trim event)

Usage:
    python step2_data_preperation/build_context_cards.py
    python step2_data_preperation/build_context_cards.py --no-token-check
"""

import argparse
import ast
import json
import logging
import sys
import textwrap
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources"
CANDIDATES_FILE = SOURCES_DIR / "v2_candidates.jsonl"
CARDS_DIR = PROJECT_ROOT / "cards"
CARDS_FILE = CARDS_DIR / "v2_cards.jsonl"
TRIM_LOG_FILE = CARDS_DIR / "trim_log.jsonl"

MAX_INPUT_TOKENS = 6500   # hard cap (design.yaml max_input_tokens)

COHORT_MODEL_IDS = [
    "google/gemma-4-E4B-it",
    "Qwen/Qwen3.5-4B",
    "Qwen/Qwen3-4B-Thinking-2507",
    "mistralai/Ministral-3-3B-Reasoning-2512",
    "ibm-granite/granite-4.0-micro",
]

_TOKENIZERS: dict = {}


def _load_tokenizers() -> None:
    try:
        from transformers import AutoTokenizer
    except ImportError:
        logging.error("transformers not installed. Run: pip install transformers")
        sys.exit(1)
    for model_id in COHORT_MODEL_IDS:
        logging.info(f"Loading tokenizer: {model_id}")
        try:
            _TOKENIZERS[model_id] = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        except Exception as e:
            logging.warning(f"  Could not load {model_id}: {e}")


def _count_all(text: str) -> dict[str, int]:
    if not _TOKENIZERS:
        return {}
    result = {}
    for model_id, tok in _TOKENIZERS.items():
        try:
            result[model_id] = len(tok.encode(text, add_special_tokens=False))
        except Exception:
            result[model_id] = -1
    return result


def _max_tokens(counts: dict[str, int]) -> int:
    vals = [v for v in counts.values() if v >= 0]
    return max(vals) if vals else 0


# ---------------------------------------------------------------------------
# AST stub builder
# ---------------------------------------------------------------------------

def _to_stub(src: str) -> str:
    """
    Replace function/method/class bodies with `...`, keeping only the
    signature line and any existing docstring.  Never include implementation.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src  # can't parse — return as-is (will be token-checked anyway)

    class StubTransformer(ast.NodeTransformer):
        def _stub_body(self, node):
            doc = ast.get_docstring(node)
            new_body = []
            if doc:
                new_body.append(ast.Expr(value=ast.Constant(value=doc)))
            new_body.append(ast.Expr(value=ast.Constant(value=...)))
            node.body = new_body
            return node

        def visit_FunctionDef(self, node):
            return self._stub_body(node)

        def visit_AsyncFunctionDef(self, node):
            return self._stub_body(node)

        def visit_ClassDef(self, node):
            # Stub class body but recurse into methods first
            self.generic_visit(node)
            return self._stub_body(node)

    transformer = StubTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:
        return src


def _extract_signature_and_doc(func_source: str) -> str:
    """Return just the signature line + docstring (Tier A content)."""
    try:
        tree = ast.parse(func_source)
    except SyntaxError:
        return func_source

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            # Reconstruct: def name(args) -> ret: """docstring"""
            try:
                args_str = ast.unparse(node.args)
            except Exception:
                args_str = "..."
            returns_str = ""
            if node.returns:
                try:
                    returns_str = f" -> {ast.unparse(node.returns)}"
                except Exception:
                    pass
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            sig = f"{prefix} {node.name}({args_str}){returns_str}:"
            if doc:
                indented_doc = textwrap.indent(f'"""{doc}"""', "    ")
                return f"{sig}\n{indented_doc}\n    ..."
            return f"{sig}\n    ..."
    return func_source


def _build_file_def_stubs(full_file_source: str) -> dict[str, str]:
    """
    Parse a file once and return {def_name: stub_text} for every top-level
    function/class definition.  Called once per unique file, not per record.
    """
    try:
        file_tree = ast.parse(full_file_source)
    except SyntaxError:
        return {}

    file_lines = full_file_source.splitlines()
    defs: dict[str, str] = {}
    for node in ast.walk(file_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if hasattr(node, "end_lineno") and node.end_lineno:
                def_src = "\n".join(file_lines[node.lineno - 1: node.end_lineno])
                try:
                    stub = _to_stub(textwrap.dedent(def_src))
                    defs[node.name] = stub
                except Exception:
                    pass
    return defs


def _collect_dependency_stubs(func_source: str,
                               file_def_stubs: dict[str, str]) -> list[tuple[str, int]]:
    """
    Count calls made in func_source, then look up stubs from the pre-built
    file_def_stubs dict.  Only parses the small func_source — never the full file.
    """
    try:
        func_tree = ast.parse(func_source)
    except SyntaxError:
        return []

    call_counts: dict[str, int] = {}
    for node in ast.walk(func_tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            call_counts[name] = call_counts.get(name, 0) + 1

    stubs: list[tuple[str, int]] = []
    for name, count in call_counts.items():
        if name in file_def_stubs:
            stubs.append((file_def_stubs[name], count))

    stubs.sort(key=lambda x: x[1], reverse=True)
    return stubs


def _mock_hint(func_source: str, full_file_source: str) -> str:
    """
    Heuristic: detect likely external IO patterns and generate a mock hint.
    Looks for: open(), requests., http., socket, subprocess, os.environ,
    datetime.now(), random., database/session patterns.
    """
    hints = []
    lower = func_source.lower()

    patterns = {
        "open(":           ("builtins.open", "patch('builtins.open', mock_open(read_data=''))"),
        "requests.":       ("requests.Session", "patch('requests.get') or patch('requests.Session')"),
        "http":            ("http.client", "patch('http.client.HTTPConnection')"),
        "socket":          ("socket.socket", "patch('socket.socket')"),
        "subprocess":      ("subprocess.run", "patch('subprocess.run', return_value=CompletedProcess(...))"),
        "os.environ":      ("os.environ", "patch.dict('os.environ', {'KEY': 'value'})"),
        "datetime.now":    ("datetime.datetime", "patch('datetime.datetime.now', return_value=datetime(...))"),
        "random.":         ("random.randint", "patch('random.randint', return_value=42)"),
        "session":         ("db.session", "MagicMock(spec=Session)"),
        ".execute(":       ("db.execute", "MagicMock(spec=Connection)"),
        "boto":            ("boto3.client", "patch('boto3.client')"),
    }

    for pattern, (what, how) in patterns.items():
        if pattern in lower:
            hints.append(f"# Mock hint: patch '{what}' — e.g. {how}")

    if not hints:
        # Generic mock hint
        hints.append(
            "# Mock hint: use unittest.mock.patch for any external dependencies.\n"
            "# @pytest.fixture: return MagicMock(spec=<ClassName>) for complex objects."
        )

    return "\n".join(hints)


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------

def build_tier_a(func_source: str) -> str:
    return _extract_signature_and_doc(func_source)


def build_tier_b(func_source: str,
                 file_def_stubs: dict[str, str]) -> tuple[str, list[tuple[str, int]]]:
    """Returns (tier_b_text, stubs_used). Uses pre-built file def stubs."""
    tier_a = build_tier_a(func_source)
    stubs = _collect_dependency_stubs(func_source, file_def_stubs)
    if not stubs:
        return tier_a, []
    stub_section = "\n\n# --- Dependency stubs ---\n" + "\n\n".join(s for s, _ in stubs)
    return tier_a + stub_section, stubs


def build_tier_c(tier_b_text: str, func_source: str, full_file_source: str) -> str:
    hint = _mock_hint(func_source, full_file_source)
    return tier_b_text + "\n\n" + hint


def trim_to_budget(
    tier_b_text: str,
    stubs: list[tuple[str, int]],
    func_source: str,
    full_file_source: str,
    func_id: str,
    trim_log: list[dict],
) -> tuple[str, str]:
    """
    Build Tier C; if it exceeds MAX_INPUT_TOKENS, drop stubs (least-used first)
    until it fits.  Returns (trimmed_tier_b, tier_c).
    """
    tier_c = build_tier_c(tier_b_text, func_source, full_file_source)

    if not _TOKENIZERS:
        return tier_b_text, tier_c

    # Work with a mutable copy of stubs (already sorted most-used-first)
    active_stubs = list(stubs)

    while _max_tokens(_count_all(tier_c)) > MAX_INPUT_TOKENS and active_stubs:
        dropped_stub, dropped_count = active_stubs.pop()  # drop least-used (last)
        trim_log.append({
            "id": func_id,
            "dropped_stub_preview": dropped_stub[:120],
            "dropped_call_count": dropped_count,
            "reason": "tier_c_over_budget",
        })
        logging.debug(f"  [{func_id}] Trimmed one stub ({dropped_call_count} calls)")

        # Rebuild tier_b and tier_c with remaining stubs (no re-parse needed)
        tier_a = build_tier_a(func_source)
        if active_stubs:
            stub_section = "\n\n# --- Dependency stubs ---\n" + "\n\n".join(s for s, _ in active_stubs)
            tier_b_text = tier_a + stub_section
        else:
            tier_b_text = tier_a
        tier_c = build_tier_c(tier_b_text, func_source, full_file_source)  # full_file used only for mock hint string scan

    return tier_b_text, tier_c


# ---------------------------------------------------------------------------
# Per-record processing
# ---------------------------------------------------------------------------

def build_file_cache(records: list[dict]) -> dict[tuple[str, str], tuple[str, dict[str, str]]]:
    """
    For each unique (repo, source_file): read once, parse AST once, build
    {def_name: stub_text} dict once.
    Returns {(repo, source_file): (full_source_text, def_stubs_dict)}.
    process_record then only parses the small func_source per record.
    """
    unique_pairs: set[tuple[str, str]] = set()
    for rec in records:
        unique_pairs.add((rec.get("repo", ""), rec.get("source_file", "")))

    file_cache: dict[tuple[str, str], tuple[str, dict[str, str]]] = {}
    for repo, source_file in unique_pairs:
        leaked_path = PROJECT_ROOT / "TestEval" / "data" / "real_world" / source_file
        if leaked_path.exists():
            src_path = leaked_path
        else:
            clone_dir = PROJECT_ROOT / "sources" / "repos" / repo.replace("/", "_")
            if not clone_dir.exists():
                continue
            matches = list(clone_dir.rglob(source_file))
            if not matches:
                continue
            src_path = matches[0]

        try:
            src = src_path.read_text(encoding="utf-8", errors="ignore")
            def_stubs = _build_file_def_stubs(src)   # parse AST once per file
            file_cache[(repo, source_file)] = (src, def_stubs)
        except Exception:
            pass

    logging.info(f"File cache built: {len(file_cache)}/{len(unique_pairs)} files (read+AST parsed once each)")
    return file_cache


def process_record(rec: dict, trim_log: list[dict],
                   file_cache: dict | None = None) -> dict:
    func_source = rec.get("focal_function", "")
    key = (rec.get("repo", ""), rec.get("source_file", ""))

    if file_cache and key in file_cache:
        full_file, def_stubs = file_cache[key]
    else:
        full_file = func_source
        def_stubs = {}

    func_id = rec.get("id", rec.get("func_name", "unknown"))

    tier_a_text = build_tier_a(func_source)
    # Only parses func_source (small); looks up stubs from pre-built dict
    tier_b_text, stubs = build_tier_b(func_source, def_stubs)
    tier_b_text, tier_c_text = trim_to_budget(tier_b_text, stubs, func_source, full_file, func_id, trim_log)

    card = {
        "A": {"text": tier_a_text, "tokens": _count_all(tier_a_text)},
        "B": {"text": tier_b_text, "tokens": _count_all(tier_b_text)},
        "C": {"text": tier_c_text, "tokens": _count_all(tier_c_text)},
    }

    rec["context_card"] = card
    return rec


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build Tier A/B/C context cards for v2 candidates")
    parser.add_argument("--no-token-check", action="store_true",
                        help="Skip tokenizer loading (cards built but no token counts)")
    args = parser.parse_args()

    if not CANDIDATES_FILE.exists():
        logging.error(f"Candidates file not found: {CANDIDATES_FILE}")
        logging.error("Run create_v2_dataset.py (and classify_dependency_level.py) first.")
        sys.exit(1)

    if not args.no_token_check:
        logging.info("Loading cohort tokenizers...")
        _load_tokenizers()

    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    with CANDIDATES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    logging.info(f"Building file cache for {len(records)} records...")
    file_cache = build_file_cache(records)

    logging.info(f"Building context cards for {len(records)} candidates...")

    trim_log: list[dict] = []
    card_records = []

    for i, rec in enumerate(records):
        rec = process_record(rec, trim_log, file_cache)
        records[i] = rec

        card_rec = {
            "id": rec.get("id"),
            "repo": rec.get("repo"),
            "func_name": rec.get("func_name"),
            "leaked": rec.get("leaked"),
            "dependency_level": rec.get("dependency_level"),
            "context_card": rec["context_card"],
        }
        card_records.append(card_rec)

        if (i + 1) % 500 == 0:
            logging.info(f"  {i+1}/{len(records)} processed")

    # Write updated candidates (with context_card field)
    with CANDIDATES_FILE.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    # Write cards file
    with CARDS_FILE.open("w", encoding="utf-8") as f:
        for cr in card_records:
            f.write(json.dumps(cr) + "\n")

    # Write trim log
    with TRIM_LOG_FILE.open("w", encoding="utf-8") as f:
        for entry in trim_log:
            f.write(json.dumps(entry) + "\n")

    logging.info(f"Cards written to {CARDS_FILE}")
    logging.info(f"Trim log: {len(trim_log)} entries -> {TRIM_LOG_FILE}")

    # Budget compliance check
    over_budget = 0
    for rec in records:
        card = rec.get("context_card") or {}
        tier_c = card.get("C", {})
        tok = tier_c.get("tokens", {})
        if any(v > MAX_INPUT_TOKENS for v in tok.values() if v >= 0):
            over_budget += 1

    print(f"\n{'='*50}")
    print(f"Cards built:       {len(records)}")
    print(f"Trim events:       {len(trim_log)}")
    print(f"Over-budget (C):   {over_budget}  (should be 0)")
    print(f"Cards file:        {CARDS_FILE}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
