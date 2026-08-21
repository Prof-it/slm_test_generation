"""Create a stratified oracle-site sample for blinded manual validation.

This is a static pre-validation step. Runtime fields are deliberately blank
until the instrumented evaluator is run. Existing prediction/evaluation files
are read-only and never modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from oracle_analysis import classify_oracles


def _strip_markdown(source: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", source or "", re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else (source or "").strip()


def _pipeline(filename: str) -> str:
    return "two-step" if filename.startswith("linecov2_") else "single-step"


def collect_sites(predictions_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(predictions_dir.rglob("*.jsonl")):
        if path.name == "pynguin_results.jsonl":
            continue
        tier = next((part.removeprefix("tier_") for part in path.parts if part.startswith("tier_")), "")
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                tests = record.get("tests") or {}
                for target, payload in tests.items():
                    raw = payload.get("test_code", "") if isinstance(payload, dict) else str(payload)
                    source = _strip_markdown(raw)
                    if not source:
                        continue
                    try:
                        sites = classify_oracles(source, sut_names={record.get("func_name", "")})
                    except SyntaxError:
                        continue
                    source_lines = source.splitlines()
                    generation_id = f"{path.stem}:{record.get('task_num')}:{target}"
                    for site in sites:
                        start = max(0, site.lineno - 2)
                        end = min(len(source_lines), site.lineno + 2)
                        rows.append({
                            "generation_id": generation_id,
                            "benchmark": "TestContextBench-Py",
                            "task_id": record.get("task_num"),
                            "model": record.get("model", path.stem),
                            "pipeline": _pipeline(path.name),
                            "tier": record.get("tier", tier),
                            "dependency_level": record.get("dependency_level", ""),
                            "target": target,
                            "oracle_id": site.oracle_id,
                            "oracle_kind": site.oracle_kind,
                            "predicted_class": site.oracle_class.value,
                            "lineno": site.lineno,
                            "col_offset": site.col_offset,
                            "sut_dependent": site.sut_dependent,
                            "classification_reason": site.classification_reason,
                            "executed": "",
                            "suite_passed": "",
                            "source_context": "\n".join(source_lines[start:end]),
                            "manual_class": "",
                            "manual_notes": "",
                        })
    return rows


def stratified_sample(rows: list[dict], size: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["predicted_class"], row["pipeline"], row["tier"])].append(row)
    for group in groups.values():
        rng.shuffle(group)

    selected: list[dict] = []
    keys = sorted(groups)
    # Round-robin sampling prevents large STRONG strata from crowding out rare
    # preliminary classes while retaining pipeline/tier representation.
    while len(selected) < min(size, len(rows)):
        progressed = False
        for key in keys:
            if groups[key] and len(selected) < size:
                selected.append(groups[key].pop())
                progressed = True
        if not progressed:
            break
    rng.shuffle(selected)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=250)
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument("--artifact-suffix", default="",
                        help="Optional non-empty suffix such as 'v2'; creates separate sample/manifest files")
    args = parser.parse_args()

    rows = collect_sites(args.predictions_dir)
    sample = stratified_sample(rows, args.sample_size, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.artifact_suffix.strip('_')}" if args.artifact_suffix else ""
    output = args.output_dir / f"oracle_manual_validation_sample{suffix}.csv"
    manifest_path = args.output_dir / f"oracle_manual_validation_manifest{suffix}.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing validation sample: {output}")
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing validation manifest: {manifest_path}")
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(sample[0]) if sample else [])
        if sample:
            writer.writeheader()
            writer.writerows(sample)

    manifest = {
        "predictions_dir": str(args.predictions_dir.resolve()),
        "seed": args.seed,
        "requested_sample_size": args.sample_size,
        "available_oracle_sites": len(rows),
        "sampled_oracle_sites": len(sample),
        "runtime_fields_populated": False,
        "artifact_suffix": args.artifact_suffix,
        "class_counts": {name: sum(r["predicted_class"] == name for r in sample)
                         for name in sorted({r["predicted_class"] for r in sample})},
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
