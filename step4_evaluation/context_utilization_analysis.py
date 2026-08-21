"""
Context-utilization analysis: does the generated test actually reference the
extra material Tier B (dependency stubs) / Tier C (mock hint) supplied, or is
the extra context tier an unused input condition?

Isolated, non-overwriting. Reuses evaluate_results.py's own suite-construction
helpers; does not modify evaluate_results.py, assertion_gate.py,
gated_reanalysis.py, oracle_analysis.py, or any legacy result/paper file.

Method (static, associational only — this measures reference, not correct use):
  - Tier B/C predictions embed their own `context_card` (as sent to the model).
  - Dependency stub names are parsed from context_card['B']['text'] (the
    "--- Dependency stubs ---" section: every `def <name>(` there).
  - The Tier C mock-hint target is parsed from context_card['C']['text']
    (`patch '<target>'`), plus the generic-hint fallback ("MagicMock"/
    "unittest.mock" mention when no specific pattern was detected upstream).
  - A generated test "uses" a dependency stub if the stub name appears as a
    whole-word token anywhere in the combined test source (call or reference).
  - A generated test "uses" the mock hint if the mock target string appears in
    the test source, or (fallback for the generic hint) it calls
    unittest.mock.patch / MagicMock at all.
  - Joined against the evaluated jsonl (Execution Pass@1 status) via task_num
    for the same tier/model/pipeline/dependency-level breakdown as rq3_dependency_level.py.

Run: python step4_evaluation/context_utilization_analysis.py
"""
import json
import re
import sys
import glob
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "step4_evaluation"))
from evaluate_results import _combine_tests_for_task, strip_markdown  # noqa: E402

SEC = ROOT / "evaluation_results" / "second_experiment" / "run_1"
PRED_B_GLOB = str(ROOT / "downloaded_predictions" / "second_experiment" / "run_1" / "tier_*" / "*.jsonl")

MODELS = ["Qwen3-4B-Thinking-2507", "Qwen3.5-4B", "gemma-4-E4B-it",
          "granite-4.0-micro", "Ministral-3-3B-Reasoning-2512"]
PREFIX = {"linecov": "Single-step", "linecov2": "Two-step"}
TIERS = ["B", "C"]  # Tier A has no dependency/mock material to utilize by construction

STUB_DEF_RE = re.compile(r"def\s+(\w+)\s*\(")
MOCK_TARGET_RE = re.compile(r"Mock hint: patch '([^']+)'")


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def parse_dep_stub_names(card_b_text: str) -> list[str]:
    if "--- Dependency stubs ---" not in card_b_text:
        return []
    section = card_b_text.split("--- Dependency stubs ---", 1)[1]
    return sorted(set(STUB_DEF_RE.findall(section)))


def parse_mock_target(card_c_text: str) -> str | None:
    m = MOCK_TARGET_RE.search(card_c_text)
    if m:
        return m.group(1)
    if "Mock hint: use unittest.mock.patch" in card_c_text:
        return "__generic__"
    return None


def get_test_source(entry: dict) -> str:
    tests = entry.get("tests")
    if not tests:
        return ""
    test_list = list(tests.items()) if isinstance(tests, dict) else [(str(i), t) for i, t in enumerate(tests)]
    func_name = entry.get("func_name", "solution")
    combined = _combine_tests_for_task(test_list, func_name)
    return strip_markdown(combined)


def dep_used(names: list[str], source: str) -> bool:
    return any(re.search(rf"\b{re.escape(n)}\b", source) for n in names)


def mock_used(target: str | None, source: str) -> bool:
    if target is None:
        return False
    if target == "__generic__":
        return ("unittest.mock" in source or "MagicMock" in source
                or re.search(r"\bpatch\s*\(", source) is not None)
    return target in source or target.split(".")[-1] in source


pred_b_files = {
    (Path(f).parent.name, Path(f).stem): f for f in glob.glob(PRED_B_GLOB)
}

# key: (tier, model, pipeline, dependency_level, exec_status) -> counters
rows = []

for m in MODELS:
    for pfx, pipeline in PREFIX.items():
        for t in TIERS:
            pred_path = pred_b_files.get((f"tier_{t}", f"{pfx}_{m}_temp_0.0"))
            eval_path = SEC / f"tier_{t}" / f"{pfx}_{m}_temp_0.0_evaluated.jsonl"
            if not pred_path or not eval_path.exists():
                continue
            status_by_task = {}
            for r in load_jsonl(eval_path):
                status_by_task[str(r["task_num"])] = r.get("status")

            for entry in load_jsonl(pred_path):
                tn = str(entry.get("task_num"))
                status = status_by_task.get(tn)
                if status is None:
                    continue
                passed = (status == "Pass")

                card = entry.get("context_card") or {}
                b_text = card.get("B", {}).get("text", "")
                dep_names = parse_dep_stub_names(b_text)

                source = get_test_source(entry)
                if not source.strip():
                    continue

                du = dep_used(dep_names, source) if dep_names else None  # None = no stubs supplied for this task

                mu = None
                if t == "C":
                    c_text = card.get("C", {}).get("text", "")
                    target = parse_mock_target(c_text)
                    mu = mock_used(target, source) if target else None

                rows.append({
                    "model": m,
                    "pipeline": pipeline,
                    "tier": t,
                    "dependency_level": entry.get("dependency_level", "?"),
                    "passed": passed,
                    "has_dep_stubs": dep_names != [],
                    "dep_used": du,
                    "has_mock_hint": mu is not None,
                    "mock_used": mu,
                })

print(f"Total (tier B/C, task_num, model, pipeline) rows analyzed: {len(rows)}")
print()


def rate(subset, key):
    vals = [r[key] for r in subset if r[key] is not None]
    if not vals:
        return None, 0
    return 100.0 * sum(vals) / len(vals), len(vals)


def summarize(group_key_fn, label):
    print("=" * 90)
    print(label)
    print("=" * 90)
    groups = defaultdict(list)
    for r in rows:
        groups[group_key_fn(r)].append(r)
    for key in sorted(groups):
        subset = groups[key]
        dep_pct, dep_n = rate(subset, "dep_used")
        mock_pct, mock_n = rate(subset, "mock_used")
        dep_str = f"{dep_pct:5.1f}% (n={dep_n})" if dep_pct is not None else "   n/a"
        mock_str = f"{mock_pct:5.1f}% (n={mock_n})" if mock_pct is not None else "   n/a"
        print(f"  {str(key):55s}  dep_used={dep_str:22s}  mock_used={mock_str}")
    print()


summarize(lambda r: (r["tier"], r["model"], r["pipeline"]), "By tier x model x pipeline")
summarize(lambda r: (r["tier"], r["dependency_level"]), "By tier x dependency level")
summarize(lambda r: (r["tier"], r["passed"]), "By tier x execution-pass status (associational only)")
summarize(lambda r: (r["tier"],), "By tier (overall)")

out_path = ROOT / "step4_evaluation" / "oracle_validation" / "context_utilization_rows.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=1)
print(f"Per-row data written to {out_path}")
