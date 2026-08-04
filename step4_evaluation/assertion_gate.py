"""
assertion_gate.py -- static (AST-only) audit of whether "passing" generated
test suites actually contain a detectable assertion.

This directly answers the Threats-to-Validity caveat previously stated as an
open limitation ("the project's narrow AST checker did not flag an explicit
assert ... in 550 of 1,976 passing configuration-task observations"): rather
than leaving that as a caveat, this tool computes the real number, with a
slightly broader (still conservative/lower-bound) check than
evaluate_results.py's check_for_assertions: bare `assert` statements,
`self.assert*`/`<any_obj>.assert*` calls (covers both unittest-style and mock
assertion methods like `mock.assert_called_once()`), and `pytest.raises` /
`self.assertRaises` context managers (an exception-based assertion that a
narrower checker would otherwise miss and misreport as "no assertion").

Pure AST parse -- no execution, no sandbox, seconds not minutes.

Usage:
    python step4_evaluation/assertion_gate.py --predictions-dir downloaded_predictions/second_experiment/run_1
    python step4_evaluation/assertion_gate.py --predictions-dir downloaded_predictions/second_experiment/run_1 --evaluated-dir evaluation_results/second_experiment/run_1
"""

import argparse
import ast
import glob
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "step4_evaluation"))
# Reuse the exact same test-reconstruction logic evaluate_results.py uses at
# execution time (tests is a dict of {"test_code": ..., "generated_tokens": ...}
# entries, not a dict of plain strings -- a naive str()-per-value join produces
# Python dict reprs, not source code, and silently fails every ast.parse call).
from evaluate_results import _combine_tests_for_task, strip_markdown  # noqa: E402


def has_detectable_assertion(source: str) -> tuple[bool, str | None]:
    """Returns (has_assertion, kind) where kind in
    {'assert_stmt', 'assert_call', 'raises_context', None}."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False, None

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            return True, "assert_stmt"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith("assert"):
                return True, "assert_call"
            if node.func.attr in ("raises", "assertRaises", "assertRaisesRegex"):
                return True, "raises_context"
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
                    if call.func.attr in ("raises", "assertRaises", "assertRaisesRegex"):
                        return True, "raises_context"
                if isinstance(call, ast.Attribute) and call.attr in ("raises",):
                    return True, "raises_context"
    return False, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions-dir", required=True,
                     help="Directory (searched recursively) of prediction *.jsonl files with a 'tests' field")
    ap.add_argument("--evaluated-dir", default=None,
                     help="Optional: matching evaluation_results dir with *_evaluated.jsonl, to restrict "
                          "the audit to suites that were scored Pass (matches by task_num + filename stem)")
    ap.add_argument("--out", default=str(PROJECT_ROOT / "step4_evaluation" / "assertion_gate_report.json"))
    args = ap.parse_args()

    pred_files = sorted(glob.glob(str(Path(args.predictions_dir) / "**" / "*.jsonl"), recursive=True))
    if not pred_files:
        raise RuntimeError(f"No prediction files found under {args.predictions_dir}")

    pass_ids_by_stem = None
    if args.evaluated_dir:
        pass_ids_by_stem = {}
        for f in glob.glob(str(Path(args.evaluated_dir) / "**" / "*_evaluated.jsonl"), recursive=True):
            stem = Path(f).stem.replace("_evaluated", "")
            recs = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
            pass_ids_by_stem[stem] = {str(r["task_num"]) for r in recs if r.get("status") == "Pass"}

    total_checked = 0
    total_with_assertion = 0
    kind_counts = {"assert_stmt": 0, "assert_call": 0, "raises_context": 0}
    no_assertion_examples = []

    for f in pred_files:
        stem = Path(f).stem
        restrict_ids = pass_ids_by_stem.get(stem) if pass_ids_by_stem is not None else None
        if pass_ids_by_stem is not None and restrict_ids is None:
            continue  # no matching evaluated file for this prediction file -- skip

        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            entry = json.loads(line)
            tn = str(entry.get("task_num"))
            if restrict_ids is not None and tn not in restrict_ids:
                continue
            tests = entry.get("tests")
            if not tests:
                continue
            test_list = list(tests.items()) if isinstance(tests, dict) else [(str(i), t) for i, t in enumerate(tests)]
            func_name = entry.get("func_name", "solution")
            combined = _combine_tests_for_task(test_list, func_name)
            source = strip_markdown(combined)
            if not source.strip():
                continue
            total_checked += 1
            ok, kind = has_detectable_assertion(source)
            if ok:
                total_with_assertion += 1
                kind_counts[kind] += 1
            else:
                if len(no_assertion_examples) < 20:
                    no_assertion_examples.append({"file": str(Path(f).resolve().relative_to(PROJECT_ROOT)), "task_num": tn})

    n_no_assertion = total_checked - total_with_assertion
    pct = 100 * n_no_assertion / total_checked if total_checked else float("nan")

    print(f"Checked: {total_checked} suites"
          + (" (restricted to Pass-status suites)" if pass_ids_by_stem is not None else " (all suites with generated tests)"))
    print(f"  With detectable assertion:    {total_with_assertion} ({100 * total_with_assertion / total_checked:.1f}%)")
    print(f"    - bare assert statement:    {kind_counts['assert_stmt']}")
    print(f"    - obj.assert*() call:       {kind_counts['assert_call']}")
    print(f"    - raises() context:         {kind_counts['raises_context']}")
    print(f"  WITHOUT detectable assertion: {n_no_assertion} ({pct:.1f}%)")

    payload = {
        "total_checked": total_checked, "with_assertion": total_with_assertion,
        "without_assertion": n_no_assertion, "pct_without_assertion": round(pct, 2),
        "kind_counts": kind_counts, "restricted_to_pass": pass_ids_by_stem is not None,
        "no_assertion_examples": no_assertion_examples,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
