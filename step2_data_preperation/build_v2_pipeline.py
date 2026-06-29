"""
RealWorldTests-Py v2 — Full Dataset Build Script
=================================================

Runs all pipeline phases in order to produce a reproducible, publication-ready
benchmark dataset. Every phase is a standalone script; this orchestrator calls
them sequentially with documented flags and checks their exit codes.

Outputs
-------
  TestEval/data/realworld-py-v2.jsonl   — public dataset (300 functions)
  sources/v2_repos.json                 — repo metadata with frozen SHAs
  sources/v2_candidates.jsonl           — full candidate pool (pre-sampling)
  sources/level_audit_sample.csv        — 30-item manual QC checklist
  cards/v2_cards.jsonl                  — context cards for all candidates
  gold/failtopass_v2.jsonl              — held-out fail-to-pass pairs (private)

Design parameters are locked in design.yaml. Do NOT change them mid-build.

Prerequisites
-------------
  pip install radon jedi PyGithub transformers
  GITHUB_TOKEN=<token>   in .env or environment  (needed for unleaked pool)
  HUGGINGFACE_TOKEN=<token>  in .env              (needed for tokenizer download)

Usage
-----
  # Full run (recommended for paper):
  python build_dataset_v2.py

  # Skip GitHub crawl (leaked pool only, no unleaked repos):
  python build_dataset_v2.py --leaked-only

  # Skip token counting (faster, no HF download needed):
  python build_dataset_v2.py --no-token-check

  # Skip fail-to-pass mining (if repos cloned with --depth=50):
  python build_dataset_v2.py --skip-failtopass

  # Resume from a specific phase (if earlier phases already completed):
  python build_dataset_v2.py --start-phase 4

  # Dry-run: print what would be executed without running anything:
  python build_dataset_v2.py --dry-run
"""

import argparse
import io
import os
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so box-drawing chars don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # repo root (one level up from step2_data_preperation/)

# Colour helpers — degrade gracefully when not a TTY
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

GREEN  = lambda t: _c("32;1", t)
YELLOW = lambda t: _c("33;1", t)
RED    = lambda t: _c("31;1", t)
BOLD   = lambda t: _c("1",    t)
DIM    = lambda t: _c("2",    t)


def banner(text: str) -> None:
    width = 70
    print(f"\n{'=' * width}")
    print(f"  {BOLD(text)}")
    print(f"{'=' * width}")


def step(n: int, total: int, label: str) -> None:
    print(f"\n{BOLD(f'[{n}/{total}]')} {label}")
    print(DIM("-" * 60))


def ok(msg: str) -> None:
    print(GREEN(f"  [OK] {msg}"))


def warn(msg: str) -> None:
    print(YELLOW(f"  [WARN] {msg}"))


def fail(msg: str) -> None:
    print(RED(f"  [FAIL] {msg}"))


# ── prerequisite checks ──────────────────────────────────────────────────────

def check_prerequisites(args) -> bool:
    print(BOLD("\nChecking prerequisites..."))
    all_ok = True

    # Python packages
    for pkg, import_name in [
        ("radon",        "radon"),
        ("jedi",         "jedi"),
        ("PyGithub",     "github"),
        ("transformers", "transformers"),
    ]:
        try:
            __import__(import_name)
            ok(f"{pkg} installed")
        except ImportError:
            if pkg == "jedi" or pkg == "PyGithub":
                warn(f"{pkg} not installed — run: pip install {pkg}")
                if pkg == "PyGithub" and not args.leaked_only:
                    fail("PyGithub required for unleaked pool. Use --leaked-only to skip.")
                    all_ok = False
            elif pkg == "transformers" and not args.no_token_check:
                fail("transformers required for token counting. Use --no-token-check to skip.")
                all_ok = False
            else:
                warn(f"{pkg} not installed (optional for current flags)")

    # design.yaml
    design_file = PROJECT_ROOT / "design.yaml"
    if design_file.exists():
        ok("design.yaml present")
    else:
        fail("design.yaml missing — run was not started from a clean state")
        all_ok = False

    # GitHub token
    github_token = _load_env_key("GITHUB_TOKEN") or _load_env_key("GH_TOKEN")
    if github_token:
        ok("GITHUB_TOKEN found")
    elif not args.leaked_only:
        fail("GITHUB_TOKEN not found in .env or environment. Use --leaked-only to skip GitHub crawl.")
        all_ok = False
    else:
        warn("GITHUB_TOKEN not found — running leaked-only mode")

    # HF token
    hf_token = _load_env_key("HF_TOKEN") or _load_env_key("HUGGINGFACE_TOKEN")
    if hf_token:
        ok("HF_TOKEN found")
    elif not args.no_token_check:
        warn("HF_TOKEN not found — tokenizer download may fail. Use --no-token-check to skip.")

    return all_ok


def _load_env_key(key: str) -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


# ── phase runner ─────────────────────────────────────────────────────────────

def run_phase(
    label: str,
    script: str,
    extra_args: list[str],
    dry_run: bool,
    check_output: Path | None = None,
) -> bool:
    """Run a pipeline phase script. Returns True on success."""
    cmd = [sys.executable, str(PROJECT_ROOT / script)] + extra_args
    print(DIM(f"  cmd: {' '.join(cmd)}"))

    if dry_run:
        print(YELLOW("  [DRY-RUN] skipped"))
        return True

    if check_output and check_output.exists():
        ok(f"Output already exists: {check_output.name} — skipping")
        return True

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    elapsed = time.time() - t0

    if result.returncode == 0:
        ok(f"Completed in {elapsed:.0f}s")
        return True
    else:
        fail(f"Phase failed (exit {result.returncode}) after {elapsed:.0f}s")
        return False


# ── main pipeline ────────────────────────────────────────────────────────────

PHASES = [
    # (phase_number, label)
    (1, "Source collection (leaked + unleaked repos)"),
    (2, "Function extraction & filtering"),
    (3, "Dependency level classification (L0–L3)"),
    (4, "Context card construction (Tier A / B / C)"),
    (5, "Fail-to-pass pair mining"),
    (8, "Package public dataset JSONL"),
]


def main():
    parser = argparse.ArgumentParser(
        description="Build RealWorldTests-Py v2 dataset end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--leaked-only", action="store_true",
                        help="Skip GitHub crawl; use only existing leaked real_world files")
    parser.add_argument("--no-token-check", action="store_true",
                        help="Skip HuggingFace tokenizer loading (no token counts in output)")
    parser.add_argument("--skip-failtopass", action="store_true",
                        help="Skip Phase 5 fail-to-pass mining (requires full git history)")
    parser.add_argument("--full-clone", action="store_true",
                        help="Clone unleaked repos with full git history (needed for fail-to-pass). Slower.")
    parser.add_argument("--start-phase", type=int, default=1, choices=[1,2,3,4,5,8],
                        help="Resume from this phase number (skip earlier phases)")
    parser.add_argument("--per-domain", type=int, default=5,
                        help="Max unleaked repos to collect per domain (default 5)")
    parser.add_argument("--target", type=int, default=75,
                        help="Target functions per dependency level (default 75 → 300 total)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without executing them")
    parser.add_argument("--skip-prereq-check", action="store_true")
    args = parser.parse_args()

    banner("RealWorldTests-Py v2 — Dataset Build")
    print(f"  Cutoff date:     2026-06-10")
    print(f"  Target:          {args.target * 4} functions ({args.target} per level × 4 levels)")
    print(f"  Leaked-only:     {args.leaked_only}")
    print(f"  Token check:     {not args.no_token_check}")
    print(f"  Fail-to-pass:    {not args.skip_failtopass}")
    print(f"  Start phase:     {args.start_phase}")
    print(f"  Dry-run:         {args.dry_run}")

    if not args.skip_prereq_check:
        if not check_prerequisites(args) and not args.dry_run:
            print(RED("\nPrerequisite check failed. Fix the issues above and retry."))
            sys.exit(1)

    total = len(PHASES) + 1  # +1 for tier dataset prep after packaging
    t_start = time.time()
    failed_phases = []

    # ── Phase 1: Source collection ──────────────────────────────────────────
    if args.start_phase <= 1:
        step(1, total, "Source collection — leaked pool + GitHub unleaked crawl")
        p1_args = []
        if args.leaked_only:
            p1_args.append("--leaked-only")
        else:
            p1_args += ["--per-domain", str(args.per_domain)]
        if args.full_clone:
            p1_args += ["--full-clone", "--reclone"]
        if args.dry_run:
            p1_args.append("--dry-run")

        if not run_phase(
            "Source collection",
            "step2_data_preperation/collect_sources_v2.py",
            p1_args,
            dry_run=args.dry_run,   # fully skip in dry-run; Phase 1 mutates v2_repos.json
        ):
            failed_phases.append(1)

    # ── Phase 2: Function extraction ────────────────────────────────────────
    if args.start_phase <= 2:
        step(2, total, "Function extraction & filtering (CC≥3, docstring, 3–80 LOC)")
        p2_args = []
        if args.no_token_check:
            p2_args.append("--no-token-check")
        if args.leaked_only:
            p2_args.append("--leaked-only")
        if not run_phase(
            "Function extraction",
            "step2_data_preperation/create_v2_dataset.py",
            p2_args,
            dry_run=args.dry_run,
        ):
            failed_phases.append(2)

    # ── Phase 3: Dependency classification ──────────────────────────────────
    if args.start_phase <= 3:
        step(3, total, "Dependency level classification — L0 / L1 / L2 / L3")
        p3_args = ["--no-jedi"]    # heuristic is fast and sufficient at this scale
        if not run_phase(
            "Dependency classification",
            "step2_data_preperation/classify_dependency_level.py",
            p3_args,
            dry_run=args.dry_run,
        ):
            failed_phases.append(3)

    # ── Phase 4: Context cards ───────────────────────────────────────────────
    if args.start_phase <= 4:
        step(4, total, "Context card construction — Tier A / B / C (≤6 500 tokens each)")
        p4_args = []
        if args.no_token_check:
            p4_args.append("--no-token-check")
        if not run_phase(
            "Context cards",
            "step2_data_preperation/build_context_cards.py",
            p4_args,
            dry_run=args.dry_run,
        ):
            failed_phases.append(4)

    # ── Phase 5: Fail-to-pass mining ────────────────────────────────────────
    if args.start_phase <= 5:
        if args.skip_failtopass:
            warn("Phase 5 skipped (--skip-failtopass). "
                 "Re-run without this flag after cloning repos with full git history.")
        else:
            step(5, total, "Fail-to-pass pair mining (requires full git history)")
            p5_args = ["--no-validate"]   # fast pass; run with --validate for final paper
            if not run_phase(
                "Fail-to-pass mining",
                "step2_data_preperation/mine_failtopass.py",
                p5_args,
                dry_run=args.dry_run,
            ):
                failed_phases.append(5)

    # ── Phase 8: Package ────────────────────────────────────────────────────
    step(6, total, "Package public dataset JSONL (stratified 75/level, invariant checks)")
    p8_args = ["--target", str(args.target), "--seed", str(args.seed), "--max-per-repo", "15"]
    if not run_phase(
        "Package dataset",
        "step2_data_preperation/package_v2_dataset.py",
        p8_args,
        dry_run=args.dry_run,
    ):
        failed_phases.append(8)

    # ── Phase 9-prep: Generate tier inference JSONL files ───────────────────
    step(7, total, "Prepare tier A/B/C inference JSONL files")
    if not run_phase(
        "Tier dataset preparation",
        "step2_data_preperation/prepare_v2_tier_datasets.py",
        [],
        dry_run=args.dry_run,
    ):
        failed_phases.append(9)

    # ── Summary ──────────────────────────────────────────────────────────────
    total_elapsed = time.time() - t_start
    banner("Build Complete" if not failed_phases else "Build Finished with Errors")

    output = PROJECT_ROOT / "TestEval" / "data" / "realworld-py-v2.jsonl"
    if output.exists() and not args.dry_run:
        import json
        records = [json.loads(l) for l in output.read_text().splitlines() if l.strip()]
        leaked_n  = sum(1 for r in records if r.get("leaked"))
        unleaked_n = len(records) - leaked_n
        by_level = {}
        for r in records:
            lv = r.get("dependency_level", "?")
            by_level[lv] = by_level.get(lv, 0) + 1
        ftp_n = sum(1 for r in records if r.get("has_failtopass"))

        print(f"\n  Output:          {output}")
        print(f"  Functions:       {len(records)}")
        print(f"  Leaked:          {leaked_n}    Unleaked: {unleaked_n}")
        print(f"  L0:{by_level.get('L0',0):>4}  "
              f"L1:{by_level.get('L1',0):>4}  "
              f"L2:{by_level.get('L2',0):>4}  "
              f"L3:{by_level.get('L3',0):>4}")
        print(f"  Fail-to-pass:    {ftp_n}")

    print(f"\n  Total wall time: {total_elapsed/60:.1f} min")

    if failed_phases:
        print(RED(f"\n  Failed phases: {failed_phases}"))
        print("  Re-run with --start-phase <N> to resume from the first failed phase.")
        sys.exit(1)
    else:
        print(GREEN("\n  All phases succeeded."))
        print("\n  Next steps:")
        print("    1. Manual QC audit: fill in sources/level_audit_sample.csv")
        if args.no_token_check:
            print("    2. Re-run without --no-token-check to populate token counts per model")
        if args.skip_failtopass:
            print("    3. Re-run with --full-clone (no --skip-failtopass) for fail-to-pass pairs")
        print("    4. Run v2 inference (on GPU machine):")
        print("         python step3_modelling/run_realworld_experiments_v2.py")
        print("    5. Run evaluation:")
        print("         python step4_evaluation/evaluate_results.py \\ ")
        print("           --input-dir /workspace/predictions/v2 \\ ")
        print("           --dataset TestEval/data/realworld-py-v2.jsonl")


if __name__ == "__main__":
    main()
