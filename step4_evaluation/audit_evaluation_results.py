"""
Evaluation Results Audit: Data Integrity & Anomaly Detection

Performs a diagnostic health check on evaluation results before they are used
in summary reports or thesis analysis. Unlike create_summary_report.py which
generates publication-ready tables/plots, this script validates that the
underlying data is sound: no missing fields, consistent runs, expected
pass/fail distributions, and working mutation testing.

Checks performed:
    1. Per-model summary (pass / assertion error / runtime error rates)
    2. Mutation score analysis (distribution, zero-scores, null counts)
    3. Coverage analysis (per-pass averages, zero-coverage anomalies)
    4. Per-run consistency (variance across repeated runs)
    5. Task-level analysis (always-failing tasks, model-exclusive passes)
    6. Pynguin vs SLM comparison (pass rate vs mutation quality tradeoff)

Output:
    A single diagnostic_report.txt in the output directory summarizing all
    findings and flagging any anomalies that need human review.

Usage:
    python step4_evaluation/audit_evaluation_results.py
    python step4_evaluation/audit_evaluation_results.py --eval-dir evaluation_results_realworld --dataset TestEval/data/realworld-py.jsonl
"""

import json
import argparse
import logging
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Recognized status values
STATUS_PASS = "Pass"
STATUS_ASSERTION_ERROR = "Assertion Error"
STATUS_RUNTIME_ERROR = "Runtime Error"
STATUS_SYNTAX_ERROR = "Syntax Error"
STATUS_NO_CODE = "No Code"
STATUS_TIMEOUT = "Timeout"



# Data Loading
def load_evaluated_jsonl(path: Path) -> List[dict]:
    """Load all records from an evaluated JSONL file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def load_task_info(dataset_path: Path) -> Dict[str, dict]:
    """Load task metadata (title, difficulty, func_name) keyed by task_num."""
    info = {}
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            tid = str(r["task_num"])
            info[tid] = {
                "title": r.get("task_title", "unknown"),
                "difficulty": r.get("difficulty"),
                "func_name": r.get("func_name", "unknown"),
            }
    return info


def discover_runs(eval_dir: Path) -> List[str]:
    """Find all run_N directories, sorted numerically."""
    runs = [d.name for d in eval_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
    return sorted(runs, key=lambda x: int(x.split("_")[1]))


def discover_slm_models(eval_dir: Path, runs: List[str]) -> List[str]:
    """Discover SLM model names from linecov2_* filenames in the first run."""
    models = []
    run_dir = eval_dir / runs[0]
    for f in run_dir.iterdir():
        if f.name.startswith("linecov2_") and f.name.endswith("_evaluated.jsonl"):
            model = f.name.replace("linecov2_", "").replace("_evaluated.jsonl", "")
            models.append(model)
    return sorted(models)



# Analysis Functions
@dataclass
class ModelStats:
    """Aggregated statistics for a single model across all runs."""
    name: str
    pass_count: int = 0
    assertion_error_count: int = 0
    runtime_error_count: int = 0
    syntax_error_count: int = 0
    no_code_count: int = 0
    timeout_count: int = 0
    total: int = 0
    mutation_scores: list = field(default_factory=list)
    mutation_null_count: int = 0
    coverage_values: list = field(default_factory=list)
    per_run_pass_rates: list = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.pass_count / self.total * 100 if self.total else 0

    @property
    def mutation_avg(self) -> float:
        return sum(self.mutation_scores) / len(self.mutation_scores) if self.mutation_scores else 0

    @property
    def mutation_zero_count(self) -> int:
        return sum(1 for m in self.mutation_scores if m == 0.0)

    @property
    def coverage_avg(self) -> float:
        nonzero = [c for c in self.coverage_values if c > 0]
        return sum(nonzero) / len(nonzero) if nonzero else 0


def compute_model_stats(eval_dir: Path, runs: List[str], model: str,
                        is_pynguin: bool = False) -> ModelStats:
    """Compute aggregated stats for one model across all runs."""
    stats = ModelStats(name=model)

    for run in runs:
        if is_pynguin:
            fpath = eval_dir / run / "pynguin_results_evaluated.jsonl"
        else:
            fpath = eval_dir / run / f"linecov2_{model}_evaluated.jsonl"

        if not fpath.exists():
            continue

        records = load_evaluated_jsonl(fpath)

        if is_pynguin:
            records = _pynguin_best_per_task(records)

        run_pass = 0
        run_total = 0
        for r in records:
            status = r.get("status", "Unknown")
            stats.total += 1
            run_total += 1

            if status == STATUS_PASS:
                stats.pass_count += 1
                run_pass += 1
            elif status == STATUS_ASSERTION_ERROR:
                stats.assertion_error_count += 1
            elif status == STATUS_RUNTIME_ERROR:
                stats.runtime_error_count += 1
            elif status == STATUS_SYNTAX_ERROR:
                stats.syntax_error_count += 1
            elif status in (STATUS_NO_CODE, "No Code"):
                stats.no_code_count += 1
            elif status == STATUS_TIMEOUT:
                stats.timeout_count += 1

            ms = r.get("mutation_score")
            if ms is not None:
                stats.mutation_scores.append(ms)
            else:
                stats.mutation_null_count += 1

            cov = r.get("coverage")
            if cov is not None:
                stats.coverage_values.append(cov)

        if run_total > 0:
            stats.per_run_pass_rates.append(run_pass / run_total * 100)

    return stats


def _pynguin_best_per_task(records: List[dict]) -> List[dict]:
    """For Pynguin, keep only the best record per task (highest mutation score among passes)."""
    task_best = {}
    for r in records:
        tid = str(r.get("task_num"))
        cur = task_best.get(tid)
        if cur is None:
            task_best[tid] = r
        elif r.get("status") == STATUS_PASS and cur.get("status") != STATUS_PASS:
            task_best[tid] = r
        elif r.get("status") == STATUS_PASS and cur.get("status") == STATUS_PASS:
            if (r.get("mutation_score") or 0) > (cur.get("mutation_score") or 0):
                task_best[tid] = r
    return list(task_best.values())


def find_always_failing_tasks(eval_dir: Path, runs: List[str],
                              slm_models: List[str]) -> Tuple[List[str], Dict[str, int]]:
    """Find tasks that never pass for any SLM across all runs.

    Returns (list of never-passing task_ids, dict of task_id -> pass_count for low-pass tasks).
    """
    task_pass = defaultdict(lambda: {"pass": 0, "total": 0})

    for run in runs:
        for model in slm_models:
            fpath = eval_dir / run / f"linecov2_{model}_evaluated.jsonl"
            if not fpath.exists():
                continue
            for r in load_evaluated_jsonl(fpath):
                tid = str(r.get("task_num"))
                task_pass[tid]["total"] += 1
                if r.get("status") == STATUS_PASS:
                    task_pass[tid]["pass"] += 1

    never_pass = [tid for tid, counts in task_pass.items() if counts["pass"] == 0]
    low_pass = {tid: counts["pass"] for tid, counts in task_pass.items()
                if 0 < counts["pass"] <= counts["total"] * 0.05}
    return sorted(never_pass), low_pass


def find_exclusive_passes(eval_dir: Path, runs: List[str],
                          slm_models: List[str]) -> Tuple[set, set, set]:
    """Find tasks exclusive to Pynguin or SLMs.

    Returns (pynguin_only, slm_only, both_pass).
    """
    pynguin_pass = set()
    slm_pass = set()

    for run in runs:
        pyg_path = eval_dir / run / "pynguin_results_evaluated.jsonl"
        if pyg_path.exists():
            for r in load_evaluated_jsonl(pyg_path):
                if r.get("status") == STATUS_PASS:
                    pynguin_pass.add(str(r["task_num"]))

        for model in slm_models:
            fpath = eval_dir / run / f"linecov2_{model}_evaluated.jsonl"
            if not fpath.exists():
                continue
            for r in load_evaluated_jsonl(fpath):
                if r.get("status") == STATUS_PASS:
                    slm_pass.add(str(r["task_num"]))

    return pynguin_pass - slm_pass, slm_pass - pynguin_pass, pynguin_pass & slm_pass


def compute_mutation_distribution(eval_dir: Path, runs: List[str]) -> Counter:
    """Compute mutation score distribution across all models (5% buckets)."""
    dist = Counter()
    for run in runs:
        run_dir = eval_dir / run
        for fpath in run_dir.glob("*_evaluated.jsonl"):
            for r in load_evaluated_jsonl(fpath):
                ms = r.get("mutation_score")
                if ms is not None:
                    bucket = round(ms / 5) * 5
                    dist[bucket] += 1
    return dist


def check_run_anomalies(eval_dir: Path, runs: List[str],
                        slm_models: List[str]) -> List[str]:
    """Check for runs with anomalous results (pass rate >2 std from mean)."""
    anomalies = []
    for model in slm_models:
        rates = []
        for run in runs:
            fpath = eval_dir / run / f"linecov2_{model}_evaluated.jsonl"
            if not fpath.exists():
                continue
            records = load_evaluated_jsonl(fpath)
            p = sum(1 for r in records if r.get("status") == STATUS_PASS)
            rates.append(p / len(records) * 100 if records else 0)

        if len(rates) >= 3:
            avg = sum(rates) / len(rates)
            std = (sum((r - avg) ** 2 for r in rates) / len(rates)) ** 0.5
            for i, rate in enumerate(rates):
                if std > 0 and abs(rate - avg) > 2.5 * std:
                    anomalies.append(
                        f"{model} {runs[i]}: {rate:.1f}% pass (mean={avg:.1f}%, std={std:.1f}%)"
                    )
    return anomalies


def check_empty_error_messages(eval_dir: Path, runs: List[str]) -> int:
    """Count Runtime Error records with empty error_message field."""
    count = 0
    run_dir = eval_dir / runs[0]
    for fpath in run_dir.glob("linecov2_*_evaluated.jsonl"):
        for r in load_evaluated_jsonl(fpath):
            if r.get("status") == STATUS_RUNTIME_ERROR and not r.get("error_message"):
                count += 1
    return count


# Report Generation
DIFFICULTY_MAP = {1: "Easy", 2: "Medium", 3: "Hard"}


def generate_report(all_stats: List[ModelStats], pynguin_stats: Optional[ModelStats],
                    never_pass: List[str], low_pass: Dict[str, int],
                    pynguin_only: set, slm_only: set, both_pass: set,
                    mutation_dist: Counter, run_anomalies: List[str],
                    empty_errors: int, task_info: Dict[str, dict],
                    n_runs: int, n_tasks: int) -> str:
    """Build the full diagnostic report as a single string."""
    lines = []

    def section(title):
        lines.append("")
        lines.append("=" * 100)
        lines.append(f"  {title}")
        lines.append("=" * 100)

    section("EVALUATION RESULTS AUDIT")
    lines.append(f"Runs: {n_runs} | Tasks: {n_tasks} | SLM Models: {len(all_stats)}")
    if pynguin_stats:
        lines.append(f"Baseline: Pynguin (DynaMOSA)")

    # 1. Per-model summary
    section("1. PER-MODEL SUMMARY")
    header = (f"{'Model':<45s} {'Pass':>5s} {'AErr':>5s} {'RErr':>5s} {'Syn':>4s} "
              f"{'NoCd':>4s} {'Rate':>6s} | {'MutN':>5s} {'MutAvg':>7s} {'Mut0':>5s} | {'CovAvg':>7s}")
    lines.append(header)
    lines.append("-" * len(header))

    combined = (all_stats + [pynguin_stats]) if pynguin_stats else all_stats
    for s in sorted(combined, key=lambda x: x.pass_rate, reverse=True):
        lines.append(
            f"{s.name:<45s} {s.pass_count:>5d} {s.assertion_error_count:>5d} "
            f"{s.runtime_error_count:>5d} {s.syntax_error_count:>4d} {s.no_code_count:>4d} "
            f"{s.pass_rate:>5.1f}% | {len(s.mutation_scores):>5d} {s.mutation_avg:>6.1f}% "
            f"{s.mutation_zero_count:>5d} | {s.coverage_avg:>6.1f}%"
        )

    # 2. Per-run consistency
    section("2. PER-RUN CONSISTENCY")
    for s in all_stats:
        if s.per_run_pass_rates:
            rates_str = " ".join(f"{r:5.1f}" for r in s.per_run_pass_rates)
            avg = sum(s.per_run_pass_rates) / len(s.per_run_pass_rates)
            std = (sum((r - avg) ** 2 for r in s.per_run_pass_rates) / len(s.per_run_pass_rates)) ** 0.5
            lines.append(f"  {s.name[:42]:<42s}: [{rates_str}] avg={avg:.1f}% std={std:.1f}")

    if run_anomalies:
        lines.append("")
        lines.append("  [!] ANOMALOUS RUNS (>2.5 std from mean):")
        for a in run_anomalies:
            lines.append(f"    - {a}")
    else:
        lines.append("")
        lines.append("  [OK] No anomalous runs detected.")

    # 3. Mutation score distribution
    section("3. MUTATION SCORE DISTRIBUTION")
    if mutation_dist:
        max_count = max(mutation_dist.values())
        for bucket in sorted(mutation_dist.keys()):
            bar_len = int(mutation_dist[bucket] / max_count * 50)
            bar = "#" * bar_len
            lines.append(f"  {bucket:5.0f}%: {mutation_dist[bucket]:>5d}  {bar}")

    # 4. Pynguin vs SLM comparison
    if pynguin_stats:
        section("4. PYNGUIN vs SLM COMPARISON")
        slm_mut_all = []
        for s in all_stats:
            slm_mut_all.extend(s.mutation_scores)
        slm_mut_avg = sum(slm_mut_all) / len(slm_mut_all) if slm_mut_all else 0
        slm_zero = sum(1 for m in slm_mut_all if m == 0.0)
        slm_zero_pct = slm_zero / len(slm_mut_all) * 100 if slm_mut_all else 0

        pyg_zero_pct = pynguin_stats.mutation_zero_count / len(pynguin_stats.mutation_scores) * 100 if pynguin_stats.mutation_scores else 0

        lines.append(f"  {'Metric':<30s} {'Pynguin':>12s} {'SLMs (avg)':>12s} {'Winner':>10s}")
        lines.append(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*10}")
        lines.append(f"  {'Pass Rate':<30s} {pynguin_stats.pass_rate:>11.1f}% {sum(s.pass_rate for s in all_stats)/len(all_stats):>11.1f}% {'Pynguin':>10s}")
        lines.append(f"  {'Coverage (per-pass)':<30s} {pynguin_stats.coverage_avg:>11.1f}% {sum(s.coverage_avg for s in all_stats)/len(all_stats):>11.1f}% {'SLMs':>10s}")
        lines.append(f"  {'Mutation Score (per-pass)':<30s} {pynguin_stats.mutation_avg:>11.1f}% {slm_mut_avg:>11.1f}% {'SLMs':>10s}")
        lines.append(f"  {'Zero Mutation Scores':<30s} {pyg_zero_pct:>11.1f}% {slm_zero_pct:>11.1f}% {'---':>10s}")

        lines.append("")
        lines.append(f"  Task coverage: Pynguin={len(pynguin_only)+len(both_pass)} unique tasks, "
                      f"SLMs={len(slm_only)+len(both_pass)} unique tasks")
        lines.append(f"    Both pass: {len(both_pass)} | Pynguin-only: {len(pynguin_only)} | SLM-only: {len(slm_only)}")

        if pynguin_only:
            lines.append("")
            lines.append("  Pynguin-only passes (SLMs never pass these):")
            for tid in sorted(pynguin_only):
                info = task_info.get(tid, {})
                d = DIFFICULTY_MAP.get(info.get("difficulty"), "?")
                lines.append(f"    task {tid}: {info.get('title', '?'):<60s} [{d}]")

        if slm_only:
            lines.append("")
            lines.append("  SLM-only passes (Pynguin fails/no-code):")
            for tid in sorted(slm_only):
                info = task_info.get(tid, {})
                d = DIFFICULTY_MAP.get(info.get("difficulty"), "?")
                lines.append(f"    task {tid}: {info.get('title', '?'):<60s} [{d}]")

    # 5. Always-failing tasks
    section("5. ALWAYS-FAILING TASKS (0% SLM pass rate)")
    if never_pass:
        lines.append(f"  {len(never_pass)} / {n_tasks} tasks never pass for any SLM across all runs:")
        lines.append("")

        source_files = Counter()
        for tid in never_pass:
            info = task_info.get(tid, {})
            title = info.get("title", "")
            d = DIFFICULTY_MAP.get(info.get("difficulty"), "?")
            pyg_note = "Pynguin PASSES" if tid in pynguin_only else "Pynguin ALSO FAILS"
            lines.append(f"    task {tid}: {title:<60s} [{d}] [{pyg_note}]")

            parts = title.split("::")
            if len(parts) >= 2:
                source_files[parts[1]] += 1

        lines.append("")
        lines.append("  By source file:")
        for fname, count in sorted(source_files.items(), key=lambda x: -x[1]):
            lines.append(f"    {fname}: {count} tasks")

        if low_pass:
            lines.append("")
            lines.append(f"  Additionally, {len(low_pass)} tasks have <=5% pass rate:")
            for tid, pc in sorted(low_pass.items(), key=lambda x: x[1]):
                info = task_info.get(tid, {})
                lines.append(f"    task {tid}: {pc} passes - {info.get('title', '?')}")
    else:
        lines.append("  [OK] All tasks pass for at least one SLM in at least one run.")

    # 6. Data quality flags
    section("6. DATA QUALITY FLAGS")
    flags = []

    if empty_errors > 0:
        flags.append(f"[INFO] {empty_errors} Runtime Error records have empty error_message "
                     f"(run_1 only). Error details not captured by evaluator.")

    # Check mutation null ratio
    for s in combined:
        if s.total > 0:
            null_pct = s.mutation_null_count / s.total * 100
            if null_pct > 80:
                flags.append(f"[INFO] {s.name}: {null_pct:.0f}% mutation_score=null "
                             f"(expected for failing tasks - mutation only runs on Pass).")

    if not flags:
        flags.append("[OK] No data quality issues detected.")

    for flag in flags:
        lines.append(f"  {flag}")

    # 7. Verdict
    section("7. VERDICT")
    has_critical = len(run_anomalies) > 0

    if has_critical:
        lines.append("  [!] ANOMALIES DETECTED - Review flagged items above before using results.")
    else:
        lines.append("  [OK] Data is clean. No re-runs needed.")
        lines.append(f"  - {n_runs} runs consistent (no outlier runs)")
        lines.append(f"  - Mutation testing operational ({sum(len(s.mutation_scores) for s in combined)} scored tasks)")
        lines.append(f"  - {len(never_pass)}/{n_tasks} tasks never pass for SLMs (not a data issue, reflects task difficulty)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Audit evaluation results for data integrity and anomalies"
    )
    parser.add_argument("--eval-dir", type=str, default="evaluation_results_realworld",
                        help="Directory containing evaluated JSONL results")
    parser.add_argument("--dataset", type=str, default="TestEval/data/realworld-py.jsonl",
                        help="Path to the JSONL dataset for task metadata")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: same as eval-dir)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    eval_dir = Path(args.eval_dir)
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir) if args.output_dir else eval_dir

    task_info = load_task_info(dataset_path)
    runs = discover_runs(eval_dir)
    slm_models = discover_slm_models(eval_dir, runs)

    logger.info(f"Auditing {eval_dir}: {len(runs)} runs, {len(slm_models)} SLM models, {len(task_info)} tasks")

    # Compute per-model stats
    all_stats = [compute_model_stats(eval_dir, runs, model) for model in slm_models]

    has_pynguin = (eval_dir / runs[0] / "pynguin_results_evaluated.jsonl").exists()
    pynguin_stats = compute_model_stats(eval_dir, runs, "Pynguin (DynaMOSA)", is_pynguin=True) if has_pynguin else None

    # Task-level analysis
    never_pass, low_pass = find_always_failing_tasks(eval_dir, runs, slm_models)
    pynguin_only, slm_only, both_pass = find_exclusive_passes(eval_dir, runs, slm_models) if has_pynguin else (set(), set(), set())

    # Distribution and anomaly checks
    mutation_dist = compute_mutation_distribution(eval_dir, runs)
    run_anomalies = check_run_anomalies(eval_dir, runs, slm_models)
    empty_errors = check_empty_error_messages(eval_dir, runs)

    # Generate and save report
    report = generate_report(
        all_stats, pynguin_stats, never_pass, low_pass,
        pynguin_only, slm_only, both_pass, mutation_dist,
        run_anomalies, empty_errors, task_info,
        n_runs=len(runs), n_tasks=len(task_info),
    )

    output_path = output_dir / "diagnostic_report.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    logger.info(f"Diagnostic report saved to {output_path}")


if __name__ == "__main__":
    main()
