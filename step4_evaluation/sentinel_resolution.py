"""
Sentinel-pair resolution: of the 3 hidden reliability-check sentinel items
(same code pair as an existing item, A/B swapped), how many did each
annotator resolve consistently with their own source-item answer, and how
many did the LLM judge resolve consistently with its own source-item verdict?

Run: python step4_evaluation/sentinel_resolution.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_llm_judge import load_inputs, build_unified  # noqa: E402

ann_data, csv_df, jlookup = load_inputs()
df = build_unified(ann_data, csv_df, jlookup)

sentinel_rows = df[df["is_sentinel"] == True]
print(f"{len(sentinel_rows)} sentinel rows found\n")

ann_ids = [a["annotator_id"] for a in ann_data]

for _, srow in sentinel_rows.iterrows():
    orig_tid = srow["task_id"] - 100000
    orig_row = df[df["task_id"] == orig_tid]
    if orig_row.empty:
        print(f"sentinel {srow['task_id']}: source task {orig_tid} not found in unified df")
        continue
    orig_row = orig_row.iloc[0]
    print(f"sentinel task_id={srow['task_id']}  source task_id={orig_tid}  stratum={srow['stratum']}")
    print(f"  LLM judge: source winner={orig_row['llm_winner']}  sentinel winner={srow['llm_winner']} "
          f"(sentinel is source with A/B swapped, so a consistent judge should flip)")
    for i in range(1, len(ann_data) + 1):
        src_w = orig_row.get(f"ann{i}_winner")
        sen_w = srow.get(f"ann{i}_winner")
        print(f"  ann{i} ({ann_ids[i-1]}): source winner={src_w}  sentinel winner={sen_w}")
    print()

# ---- aggregate correctness: a resolution is "correct" if the swapped winner
# label is the FLIP of the source winner (A<->B), or both are Tie.
def flip(w):
    return {"A": "B", "B": "A", "Tie": "Tie"}.get(w, w)

judge_correct = 0
ann_correct = {i: 0 for i in range(1, len(ann_data) + 1)}
n_sentinels = 0

for _, srow in sentinel_rows.iterrows():
    orig_tid = srow["task_id"] - 100000
    orig_row = df[df["task_id"] == orig_tid]
    if orig_row.empty:
        continue
    orig_row = orig_row.iloc[0]
    n_sentinels += 1
    if srow["llm_winner"] == flip(orig_row["llm_winner"]) and orig_row["llm_winner"] is not None:
        judge_correct += 1
    for i in range(1, len(ann_data) + 1):
        src_w = orig_row.get(f"ann{i}_winner")
        sen_w = srow.get(f"ann{i}_winner")
        if src_w is not None and sen_w == flip(src_w):
            ann_correct[i] += 1

print("=" * 70)
print("SENTINEL RESOLUTION SUMMARY")
print("=" * 70)
print(f"n_sentinels = {n_sentinels}")
print(f"LLM judge: {judge_correct}/{n_sentinels} consistent with own source-item verdict")
total_ann_correct = sum(ann_correct.values())
total_ann_obs = len(ann_data) * n_sentinels
for i in range(1, len(ann_data) + 1):
    print(f"  ann{i} ({ann_ids[i-1]}): {ann_correct[i]}/{n_sentinels} consistent")
print(f"Annotators pooled: {total_ann_correct}/{total_ann_obs} consistent")
