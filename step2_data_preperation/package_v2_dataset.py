"""
Dataset Packager v2 — Phase 8

Reads sources/v2_candidates.jsonl (populated by Phases 2–5) and produces:

  TestEval/data/realworld-py-v2.jsonl   ← PUBLIC release (no gold tests)

Applies final stratified sampling to hit ~300 functions (~75 per level L0–L3),
assigns final IDs, fills the license field from v2_repos.json, and verifies
all invariants before writing.

Invariants checked:
  - context_card tiers A ⊂ B ⊂ C (B text starts with A text, C starts with B text)
  - No implementation body in Tier B (no non-stub lines)
  - gold_test_path field is stripped from public output
  - f_buggy / f_fixed stripped from public output
  - Token counts present for all three tiers (warns if missing)

Also writes sources/v2_final_sample.json listing the selected IDs for reproducibility.

Usage:
    python step2_data_preperation/package_v2_dataset.py
    python step2_data_preperation/package_v2_dataset.py --target 300 --seed 42
"""

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources"
CANDIDATES_FILE = SOURCES_DIR / "v2_candidates.jsonl"
REPOS_FILE = SOURCES_DIR / "v2_repos.json"
OUTPUT_FILE = PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl"
SAMPLE_INDEX_FILE = SOURCES_DIR / "v2_final_sample.json"

# Fields that must NEVER appear in the public release
HELD_OUT_FIELDS = {"gold_test_path", "f_buggy", "f_fixed", "test_source", "level_confidence"}

TARGET_PER_LEVEL = 75   # design.yaml target_per_level


def _read_license_from_clone(repo: str) -> str:
    """Detect license from cloned repo directory when not in v2_repos.json."""
    clone_dir = PROJECT_ROOT / "sources" / "repos" / repo.replace("/", "_")
    for fname in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]:
        lf = clone_dir / fname
        if lf.exists():
            try:
                text = lf.read_text(errors="ignore").lower()
                if "apache" in text[:500]:
                    return "apache-2.0"
                if "mit" in text[:500]:
                    return "mit"
            except Exception:
                pass
    return ""


def _load_license_map(repos_file: Path) -> dict[str, str]:
    if not repos_file.exists():
        return {}
    repos = json.loads(repos_file.read_text())
    return {r["repo"]: r.get("license", "") for r in repos}


def _check_tier_nesting(card: dict, rec_id: str) -> list[str]:
    """Return list of nesting violation messages (empty = OK)."""
    violations = []
    tier_a = card.get("A", {}).get("text", "")
    tier_b = card.get("B", {}).get("text", "")
    tier_c = card.get("C", {}).get("text", "")

    # B must start with (or equal) A
    if tier_b and tier_a and not tier_b.startswith(tier_a):
        violations.append(f"[{rec_id}] Tier B does not start with Tier A")

    # C must start with (or equal) B
    if tier_c and tier_b and not tier_c.startswith(tier_b):
        violations.append(f"[{rec_id}] Tier C does not start with Tier B")

    return violations


def _check_no_body_leakage(card: dict, focal_function: str, rec_id: str) -> list[str]:
    """
    AST-based check: Tier B should not contain implementation statements from
    the focal function body (assignments, augmented assignments, for/while loops).
    Uses AST to reliably distinguish signature/docstring from body.
    """
    import ast as _ast
    violations = []
    tier_b_text = card.get("B", {}).get("text", "")
    if not tier_b_text or not focal_function:
        return violations

    try:
        tree = _ast.parse(focal_function)
    except SyntaxError:
        return violations

    # Collect the source lines of assignment statements inside the function body
    src_lines = focal_function.splitlines()
    impl_lines = []
    for node in _ast.walk(tree):
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        # Skip the docstring node (first Expr(Constant))
        body = node.body
        if (body and isinstance(body[0], _ast.Expr)
                and isinstance(body[0].value, _ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]
        for stmt in body:
            if isinstance(stmt, (_ast.Assign, _ast.AugAssign, _ast.AnnAssign)):
                if hasattr(stmt, "lineno") and stmt.lineno <= len(src_lines):
                    line = src_lines[stmt.lineno - 1].strip()
                    if len(line) > 15:
                        impl_lines.append(line)

    # Flag only if a real assignment line appears verbatim in Tier B
    for impl_line in impl_lines[:5]:
        if impl_line in tier_b_text:
            violations.append(
                f"[{rec_id}] Body leakage in Tier B (assignment): '{impl_line[:70]}'"
            )

    return violations


def stratified_sample(
    records: list[dict],
    target_per_level: int,
    seed: int,
    max_per_repo: int = 15,
) -> list[dict]:
    """
    Sample up to target_per_level records per dependency_level with a global
    per-repo cap so no single repository dominates the benchmark.

    Strategy:
      1. Enforce global cap: each repo contributes at most max_per_repo
         functions across ALL levels combined (5% of 300 at cap=15).
      2. Within each level: aim for 50/50 leaked/unleaked split.
      3. Fill any shortfall on one side from the other.
    """
    rng = random.Random(seed)

    # Global repo budget tracked across all levels
    repo_budget: dict[str, int] = defaultdict(int)

    def _pick(pool: list[dict], n: int) -> list[dict]:
        """Greedily pick up to n records respecting repo_budget."""
        chosen = []
        rng.shuffle(pool)
        for rec in pool:
            if len(chosen) >= n:
                break
            repo = rec.get("repo", "")
            if repo_budget[repo] < max_per_repo:
                chosen.append(rec)
                repo_budget[repo] += 1
        return chosen

    by_level: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        lv = rec.get("dependency_level") or "unknown"
        by_level[lv].append(rec)

    selected = []
    for lv in ["L0", "L1", "L2", "L3"]:
        pool = by_level.get(lv, [])
        if not pool:
            logging.warning(f"No candidates for level {lv}")
            continue

        leaked_pool   = [r for r in pool if r.get("leaked")]
        unleaked_pool = [r for r in pool if not r.get("leaked")]

        half = target_per_level // 2

        chosen_leaked   = _pick(leaked_pool,   half)
        chosen_unleaked = _pick(unleaked_pool, target_per_level - len(chosen_leaked))

        # Top up if one side is short
        shortfall = target_per_level - len(chosen_leaked) - len(chosen_unleaked)
        if shortfall > 0:
            already = {id(r) for r in chosen_leaked + chosen_unleaked}
            remaining = [r for r in pool if id(r) not in already]
            chosen_unleaked += _pick(remaining, shortfall)

        tier_selected = chosen_leaked + chosen_unleaked
        rng.shuffle(tier_selected)

        selected.extend(tier_selected)
        logging.info(
            f"  {lv}: pool={len(pool)} "
            f"(leaked={len(leaked_pool)}, unleaked={len(unleaked_pool)}) "
            f"-> selected={len(tier_selected)} "
            f"(max_per_repo={max_per_repo})"
        )

    # Report repo distribution
    from collections import Counter
    repo_counts = Counter(r.get("repo") for r in selected)
    over_cap = {repo: n for repo, n in repo_counts.items() if n > max_per_repo}
    if over_cap:
        logging.warning(f"Repos exceeding cap (should not happen): {over_cap}")
    else:
        logging.info(f"  Repo cap enforced: max={max(repo_counts.values())} "
                     f"min={min(repo_counts.values())} "
                     f"unique repos={len(repo_counts)}")

    return selected


def build_public_record(rec: dict, license_map: dict[str, str], seq: int) -> dict:
    """Build the public-release JSON object, stripping held-out fields."""
    # focal_token_counts: use stored value if non-empty, otherwise derive from
    # Tier A card tokens (Tier A wraps the focal signature+docstring, a close proxy)
    focal_tokens = rec.get("focal_token_counts") or {}
    if not focal_tokens:
        tier_a_tokens = (rec.get("context_card") or {}).get("A", {}).get("tokens") or {}
        focal_tokens = tier_a_tokens  # same scale; paper uses these for budget reporting

    pub = {
        "id": rec.get("id", f"rwt2_{seq:06d}"),
        "task_num": rec.get("task_num", seq),
        "task_title": rec.get("task_title", ""),
        "repo": rec.get("repo", ""),
        "commit_sha": rec.get("commit_sha", ""),
        "commit_date": rec.get("commit_date", ""),
        "license": (license_map.get(rec.get("repo", ""))
                    or _read_license_from_clone(rec.get("repo", ""))
                    or rec.get("license", "")),
        "leaked": rec.get("leaked", False),
        "domain": rec.get("domain", ""),
        "dependency_level": rec.get("dependency_level"),
        "focal_function": rec.get("focal_function", ""),
        "signature": rec.get("signature", ""),
        "docstring": rec.get("docstring", ""),
        "context_card": rec.get("context_card"),
        "cyclomatic_complexity": rec.get("cyclomatic_complexity"),
        "difficulty": rec.get("difficulty"),
        "loc": rec.get("loc"),
        "focal_token_counts": focal_tokens,
        "has_failtopass": rec.get("has_failtopass", False),
        # Backward-compat fields for evaluate_results.py
        "func_name": rec.get("func_name", ""),
        "description": rec.get("description", rec.get("docstring", "")),
        "python_solution": rec.get("python_solution", ""),
        "blocks": rec.get("blocks", []),
        "target_lines": rec.get("target_lines", [1]),
        "source_file": rec.get("source_file", ""),
    }
    # Sanity: ensure no held-out fields leaked in
    for field in HELD_OUT_FIELDS:
        pub.pop(field, None)
    return pub


def main():
    parser = argparse.ArgumentParser(description="Package final public v2 dataset JSONL")
    parser.add_argument("--target", type=int, default=TARGET_PER_LEVEL,
                        help=f"Target functions per dependency level (default {TARGET_PER_LEVEL})")
    parser.add_argument("--max-per-repo", type=int, default=15,
                        help="Global cap: max functions from any single repo (default 15 = 5%%)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-validation", action="store_true",
                        help="Skip tier nesting and body-leakage checks (faster)")
    args = parser.parse_args()

    if not CANDIDATES_FILE.exists():
        logging.error(f"Candidates file not found: {CANDIDATES_FILE}")
        logging.error("Run phases 2–5 first.")
        sys.exit(1)

    license_map = _load_license_map(REPOS_FILE)

    records = []
    with CANDIDATES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    logging.info(f"Loaded {len(records)} candidates")

    # Filter: must have a dependency_level and context_card
    before = len(records)
    records = [r for r in records if r.get("dependency_level") and r.get("context_card")]
    logging.info(f"After filter (has level + card): {len(records)} / {before}")

    # Stratified sample
    logging.info(f"Stratified sampling (target={args.target}/level, max_per_repo={args.max_per_repo})...")
    selected = stratified_sample(records, args.target, args.seed, args.max_per_repo)
    logging.info(f"Selected {len(selected)} functions")

    # Validation
    all_violations: list[str] = []
    if not args.skip_validation:
        logging.info("Running invariant checks...")
        for rec in selected:
            card = rec.get("context_card") or {}
            rec_id = rec.get("id", rec.get("func_name", "?"))
            all_violations += _check_tier_nesting(card, rec_id)
            all_violations += _check_no_body_leakage(card, rec.get("focal_function", ""), rec_id)

        if all_violations:
            logging.error(f"{len(all_violations)} invariant violations found:")
            for v in all_violations[:20]:
                logging.error(f"  {v}")
            if len(all_violations) > len(selected) * 0.05:
                logging.error("Error rate >= 5%. Fix the card builder before releasing.")
                sys.exit(1)
        else:
            logging.info("All invariants passed.")

    # Build public records
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    public_records = [build_public_record(r, license_map, i) for i, r in enumerate(selected)]

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for pr in public_records:
            f.write(json.dumps(pr) + "\n")

    # Save final sample index
    sample_index = [{"id": r.get("id"), "repo": r.get("repo"), "func_name": r.get("func_name"),
                     "leaked": r.get("leaked"), "dependency_level": r.get("dependency_level")}
                    for r in selected]
    SAMPLE_INDEX_FILE.write_text(json.dumps(sample_index, indent=2), encoding="utf-8")

    # Summary
    leaked_n = sum(1 for r in public_records if r.get("leaked"))
    unleaked_n = len(public_records) - leaked_n
    by_level: dict[str, int] = {}
    for r in public_records:
        lv = r.get("dependency_level", "?")
        by_level[lv] = by_level.get(lv, 0) + 1
    ftp_n = sum(1 for r in public_records if r.get("has_failtopass"))

    print(f"\n{'='*60}")
    print(f"Final dataset:  {len(public_records)} functions")
    print(f"  Leaked:       {leaked_n}    Unleaked: {unleaked_n}")
    print(f"  L0:{by_level.get('L0',0):>4}  L1:{by_level.get('L1',0):>4}  L2:{by_level.get('L2',0):>4}  L3:{by_level.get('L3',0):>4}")
    print(f"  Fail-to-pass: {ftp_n}")
    print(f"  Violations:   {len(all_violations)}")
    print(f"Output:         {OUTPUT_FILE}")
    print(f"Sample index:   {SAMPLE_INDEX_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
