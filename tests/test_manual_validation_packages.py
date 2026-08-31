import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from manual_validation.build_review_packages import write_response_template


ROOT = Path(__file__).resolve().parents[1]


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_blinded_sheets_have_no_prior_labels_and_complete_evidence():
    dependency = _rows(ROOT / "manual_validation/dependency_levels/second_rater_sheet.csv")
    oracle = _rows(ROOT / "manual_validation/oracle_classes/second_rater_sheet.csv")
    assert len(dependency) == 30
    assert len(oracle) == 250
    assert all(row["function_source"] and row["dependency_context"] and row["content_sha256"]
               for row in dependency)
    forbidden = {"first_rater", "human_class", "predicted_class", "automated_label", "manual_class"}
    for rows in (dependency, oracle):
        headers = {name.lower() for name in rows[0]}
        assert not any(any(token in header for token in forbidden) for header in headers)


def test_dependency_provenance_reconciles_all_30_rows():
    rows = _rows(ROOT / "manual_validation/dependency_levels/sample_manifest.csv")
    counts = {}
    for row in rows:
        counts[row["provenance_status"]] = counts.get(row["provenance_status"], 0) + 1
        assert row["source_evidence"] == "yes"
        assert len(row["content_sha256"]) == 64
    assert counts == {
        "preserved_sample_and_completed_audit": 19,
        "completed_audit_current_candidate": 5,
        "completed_audit_git_recovered": 6,
    }


def test_agreement_excludes_not_rateable_and_unsure(tmp_path):
    source = _rows(ROOT / "manual_validation/dependency_levels/first_rater_labels.csv")
    output = tmp_path / "second.csv"
    fields = ["validation_row_id", "second_rater_label"]
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(source):
            label = row["first_rater_label"]
            if index == 0:
                label = "NOT_RATEABLE_MISSING_EVIDENCE"
            elif index == 1:
                label = "UNSURE"
            elif index == 2:
                label = ""
            writer.writerow({"validation_row_id": row["validation_row_id"],
                             "second_rater_label": label})
    result_path = tmp_path / "agreement.json"
    subprocess.run([
        sys.executable, str(ROOT / "manual_validation/calculate_agreement.py"),
        "dependency_levels", "--second-rater-file", str(output),
        "--json-output", str(result_path),
    ], check=True, capture_output=True, text=True)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["original_sample_n"] == 30
    assert result["rateable_paired_n"] == 27
    assert result["excluded_not_rateable_n"] == 1
    assert result["excluded_uncertain_n"] == 1
    assert result["excluded_missing_rating_n"] == 1
    assert result["raw_agreement"] == 1.0
    assert result["cohens_kappa_unweighted"] == 1.0


def test_builder_refuses_to_erase_partial_second_rating(tmp_path):
    path = tmp_path / "ratings.csv"
    fields = ["validation_row_id", "second_rater_label", "second_rater_notes"]
    rows = [{"validation_row_id": "row_1", "second_rater_label": "L2",
             "second_rater_notes": "reviewed"}]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    original = path.read_bytes()
    blank = [{"validation_row_id": "row_1", "second_rater_label": "",
              "second_rater_notes": ""}]
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_response_template(path, blank, fields,
                                ("second_rater_label", "second_rater_notes"))
    assert path.read_bytes() == original


def test_builder_refuses_to_erase_adjudication_notes_without_label(tmp_path):
    path = tmp_path / "adjudication.csv"
    fields = ["validation_row_id", "adjudicated_label", "adjudication_reason"]
    rows = [{"validation_row_id": "row_1", "adjudicated_label": "",
             "adjudication_reason": "discussion started"}]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(FileExistsError, match="human responses"):
        write_response_template(path, [], fields,
                                ("adjudicated_label", "adjudication_reason"))
