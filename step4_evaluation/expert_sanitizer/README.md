# Human Expert Evaluation App — LLM-as-Judge Sanitisation

A Streamlit + Firebase application for collecting human expert evaluations of AI-generated
Python unit tests. Used as the human-expert sanitisation step in a master's thesis study
evaluating Small Language Models (SLMs) for unit test generation.

---

## Architecture

```mermaid
graph TD
    classDef web    fill:#D5F5E3,stroke:#2ECC71,stroke-width:2px;
    classDef server fill:#EBF5FB,stroke:#3498DB,stroke-width:2px;
    classDef db     fill:#FDEDEC,stroke:#E74C3C,stroke-width:2px;
    classDef local  fill:#FDEBD0,stroke:#F39C12,stroke-width:2px;

    A[Expert opens app] --> B[GDPR consent + Annotator ID]
    B --> C[Demographics: experience / expertise / domain]
    C --> D[Rubric review]
    D --> EvalLoop(For each of 30 cases — randomised order)

    subgraph "Per-case evaluation"
        EvalLoop --> E[Focal code shown]
        E --> F[Test Suite A vs B shown<br>A/B position randomised per annotator+task]
        F --> G[Rate A on 4 criteria 1–5]
        G --> H[Rate B on 4 criteria 1–5]
        H --> I[Overall winner: A / B / Tie]
    end

    EvalLoop --> J[Submit to Firestore]
    J --> K{Optional reasoning review}
    K -->|Yes| L[Show LLM reasoning per case<br>Ask: agree / partially / no]
    L --> M[Submit reasoning to Firestore]
    K -->|No| N[Done]

    subgraph "Firebase Firestore"
        J --> P[(human_evaluations)]
        M --> Q[(reasoning_agreements)]
    end

    subgraph "Offline analysis"
        R(analyze_human_eval.py) --> P
        R --> Q
        R --> S[[cohen_kappa.csv / criterion_correlation.csv]]
    end

    class A,B,C,D,EvalLoop,E,F,G,H,I,K,L,N web;
    class J,M server;
    class P,Q db;
    class R,S local;
```

---

## Files

| File | Description |
|---|---|
| `app.py` | Streamlit application — full evaluation flow |
| `requirements.txt` | Python dependencies |
| `firebase_creds.json` | **Local only** — service account key (never commit) |
| `.streamlit/secrets.toml` | **Local only** — Streamlit secrets for cloud deployment |

**Input data** (read-only, lives in the main repo):

```
TestEval/predictions_judgellm/stratified_human_eval_full_factorial.csv
```

30 stratified pairwise comparisons (10 Clear / 10 Marginal / 10 Tie).
Columns: `task_id`, `stratum`, `score_diff`, `model_a`, `model_b`,
`model_a_total_score`, `model_b_total_score`, `docstring`, `focal_code`,
`code_a`, `code_b`, `reasoning_pass_full`.

---

## Firestore schema

### Collection: `human_evaluations`

Document ID = annotator_id

```json
{
  "annotator_id": "JD1",
  "timestamp": "2026-02-26T10:00:00Z",
  "demographics": {
    "years_experience": "5–9",
    "testing_expertise": "Advanced",
    "domain_familiarity": ["Machine Learning / Deep Learning"]
  },
  "total_comparisons": 30,
  "responses": [
    {
      "task_id": 24238,
      "stratum": "Clear",
      "display_order": 1,
      "ab_swapped": false,
      "winner_display": "A",
      "winner_actual": "A",
      "scores_display_a": { "robustness": 4, "assertions": 5, "readability": 3, "conciseness": 4 },
      "scores_display_b": { "robustness": 2, "assertions": 3, "readability": 4, "conciseness": 3 },
      "notes": ""
    }
  ]
}
```

**Key fields for analysis:**

| Field | Purpose |
|---|---|
| `winner_actual` | Winner corrected for A/B swap — use this for Cohen's Kappa |
| `ab_swapped` | Whether display A/B were swapped vs raw CSV order |
| `scores_display_a/b` | Per-criterion scores for the test shown as A/B |
| `stratum` | Clear / Marginal / Tie — report kappa separately per stratum |

### Collection: `reasoning_agreements`

Document ID = annotator_id

```json
{
  "annotator_id": "JD1",
  "timestamp": "...",
  "agreements": [
    {
      "task_id": 24238,
      "agreement": "Partially",
      "disagreement_notes": "LLM overweighted readability..."
    }
  ]
}
```

---

## Evaluation methodology

### Why hybrid (pairwise + per-criterion scoring)?

| | Pure A/B/Tie | Hybrid |
|---|---|---|
| Cohen's Kappa | ✅ | ✅ |
| Criterion-level human vs LLM correlation | ❌ | ✅ |
| Diagnosis of where LLM diverges from humans | ❌ | ✅ |
| Time per expert | ~10 min | ~20–25 min |

### Validity safeguards

- **Anchoring bias prevented** — LLM reasoning is hidden until *after* all 30 assessments
- **A/B position randomised** per `(annotator_id, task_id)` using MD5-seeded RNG; `ab_swapped` flag recorded
- **Case order randomised** per annotator (deterministic, reproducible for debugging)
- **Criteria aligned exactly** with LLM judge (Robustness, Assertions, Readability, Conciseness)
- **GDPR compliant** — no name, email, IP, or other identifying data collected; consent checkbox required

### Post-collection analysis

From `human_evaluations`, compute:

1. **Cohen's Kappa (human–human)** — inter-rater reliability using `winner_actual`
2. **Cohen's Kappa (human–LLM)** — human `winner_actual` vs `final_winner_model` from JSONL
3. **Pearson/Spearman correlation** — `scores_display_a/b` vs LLM criterion scores per dimension
4. **Kappa by stratum** — report separately for Clear, Marginal, Tie
5. **Reasoning agreement rate** — from `reasoning_agreements` collection

---

## Local setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add Firebase service account key
cp /path/to/serviceAccountKey.json firebase_creds.json

# 3. Run (from repo root so the CSV path resolves)
cd /path/to/slm-python-unit-test-benchmark
streamlit run temp/app.py
```

## Streamlit Cloud deployment

1. Push `temp/` contents to a GitHub repo (exclude `firebase_creds.json`)
2. Create app on [share.streamlit.io](https://share.streamlit.io) pointing to `app.py`
3. Add Firebase credentials under **Settings → Secrets**:

```toml
[firebase]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

4. The CSV must be accessible at `TestEval/predictions_judgellm/stratified_human_eval_full_factorial.csv`
   relative to where the app runs. On Streamlit Cloud, include it in the repo or adjust `SAMPLE_CSV` to an
   absolute URL / hosted path.

---

## GDPR notes

- Legal basis: **Art. 6(1)(e) GDPR** (task in the public interest) + **Art. 89** (scientific research)
- Data minimisation: only non-identifying categorical background data collected
- No special category data (Art. 9) collected
- Participants informed that anonymised responses will be published
- Consent recorded via checkbox on welcome screen (stored implicitly — participants cannot proceed without checking it)
- Retention: data retained until thesis publication and review period; inform participants of retention period if required by your institution
