"""Calculate raw agreement and unweighted Cohen's kappa after second rating."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

NON_RATEABLE = {"NOT_RATEABLE", "NOT_RATEABLE_MISSING_EVIDENCE"}
UNCERTAIN = {"UNSURE", "UNCERTAIN"}

def load(path: Path, delimiter: str = ",") -> dict[str, dict[str, str]]:
    # Use Python's csv module with a custom delimiter:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if delimiter == "#,##":
            # Work around multi-char delimiter by splitting manually
            lines = [line.rstrip("\n") for line in stream]
            header = [h.strip() for h in lines[0].split(delimiter)]
            data = [
                dict(zip(header, [v.strip() for v in row.split(delimiter)]))
                for row in lines[1:] if row.strip()
            ]
            return {row["validation_row_id"]: row for row in data}
        else:
            reader = csv.DictReader(stream, delimiter=delimiter)
            return {row["validation_row_id"]: row for row in reader}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=("dependency_levels", "oracle_classes"))
    parser.add_argument("--second-rater-file", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--delimiter", type=str, default=",",
                        help="Delimiter used by both rater CSVs unless overridden")
    parser.add_argument("--first-delimiter", type=str, help="Delimiter for first-rater CSV")
    parser.add_argument("--second-delimiter", type=str, help="Delimiter for second-rater CSV")

    args = parser.parse_args()
    folder = Path(__file__).resolve().parent / args.task
    first_delimiter = args.first_delimiter or args.delimiter
    second_delimiter = args.second_delimiter or args.delimiter
    first = load(folder / "first_rater_labels.csv", first_delimiter)
    second = load(args.second_rater_file or folder / "second_rater_sheet.csv", second_delimiter)
    first_col = "first_rater_label" if args.task == "dependency_levels" else "first_rater_class"
    second_col = "second_rater_label" if args.task == "dependency_levels" else "second_rater_class"
    allowed = ({"L0", "L1", "L2", "L3"} if args.task == "dependency_levels"
               else {"TRIVIAL", "WEAK", "STRONG", "UNKNOWN"})
    valid = []
    missing, non_rateable, uncertain = [], [], []
    for row_id, a in first.items():
        b = second.get(row_id, {}).get(second_col, "").strip().upper()
        x = a[first_col].strip().upper()
        if not b:
            missing.append(row_id)
        elif b in NON_RATEABLE:
            non_rateable.append(row_id)
        elif b in UNCERTAIN:
            uncertain.append(row_id)
        else:
            if b not in allowed:
                raise SystemExit(f"Invalid substantive label {b!r} for {row_id}; allowed: {sorted(allowed)}")
            valid.append((x, b))
    if not valid:
        raise SystemExit(f"No completed labels found in {second_col}")
    n = len(valid)
    observed = sum(a == b for a, b in valid) / n
    a_counts, b_counts = Counter(a for a, _ in valid), Counter(b for _, b in valid)
    labels = set(a_counts) | set(b_counts)
    expected = sum((a_counts[x] / n) * (b_counts[x] / n) for x in labels)
    kappa = (observed - expected) / (1 - expected) if expected != 1 else 1.0
    result = {
        "original_sample_n": len(first),
        "rateable_paired_n": n,
        "excluded_missing_rating_n": len(missing),
        "excluded_not_rateable_n": len(non_rateable),
        "excluded_uncertain_n": len(uncertain),
        "raw_agreement": observed,
        "agreement_count": sum(a == b for a, b in valid),
        "cohens_kappa_unweighted": kappa,
        "calculation_basis": "original independent ratings before adjudication",
    }
    print(f"Original sample: {len(first)}")
    print(f"Rateable paired observations: {n}")
    print(f"Excluded missing second-rater rating: {len(missing)}")
    print(f"Excluded NOT_RATEABLE: {len(non_rateable)}")
    print(f"Excluded genuine UNSURE: {len(uncertain)}")
    print(f"Raw agreement: {observed:.3f} ({result['agreement_count']}/{n})")
    print(f"Cohen's kappa (unweighted): {kappa:.3f}")
    if args.json_output:
        args.json_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
