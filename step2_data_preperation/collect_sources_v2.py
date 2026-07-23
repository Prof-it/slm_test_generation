"""
Source Collector v2 — Phase 1

Builds two JSON pools for RealWorldTests-Py v2:
  LEAKED   — the 14 existing repos already in TestEval/data/real_world/
  UNLEAKED — fresh GitHub repos with commits after CUTOFF_DATE

Output: sources/v2_repos.json  (one object per repo with frozen metadata)

Usage:
    # Leaked pool only (no token needed):
    python step2_data_preperation/collect_sources_v2.py --leaked-only

    # Full crawl (needs GITHUB_TOKEN in .env or env):
    python step2_data_preperation/collect_sources_v2.py

    # Dry-run to inspect queries without cloning:
    python step2_data_preperation/collect_sources_v2.py --dry-run
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources"
OUTPUT_FILE = SOURCES_DIR / "v2_repos.json"
REAL_WORLD_DIR = PROJECT_ROOT / "TestEval" / "data" / "real_world"
CLONE_DIR = PROJECT_ROOT / "sources" / "repos"

CUTOFF_DATE = "2026-06-10"

# Domains → query keywords for GitHub search.
# We diversify so no single library dominates the benchmark.
DOMAIN_QUERIES = {
    "web":           "language:python topic:web pushed:>2026-06-10",
    "data":          "language:python topic:data-processing pushed:>2026-06-10",
    "ml":            "language:python topic:machine-learning pushed:>2026-06-10",
    "cli":           "language:python topic:cli pushed:>2026-06-10",
    "serialization": "language:python topic:serialization pushed:>2026-06-10",
}

# Known repos that map the real_world .py files back to their GitHub origins.
# Add the commit SHA that was in use when the file was captured.
LEAKED_REPOS = [
    {"repo": "agronholm/apscheduler",       "domain": "scheduling", "file": "apscheduler_expressions.py"},
    {"repo": "Bogdanp/dramatiq",            "domain": "task-queue", "file": "dramatiq_message.py"},
    {"repo": "encode/httpx",               "domain": "web",        "file": "encode__utils.py"},
    {"repo": "jmoiron/humanize",           "domain": "cli",        "file": "humanize_time.py"},
    {"repo": "pandas-dev/pandas",         "domain": "data",       "file": "pandas_common.py"},
    {"repo": "pandas-dev/pandas",         "domain": "data",       "file": "pandas_numeric.py"},
    {"repo": "pytorch/pytorch",           "domain": "ml",         "file": "pytorch_utils.py"},
    {"repo": "psf/requests",              "domain": "web",        "file": "requests_utils.py"},
    {"repo": "scikit-learn/scikit-learn", "domain": "ml",         "file": "scikit_validation.py"},
    {"repo": "scrapy/scrapy",             "domain": "web",        "file": "scrapy_url.py"},
    {"repo": "huggingface/transformers",  "domain": "ml",         "file": "transformers_activations.py"},
    {"repo": "vllm-project/vllm",        "domain": "ml",         "file": "vllm_hashing.py"},
]


def _require_github() -> "github.Github":
    try:
        from github import Github, Auth
    except ImportError:
        logging.error("PyGithub not installed. Run: pip install PyGithub")
        sys.exit(1)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        # Try loading .env manually (avoid importing python-dotenv just for this)
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GITHUB_TOKEN=") or line.startswith("GH_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not token:
        logging.error(
            "No GITHUB_TOKEN found. Set it in .env or as an environment variable."
        )
        sys.exit(1)

    return Github(auth=Auth.Token(token))


def _get_commit_sha(repo_obj) -> tuple[str, str]:
    """Return (sha, date_iso) of the latest commit on the default branch."""
    try:
        branch = repo_obj.get_branch(repo_obj.default_branch)
        sha = branch.commit.sha
        date = branch.commit.commit.committer.date.strftime("%Y-%m-%d")
        return sha, date
    except Exception as e:
        logging.warning(f"Could not get commit SHA for {repo_obj.full_name}: {e}")
        return "unknown", "unknown"


def _contributor_count(repo_obj) -> int:
    try:
        return repo_obj.get_contributors().totalCount
    except Exception:
        return 0


def collect_leaked() -> list[dict]:
    """Build the leaked pool from the pre-existing real_world .py files."""
    records = []
    existing_files = {p.name for p in REAL_WORLD_DIR.glob("*.py")} if REAL_WORLD_DIR.exists() else set()

    for entry in LEAKED_REPOS:
        file_present = entry["file"] in existing_files
        record = {
            "repo": entry["repo"],
            "commit_sha": "frozen-in-TestEval",  # already captured; no live clone needed
            "commit_date": "pre-2026-06-10",
            "license": "varies",
            "stars": -1,             # not crawled for leaked pool
            "contributors": -1,
            "domain": entry["domain"],
            "leaked": True,
            "local_file": entry["file"],
            "file_present": file_present,
        }
        records.append(record)
        status = "OK" if file_present else "MISSING"
        logging.info(f"  [LEAKED/{status}] {entry['repo']} -> {entry['file']}")

    return records


def collect_unleaked(g, dry_run: bool = False, per_domain: int = 5) -> list[dict]:
    """Search GitHub for repos pushed after CUTOFF_DATE and return metadata records."""
    records = []
    seen = set()

    for domain, base_query in DOMAIN_QUERIES.items():
        # GitHub Search API does not support OR on qualifiers — run one query per license
        queries = [
            f"{base_query} stars:40..5000 license:mit",
            f"{base_query} stars:40..5000 license:apache-2.0",
        ]
        count = 0

        for full_query in queries:
            if count >= per_domain:
                break
            logging.info(f"Searching GitHub: domain={domain!r}  query={full_query!r}")

            if dry_run:
                logging.info("  [DRY-RUN] skipping API call")
                continue

            try:
                results = g.search_repositories(query=full_query, sort="updated", order="desc")
                for repo in results:
                    if count >= per_domain:
                        break
                    if repo.full_name in seen:
                        continue
                    if repo.language != "Python":
                        continue
                    if repo.license is None:
                        continue
                    license_key = (repo.license.key or "").lower()
                    if license_key not in ("mit", "apache-2.0"):
                        continue

                    pushed = repo.pushed_at
                    if pushed is None or pushed.strftime("%Y-%m-%d") <= CUTOFF_DATE:
                        logging.debug(f"  skip {repo.full_name}: pushed={pushed}")
                        continue

                    contribs = _contributor_count(repo)
                    if contribs < 2:
                        logging.debug(f"  skip {repo.full_name}: contributors={contribs}")
                        continue

                    sha, commit_date = _get_commit_sha(repo)
                    record = {
                        "repo": repo.full_name,
                        "commit_sha": sha,
                        "commit_date": commit_date,
                        "license": license_key,
                        "stars": repo.stargazers_count,
                        "contributors": contribs,
                        "domain": domain,
                        "leaked": False,
                        "clone_url": repo.clone_url,
                    }
                    records.append(record)
                    seen.add(repo.full_name)
                    logging.info(
                        f"  [UNLEAKED] {repo.full_name}  stars={repo.stargazers_count}  "
                        f"pushed={pushed.strftime('%Y-%m-%d')}  sha={sha[:8]}"
                    )
                    count += 1

            except Exception as e:
                logging.error(f"GitHub search failed for domain={domain!r} query={full_query!r}: {e}")

    return records


def clone_unleaked(records: list[dict], full_clone: bool = False,
                   reclone: bool = False) -> None:
    """
    Clone each unleaked repo at its frozen commit SHA into sources/repos/<owner>/<name>.
    full_clone=True  — omit --depth so the entire git history is fetched (needed for
                       fail-to-pass mining; slower but required for paper).
    reclone=True     — delete existing clone first and re-clone from scratch.
    """
    CLONE_DIR.mkdir(parents=True, exist_ok=True)
    depth_args = [] if full_clone else ["--depth=50"]

    for rec in records:
        if rec.get("leaked"):
            continue
        dest = CLONE_DIR / rec["repo"].replace("/", "_")

        if dest.exists():
            if reclone:
                logging.info(f"Removing existing clone for reclone: {dest}")
                import shutil, stat
                def _force_remove(func, path, _):
                    # Git pack files are read-only on Windows; reset before delete
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(dest, onerror=_force_remove)
            else:
                logging.info(f"Already cloned: {dest}")
                continue

        logging.info(f"Cloning {rec['repo']} -> {dest} (full={full_clone})")
        try:
            subprocess.run(
                ["git", "clone"] + depth_args + [rec["clone_url"], str(dest)],
                check=True,
                capture_output=True,
            )
            sha = rec["commit_sha"]
            if sha not in ("unknown", "frozen-in-TestEval"):
                subprocess.run(
                    ["git", "-C", str(dest), "checkout", sha],
                    check=True,
                    capture_output=True,
                )
                logging.info(f"  Checked out SHA {sha[:8]}")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr)
            logging.error(f"  Clone/checkout failed for {rec['repo']}: {stderr[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Collect source repos for RealWorldTests-Py v2")
    parser.add_argument("--leaked-only", action="store_true", help="Only build the leaked pool (no GitHub API)")
    parser.add_argument("--dry-run", action="store_true", help="Print queries but do not call GitHub API or clone")
    parser.add_argument("--per-domain", type=int, default=5, help="Max repos per domain to collect (default 5)")
    parser.add_argument("--no-clone", action="store_true", help="Skip git cloning of unleaked repos")
    parser.add_argument("--full-clone", action="store_true",
                        help="Clone with full git history (no --depth limit). Required for fail-to-pass mining.")
    parser.add_argument("--reclone", action="store_true",
                        help="Delete and re-clone repos that already exist locally.")
    args = parser.parse_args()

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    all_records = []

    # --- Leaked pool ---
    logging.info("=== Building LEAKED pool ===")
    leaked = collect_leaked()
    all_records.extend(leaked)
    logging.info(f"Leaked pool: {len(leaked)} repos")

    # --- Unleaked pool ---
    if not args.leaked_only:
        logging.info("=== Building UNLEAKED pool ===")
        g = _require_github()
        unleaked = collect_unleaked(g, dry_run=args.dry_run, per_domain=args.per_domain)
        all_records.extend(unleaked)
        logging.info(f"Unleaked pool: {len(unleaked)} repos across {len(DOMAIN_QUERIES)} domains")

        if not args.dry_run and not args.no_clone:
            logging.info("=== Cloning unleaked repos ===")
            clone_unleaked(unleaked, full_clone=args.full_clone, reclone=args.reclone)

    # --- Save ---
    OUTPUT_FILE.write_text(json.dumps(all_records, indent=2), encoding="utf-8")
    logging.info(f"Saved {len(all_records)} repo records to {OUTPUT_FILE}")

    # Summary
    n_leaked = sum(1 for r in all_records if r.get("leaked"))
    n_unleaked = sum(1 for r in all_records if not r.get("leaked"))
    domains = {r["domain"] for r in all_records if not r.get("leaked")}
    print(f"\n{'='*50}")
    print(f"Leaked repos:   {n_leaked}")
    print(f"Unleaked repos: {n_unleaked}  (domains: {', '.join(sorted(domains))})")
    print(f"Output:         {OUTPUT_FILE}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
