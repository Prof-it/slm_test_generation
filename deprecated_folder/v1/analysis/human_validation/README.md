# Human Validation for LLM-as-Judge

Scripts for validating LLM-as-Judge using human expert annotations and
Cohen's Kappa agreement analysis.

---

## Workflow

### Step 1 — Human Evaluation (Streamlit app)

Experts evaluate 30 pairwise comparisons through the app at
`step4_evaluation/expert_sanitizer/app.py`.

- Evaluators score each test suite on 4 criteria (1–5) and pick an overall winner (A / B / Tie).
- A/B positions are randomised per annotator (counters position bias); the app
  records both the display label and the canonical `winner_actual` label.
- Export results from Firebase as JSON:
  `step4_evaluation/expert_sanitizer/human_evaluation_exports.json`

---

### Step 2 — Integrate & Merge

```bash
python step4_evaluation/human_validation/integrate_human_eval.py \
    --json_export step4_evaluation/expert_sanitizer/human_evaluation_exports.json \
    --csv         TestEval/predictions_judgellm/stratified_human_eval_full_factorial.csv \
    --jsonl       TestEval/predictions_judgellm/pairwise_judgements_full_factorial.jsonl \
    --output      TestEval/predictions_judgellm/unified_human_eval.csv
```

**What it does:**

1. Reconstructs each annotator's case order (deterministic, seeded by annotator ID)
   to map `display_order` -> CSV row index -> `(task_id, model_a, model_b)`.
2. De-swaps per-criterion human scores from display order to canonical
   `model_a` / `model_b` order (needed for correlation with LLM scores).
3. Joins with the JSONL to add LLM per-criterion scores (average of both
   evaluation passes) and the bias-corrected `final_winner_model`.
4. Writes one 30-row CSV with all annotator, LLM, and metadata columns.

**Output columns (39 total):**

| Column group | Columns |
|---|---|
| Identification | `csv_row_idx`, `task_id`, `model_a`, `model_b`, `stratum` |
| LLM judgment | `llm_winner`, `llm_score_a`, `llm_score_b`, `llm_{crit}_a/b` (×4) |
| Annotator 1 | `ann1_id`, `ann1_winner`, `ann1_{crit}_a/b` (×4), `ann1_notes` |
| Annotator 2 | `ann2_id`, `ann2_winner`, `ann2_{crit}_a/b` (×4), `ann2_notes` |
| Consensus | `human_consensus` (A/B/Tie if both agree, else "Disagreement") |

---

### Step 3 — Calculate Agreement Statistics

```bash
python step4_evaluation/human_validation/calculate_kappa.py \
    --unified_csv TestEval/predictions_judgellm/unified_human_eval.csv \
    --output_dir  TestEval/predictions_judgellm
```

**Output — printed report and `kappa_results.json`:**

| Section | Statistic |
|---|---|
| 1. Inter-Annotator Agreement | Cohen's Kappa (ann1 vs ann2) + observed agreement |
| 2. LLM vs Human | Kappa: LLM vs ann1, LLM vs ann2, LLM vs consensus |
| 3. Confusion Matrices | LLM vs each annotator |
| 4. Per-Criterion Correlation | Pearson r (human avg vs LLM), 60 pairs per criterion |
| 5. Total Score Correlation | Pearson r on summed scores, 60 pairs |
| 6. Stratum Breakdown | Agreement rates by Clear / Marginal / Tie |
| 7. Summary | Thesis-ready one-paragraph summary |

---

## Example Results (2 annotators, 30 comparisons)

```
Inter-annotator agreement:  k = 0.526  (Moderate)   70% observed
LLM vs Ann1 (Advanced):     k = 0.632  (Substantial) 76.7% observed  [PASS]
LLM vs Ann2 (Beginner):     k = 0.474  (Moderate)    66.7% observed  [FAIL]
LLM vs Human Consensus:     k = 0.780  (Substantial) 85.7% (on 21/30 agreement cases)

Score correlation (r, human avg vs LLM):
  Robustness:         r = 0.614 ***  (Strong)
  Assertion Strength: r = 0.568 ***  (Moderate)
  Readability:        r = 0.771 ***  (Strong)
  Conciseness:        r = 0.811 ***  (Very Strong)
  Total score:        r = 0.753 ***  (Strong)
```

---

## Validation Threshold

Following Siddiq et al. (2024): **k >= 0.60 = Substantial agreement** confirms the
LLM judge can be trusted for the full dataset.

Interpretation scale (Landis & Koch, 1977):

| k | Interpretation |
|---|---|
| < 0.20 | Slight |
| 0.20 – 0.40 | Fair |
| 0.40 – 0.60 | Moderate |
| **0.60 – 0.80** | **Substantial** (required) |
| >= 0.80 | Almost Perfect |

---

## Files

| File | Description |
|---|---|
| `integrate_human_eval.py` | Merges JSON export + CSV + JSONL into unified CSV |
| `calculate_kappa.py` | Computes all agreement and correlation statistics |
| `TestEval/predictions_judgellm/unified_human_eval.csv` | 30-row merged analysis file |
| `TestEval/predictions_judgellm/kappa_results.json` | Machine-readable results |

---

## Reporting in Thesis

**Methodology section:**
- 2 annotators (Advanced + Beginner expertise), 30 pairwise comparisons
- Sampling strategy: stratified 10 Clear / 10 Marginal / 10 Tie
- Annotation task: A/B/Tie overall preference + 4 per-criterion scores (1–5)
- A/B position randomised per annotator to control position bias

**Results section:**
- Inter-Annotator Agreement (Cohen's Kappa)
- LLM vs each annotator (Kappa + observed agreement)
- LLM vs human consensus on agreed cases
- Per-criterion Pearson correlation
- Stratum-level breakdown

**Threats to validity:**
- Small sample (30 pairs) — typical for human evaluation studies
- Only 2 annotators — individual agreement reported separately, not averaged
- Expertise mismatch — Advanced vs Beginner annotator noted in analysis

---

## Scientific Citations

- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*.
- Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159–174.
- Siddiq et al. (2024). An Empirical Study on LLM-as-a-Judge for Software Testing. *IEEE Transactions on Software Engineering*.
