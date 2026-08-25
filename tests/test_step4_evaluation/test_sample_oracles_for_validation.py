import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "step4_evaluation"))

from sample_oracles_for_validation import stratified_sample


def test_stratified_sample_is_deterministic_and_preserves_rare_classes():
    rows = []
    for cls, count in (("STRONG", 20), ("WEAK", 3), ("TRIVIAL", 2), ("UNKNOWN", 1)):
        for i in range(count):
            rows.append({"predicted_class": cls, "pipeline": "single-step", "tier": "A", "i": i})
    first = stratified_sample(rows, 8, 7)
    second = stratified_sample(rows, 8, 7)
    assert first == second
    assert {row["predicted_class"] for row in first} == {"STRONG", "WEAK", "TRIVIAL", "UNKNOWN"}
