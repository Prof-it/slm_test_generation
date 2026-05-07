"""
Streamlit App: Human Expert Evaluation of LLM-as-Judge Results

Implements a hybrid methodology:
  - Step 0: Demographics
  - Step 1: Rubric review
  - Step 2: 30 pairwise evaluations — per-criterion scoring (1-5) + overall A/B/Tie
  - Step 3 (optional): Review LLM judge reasoning and indicate agreement

Data: stratified_human_eval_full_factorial.csv
Storage: Firebase Firestore (collections: human_evaluations, reasoning_agreements)

Validity safeguards:
  - LLM reasoning hidden until AFTER all 30 assessments are complete (prevents anchoring)
  - Case order randomised per annotator (counters fatigue/order effects)
  - A/B display position randomised per (annotator, task) and recorded (counters position bias)
  - Criteria aligned exactly with LLM judge (Robustness, Assertions, Readability, Conciseness)
"""

import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import os
import hashlib
import random
import uuid


# Configuration
SAMPLE_CSV    = "stratified_human_eval_full_factorial.csv"
JUDGEMENTS_JSONL = "pairwise_judgements_full_factorial.jsonl"
FIREBASE_CREDS_LOCAL = "firebase_creds.json"

CRITERIA = ["robustness", "assertions", "readability", "conciseness"]
CRITERIA_LABELS = {
    "robustness":   "Robustness",
    "assertions":   "Assertion Strength",
    "readability":  "Readability",
    "conciseness":  "Conciseness",
}

RUBRIC_FULL = """
### Scoring Guide (1 = Very Poor → 5 = Excellent)

---

**1. ROBUSTNESS** — Edge cases & boundary values

| Score | Description |
|-------|-------------|
| **5** | Comprehensive coverage: empty inputs, None, negatives, type errors, boundary limits, multiple edge cases |
| **4** | Multiple edge cases covered with some depth |
| **3** | Basic edge cases or happy path with some variation |
| **2** | Only happy path tested with standard valid inputs |
| **1** | Minimal/No edge case coverage, missing critical scenarios |

---

**2. ASSERTION STRENGTH** — Verification quality

| Score | Description |
|-------|-------------|
| **5** | Strong, specific assertions: exact return values, state changes, specific exception types with messages |
| **4** | Specific assertions covering key behaviours |
| **3** | Basic assertions that verify correctness |
| **2** | Weak/generic: asserts type only, or `is not None` |
| **1** | Trivial or absent: `assert True`, or no meaningful assertions |

---

**3. READABILITY** — Code clarity

| Score | Description |
|-------|-------------|
| **5** | Professional: clear naming, AAA (Arrange-Act-Assert) pattern, proper setup, well-documented |
| **4** | Clean structure with clear intent |
| **3** | Understandable but could be clearer |
| **2** | Messy or unclear structure |
| **1** | Obfuscated or confusing, hard to understand |

---

**4. CONCISENESS** — Efficiency

| Score | Description |
|-------|-------------|
| **5** | Highly efficient: minimal code, no redundancy, elegant |
| **4** | Efficient with minimal unnecessary code |
| **3** | Some unnecessary code but functional |
| **2** | Notable redundancy or verbosity |
| **1** | Bloated: excessive redundancy, dead code, unnecessary complexity |

---

> **Important:** Rate each test suite *independently* before choosing an overall winner.
> A test with no meaningful assertions should score **1** for Assertion Strength regardless of other qualities.
"""

RUBRIC_COMPACT = """
**1 → 5 scale:** 1 = Very Poor, 3 = Acceptable, 5 = Excellent

- **Robustness**: edge case & boundary coverage
- **Assertions**: strength & specificity of assertions
- **Readability**: clarity, naming, AAA structure
- **Conciseness**: no redundancy, no dead code
"""

# Firebase
def init_firebase():
    if not firebase_admin._apps:
        try:
            creds_json = {
                "type": st.secrets["firebase"]["type"],
                "project_id": st.secrets["firebase"]["project_id"],
                "private_key_id": st.secrets["firebase"]["private_key_id"],
                "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),
                "client_email": st.secrets["firebase"]["client_email"],
                "client_id": st.secrets["firebase"]["client_id"],
                "auth_uri": st.secrets["firebase"]["auth_uri"],
                "token_uri": st.secrets["firebase"]["token_uri"],
                "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
            }
            creds = credentials.Certificate(creds_json)
        except (KeyError, Exception):
            if os.path.exists(FIREBASE_CREDS_LOCAL):
                creds = credentials.Certificate(FIREBASE_CREDS_LOCAL)
            else:
                st.error("Firebase credentials not found. Add firebase_creds.json locally or configure Streamlit secrets.")
                st.stop()
        firebase_admin.initialize_app(creds)
    return firestore.client()


# Data loading & randomisation helpers
@st.cache_data
def load_data(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        st.error(f"CSV not found: {csv_path}")
        st.info("Expected: stratified_human_eval_full_factorial.csv")
        st.stop()
    return pd.read_csv(csv_path)


@st.cache_data
def load_judgements(jsonl_path: str) -> dict:
    """Load JSONL into a dict keyed by (task_id, model_a, model_b) for fast lookup.

    Per-criterion scores are averaged across both passes (position-bias-corrected).
    Order: [robustness, assertions, readability, conciseness]
    """
    import json as _json
    lookup = {}
    if not os.path.exists(jsonl_path):
        return lookup
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = _json.loads(line)
            p1a = rec.get("model_a_scores_pass1", [0, 0, 0, 0])
            p2a = rec.get("model_a_scores_pass2", [0, 0, 0, 0])
            p1b = rec.get("model_b_scores_pass1", [0, 0, 0, 0])
            p2b = rec.get("model_b_scores_pass2", [0, 0, 0, 0])
            key = (str(rec["task_id"]), rec["model_a"], rec["model_b"])
            lookup[key] = {
                "pass1_a": p1a,
                "pass2_a": p2a,
                "pass1_b": p1b,
                "pass2_b": p2b,
            }
    return lookup


def _stable_hash(text: str) -> int:
    """Deterministic integer hash (MD5) that is stable across Python sessions."""
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def get_case_order(annotator_id: str, n: int) -> list:
    """Deterministic shuffle of indices [0..n-1] seeded by annotator_id."""
    seed = _stable_hash(f"case_order_{annotator_id}") % (2**31)
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    return order


def is_ab_swapped(annotator_id: str, task_id: int) -> bool:
    """Deterministically decide if A/B positions are swapped for this annotator+task."""
    return _stable_hash(f"ab_swap_{annotator_id}_{task_id}") % 2 == 1


# Page: Welcome / GDPR consent / ID entry
def page_welcome():
    st.title("Unit Test Quality Evaluation Study")
    st.markdown("""
You are invited to participate in a research study that is part of a master's thesis project.

**Your task:** Review pairs of AI-generated Python unit tests, rate each on 4 quality criteria, and choose which is overall better.

| | |
|---|---|
| **Comparisons** | 30 pairs |
| **Estimated time** | 20–25 minutes |
| **Contact** | c.barkinozer@gmail.com |

---
""")

    # --- GDPR / Consent block ---
    st.subheader("Participant Information & Data Protection Notice")
    st.markdown("""
**Purpose of this study**

This survey collects expert evaluations of AI-generated Python unit tests to validate an automated
evaluation approach (LLM-as-Judge) developed as part of a master's thesis in software engineering.
Results will be reported in the thesis and may be published in related academic work.

**Legal basis for processing (GDPR Art. 6(1)(e) and Art. 89)**

Your responses are processed solely for scientific research purposes. Participation is voluntary.
You may withdraw at any time before final submission without consequence.

**What data is collected**

- An automatic anonymous identifier (no name, email, or contact details)
- Professional background (years of experience, expertise level, domain familiarity)
- Evaluation responses (numeric ratings and preference choices)
- Optional free-text notes

**What is NOT collected**

No name, surname, email address, IP address, employer, or any other information that could
identify you is collected or stored. Any information you enter cannot be linked back
to you by the researcher.

**Public disclosure**

Aggregated results and anonymised individual response records will be published in the thesis
and potentially in academic venues. By participating, you agree that your anonymised responses
may be shared publicly in this context.

**Free-text fields**

The evaluation form contains optional notes fields. **Do not enter any personal information**
(names, contact details, employer, or other identifying details) in these fields.
""")

    agreed = st.checkbox(
        "I have read the above information, I understand that my anonymised responses may be "
        "published in academic research, and I voluntarily agree to participate.",
        key="gdpr_agreed",
    )

    st.markdown("---")

    if not agreed:
        st.info("Please read and accept the conditions above to continue.")
        return

    # Auto-generate a session ID the first time the user accepts consent.
    # Format: p-<8 random hex chars>  e.g. p-3a7f9c2b
    if "annotator_id" not in st.session_state or not st.session_state.annotator_id:
        st.session_state.annotator_id = "p-" + uuid.uuid4().hex[:8]

    annotator_id = st.session_state.annotator_id

    st.subheader("Your Session ID")
    st.markdown(
        f"Your anonymous session ID has been generated automatically: &nbsp; **`{annotator_id}`**\n\n"
        "Note it down if you think you may need to reload the page mid-way through."
    )

    if st.button("Start Evaluation →", type="primary"):
        st.session_state.page = "demographics"
        st.rerun()


# Page: Demographics
def page_demographics():
    st.title("About You")
    st.caption("Step 1 of 3 — This information helps us analyse how expert background affects inter-rater agreement.")
    st.markdown("---")

    years = st.radio(
        "Years of professional software development experience:",
        ["0–1", "2–4", "5–9", "10+"],
        horizontal=True,
        index=None,
        key="demo_years",
    )
    expertise = st.radio(
        "Python unit-testing expertise (e.g., pytest):",
        ["Beginner", "Intermediate", "Advanced", "Expert"],
        horizontal=True,
        index=None,
        key="demo_expertise",
    )
    domains = st.multiselect(
        "Domains you are most familiar with (select all that apply):",
        [
            "Machine Learning / Deep Learning",
            "Web / API development",
            "Backend / Systems",
            "Data engineering",
            "Other",
        ],
        key="demo_domains",
    )

    st.markdown("---")
    if st.button("Continue →", type="primary"):
        if not years or not expertise:
            st.error("Please answer the first two questions.")
        else:
            st.session_state.demographics = {
                "years_experience": years,
                "testing_expertise": expertise,
                "domain_familiarity": domains,
            }
            st.session_state.page = "rubric"
            st.rerun()


# Page: Rubric
def page_rubric():
    st.title("Evaluation Rubric")
    st.caption("Step 2 of 3 — Read before starting. The rubric is also available in the sidebar during evaluation.")
    st.markdown("""
You will score each unit test on **4 criteria** using a **1–5 scale**.
These criteria match the automated judge used in this study, enabling direct comparison.
""")
    st.markdown(RUBRIC_FULL)
    st.markdown("---")
    if st.button("Begin Evaluation (30 comparisons) →", type="primary"):
        df = load_data(SAMPLE_CSV)
        st.session_state.case_order = get_case_order(st.session_state.annotator_id, len(df))
        st.session_state.current_case_idx = 0
        st.session_state.responses = {}
        st.session_state.page = "evaluation"
        st.rerun()


# Page: Evaluation (one case at a time)
def page_evaluation():
    df = load_data(SAMPLE_CSV)
    total = len(df)
    case_order = st.session_state.case_order
    idx = st.session_state.current_case_idx
    row = df.iloc[case_order[idx]]

    task_id = int(row["task_id"])
    stratum = str(row["stratum"])
    focal_code = str(row["focal_code"])
    docstring = str(row.get("docstring", "")).strip()
    swapped = is_ab_swapped(st.session_state.annotator_id, task_id)

    display_a = str(row["code_b"]) if swapped else str(row["code_a"])
    display_b = str(row["code_a"]) if swapped else str(row["code_b"])

    resp_key = f"{task_id}_{case_order[idx]}"
    existing = st.session_state.responses.get(resp_key, {})

    # --- Sidebar ---
    with st.sidebar:
        completed = sum(1 for v in st.session_state.responses.values() if v)
        st.progress(completed / total, text=f"{completed}/{total} completed")
        st.markdown("---")
        with st.expander("Rubric reference", expanded=True):
            st.markdown(RUBRIC_COMPACT)

    # --- Header ---
    st.title(f"Comparison {idx + 1} / {total}")
    st.caption(f"Step 3 of 3 — Use the ← → buttons to navigate. Changes are saved automatically.")

    # --- Focal code ---
    with st.expander("Focal Method (code under test)", expanded=True):
        if docstring and docstring not in ("No docstring.", "nan"):
            st.caption(f"Docstring: {docstring}")
        st.code(focal_code, language="python")

    st.markdown("---")

    # --- Side-by-side tests ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Test Suite A")
        st.code(display_a, language="python")
    with col2:
        st.subheader("Test Suite B")
        st.code(display_b, language="python")

    st.markdown("---")
    st.markdown("### Scores (1 = Very Poor → 5 = Excellent)")
    with st.expander("📋 Full scoring rubric", expanded=False):
        st.markdown(RUBRIC_FULL)

    # --- Per-criterion scoring ---
    def render_scores(suite_label: str, suite_key: str) -> dict:
        st.markdown(f"**Test Suite {suite_label}**")
        cols = st.columns(4)
        scores = {}
        for i, crit in enumerate(CRITERIA):
            default = existing.get(f"scores_{suite_key}", {}).get(crit, 3)
            with cols[i]:
                scores[crit] = st.select_slider(
                    CRITERIA_LABELS[crit],
                    options=[1, 2, 3, 4, 5],
                    value=default,
                    key=f"{resp_key}_{crit}_{suite_key}",
                )
        return scores

    scores_a = render_scores("A", "a")
    scores_b = render_scores("B", "b")

    st.markdown("---")
    st.markdown("### Overall: Which test suite is better?")
    winner_options = ["A", "B", "Tie"]
    winner_default = existing.get("winner_display")
    winner = st.radio(
        "Overall preference:",
        winner_options,
        index=winner_options.index(winner_default) if winner_default in winner_options else None,
        horizontal=True,
        key=f"{resp_key}_winner",
        captions=["A is clearly better", "B is clearly better", "About equal quality"],
    )

    notes = st.text_area(
        "Optional notes (e.g., 'Test A handles None better but B is more concise'):",
        value=existing.get("notes", ""),
        height=70,
        key=f"{resp_key}_notes",
        help="Do not include personal information (names, contact details, employer) in this field.",
    )

    st.markdown("---")

    # --- Navigation ---
    col_prev, col_mid, col_next = st.columns([1, 3, 1])

    with col_prev:
        if idx > 0:
            if st.button("← Previous", use_container_width=True):
                _save_response(resp_key, task_id, stratum, idx, swapped, winner, scores_a, scores_b, notes)
                st.session_state.current_case_idx -= 1
                st.rerun()

    with col_mid:
        is_last = idx == total - 1
        btn_label = "Save & Submit All →" if is_last else "Save & Next →"
        if st.button(btn_label, type="primary", disabled=(winner is None), use_container_width=True):
            _save_response(resp_key, task_id, stratum, idx, swapped, winner, scores_a, scores_b, notes)
            if is_last:
                _submit_evaluation()
            else:
                st.session_state.current_case_idx += 1
                st.rerun()

    with col_next:
        # Allow jumping to next already-answered case without saving current winner
        if idx < total - 1 and winner is not None:
            if st.button("Next (no change) →", use_container_width=True):
                _save_response(resp_key, task_id, stratum, idx, swapped, winner, scores_a, scores_b, notes)
                st.session_state.current_case_idx += 1
                st.rerun()

    if winner is None:
        st.warning("Please select an overall preference (A / B / Tie) before proceeding.")


def _save_response(resp_key, task_id, stratum, display_order, swapped, winner_display, scores_a, scores_b, notes):
    if winner_display is None:
        return
    winner_actual = {"A": "B", "B": "A", "Tie": "Tie"}[winner_display] if swapped else winner_display
    st.session_state.responses[resp_key] = {
        "task_id": task_id,
        "stratum": stratum,
        "display_order": display_order + 1,
        "ab_swapped": swapped,
        "winner_display": winner_display,
        "winner_actual": winner_actual,
        "scores_display_a": scores_a,
        "scores_display_b": scores_b,
        "notes": notes,
    }


def _submit_evaluation():
    db = init_firebase()
    submission = {
        "annotator_id": st.session_state.annotator_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "demographics": st.session_state.get("demographics", {}),
        "total_comparisons": len(st.session_state.responses),
        "responses": list(st.session_state.responses.values()),
    }
    try:
        db.collection("human_evaluations").document(st.session_state.annotator_id).set(submission)
        st.session_state.page = "submitted"
        st.rerun()
    except Exception as e:
        st.error(f"Submission failed: {e}")
        st.info("Please contact the researcher if this error persists.")


# Page: Submitted
def page_submitted():
    st.title("Evaluation Submitted — Thank You!")
    st.success("Your 30 evaluations have been recorded.")
    st.balloons()
    st.markdown("---")
    st.markdown("""
**Optional next step:** You can now review the LLM judge's reasoning for each case and indicate whether you agree.

This helps us understand where the automated judge aligns with human expert judgment — and where it diverges.
Your evaluations above were collected **before** showing you the LLM reasoning to avoid anchoring bias.
""")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Review LLM Reasoning (optional, 20-30 min)", type="secondary"):
            st.session_state.reasoning_case_idx = 0
            st.session_state.reasoning_agreements = {}
            st.session_state.page = "reasoning_review"
            st.rerun()
    with col2:
        if st.button("Done — No reasoning review", type="secondary"):
            st.session_state.page = "done"
            st.rerun()


# Page: Reasoning review (optional)
def page_reasoning_review():
    df = load_data(SAMPLE_CSV)
    case_order = st.session_state.case_order
    total = len(df)
    idx = st.session_state.reasoning_case_idx
    row = df.iloc[case_order[idx]]

    task_id = int(row["task_id"])
    resp_key = f"{task_id}_{case_order[idx]}"
    human_resp = st.session_state.responses.get(resp_key, {})
    reasoning = str(row.get("reasoning_pass_full", "No reasoning available."))
    focal_code = str(row["focal_code"])
    docstring = str(row.get("docstring", "")).strip()
    swapped = is_ab_swapped(st.session_state.annotator_id, task_id)
    display_a = str(row["code_b"]) if swapped else str(row["code_a"])
    display_b = str(row["code_a"]) if swapped else str(row["code_b"])

    with st.sidebar:
        agreed = len(st.session_state.reasoning_agreements)
        st.progress(agreed / total, text=f"Reasoning review: {agreed}/{total}")

    st.title(f"LLM Reasoning Review — Case {idx + 1} / {total}")
    st.caption("The code is shown again for reference. The LLM judge's reasoning was hidden during your evaluation to prevent anchoring.")

    # --- Focal code ---
    with st.expander("Focal Method (code under test)", expanded=False):
        if docstring and docstring not in ("No docstring.", "nan"):
            st.caption(f"Docstring: {docstring}")
        st.code(focal_code, language="python")

    # --- Test suites side by side ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Test Suite A")
        st.code(display_a, language="python")
    with col2:
        st.subheader("Test Suite B")
        st.code(display_b, language="python")

    st.markdown("---")

    # --- Human scores recap ---
    # Use winner_display (the label the human saw on screen) so it matches the
    # displayed A/B code order, not the canonical model_a/model_b order.
    winner_display_recap = human_resp.get("winner_display", "?")
    scores_a = human_resp.get("scores_display_a", {})
    scores_b = human_resp.get("scores_display_b", {})
    user_notes = human_resp.get("notes", "").strip()

    st.markdown("**Your earlier judgment:**")
    recap_col1, recap_col2, recap_col3 = st.columns([2, 2, 1])
    with recap_col1:
        st.caption("Test Suite A — your scores")
        st.markdown("  \n".join(f"- {CRITERIA_LABELS[c]}: **{scores_a.get(c, '?')}**" for c in CRITERIA))
    with recap_col2:
        st.caption("Test Suite B — your scores")
        st.markdown("  \n".join(f"- {CRITERIA_LABELS[c]}: **{scores_b.get(c, '?')}**" for c in CRITERIA))
    with recap_col3:
        st.caption("Overall winner")
        st.markdown(f"## {winner_display_recap}")

    if user_notes:
        st.caption("Your notes from the evaluation:")
        st.info(user_notes)

    # --- LLM judge scores & decision ---
    # Total scores come from the CSV; per-criterion averages (across both passes)
    # come from the JSONL, joined by (task_id, model_a, model_b).
    # All scores are re-mapped to display A/B order using the same swap flag.
    llm_score_csv_a = float(row.get("model_a_total_score", 0))
    llm_score_csv_b = float(row.get("model_b_total_score", 0))
    llm_score_display_a = llm_score_csv_b if swapped else llm_score_csv_a
    llm_score_display_b = llm_score_csv_a if swapped else llm_score_csv_b

    TIE_THRESHOLD = 2.0
    llm_csv_winner = (
        "A" if llm_score_csv_a - llm_score_csv_b > TIE_THRESHOLD else
        "B" if llm_score_csv_b - llm_score_csv_a > TIE_THRESHOLD else
        "Tie"
    )
    llm_display_winner = (
        {"A": "B", "B": "A", "Tie": "Tie"}[llm_csv_winner] if swapped else llm_csv_winner
    )

    # Per-criterion scores from JSONL — shown as pass1 → pass2 (integers only,
    # no averaging) so they stay on the same 1–5 scale as the human scores.
    judgements = load_judgements(JUDGEMENTS_JSONL)
    jkey = (str(task_id), str(row["model_a"]), str(row["model_b"]))
    jrec = judgements.get(jkey, {})
    # All four arrays are in CSV model_a/model_b order; remap to display order.
    llm_p1_disp_a = jrec.get("pass1_b" if swapped else "pass1_a", [None] * 4)
    llm_p2_disp_a = jrec.get("pass2_b" if swapped else "pass2_a", [None] * 4)
    llm_p1_disp_b = jrec.get("pass1_a" if swapped else "pass1_b", [None] * 4)
    llm_p2_disp_b = jrec.get("pass2_a" if swapped else "pass2_b", [None] * 4)

    def fmt_passes(p1, p2):
        v1 = str(int(p1)) if p1 is not None else "?"
        v2 = str(int(p2)) if p2 is not None else "?"
        flag = " ⚠" if v1 != v2 else ""
        return f"**{v1} → {v2}**{flag}"

    st.markdown("**LLM Judge's scores & decision** *(pass 1 → pass 2 on 1–5 scale; ⚠ = inconsistent between passes):*")
    llm_col1, llm_col2, llm_col3 = st.columns([2, 2, 1])
    with llm_col1:
        st.caption("Test Suite A — LLM scores")
        st.markdown("  \n".join(
            f"- {CRITERIA_LABELS[c]}: {fmt_passes(llm_p1_disp_a[i], llm_p2_disp_a[i])}"
            for i, c in enumerate(CRITERIA)
        ))
        st.caption(f"Total: {llm_score_display_a:.0f} / 40")
    with llm_col2:
        st.caption("Test Suite B — LLM scores")
        st.markdown("  \n".join(
            f"- {CRITERIA_LABELS[c]}: {fmt_passes(llm_p1_disp_b[i], llm_p2_disp_b[i])}"
            for i, c in enumerate(CRITERIA)
        ))
        st.caption(f"Total: {llm_score_display_b:.0f} / 40")
    with llm_col3:
        st.caption("LLM winner")
        st.markdown(f"## {llm_display_winner}")

    st.markdown("---")
    st.markdown("### LLM Judge's Reasoning")

    # The LLM always reasons about "Test A" = model_a and "Test B" = model_b
    # (the canonical order stored in the CSV/JSONL).  When the display is swapped
    # we relabel those references so the reasoning matches what is shown above.
    if swapped:
        st.warning(
            "**Label notice:** The LLM evaluated these tests in the opposite order "
            "to what you saw above. Its 'Test A' / 'Test B' labels have been "
            "swapped below to match the display (A = left column, B = right column)."
        )
        reasoning_display = (
            reasoning
            .replace("Test A", "\x00A\x00")
            .replace("Test B", "\x00B\x00")
            .replace("\x00A\x00", "Test B")
            .replace("\x00B\x00", "Test A")
        )
    else:
        reasoning_display = reasoning

    st.markdown(reasoning_display)

    st.markdown("---")
    agree_options = ["Yes — I agree with the reasoning", "Partially — some points are correct", "No — I disagree with the reasoning"]
    agreement = st.radio(
        "Do you agree with the LLM judge's reasoning above?",
        agree_options,
        index=None,
        key=f"agree_{resp_key}",
    )

    disagree_notes = ""
    if agreement and "Partially" in agreement or agreement and "No" in agreement:
        disagree_notes = st.text_area(
            "What did the LLM get wrong or miss?",
            height=80,
            key=f"disagree_{resp_key}",
            help="Do not include personal information (names, contact details, employer) in this field.",
        )

    st.markdown("---")
    col_prev, col_next = st.columns([1, 3])
    with col_prev:
        if idx > 0 and st.button("← Previous"):
            st.session_state.reasoning_case_idx -= 1
            st.rerun()
    with col_next:
        is_last = idx == total - 1
        btn_label = "Submit Reasoning →" if is_last else "Next →"
        if st.button(btn_label, type="primary", disabled=(agreement is None)):
            agreement_short = "Yes" if "Yes" in agreement else ("Partially" if "Partially" in agreement else "No")
            st.session_state.reasoning_agreements[resp_key] = {
                "task_id": task_id,
                "agreement": agreement_short,
                "disagreement_notes": disagree_notes,
            }
            _push_reasoning_progress()   # incremental save after every case
            if is_last:
                _submit_reasoning()
            else:
                st.session_state.reasoning_case_idx += 1
                st.rerun()


def _push_reasoning_progress():
    """Incrementally write current reasoning agreements to Firestore after each case.

    Uses merge=True so each case's answer is upserted without losing previously
    saved answers. This prevents data loss if the session crashes mid-review and
    lets us catch Firestore permission errors early.
    """
    db = init_firebase()
    try:
        db.collection("reasoning_agreements").document(st.session_state.annotator_id).set(
            {
                "annotator_id": st.session_state.annotator_id,
                "last_updated": datetime.datetime.now(datetime.timezone.utc),
                "agreements": list(st.session_state.reasoning_agreements.values()),
            },
            merge=True,
        )
    except Exception as e:
        st.warning(f"Auto-save failed (your answer is still stored locally): {e}")


def _submit_reasoning():
    db = init_firebase()
    try:
        db.collection("reasoning_agreements").document(st.session_state.annotator_id).set({
            "annotator_id": st.session_state.annotator_id,
            "completed_timestamp": datetime.datetime.now(datetime.timezone.utc),
            "agreements": list(st.session_state.reasoning_agreements.values()),
        })
        st.session_state.page = "done"
        st.rerun()
    except Exception as e:
        st.error(f"Submission failed: {e}")


# Page: All done
def page_done():
    st.title("All Done — Thank You!")
    st.success("Your contributions are greatly appreciated and will directly support this research.")
    st.markdown("""
---
**What happens next:**
- Your evaluations will be compared against the automated LLM judge's decisions using Cohen's Kappa.
- Per-criterion scores will be used to compute Pearson correlation between human and LLM scoring per dimension.
- Results will be reported in the thesis with full anonymity.
""")
    st.caption(
        f"Your submission reference: `{st.session_state.annotator_id}` — "
        "quote this if you need to contact the researcher about your submission."
    )
    st.markdown("You can safely close this browser tab.")


def main():
    st.set_page_config(
        layout="wide",
        page_title="Unit Test Evaluation Study",
        page_icon="🧪",
    )

    defaults = {
        "page": "welcome",
        "annotator_id": "",
        "demographics": {},
        "case_order": [],
        "current_case_idx": 0,
        "responses": {},
        "reasoning_case_idx": 0,
        "reasoning_agreements": {},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    page = st.session_state.page
    routes = {
        "welcome":         page_welcome,
        "demographics":    page_demographics,
        "rubric":          page_rubric,
        "evaluation":      page_evaluation,
        "submitted":       page_submitted,
        "reasoning_review": page_reasoning_review,
        "done":            page_done,
    }
    render = routes.get(page)
    if render:
        render()
    else:
        st.error(f"Unknown page state: '{page}'. Please refresh and re-enter your annotator ID.")


if __name__ == "__main__":
    main()
