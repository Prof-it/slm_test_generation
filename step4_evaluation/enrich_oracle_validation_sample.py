"""Create a non-overwriting blinded validation view with exact oracle source.

This utility does not read predicted labels and does not modify samples. It
joins stable sample identifiers back to the original generated test source so
an annotator can distinguish the sampled oracle from neighboring assertions.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path

from oracle_analysis import classify_oracles
from sample_oracles_for_validation import _strip_markdown


def _oracle_node(tree: ast.AST, lineno: int, col: int, kind: str) -> ast.AST | None:
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) != lineno or getattr(node, "col_offset", None) != col:
            continue
        if kind == "assert" and isinstance(node, ast.Assert):
            return node
        if kind in {"exception_contract", "warning_contract"} and isinstance(node, ast.With):
            return node
        if kind in {"mock_contract", "unittest_assertion"} and isinstance(node, ast.Expr):
            return node
    return None


def _enclosing_function(tree: ast.AST, lineno: int) -> ast.AST | None:
    candidates = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.lineno <= lineno <= getattr(n, "end_lineno", n.lineno)]
    return min(candidates, key=lambda n: getattr(n, "end_lineno", n.lineno) - n.lineno) if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blinded-sample", type=Path, required=True)
    parser.add_argument("--predictions-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")

    rows = list(csv.DictReader(args.blinded_sample.open(encoding="utf-8-sig", newline="")))
    cache: dict[Path, dict[str, dict]] = {}
    output_rows = []
    for row in rows:
        stem, task_id, target = row["generation_id"].rsplit(":", 2)
        path = args.predictions_dir / f"tier_{row['tier']}" / f"{stem}.jsonl"
        if path not in cache:
            cache[path] = {str(r["task_num"]): r for r in
                           (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())}
        record = cache[path][task_id]
        payload = (record.get("tests") or {})[target]
        source = _strip_markdown(payload.get("test_code", "") if isinstance(payload, dict) else str(payload))
        tree = ast.parse(source)
        node = _oracle_node(tree, int(row["lineno"]), int(row["col_offset"]), row["oracle_kind"])
        function = _enclosing_function(tree, int(row["lineno"]))
        enriched = dict(row)
        enriched["focal_function"] = record.get("func_name", "")
        enriched["oracle_source"] = ast.get_source_segment(source, node) if node else ""
        enriched["enclosing_test_source"] = ast.get_source_segment(source, function) if function else source
        output_rows.append(enriched)

    fields = list(output_rows[0])
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"wrote {len(output_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
