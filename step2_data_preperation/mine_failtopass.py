"""
Fail-to-Pass Miner — Phase 5

For each candidate function, walks the git history of its repo to find
commits that:
  1. Modified the focal function's body
  2. Added or changed a test file in the same commit

For each qualifying commit, extracts:
  f_buggy  — the function as it existed BEFORE the fix commit
  f_fixed  — the function AFTER the fix commit

Then validates:
  - Running the developer test on f_buggy -> FAILS (as expected)
  - Running the developer test on f_fixed -> PASSES

Validated pairs are written to gold/failtopass_v2.jsonl (held out, never released).

Target: >= 50 validated pairs.

Usage:
    python step2_data_preperation/mine_failtopass.py
    python step2_data_preperation/mine_failtopass.py --max-per-func 3 --validate
    python step2_data_preperation/mine_failtopass.py --no-validate  # skip pytest validation
"""

import argparse
import ast
import json
import logging
import subprocess
import sys
import tempfile
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
GOLD_DIR = PROJECT_ROOT / "gold"
OUTPUT_FILE = GOLD_DIR / "failtopass_v2.jsonl"


def _run(cmd: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str, str]:
    """Run a command; return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace",   # force utf-8, replace unmappable bytes
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def _git(args: list[str], repo_dir: Path) -> tuple[int, str]:
    code, out, _err = _run(["git"] + args, cwd=repo_dir)
    return code, (out or "").strip()


def _commits_touching_file(repo_dir: Path, file_rel: str, max_commits: int = 200) -> list[str]:
    """Return SHAs of commits that touched file_rel (most recent first)."""
    code, out = _git(
        ["log", "--format=%H", f"-{max_commits}", "--", file_rel],
        repo_dir,
    )
    if code != 0:
        return []
    return [sha.strip() for sha in out.splitlines() if sha.strip()]


def _func_source_at(repo_dir: Path, file_rel: str, commit_sha: str, func_name: str) -> str | None:
    """
    Extract the source of func_name from file_rel at commit_sha.
    Returns None if not found.
    """
    code, content = _git(["show", f"{commit_sha}:{file_rel}"], repo_dir)
    if code != 0 or not content:
        return None
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    lines = content.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name and node.end_lineno:
                return textwrap.dedent("\n".join(lines[node.lineno - 1: node.end_lineno]))
    return None


def _test_files_changed_in_commit(repo_dir: Path, commit_sha: str) -> list[str]:
    """Return list of test file paths changed in this commit."""
    code, out = _git(
        ["diff-tree", "--no-commit-id", "-r", "--name-only", commit_sha],
        repo_dir,
    )
    if code != 0:
        return []
    files = [f.strip() for f in out.splitlines() if f.strip()]
    return [f for f in files if "test" in f.lower() and f.endswith(".py")]


def _func_changed_in_commit(repo_dir: Path, file_rel: str, commit_sha: str, func_name: str) -> bool:
    """Return True if func_name appears in the diff of file_rel at commit_sha."""
    code, diff = _git(
        ["show", "--unified=0", commit_sha, "--", file_rel],
        repo_dir,
    )
    if code != 0:
        return False
    return f"def {func_name}" in diff or f"def {func_name}(self" in diff


def _validate_fail_then_pass(
    f_buggy: str,
    f_fixed: str,
    test_source: str,
    func_name: str,
    timeout: int = 30,
) -> tuple[bool, bool]:
    """
    Write temp files and run pytest.
    Returns (buggy_fails, fixed_passes).
    A good fail-to-pass pair has buggy_fails=True AND fixed_passes=True.
    """
    def _write_and_test(func_src: str) -> bool:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Write the function wrapped in a Solution class (harness-compat)
            solution = "class Solution:\n" + textwrap.indent(func_src, "    ")
            (tmp / "under_test.py").write_text(solution, encoding="utf-8")
            (tmp / "test_func.py").write_text(test_source, encoding="utf-8")
            rc, _, _ = _run(["python", "-m", "pytest", "test_func.py", "-x", "-q"], tmp, timeout)
            return rc == 0

    try:
        fixed_passes = _write_and_test(f_fixed)
        buggy_fails = not _write_and_test(f_buggy)
        return buggy_fails, fixed_passes
    except Exception as e:
        logging.warning(f"  Validation error: {e}")
        return False, False


def mine_repo(
    repo_meta: dict,
    candidates: list[dict],
    max_per_func: int,
    validate: bool,
) -> list[dict]:
    """Mine fail-to-pass pairs for all candidates from this repo."""
    repo_name = repo_meta["repo"]
    leaked = repo_meta.get("leaked", False)
    pairs: list[dict] = []

    if leaked:
        # Leaked repos are in TestEval/data/real_world/ as single files — no git history
        logging.info(f"  [LEAKED] {repo_name}: skipping git history (use unleaked repos for fail-to-pass)")
        return []

    repo_dir = PROJECT_ROOT / "sources" / "repos" / repo_name.replace("/", "_")
    if not repo_dir.exists():
        logging.warning(f"  Repo dir missing: {repo_dir}")
        return []

    repo_candidates = [c for c in candidates if c.get("repo") == repo_name]
    logging.info(f"  Mining {len(repo_candidates)} candidates in {repo_name}")

    for rec in repo_candidates:
        func_name = rec["func_name"]
        source_file = rec["source_file"]

        # Find the relative path to the source file inside the clone
        matches = list(repo_dir.rglob(source_file))
        if not matches:
            logging.debug(f"    {func_name}: source file not found in clone")
            continue
        abs_path = matches[0]
        file_rel = str(abs_path.relative_to(repo_dir))

        commits = _commits_touching_file(repo_dir, file_rel)
        if len(commits) < 2:
            logging.debug(f"    {func_name}: fewer than 2 commits")
            continue

        found = 0
        # Iterate pairs of (child, parent) commits
        for i in range(len(commits) - 1):
            if found >= max_per_func:
                break

            child_sha = commits[i]
            parent_sha = commits[i + 1]

            if not _func_changed_in_commit(repo_dir, file_rel, child_sha, func_name):
                continue
            test_files = _test_files_changed_in_commit(repo_dir, child_sha)
            if not test_files:
                continue

            f_buggy = _func_source_at(repo_dir, file_rel, parent_sha, func_name)
            f_fixed = _func_source_at(repo_dir, file_rel, child_sha, func_name)

            if not f_buggy or not f_fixed or f_buggy == f_fixed:
                continue

            # Load one test file as the validator
            test_source = ""
            for tf in test_files:
                rc, ts = _git(["show", f"{child_sha}:{tf}"], repo_dir)
                if rc == 0 and ts:
                    test_source = ts
                    break

            if not test_source:
                continue

            buggy_fails = fixed_passes = None
            if validate:
                buggy_fails, fixed_passes = _validate_fail_then_pass(
                    f_buggy, f_fixed, test_source, func_name
                )
                if not (buggy_fails and fixed_passes):
                    logging.debug(
                        f"    {func_name}@{child_sha[:8]}: validation failed "
                        f"(buggy_fails={buggy_fails}, fixed_passes={fixed_passes})"
                    )
                    continue

            pair = {
                "id": rec.get("id"),
                "repo": repo_name,
                "func_name": func_name,
                "source_file": source_file,
                "fix_commit": child_sha,
                "parent_commit": parent_sha,
                "f_buggy": f_buggy,
                "f_fixed": f_fixed,
                "test_source": test_source,
                "validated": validate,
                "buggy_fails": buggy_fails,
                "fixed_passes": fixed_passes,
            }
            pairs.append(pair)
            found += 1
            logging.info(
                f"    Found pair: {func_name}@{child_sha[:8]} "
                f"(validated={validate})"
            )

        if found:
            # Mark the candidate as having a fail-to-pass pair
            rec["has_failtopass"] = True

    return pairs


def main():
    parser = argparse.ArgumentParser(description="Mine fail-to-pass pairs from git history")
    parser.add_argument("--max-per-func", type=int, default=2,
                        help="Max fail-to-pass pairs to mine per function (default 2)")
    parser.add_argument("--validate", action="store_true", default=True,
                        help="Run pytest validation on each pair (default True)")
    parser.add_argument("--no-validate", action="store_false", dest="validate",
                        help="Skip pytest validation (faster, lower confidence)")
    parser.add_argument("--unleaked-only", action="store_true", default=True,
                        help="Only mine from unleaked repos (default True)")
    args = parser.parse_args()

    if not CANDIDATES_FILE.exists():
        logging.error(f"Candidates file not found: {CANDIDATES_FILE}")
        logging.error("Run create_v2_dataset.py first.")
        sys.exit(1)

    repos_file = SOURCES_DIR / "v2_repos.json"
    if not repos_file.exists():
        logging.error(f"Repo metadata not found: {repos_file}")
        logging.error("Run collect_sources_v2.py first.")
        sys.exit(1)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    candidates = []
    with CANDIDATES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))

    repos = json.loads(repos_file.read_text())
    if args.unleaked_only:
        repos = [r for r in repos if not r.get("leaked")]
        logging.info(f"Mining {len(repos)} unleaked repos")

    all_pairs: list[dict] = []
    for repo_meta in repos:
        logging.info(f"=== {repo_meta['repo']} ===")
        pairs = mine_repo(repo_meta, candidates, args.max_per_func, args.validate)
        all_pairs.extend(pairs)
        logging.info(f"  -> {len(pairs)} pairs so far from this repo")

    # Write gold file
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for pair in all_pairs:
            f.write(json.dumps(pair) + "\n")

    # Update candidates with has_failtopass flags
    with CANDIDATES_FILE.open("w", encoding="utf-8") as f:
        for rec in candidates:
            f.write(json.dumps(rec) + "\n")

    validated_n = sum(1 for p in all_pairs if p.get("validated") and p.get("buggy_fails") and p.get("fixed_passes"))
    target = 50

    print(f"\n{'='*50}")
    print(f"Total pairs found:     {len(all_pairs)}")
    print(f"Validated pairs:       {validated_n}")
    print(f"Target:                {target}")
    if validated_n < target:
        print(f"WARNING: below target ({validated_n} < {target}). Add more unleaked repos.")
    print(f"Output (held-out):     {OUTPUT_FILE}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
