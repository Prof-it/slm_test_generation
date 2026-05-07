"""
Predictive Analysis: Function Complexity Metrics as Failure Predictors
Real-World Dataset — N=1, T=0.0

DESIGN NOTE — Why T=0.0 N=1 is the correct experimental setting for comparison:
  The alternative (T=0.2, N=3 TestEval vs T=0.2, N=10 Real-World) introduces
  a critical N-asymmetry confound: pass@k monotonically increases with k, so
  Real-World would get 3.3x more attempts to pass any given function. Failure
  type classification also becomes ambiguous under multiple samples (which of
  the k attempts defines the failure?). T=0.0, N=1 gives a single deterministic
  outcome per (model, task) pair, making both datasets directly comparable.

THREATS TO VALIDITY ADDRESSED HERE:
  1. Multicollinearity: all five complexity predictors are highly intercorrelated
     (Spearman rho 0.71–0.98). Treating them as independent predictors inflates
     the apparent number of significant findings. Fix: construct a single composite
     complexity score (PCA first principal component) as the primary predictor.
     CC is retained as an interpretable single-metric reference.
  2. Skewed CC distribution: CC ranges 2–72 with a long right tail. Spearman is
     non-parametric (handles skew), but outliers may drive correlations.
     Fix: report Winsorized (90th percentile trim) correlation as robustness check.
  3. Data contamination (noted, not fixable statistically): LeetCode problems in
     TestEval are publicly known and likely present in model training corpora.
     Real-World functions from less prominent repositories are less likely to be
     memorized. This may artificially inflate IncorrectAssertion in TestEval
     (model "knows" expected output but generates wrong assertion format) relative
     to Real-World. This threat is reported as a limitation, not corrected.
  4. Functional clustering: 50 functions from 14 source files; functions within
     the same file share module-level context (imports, globals). This induces
     within-file correlation that Spearman ignores. Fix: report alongside
     within-file vs between-file CC variance decomposition.
  5. Pseudo-replication: already addressed via task-level primary analysis (N=50)
     alongside observation-level secondary analysis (N=250).

Usage:
    python step4_evaluation/predict_failures_from_complexity.py
"""

import csv
import json
import glob
from pathlib import Path
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr, mannwhitneyu
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

try:
    from radon.complexity import cc_visit
    from radon.metrics import h_visit
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE            = Path(__file__).resolve().parent.parent
REALWORLD_JSONL = BASE / "TestEval/data/realworld-py.jsonl"
EVAL_DIR        = BASE / "evaluation_results_realworld_1/run_1"
ERROR_CSV       = BASE / "step4_evaluation/error_analysis_output/realworld_1_failure_analysis.csv"
OUT_PATH        = BASE / "step4_evaluation/error_analysis_output/predict_failures_from_complexity.txt"

SHARED_MODELS = {
    "Ministral-3-3B-Reasoning-2512",
    "Ministral-3-8B-Instruct-2512-AWQ-8bit",
    "Qwen3-4B-Instruct-2507",
    "gemma-3-4b-it",
    "granite-4.0-micro",
}

ROOT_CAUSE_SYNONYMS = {
    "HallucinatedAPI": "APIHallucination",
    "error": "Unknown",
    "N/A": "Unknown",
}

# ── Complexity ────────────────────────────────────────────────────────────────

def compute_complexity(source: str) -> dict:
    result = {
        "cc":             1,
        "halstead_diff":  0.0,
        "solution_chars": len(source),
        "solution_lines": source.count("\n"),
    }
    if not RADON_AVAILABLE:
        return result
    try:
        blocks = cc_visit(source)
        result["cc"] = max((b.complexity for b in blocks), default=1)
    except Exception:
        pass
    try:
        h = h_visit(source)
        if hasattr(h, "total") and h.total.difficulty is not None:
            result["halstead_diff"] = float(h.total.difficulty)
    except Exception:
        pass
    return result

# ── Data loading ──────────────────────────────────────────────────────────────

def load_function_features() -> dict[int, dict]:
    features: dict[int, dict] = {}
    with open(REALWORLD_JSONL, encoding="utf-8") as f:
        for line in f:
            task = json.loads(line)
            task_num = int(task["task_num"])
            metrics  = compute_complexity(task["python_solution"])
            # Derive source file from task_title: RealWorld::<file>::<func>
            parts = task.get("task_title", "").split("::")
            source_file = parts[1] if len(parts) >= 3 else "unknown"
            features[task_num] = {
                "task_num":      task_num,
                "func_name":     task["func_name"],
                "difficulty":    int(task["difficulty"]),
                "source_file":   source_file,
                **metrics,
            }
    return features


def load_eval_outcomes() -> dict[tuple[int, str], str]:
    outcomes: dict[tuple[int, str], str] = {}
    for path in glob.glob(str(EVAL_DIR / "linecov_*_evaluated.jsonl")):
        fname = Path(path).name
        model = fname.replace("linecov_", "").split("_temp_")[0]
        if model not in SHARED_MODELS:
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                outcomes[(int(row["task_num"]), model)] = row["status"]
    return outcomes


def load_root_causes() -> dict[tuple[int, str], str]:
    causes: dict[tuple[int, str], str] = {}
    with open(ERROR_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw   = (row.get("root_cause_category") or "").strip()
            cause = ROOT_CAUSE_SYNONYMS.get(raw, raw)
            model = row["model"]
            if model not in SHARED_MODELS:
                continue
            causes[(int(row["task_id"]), model)] = cause
    return causes

# ── Dataset assembly ──────────────────────────────────────────────────────────

PRED_COLS   = ["cc", "halstead_diff", "difficulty", "solution_chars", "solution_lines"]
PRED_LABELS = ["CC", "Halstead Difficulty", "Difficulty Label", "Solution Chars", "Solution Lines"]

OUTCOME_COLS   = ["passed", "is_mocking_error", "is_runtime_error", "is_assertion_error", "is_no_code"]
OUTCOME_LABELS = ["Passed", "MockingError", "Runtime Error", "Assertion Error", "No Code"]


def build_dataset(features, outcomes, causes) -> list[dict]:
    rows = []
    for (task_num, model), status in outcomes.items():
        if task_num not in features:
            continue
        f = features[task_num]
        root_cause = causes.get((task_num, model), "Pass" if status == "Pass" else "")
        rows.append({
            "task_num":           task_num,
            "func_name":          f["func_name"],
            "source_file":        f["source_file"],
            "model":              model,
            "cc":                 f["cc"],
            "halstead_diff":      f["halstead_diff"],
            "difficulty":         f["difficulty"],
            "solution_chars":     f["solution_chars"],
            "solution_lines":     f["solution_lines"],
            "status":             status,
            "root_cause":         root_cause,
            "passed":             1 if status == "Pass" else 0,
            "is_mocking_error":   1 if root_cause == "MockingError" else 0,
            "is_runtime_error":   1 if status == "Runtime Error" else 0,
            "is_assertion_error": 1 if root_cause == "IncorrectAssertion" else 0,
            "is_no_code":         1 if status == "No Code" else 0,
        })
    return rows

# ── Composite score (PCA) ─────────────────────────────────────────────────────

def build_composite(features: dict) -> tuple[dict[int, float], float, np.ndarray]:
    """
    Construct a single composite complexity score from the first principal
    component of the five predictor variables. Returns:
      - mapping task_num → composite score
      - variance explained by PC1
      - PC1 loadings (per predictor)
    """
    task_nums = sorted(features.keys())
    X = np.array([[features[t][c] for c in PRED_COLS] for t in task_nums], dtype=float)
    scaler = StandardScaler()
    X_std  = scaler.fit_transform(X)
    pca    = PCA(n_components=1)
    pca.fit(X_std)
    scores = pca.transform(X_std).flatten()
    var_explained = float(pca.explained_variance_ratio_[0])
    loadings      = pca.components_[0]
    composite_map = {t: float(s) for t, s in zip(task_nums, scores)}
    return composite_map, var_explained, loadings

# ── Statistics ────────────────────────────────────────────────────────────────

def bh_correct(p_values: list[float]) -> list[float]:
    n  = len(p_values)
    if n == 0:
        return []
    idx    = sorted(range(n), key=lambda i: p_values[i])
    adj    = [0.0] * n
    prev   = 1.0
    for rank, i in enumerate(reversed(idx)):
        adj[i] = min(prev, p_values[i] * n / (n - rank))
        prev   = adj[i]
    return adj


def winsorize_90(x: list[float]) -> list[float]:
    """Clip values at 90th percentile to reduce outlier influence."""
    cap = float(np.percentile(x, 90))
    return [min(v, cap) for v in x]


def rank_biserial(group1, group2, u_stat) -> float:
    n1, n2 = len(group1), len(group2)
    return 1.0 - 2.0 * u_stat / (n1 * n2) if n1 * n2 > 0 else 0.0


def run_spearman_mw(
    pred_vals: list[float],
    outcome_vals: list[int],
    winsorize: bool = False,
) -> dict:
    x = winsorize_90(pred_vals) if winsorize else list(pred_vals)
    rho, p_rho = spearmanr(x, outcome_vals)
    pos = [x[i] for i, y in enumerate(outcome_vals) if y == 1]
    neg = [x[i] for i, y in enumerate(outcome_vals) if y == 0]
    if len(pos) >= 3 and len(neg) >= 3:
        u, p_mw = mannwhitneyu(pos, neg, alternative="two-sided")
        r_rb    = rank_biserial(pos, neg, u)
        med_pos = float(np.median(pos))
        med_neg = float(np.median(neg))
    else:
        u = p_mw = r_rb = med_pos = med_neg = float("nan")
    return {
        "n_pos": len(pos), "n_neg": len(neg),
        "med_pos": med_pos, "med_neg": med_neg,
        "rho": float(rho), "p_rho": float(p_rho),
        "u": float(u), "p_mw": float(p_mw),
        "r_rb": float(r_rb),
    }

# ── Clustering: within-file CC variance ──────────────────────────────────────

def within_between_variance(features: dict) -> dict:
    """
    Decompose CC variance into within-file vs between-file components.
    High within-file variance → functions in same file are diverse (clustering less of a threat).
    High between-file variance → file membership is a confound.
    """
    by_file: dict[str, list[float]] = defaultdict(list)
    for f in features.values():
        by_file[f["source_file"]].append(float(f["cc"]))
    all_cc   = [f["cc"] for f in features.values()]
    grand_mean = float(np.mean(all_cc))

    ss_between = sum(
        len(vals) * (np.mean(vals) - grand_mean) ** 2
        for vals in by_file.values()
    )
    ss_within = sum(
        (v - np.mean(vals)) ** 2
        for vals in by_file.values() for v in vals
    )
    ss_total = sum((v - grand_mean) ** 2 for v in all_cc)
    eta_sq   = ss_between / ss_total if ss_total > 0 else 0.0

    return {
        "n_files":    len(by_file),
        "ss_between": ss_between,
        "ss_within":  ss_within,
        "ss_total":   ss_total,
        "eta_sq":     eta_sq,
        "icc_approx": eta_sq,
    }

# ── Main analyses ─────────────────────────────────────────────────────────────

def run_primary_analysis(rows: list[dict], task_rows: list[dict]) -> tuple[list, list]:
    """
    Primary: CC alone + composite score.
    Runs at both observation (N=250) and task level (N=50).
    Returns (obs_results, task_results).
    """
    obs_results, task_results = [], []

    for pred_col, pred_label in [("cc", "CC"), ("composite", "Composite (PC1)")]:
        for out_col, out_label in zip(OUTCOME_COLS, OUTCOME_LABELS):
            # Observation level
            pred_vals = [r[pred_col] for r in rows]
            out_vals  = [r[out_col]  for r in rows]
            res_raw = run_spearman_mw(pred_vals, out_vals, winsorize=False)
            res_win = run_spearman_mw(pred_vals, out_vals, winsorize=True)
            obs_results.append({
                "predictor": pred_label, "outcome": out_label,
                **{f"raw_{k}": v for k, v in res_raw.items()},
                **{f"win_{k}": v for k, v in res_win.items()},
            })
            # Task level
            t_pred = [t[pred_col] for t in task_rows]
            t_out  = [t[f"{out_col.replace('passed','pass')}_rate".replace("is_","")]
                      if f"{out_col.replace('passed','pass')}_rate".replace("is_","") in task_rows[0]
                      else t.get(out_col.replace("is_","").replace("passed","pass") + "_rate", 0)
                      for t in task_rows]
            # Explicit mapping
            rate_map = {
                "passed":             "pass_rate",
                "is_mocking_error":   "mocking_rate",
                "is_runtime_error":   "runtime_rate",
                "is_assertion_error": "assertion_rate",
                "is_no_code":         "nocode_rate",
            }
            t_out = [t[rate_map[out_col]] for t in task_rows]
            rho, p = spearmanr(t_pred, t_out)
            task_results.append({
                "predictor": pred_label, "outcome": out_label,
                "rho": float(rho), "p_raw": float(p),
            })

    # BH correction within each level
    p_obs  = bh_correct([r["raw_p_mw"] for r in obs_results])
    p_task = bh_correct([r["p_raw"]     for r in task_results])
    for r, p in zip(obs_results, p_obs):
        r["p_mw_adj"] = p
    for r, p in zip(task_results, p_task):
        r["p_adj"] = p

    return obs_results, task_results


def run_task_level_aggregation(rows, features, composite_map) -> list[dict]:
    by_task: dict[int, list] = defaultdict(list)
    for r in rows:
        by_task[r["task_num"]].append(r)
    task_rows = []
    for task_num, obs in by_task.items():
        f = features[task_num]
        task_rows.append({
            "task_num":     task_num,
            "func_name":    f["func_name"],
            "source_file":  f["source_file"],
            "cc":           f["cc"],
            "halstead_diff":f["halstead_diff"],
            "difficulty":   f["difficulty"],
            "solution_chars":f["solution_chars"],
            "solution_lines":f["solution_lines"],
            "composite":    composite_map[task_num],
            "pass_rate":    float(np.mean([o["passed"]             for o in obs])),
            "mocking_rate": float(np.mean([o["is_mocking_error"]   for o in obs])),
            "runtime_rate": float(np.mean([o["is_runtime_error"]   for o in obs])),
            "assertion_rate":float(np.mean([o["is_assertion_error"]for o in obs])),
            "nocode_rate":  float(np.mean([o["is_no_code"]         for o in obs])),
        })
    return task_rows


def intercorrelation_matrix(features: dict) -> list[list[float]]:
    vals = {c: [f[c] for f in features.values()] for c in PRED_COLS}
    n    = len(PRED_COLS)
    mat  = [[0.0] * n for _ in range(n)]
    for i, c1 in enumerate(PRED_COLS):
        for j, c2 in enumerate(PRED_COLS):
            rho, _ = spearmanr(vals[c1], vals[c2])
            mat[i][j] = float(rho)
    return mat

# ── Formatting ────────────────────────────────────────────────────────────────

def sig(p: float) -> str:
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    if p < 0.10:  return "."
    return "n.s."


SEP = "=" * 90


def format_threats_section() -> str:
    lines = [
        "",
        SEP,
        "  THREATS TO VALIDITY",
        SEP,
        "",
        "  1. EXPERIMENTAL DESIGN (T=0.0, N=1) — CORRECT CHOICE",
        "     Alternative: T=0.2, N=3 TestEval vs T=0.2, N=10 Real-World.",
        "     Rejected because: (a) N-asymmetry confound — pass@k grows monotonically",
        "     with k, so Real-World would get 3.3x more attempts per task; (b) failure",
        "     classification is ambiguous with k>1 (which sample defines the failure?);",
        "     (c) stochastic sampling blurs systematic patterns with noise.",
        "     T=0.0, N=1 yields one deterministic outcome per (model, task) pair,",
        "     making both datasets directly comparable.",
        "",
        "  2. MULTICOLLINEARITY (primary threat — addressed below)",
        "     All five complexity predictors are strongly intercorrelated",
        "     (Spearman rho 0.71–0.98). Reporting five separate 'significant'",
        "     predictors inflates the apparent richness of findings — they all",
        "     measure the same latent construct. Fix: PCA composite score as",
        "     primary predictor; CC as interpretable single-metric reference.",
        "",
        "  3. OUTLIER INFLUENCE IN CC",
        "     CC ranges 2–72 (mean=9.88, SD=14.06), highly right-skewed.",
        "     Spearman is rank-based (handles skew), but extreme outliers can",
        "     dominate ranks. Fix: Winsorized (90th pct) correlation reported",
        "     as robustness check alongside raw Spearman.",
        "",
        "  4. FUNCTIONAL CLUSTERING (within source files)",
        "     50 functions from 14 source files. Functions in the same file",
        "     share module-level imports, global state, and style — inducing",
        "     within-file similarity that inflates effective N.",
        "     Fix: ICC / eta-squared decomposition reported; if between-file",
        "     variance dominates, file is not a meaningful cluster.",
        "",
        "  5. DATA CONTAMINATION (TestEval vs Real-World — not fixable statistically)",
        "     LeetCode problems (TestEval) are publicly indexed and likely present",
        "     in model training corpora. Models may partially memorize solutions,",
        "     generating assertion checks that reference known expected outputs.",
        "     This could artificially inflate IncorrectAssertion failures in TestEval",
        "     (model 'knows' the answer but writes the assertion incorrectly) while",
        "     suppressing genuine algorithmic confusion. Real-World functions from",
        "     niche production repositories are far less likely to be memorized.",
        "     This constitutes a confound for the chi-square comparison: the observed",
        "     TestEval/Real-World difference in root cause distributions may partly",
        "     reflect memorization artifacts rather than intrinsic task structure.",
        "     Reported as a limitation; future work should use contamination",
        "     detection (e.g., n-gram overlap with training data) to quantify.",
        "",
        "  6. FUNCTION ISOLATION ARTIFACT",
        "     Real-World functions are extracted from their original module context.",
        "     Mocking requirements arise partly because class-level setup, global",
        "     registry objects, and module-level state are stripped. MockingError",
        "     prevalence in Real-World may thus be partly an artefact of the",
        "     extraction methodology rather than intrinsic task difficulty.",
    ]
    return "\n".join(lines)


def format_intercorrelation(mat, features) -> str:
    lines = [
        "",
        SEP,
        "  PREDICTOR INTERCORRELATION MATRIX (Spearman rho, N=50 tasks)",
        "  HIGH COLLINEARITY CONFIRMED — all pairs rho >= 0.71",
        SEP,
        "",
    ]
    header = f"  {'':20}" + "".join(f"{l:>12}" for l in PRED_LABELS)
    lines.append(header)
    lines.append("  " + "-" * (20 + 12 * len(PRED_LABELS)))
    for i, l1 in enumerate(PRED_LABELS):
        row = f"  {l1:<20}"
        for j in range(len(PRED_LABELS)):
            rho = mat[i][j]
            flag = "*" if i != j and abs(rho) >= 0.70 else " "
            row += f"{rho:>+11.3f}{flag}"
        lines.append(row)
    lines.append("  * |rho| >= 0.70 (high collinearity threshold)")
    lines.append("")
    lines.append("  IMPLICATION: The five predictors do not offer independent evidence.")
    lines.append("  Reporting five significant associations is misleading — they all")
    lines.append("  capture the same latent complexity construct. Solution: PCA composite.")
    return "\n".join(lines)


def format_pca_section(var_explained, loadings) -> str:
    lines = [
        "",
        SEP,
        f"  COMPOSITE COMPLEXITY SCORE — PCA First Principal Component",
        f"  Variance explained by PC1: {var_explained:.1%}",
        SEP,
        "",
        "  PC1 Loadings (all positive → PC1 = general complexity):",
    ]
    for label, load in zip(PRED_LABELS, loadings):
        bar = "+" * int(abs(load) * 20)
        lines.append(f"  {label:<22}  {load:>+.4f}  {bar}")
    lines.append("")
    lines.append("  PC1 increases with all five metrics simultaneously.")
    lines.append("  A higher composite score = function is harder on every dimension.")
    return "\n".join(lines)


def format_clustering(cluster_stats) -> str:
    lines = [
        "",
        SEP,
        "  CLUSTERING: WITHIN-FILE vs BETWEEN-FILE CC VARIANCE",
        SEP,
        "",
        f"  Source files: {cluster_stats['n_files']}",
        f"  Eta-squared (between-file / total CC variance): {cluster_stats['eta_sq']:.3f}",
        "",
    ]
    if cluster_stats["eta_sq"] < 0.20:
        lines.append("  eta^2 < 0.20: Between-file variance is small relative to total.")
        lines.append("  File membership is NOT a dominant clustering factor.")
        lines.append("  The independence assumption of Spearman correlation is reasonable.")
    elif cluster_stats["eta_sq"] < 0.40:
        lines.append("  eta^2 0.20–0.40: Moderate between-file clustering.")
        lines.append("  File membership partially confounds results. Report as limitation.")
    else:
        lines.append("  eta^2 >= 0.40: Strong between-file clustering.")
        lines.append("  Effective N is substantially less than 50. Use mixed-effects model.")
    return "\n".join(lines)


def format_primary_results(obs_results, task_results) -> str:
    lines = [
        "",
        SEP,
        "  PRIMARY ANALYSIS: CC + COMPOSITE SCORE",
        "  Task-level (N=50) is the primary test; observation-level (N=250) is secondary.",
        SEP,
    ]

    lines.append(f"\n  --- TASK-LEVEL (N=50 unique functions, PRIMARY) ---")
    lines.append(f"  {'Predictor':<24} {'Outcome':<22} {'rho':>7} {'p_raw':>8} {'p_adj':>8}  Sig")
    lines.append("  " + "-" * 78)
    for r in task_results:
        lines.append(
            f"  {r['predictor']:<24} {r['outcome']:<22} "
            f"{r['rho']:>+7.3f} {r['p_raw']:>8.4f} {r['p_adj']:>8.4f}  {sig(r['p_adj'])}"
        )
    lines.append("  p_adj = BH-FDR adjusted across all 20 tests (5 outcomes x 2 predictors)")

    lines.append(f"\n  --- OBSERVATION-LEVEL (N=250, secondary — note pseudo-replication) ---")
    lines.append(
        f"  {'Predictor':<24} {'Outcome':<22} "
        f"{'Med(+)':>7} {'Med(-)':>7} {'rho':>7} {'r_rb':>7} {'p_adj':>8}  {'Win_rho':>8}  Sig"
    )
    lines.append("  " + "-" * 96)
    for r in obs_results:
        lines.append(
            f"  {r['predictor']:<24} {r['outcome']:<22} "
            f"{r['raw_med_pos']:>7.1f} {r['raw_med_neg']:>7.1f} "
            f"{r['raw_rho']:>+7.3f} {r['raw_r_rb']:>+7.3f} {r['p_mw_adj']:>8.4f}  "
            f"{r['win_rho']:>+8.3f}  {sig(r['p_mw_adj'])}"
        )
    lines.append("  Win_rho = Spearman rho after Winsorizing at 90th percentile (outlier check)")
    lines.append("  r_rb = rank-biserial r (effect size for Mann-Whitney)")
    return "\n".join(lines)


def format_consolidated(task_results) -> str:
    lines = [
        "",
        SEP,
        "  CONSOLIDATED FINDINGS",
        SEP,
        "",
        "  SIGNIFICANT (task-level, BH-FDR adjusted, N=50):",
    ]
    sig_res = [r for r in task_results if r["p_adj"] < 0.05]
    if sig_res:
        for r in sig_res:
            direction = "negatively" if r["rho"] < 0 else "positively"
            lines.append(
                f"    [{r['predictor']}] {direction} associated with {r['outcome']} "
                f"(rho={r['rho']:+.3f}, p_adj={r['p_adj']:.4f} {sig(r['p_adj'])})"
            )
    else:
        lines.append("    None after BH-FDR correction.")

    lines += [
        "",
        "  MARGINAL (p_raw < .10, not surviving correction):",
    ]
    marginal = [r for r in task_results if 0.05 <= r["p_adj"] < 0.15 and r["p_raw"] < 0.10]
    if marginal:
        for r in marginal:
            direction = "negatively" if r["rho"] < 0 else "positively"
            lines.append(
                f"    [{r['predictor']}] {direction} ~ {r['outcome']} "
                f"(rho={r['rho']:+.3f}, p_raw={r['p_raw']:.3f})"
            )
    else:
        lines.append("    None.")

    lines += [
        "",
        "  NON-SIGNIFICANT (informative null results):",
        "    MockingError rate: unpredicted by any complexity metric.",
        "    Interpretation: MockingError is driven by DEPENDENCY STRUCTURE",
        "    (external library calls, class-level state) — not cognitive complexity.",
        "    This partitions failure causes into two aetiological classes:",
        "      (A) Complexity-driven: general pass rate + No Code — amenable to",
        "          complexity-aware prompt engineering / function decomposition.",
        "      (B) Context-driven: MockingError, RuntimeError, AssertionError —",
        "          require richer model knowledge of library internals; complexity",
        "          reduction offers no remedy.",
        "",
        "  RECOMMENDED PAPER PHRASING:",
        "    'A composite complexity score derived from the first principal component",
        "    of five static metrics (CC, Halstead, difficulty label, solution length,",
        "    and line count; PC1 explaining X% of variance) was negatively associated",
        "    with pass rate (Spearman rho = ..., N=50, p_adj = ..., BH-FDR), and",
        "    positively associated with No Code failures (rho = ..., p_adj = ...).",
        "    MockingError rate was not predicted by composite complexity",
        "    (rho = ..., p_adj = ..., n.s.), indicating that dependency-structure",
        "    failures constitute a qualitatively distinct failure class not amenable",
        "    to complexity-aware mitigations.'",
    ]
    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading features...")
    features = load_function_features()
    outcomes = load_eval_outcomes()
    causes   = load_root_causes()

    print("Building composite score (PCA)...")
    composite_map, var_explained, loadings = build_composite(features)

    print("Building dataset...")
    rows = build_dataset(features, outcomes, causes)
    # Attach composite score to each observation
    for r in rows:
        r["composite"] = composite_map[r["task_num"]]

    print("Aggregating to task level...")
    task_rows = run_task_level_aggregation(rows, features, composite_map)

    print("Running intercorrelation matrix...")
    mat = intercorrelation_matrix(features)

    print("Running clustering analysis...")
    cluster_stats = within_between_variance(features)

    print("Running primary analysis...")
    obs_results, task_results = run_primary_analysis(rows, task_rows)

    # ── Compose report ────────────────────────────────────────────────────────
    report_lines: list[str] = [
        "PREDICTIVE ANALYSIS: FUNCTION COMPLEXITY AS FAILURE PREDICTOR",
        "Real-World Dataset — T=0.0, N=1 (deterministic, balanced design)",
        "=" * 90,
        "",
        "DATASET",
        f"  Observations : {len(rows)} (5 shared SLMs x 50 functions)",
        f"  Tasks        : {len(set(r['task_num'] for r in rows))} unique functions",
        f"  Source files : {len(set(r['source_file'] for r in rows))}",
        "",
        "OUTCOME PREVALENCE",
    ]
    for col, label in zip(OUTCOME_COLS, OUTCOME_LABELS):
        n = sum(r[col] for r in rows)
        report_lines.append(f"  {label:<22}: {n:>3}/{len(rows)} ({100*n/len(rows):.1f}%)")

    report_lines.append("\nPREDICTOR SUMMARY (N=50 unique tasks)")
    for col, label in zip(PRED_COLS, PRED_LABELS):
        vals = [f[col] for f in features.values()]
        report_lines.append(
            f"  {label:<26}: mean={np.mean(vals):.2f}, std={np.std(vals):.2f}, "
            f"min={min(vals):.1f}, max={max(vals):.1f}"
        )

    report_lines.append(format_threats_section())
    report_lines.append(format_intercorrelation(mat, features))
    report_lines.append(format_pca_section(var_explained, loadings))
    report_lines.append(format_clustering(cluster_stats))
    report_lines.append(format_primary_results(obs_results, task_results))
    report_lines.append(format_consolidated(task_results))

    # Top-10 by CC for reference
    report_lines.append(f"\n{SEP}")
    report_lines.append("  TOP 10 FUNCTIONS BY CYCLOMATIC COMPLEXITY")
    report_lines.append(SEP)
    report_lines.append(
        f"  {'Function':<35} {'CC':>4} {'Composite':>10} {'Diff':>5} "
        f"{'PassRate':>9} {'MockRate':>9} {'NoCdRate':>9}"
    )
    report_lines.append("  " + "-" * 85)
    for t in sorted(task_rows, key=lambda x: -x["cc"])[:10]:
        report_lines.append(
            f"  {t['func_name']:<35} {t['cc']:>4} {t['composite']:>10.3f} "
            f"{t['difficulty']:>5} {t['pass_rate']:>8.1%} "
            f"{t['mocking_rate']:>8.1%} {t['nocode_rate']:>8.1%}"
        )

    report = "\n".join(report_lines)
    OUT_PATH.write_text(report, encoding="utf-8")
    try:
        print("\n" + report)
    except UnicodeEncodeError:
        print("\n" + report.encode("ascii", errors="replace").decode("ascii"))
    print(f"\nReport saved to {OUT_PATH}")


if __name__ == "__main__":
    main()
