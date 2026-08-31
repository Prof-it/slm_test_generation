"""Build blinded second-rater packages from the preserved validation evidence.

Run from the repository root. Existing first-rater files are read-only; generated
review sheets contain no first-rater or automated labels.
"""

from __future__ import annotations

import csv
import hashlib
import json
import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_response_template(
    path: Path,
    rows: list[dict[str, object]],
    fields: list[str],
    response_fields: tuple[str, ...],
) -> None:
    """Write a blank template without ever erasing an existing human response."""
    if path.exists():
        existing = read_csv(path)
        populated = [
            row.get("validation_row_id", f"row-{index + 1}")
            for index, row in enumerate(existing)
            if any((row.get(field) or "").strip() for field in response_fields)
        ]
        if populated:
            preview = ", ".join(populated[:5])
            raise FileExistsError(
                f"Refusing to overwrite {path}: {len(populated)} row(s) contain human "
                f"responses ({preview}). Preserve/rename the rated file before rebuilding."
            )
    write_csv(path, rows, fields)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


RECOVERED_DEPENDENCY_ITEMS = {
    "rwt2_08ace22793aa": ("kstevica_captain-claw", "460410901b258f89cf638f91a1a47ea10e48762d", "captain_claw/cli.py", "print_tool_call"),
    "rwt2_69f222f126ec": ("kstevica_captain-claw", "460410901b258f89cf638f91a1a47ea10e48762d", "captain_claw/twitter_bridge.py", "get_updates"),
    "rwt2_7231a1f3d995": ("kstevica_captain-claw", "460410901b258f89cf638f91a1a47ea10e48762d", "captain_claw/tools/clipboard.py", "_write_image"),
    "rwt2_a999534aff39": ("kstevica_captain-claw", "460410901b258f89cf638f91a1a47ea10e48762d", "captain_claw/cli.py", "append_tool_output"),
    "rwt2_b706193e1edb": ("kstevica_captain-claw", "460410901b258f89cf638f91a1a47ea10e48762d", "captain_claw/botport_client.py", "_receive_loop"),
    "rwt2_ff1be63bb103": ("gptme_gptme", "83dbacff2fc0732187078d5214e1b78a164dd5ae", "gptme/llm/llm_openai_subscription.py", "init"),
}


def recover_dependency_item(item_id: str) -> dict[str, str]:
    clone, commit, source_path, symbol = RECOVERED_DEPENDENCY_ITEMS[item_id]
    clone_path = ROOT / "sources" / "repos" / clone
    result = subprocess.run(
        ["git", "-C", str(clone_path), "show", f"{commit}:{source_path}"],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="strict",
    )
    module_source = result.stdout
    tree = ast.parse(module_source)
    matches = [node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol]
    if len(matches) != 1:
        raise ValueError(f"Expected one {symbol} in {commit}:{source_path}, found {len(matches)}")
    function_source = ast.get_source_segment(module_source, matches[0]) or ""
    imports = "\n".join(ast.get_source_segment(module_source, node) or ast.unparse(node)
                        for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom)))
    return {
        "source_file": source_path,
        "qualified_symbol": symbol,
        "commit_sha": commit,
        "signature": ast.unparse(matches[0]).splitlines()[0],
        "focal_function": function_source,
        "python_solution": function_source,
        "dependency_context": f"{imports}\n\n{function_source}".strip(),
        "evidence_origin": f"sources/repos/{clone} Git object {commit}:{source_path}",
    }


def dependency_package() -> dict[str, object]:
    labels_path = ROOT / "sources" / "level_audit.csv"
    candidates_path = ROOT / "sources" / "v2_candidates.jsonl"
    labels = read_csv(labels_path)
    original_sample = read_csv(ROOT / "sources" / "level_audit_sample.csv")
    original_ids = {row["id"] for row in original_sample}
    wanted = {row["id"] for row in labels}
    evidence: dict[str, dict] = {}
    with candidates_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("id") in wanted:
                evidence[row["id"]] = row

    recovered = {item_id: recover_dependency_item(item_id)
                 for item_id in sorted(wanted - evidence.keys())}

    review_rows = []
    first_rows = []
    provenance_rows = []
    for index, label in enumerate(labels, 1):
        item = evidence.get(label["id"]) or recovered[label["id"]]
        in_original = label["id"] in original_ids
        status = ("preserved_sample_and_completed_audit" if in_original
                  else "completed_audit_current_candidate" if label["id"] in evidence
                  else "completed_audit_git_recovered")
        function_source = item.get("focal_function") or item.get("python_solution", "")
        dependency_context = item.get("dependency_context") or item.get("python_solution", function_source)
        row_id = f"dependency_{index:04d}"
        review_rows.append({
            "validation_row_id": row_id,
            "item_id": label["id"],
            "repository": label["repo"],
            "source_file": item.get("source_file", ""),
            "function_name": label["func_name"],
            "qualified_symbol": item.get("qualified_symbol", label["func_name"]),
            "commit_sha": item.get("commit_sha", ""),
            "content_sha256": text_sha256(function_source),
            "provenance_status": status,
            "signature": item.get("signature", ""),
            "function_source": function_source,
            "dependency_context": dependency_context,
            "second_rater_label": "",
            "second_rater_confidence": "",
            "second_rater_notes": "",
        })
        provenance_rows.append({
            "validation_row_id": row_id,
            "item_id": label["id"],
            "first_rater_record": "yes",
            "preserved_blank_sample": "yes" if in_original else "no",
            "source_evidence": "yes",
            "provenance_status": status,
            "repository": label["repo"],
            "commit_sha": item.get("commit_sha", ""),
            "source_file": item.get("source_file", ""),
            "qualified_symbol": item.get("qualified_symbol", label["func_name"]),
            "content_sha256": text_sha256(function_source),
            "evidence_origin": item.get("evidence_origin", "sources/v2_candidates.jsonl"),
        })
        first_rows.append({
            "validation_row_id": row_id,
            "item_id": label["id"],
            "automated_label": label["dependency_level"],
            "first_rater_decision": label["manual_label"],
            "first_rater_label": (
                label["dependency_level"] if label["manual_label"] == "Agree"
                else label["manual_label"].removeprefix("Disagree (").removesuffix(")")
            ),
            "first_rater_notes": label["notes"],
        })

    write_response_template(
        OUT / "dependency_levels" / "second_rater_sheet.csv", review_rows,
        list(review_rows[0]),
        ("second_rater_label", "second_rater_confidence", "second_rater_notes"),
    )
    write_csv(OUT / "dependency_levels" / "first_rater_labels.csv", first_rows,
              list(first_rows[0]))
    write_csv(OUT / "dependency_levels" / "sample_manifest.csv", provenance_rows,
              list(provenance_rows[0]))
    write_response_template(
        OUT / "dependency_levels" / "adjudication_sheet.csv",
        [{"validation_row_id": row["validation_row_id"], "adjudicated_label": "",
          "adjudication_reason": ""} for row in review_rows],
        ["validation_row_id", "adjudicated_label", "adjudication_reason"],
        ("adjudicated_label", "adjudication_reason"),
    )
    return {
        "task": "dependency-level classification",
        "reviewed_sample_size": len(labels),
        "source_population_file": "../../sources/v2_candidates.jsonl",
        "source_population_rows_current": sum(1 for _ in candidates_path.open(encoding="utf-8")),
        "source_population_sha256_current": sha256(candidates_path),
        "completed_first_rater_file": "../../sources/level_audit.csv",
        "completed_first_rater_file_sha256": sha256(labels_path),
        "evidence_rows_available": len(labels),
        "evidence_rows_from_current_candidates": len(evidence),
        "evidence_rows_recovered_from_git": len(recovered),
        "evidence_rows_missing": [],
        "declared_original_seed": 42,
        "provenance_warning": (
            "The completed first-rater file and preserved blank seed-42 sample overlap on "
            "19/30 IDs. Of the other 11 completed-audit rows, five remain in the "
            "current candidate file and six were exactly recovered from audit-era nested-repository "
            "Git objects. Evidence is complete for second rating, but the historical population "
            "snapshot/order that produced the completed sample is unavailable; do not claim exact "
            "sample-draw reconstruction."
        ),
    }


def oracle_package() -> dict[str, object]:
    base = ROOT / "step4_evaluation" / "oracle_validation"
    evidence_path = base / "oracle_manual_validation_blinded_v4_enriched.csv"
    labels_path = base / "oracle_manual_validation_v4_FULL250_human_vs_all.csv"
    manifest_path = base / "oracle_manual_validation_manifest_v4.json"
    evidence = read_csv(evidence_path)
    labels = read_csv(labels_path)
    labels_by_id = {row["validation_row_id"]: row for row in labels}
    if len(evidence) != 250 or set(labels_by_id) != {r["validation_row_id"] for r in evidence}:
        raise ValueError("Oracle evidence and first-rater labels are not a complete 1:1 match")

    review_fields = [
        "validation_row_id", "generation_id", "benchmark", "task_id", "model",
        "pipeline", "tier", "dependency_level", "target", "oracle_id", "oracle_kind",
        "focal_function", "oracle_source", "enclosing_test_source",
        "second_rater_sut_dependent", "second_rater_class", "second_rater_confidence",
        "second_rater_notes",
    ]
    review_rows = []
    first_rows = []
    provenance_rows = []
    for row in evidence:
        blinded = {key: row.get(key, "") for key in review_fields}
        review_rows.append(blinded)
        provenance_rows.append({
            "validation_row_id": row["validation_row_id"],
            "generation_id": row["generation_id"],
            "task_id": row["task_id"],
            "model": row["model"],
            "pipeline": row["pipeline"],
            "tier": row["tier"],
            "oracle_id": row["oracle_id"],
            "oracle_kind": row["oracle_kind"],
            "lineno": row["lineno"],
            "col_offset": row["col_offset"],
            "oracle_source_sha256": text_sha256(row.get("oracle_source", "")),
            "enclosing_test_source_sha256": text_sha256(row.get("enclosing_test_source", "")),
        })
        first = labels_by_id[row["validation_row_id"]]
        first_rows.append({
            "validation_row_id": row["validation_row_id"],
            "first_rater_sut_dependent": first["human_sut_dependent"],
            "first_rater_class": first["human_class"],
            "first_rater_notes": first["human_notes"],
        })

    write_response_template(
        OUT / "oracle_classes" / "second_rater_sheet.csv", review_rows, review_fields,
        ("second_rater_sut_dependent", "second_rater_class",
         "second_rater_confidence", "second_rater_notes"),
    )
    write_csv(OUT / "oracle_classes" / "first_rater_labels.csv", first_rows,
              list(first_rows[0]))
    write_csv(OUT / "oracle_classes" / "sample_manifest.csv", provenance_rows,
              list(provenance_rows[0]))
    write_response_template(
        OUT / "oracle_classes" / "adjudication_sheet.csv",
        [{"validation_row_id": row["validation_row_id"], "adjudicated_class": "",
          "adjudication_reason": ""} for row in review_rows],
        ["validation_row_id", "adjudicated_class", "adjudication_reason"],
        ("adjudicated_class", "adjudication_reason"),
    )
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "task": "oracle-site classification",
        "sampling_method": "round-robin stratified by predicted class, pipeline, and context tier",
        "seed": original["seed"],
        "source_population_file": "../../downloaded_predictions/second_experiment/run_1",
        "available_oracle_sites": original["available_oracle_sites"],
        "sample_size": original["sampled_oracle_sites"],
        "exclusions": "pynguin_results.jsonl; empty test code; test code with SyntaxError",
        "sampling_script": "../../step4_evaluation/sample_oracles_for_validation.py",
        "evidence_file": "../../step4_evaluation/oracle_validation/oracle_manual_validation_blinded_v4_enriched.csv",
        "evidence_file_sha256": sha256(evidence_path),
        "first_rater_file": "../../step4_evaluation/oracle_validation/oracle_manual_validation_v4_FULL250_human_vs_all.csv",
        "first_rater_file_sha256": sha256(labels_path),
    }


def main() -> None:
    for directory in (OUT / "dependency_levels", OUT / "oracle_classes"):
        directory.mkdir(parents=True, exist_ok=True)
    manifests = {
        OUT / "dependency_levels" / "manifest.json": dependency_package(),
        OUT / "oracle_classes" / "manifest.json": oracle_package(),
    }
    for path, content in manifests.items():
        path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    print("Built both blinded second-rater packages and separated first-rater labels.")


if __name__ == "__main__":
    main()
