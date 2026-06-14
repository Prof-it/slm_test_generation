# slm-python-unit-test-benchmark

Benchmarking Small Language Models (SLMs) for automated Python unit test generation. Evaluates models on the TestEval benchmark (LeetCode-based) and a custom real-world dataset of production Python functions.

---

## Scientific Justification: Metrics, Model Scale, and SME Relevance

### Why These Metrics Are Scientifically Valid and Comparable

This study reports three primary metrics. The table below summarises comparability with each anchor paper before the narrative explanation.

| Metric | Our definition | Wang et al. 2025a | Huang et al. 2025b | Directly comparable? |
|---|---|---|---|---|
| Pass@1 | Test compiles + runs + **all assertions pass** (strict) | "Execution Correctness": compiles + runs, assertions **not** required | Test compiles + runs + **all assertions pass** (strict) | **Huang only** — Wang uses a looser criterion |
| Code Coverage | `pytest-cov` on **assertion-passing tests only** (gated) | `cov@k` on **execution-correct tests** (includes assertion failures) | `LCov@k` on **assertion-passing tests only** (gated) | **Huang only** — Wang's coverage is more lenient |
| Mutation Score | `cosmic-ray`, gated on strict-passing tests, Cochran n=67 | Not reported | `Mut@k`, `cosmic-ray`, gated on strict-passing tests | **Huang only** |

**Pass@1 — strict definition (Chen et al., 2021 + Huang et al., 2025b).** A generated test is counted as passing only when it (1) parses without a `SyntaxError`, (2) executes without a runtime exception (`ImportError`, `RuntimeError`, etc.), and (3) all assertions pass on the original, unmodified function. This is the *strict* variant of Pass@1 defined by Chen et al. (2021, "Evaluating Large Language Models Trained on Code") and adopted identically by Huang et al. (2025b, "Benchmarking LLMs for unit test generation from real-world functions"). Our results are directly comparable to Huang et al. (2025b) Table 2. Wang et al. (2025a, "TestEval") instead reports *Execution Correctness* (EC) — a test is considered passing if it runs to completion without an unhandled exception, even if every `assert` statement fails. Wang et al.'s metric is therefore more lenient than strict Pass@1. Their baseline values are included in our tables but marked `[a]` to make this incompatibility explicit; they function as an aspirational upper bound, not a same-definition comparison.

For the 10-run stochastic condition (T=0.2), Pass@1 is computed using the unbiased Chen et al. (2021) estimator: pass@1 = mean(c_i / n) over all tasks, where c_i is the count of strictly passing generations and n = 10. A separate Pass@10 column reports the probability of at least one passing generation in 10 attempts using the general formula pass@k = E[1 − C(n−c, k) / C(n, k)].

**Gated Code Coverage (Huang et al., 2025b).** Line coverage is measured by `pytest-cov` and attributed only to tests that satisfy the strict Pass@1 criterion above. A test that runs but fails an assertion is excluded from coverage computation, because such a test may accidentally traverse solution code rather than purposefully exercising it. This *Gated Code Coverage* matches Huang et al. (2025b)'s `LCov@k` definition exactly and is directly comparable to their Table 3. Wang et al. (2025a)'s `cov@k` applies the looser EC gating (execution-correct but potentially assertion-failing), which inflates coverage numbers relative to our metric. The two are not equivalent: our gated coverage is a strictly more conservative measurement. Wang et al.'s coverage baselines are included in our tables but carry the same `[a]` incompatibility marker.

**Mutation Score (Jia & Harman, 2011; Guerino et al., 2024).** We use `cosmic-ray` to introduce syntactic mutations and compute the percentage of mutants killed. A mutant is killed when the generated test suite fails on the mutated code but passes on the original — matching Huang et al. (2025b)'s `Mut@k` kill criterion exactly. Mutation testing is gated on strict-passing tests with non-zero coverage. Wang et al. (2025a) do not report mutation scores on TestEval. To make the sample statistically defensible, the mutation subset is drawn using Cochran's finite-population formula (z = 1.96, p = 0.5, e = 0.10, N = 210), yielding n = 67 tasks at 95% confidence with a ±10% margin of error. Known limitations: equivalent mutants inflate the denominator; `cosmic-ray`'s default operator set does not cover all fault classes (Jia & Harman, 2011).

---

### Why Small Language Models for SMEs — and Why the DGX Spark Is Not a Practical Alternative

A common objection to SLM research is: "NVIDIA now sells the DGX Spark, a desktop AI workstation capable of running a 70B model locally for roughly $4 000 — so why not just run the full-size model?" The objection sounds compelling but does not hold under scrutiny.

**The DGX Spark is not a mass-market consumer product.** The DGX Spark is built around the Grace Blackwell GB10 superchip, with 128 GB of unified LPDDR5x memory, a 20-core Arm CPU, a Blackwell-class GPU, and a 240 W external power supply delivering approximately 1 petaFLOP FP4 theoretical performance. It runs models up to roughly 70B parameters under quantization and up to approximately 200B in constrained inference settings. However, it is sold exclusively through NVIDIA and select OEM partners — not through general retail channels. Real-world availability varies significantly by region: some markets face limited stock, delayed shipments, or enterprise-only allocations. US headline pricing sits at approximately $3 999–$4 699 depending on configuration, but landed cost in high-tax regions rises substantially due to VAT, import duties, currency depreciation, and reseller margins. In markets such as Turkey, the effective price can reach €6 000–€8 000 or higher. Export controls and sanctions primarily target high-end datacenter accelerators (A100/H100-class), not DGX Spark directly, but they indirectly constrain supply chains, OEM allocations, and regional distribution priorities — meaning access is uneven globally and weighted towards enterprise customers in approved markets.

**The real-world alternative is consumer GPU hardware, not DGX Spark.** For the overwhelming majority of SMEs, the practical comparison is not "DGX Spark vs. 4B SLM" but "consumer RTX 30/40-series GPU (already present in many existing developer workstations) vs. cloud LLM API." RTX 30/40-series cards are widely available through standard retail, are already deployed in large numbers, and cost €300–€1 200 for a capable tier. The tradeoff is therefore not simply "more compute vs. less compute" — it is globally constrained, high-memory integrated AI hardware of uncertain availability, versus ubiquitous consumer GPU hardware with immediate retail accessibility that an SME team very likely already owns.

**Data privacy eliminates cloud APIs for many SMEs regardless of cost.** GDPR, client NDAs, and sector-specific regulations (financial services, healthcare, legal) frequently prohibit transmitting source code to external APIs. A locally hosted SLM on consumer hardware processes code entirely on-premise with no data leaving the network. This constraint alone removes cloud-based LLM APIs from consideration for a substantial fraction of European SMEs — irrespective of pricing.

**Per-call cost scales against cloud LLMs at CI volumes.** At approximately $0.002 per task for a frontier cloud LLM API, a CI pipeline generating tests for 10 000 tasks per day accumulates roughly $7 300 per year before retries or prompt iteration. A locally hosted 4B SLM on existing consumer hardware has zero marginal cost per call after the initial hardware purchase.

---

### Why Results on 4B Models Generalize — and Why Smaller Is the Right Starting Point

Evaluating on sub-7B models is not a limitation — it is a deliberate methodological choice with two independent justifications.

**Scaling laws predict direction, not just magnitude.** A long line of work (Kaplan et al., 2020; Hoffmann et al., 2022; Wei et al., 2022) establishes that larger models are at least as capable as smaller ones at the same task, given equal training compute. If a 4B model fails at a structured code-generation task (e.g., generating syntactically valid pytest code that targets a specific branch), a 70B model from the same family will not fail for the same structural reason — it will either solve it or face a qualitatively different failure mode. Conversely, if a 4B model demonstrates consistent success (60%+ Pass@1 on TestEval), this provides a lower bound on what the same architecture family achieves at larger scale. Our findings are therefore conservative: real-world deployments of 8B+ models from the same families can be expected to meet or exceed the pass rates we report.

**Smaller models are the correct unit of comparison for SME deployment.** The research question is not "what is the absolute ceiling of LLM test generation?" — that is answered by GPT-4o (99.6% Pass@1 on TestEval, Wang et al. 2025a). The question is: "at what model size and cost point does automated test generation become viable for an SME that cannot afford cloud LLM APIs?" Evaluating 4B models directly answers this question. If a 4B model achieves 60% Pass@1 at negligible cost, the ROI argument for SME adoption is clear without needing to scale to 70B.

**Fewer tokens per call means more calls per budget.** A 4B model generates tests in 200–800 tokens. A 70B model at the same task uses 500–2 000 tokens per call and often appends chain-of-thought reasoning that inflates token counts further. For a team running test generation at scale, the cost-per-useful-test ratio strongly favors smaller models. Budget that would run 1 000 GPT-4o calls can run 50 000–100 000 calls on a locally hosted 4B SLM, enabling test generation for entire codebases rather than hand-selected critical paths.

---

## Repository Structure

```
slm-python-unit-test-benchmark/
├── step2_data_preperation/      # Dataset preparation and validation
├── step3_modelling/             # Inference orchestration and LLM-as-judge
├── step4_evaluation/            # Test execution, coverage, mutation testing, reporting
├── TestEval/                    # Cloned benchmark + predictions + prompts
│   ├── data/                    # JSONL datasets (testeval, realworld)
│   ├── predictions_*/           # Model output JSONL files per experiment
│   └── prompt/                  # System prompt templates
├── Dockerfile                   # GPU inference environment (vLLM)
├── Dockerfile.pynguin           # Pynguin baseline environment (CPU)
└── requirements.txt
```

---

## Setup and Execution

### 1. Environment Validation

```bash
python step2_data_preperation/data_preperation.py
```

Clones the TestEval repository if absent, validates dataset integrity, installs dependencies, creates output directories, and checks that the `HUGGINGFACE_TOKEN` environment variable is set.

### 2. Real-World Dataset Creation (optional)

```bash
python step2_data_preperation/create_realworld_dataset.py --target-count 50 --max-per-file 8
```

Extracts and transforms public functions from source files in `TestEval/data/real_world/`. Add your own Python source files to that directory to extend the dataset.

### 3. Inference — SLM (GPU, Docker)

```bash
docker build -t slm-py-unit-test:v1 .
docker run user_name/slm-py-unit-test:v1
```

Required environment variables: `HF_TOKEN`, `PUBLIC_KEY`, `JUPYTER_PASSWORD`, `PYTHONUNBUFFERED=1`.

When the container logs show `DONE`, download the prediction files from `/workspace/predictions/` (accessible via the Jupyter file server at port 8888) and place them in `TestEval/predictions_<experiment_name>/`.

### 4. Inference — Pynguin baseline (CPU, Docker)

```bash
docker build -t pynguin-baseline -f Dockerfile.pynguin .
docker run -v "c:\Repos\slm-python-unit-test-benchmark\TestEval\predictions_testeval_pynguin:/app/TestEval/predictions_testeval_pynguin" pynguin-baseline
```

### 5. Mutation Subset Generation

```bash
python step4_evaluation/create_mutation_subset.py
# For real-world:
python step4_evaluation/create_mutation_subset.py --data TestEval/data/realworld-py.jsonl --output step4_evaluation/mutation_subset_ids_realworld.json
```

### 6. Evaluation

```bash
python step4_evaluation/evaluate_results.py \
  --input-dir TestEval/predictions_initial \
  --output-dir evaluation_results_initial \
  --mutation-subset step4_evaluation/mutation_subset_ids.json
```

### 7. Summary Reports and Plots

```bash
# TestEval experiments
python step4_evaluation/create_summary_report.py \
  --input evaluation_results_initial \
  --output step4_evaluation/initial_plots \
  --dataset testeval

# Real-world experiment
python step4_evaluation/create_summary_report.py \
  --input evaluation_results_realworld \
  --output step4_evaluation/realworld_plots \
  --dataset realworld
```

---

## Pipeline Scripts Reference

This section documents each script's algorithm, inputs, outputs, and key libraries.

### `step2_data_preperation/data_preperation.py`

**Purpose:** Validates and prepares the local environment before any experiment is run.

**Algorithm:**
1. Checks that the `TestEval` directory exists; if not, clones it from GitHub via `subprocess`.
2. Verifies the benchmark data file (`testeval-py.jsonl`) is present and non-empty.
3. Runs `pip install -r requirements.txt` to lock dependencies.
4. Creates the `TestEval/predictions/` output directory.
5. Reads `.env` via `python-dotenv` and asserts required API keys are set.

**Libraries:** `os`, `subprocess`, `sys`, `logging`, `python-dotenv`

---

### `step2_data_preperation/create_realworld_dataset.py`

**Purpose:** Constructs the real-world benchmark dataset from raw Python source files.

**Algorithm:**
1. Walks all `.py` files in `TestEval/data/real_world/`.
2. Parses each file with Python's `ast` module to extract module-level public functions (excludes class methods, underscore-prefixed names, functions shorter than 3 lines, decorators, and `try/except` import blocks).
3. Separates `from __future__` imports from regular imports to maintain valid ordering.
4. Computes difficulty using two signals:
   - **Radon** `cc_visit`: cyclomatic complexity of the function.
   - **AST node visitor** (`DifficultyAnalyzer`): maximum control-flow nesting depth and number of distinct assigned variables.
   - Combined score maps to Easy (1), Medium (2), or Hard (3).
5. Identifies target lines for coverage-oriented evaluation (`if`, `return`, `raise`, `for`, `while`, `with` statements).
6. Wraps each function in a `class Solution:` body, prepends imports, and deterministically assigns a `task_num` using `hashlib.md5` on the filename and function name.
7. Balances the final dataset: applies a per-file cap (`--max-per-file`), then stratified sampling (Easy 40%, Medium 30%, Hard 30%) to reach `--target-count`.
8. Writes two JSONL files: `realworld-py.jsonl` (balanced subset) and `realworld-py-all.jsonl` (full set).

**Libraries:** `ast`, `radon.complexity`, `hashlib`, `argparse`, `json`, `pathlib`, `collections`, `textwrap`

---

### `step3_modelling/run_experiments.py`

**Purpose:** Orchestrates SLM inference for the initial benchmark and temperature-sweep experiments.

**Algorithm:**
1. Iterates over a fixed list of model IDs and temperature values.
2. For each (model, temperature, pass index) combination, invokes the TestEval inference scripts (`generate_targetcov_hf.py` for one-step, `gen_linecov_cot_hf.py` for two-step CoT) via `subprocess.run`.
3. Each script sends prompts to a locally served vLLM endpoint. The one-step approach constructs a single prompt per target line; the two-step approach first generates a minimal input condition, then generates the test using that condition.
4. Results are written incrementally to JSONL files under `/workspace/predictions/`.
5. After each model completes all passes, HuggingFace and vLLM caches are purged from disk to avoid out-of-memory errors on the next model load.

**Libraries:** `subprocess`, `os`, `shutil`, `logging`, `argparse`

**vLLM inference internals:** Prompts are batched and submitted to a locally running vLLM server. Token counts, wall-clock time, and tokens-per-second are recorded per task. Tasks that exceed a timeout threshold are flagged as `TIMEOUT`.

---

### `step3_modelling/run_real_world_experiments_inference.py`

**Purpose:** Same orchestration logic as `run_experiments.py` but targets the real-world dataset and applies real-world-specific system prompts (which include mocking guidance).

**Algorithm:** Identical to `run_experiments.py` with the following differences:
- Uses `SYSTEM_PROMPT_ONESTEP = system_realworld.txt` and `SYSTEM_PROMPT_TWOSTEP = system_exec_realworld.txt`.
- Operates on `realworld-py.jsonl` and `realworld-py-all.jsonl`.
- Default temperature is 0.0 for the final real-world run.

**Libraries:** `subprocess`, `os`, `shutil`, `logging`, `argparse`, `pathlib`

---

### `step3_modelling/run_real_world_experiments_pynguin.py`

**Purpose:** Runs the Pynguin DynaMOSA genetic-algorithm baseline against the real-world dataset.

**Algorithm:**
1. Reads function definitions from the dataset JSONL.
2. Writes each function to a temporary Python module file.
3. Invokes Pynguin via `subprocess` with the DynaMOSA algorithm and a per-function timeout.
4. Collects the generated test files, records pass/fail and `NO_CODE` outcomes (when Pynguin fails to import the module, typically due to missing dependencies), and writes results in the same JSONL format as SLM outputs.

**Notes:** Pynguin requires all function dependencies to be importable. Functions from modules with heavy dependencies (e.g., `torch`, `vllm`, `transformers`) produce `NO_CODE` in the lightweight Docker environment. Tokens-per-second is approximated since Pynguin is not token-based.

**Libraries:** `subprocess`, `pathlib`, `json`, `logging`

---

### `step3_modelling/llm_as_judge.py`

**Purpose:** Evaluates the qualitative superiority of one SLM's tests over another's using a Claude model as an automated judge.

**Algorithm:**
1. For each pair of models being compared, collects tasks where both models produced a passing test. This ensures quality evaluation is decoupled from pass rate.
2. For each such task, constructs two evaluation passes with the test positions swapped (A→B in pass 1, B→A in pass 2) to detect and eliminate position bias.
3. Submits both passes in parallel to the Claude API (via `anthropic` SDK) using a fixed system prompt that defines the judge as a senior QA engineer. The judge uses chain-of-thought reasoning before assigning scores.
4. Scoring decomposes quality into four criteria: Robustness, Assertion Strength, Readability, and Conciseness — each on a 1–5 Likert scale. A null-test veto rule sets the total score to 1 if assertion strength is 1, regardless of other criteria.
5. Aggregates pass-1 and pass-2 scores. If both agree, the judgment is clean. If they disagree and score variance exceeds a threshold, the judgment is flagged as stochastic noise. Position bias is detected when the same-position test wins in both passes.
6. Computes win rates and average scores per model pair. Samples comparisons across three strata (Tie, Marginal win, Clear win) for human validation and Cohen's Kappa calculation.
7. Uses MD5-based caching to persist API results across sessions, avoiding redundant calls.

**Libraries:** `anthropic`, `concurrent.futures` (ThreadPoolExecutor), `hashlib`, `json`, `argparse`, `glob`, `logging`

---

### `step4_evaluation/create_mutation_subset.py`

**Purpose:** Selects a statistically representative 20% subset of tasks for mutation testing.

**Algorithm:**
1. Loads the JSONL dataset into a Pandas DataFrame.
2. Groups tasks by difficulty level (1=Easy, 2=Medium, 3=Hard).
3. Applies stratified random sampling: draws 20% independently from each difficulty tier using `random.seed(42)` for reproducibility.
4. Writes the selected `task_num` identifiers to a JSON file consumed by `evaluate_results.py`.

**Libraries:** `pandas`, `json`, `random`, `argparse`, `pathlib`

---

### `step4_evaluation/evaluate_results.py`

**Purpose:** The core evaluation harness. Executes generated tests, measures coverage, and runs mutation testing.

**Algorithm:**
1. **Input:** Scans the predictions directory for JSONL files. Supports resume by skipping tasks already present in the output directory.
2. **Sanitization:** For each generated test string:
   - Strips Markdown fences (` ```python ... ``` `).
   - Removes `<think>...</think>` reasoning traces produced by thinking models.
   - Strips leading/trailing whitespace.
   - Standardizes the generated test function name to match the expected naming convention.
   - Extracts and removes `from __future__` lines from model-generated test code to prevent import-order `SyntaxError`.
3. **Execution harness:** Writes two temporary files to a `tempfile.mkdtemp()` directory:
   - `under_test.py`: the solution code, with `from __future__` lines placed first, followed by `fix_relative_imports`-processed imports and the function body.
   - `test_generated.py`: a harness template that imports `under_test` and appends the sanitized test code.
4. Runs `pytest` on the harness via `subprocess.run` with a timeout. Captures stdout/stderr and parses the exit code to classify the outcome as: `PASS`, `SYNTAX_ERROR`, `RUNTIME_ERROR`, `ASSERTION_ERROR`, `TIMEOUT`, or `NO_CODE`.
5. **Coverage measurement:** If the test passes, re-runs `pytest` with `coverage run` and calls `coverage json` to extract the line coverage percentage for `under_test.py`.
6. **Mutation testing (conditional):** If the task ID is in the pre-computed mutation subset, the test passes, and coverage is non-zero, launches a `cosmic-ray` session. Runs `cosmic-ray init`, then `cosmic-ray exec` with a per-session timeout (default 600 seconds). Parses the session database to compute the mutation score (killed mutants / total mutants).
7. **Parallelization:** All tasks are dispatched via `concurrent.futures.ProcessPoolExecutor`. Each worker process handles one task independently.
8. Results (outcome, coverage %, mutation score, token counts, timing) are written atomically to per-task JSONL files in the output directory.

**Libraries:** `pytest` (via subprocess), `coverage`, `cosmic-ray` (via subprocess), `concurrent.futures`, `subprocess`, `tempfile`, `ast`, `re`, `pathlib`, `json`, `argparse`, `logging`

**Key design decisions:**
- Relative imports in solution code are wrapped in `try/except` with `MagicMock` fallbacks so modules load without their full dependency tree.
- Mutation testing is gated on non-zero coverage to avoid false positives.
- The harness uses isolated temp directories per task to prevent test pollution across parallel workers.

---

### `step4_evaluation/create_summary_report.py`

**Purpose:** Aggregates per-task evaluation JSONL files into statistical tables and visualizations.

**Algorithm:**
1. Loads all JSONL files from the evaluation output directory and parses filename metadata (model name, temperature, step count, pass index) using regex.
2. Computes per-configuration statistics: pass rate, mean coverage, mean mutation score, tokens-per-second, and standard deviation across passes.
3. Calculates 95% confidence intervals using `scipy.stats.t.interval`.
4. For the `testeval` dataset, computes pairwise effect sizes (Cohen's h for proportions) between model configurations.
5. Generates the following plots using `matplotlib` and `seaborn`:
   - Pass rate vs. temperature (line chart with error bands).
   - Pass rate stability heatmap (model × temperature).
   - Quality quadrant scatter (pass rate vs. mutation score).
   - Failure taxonomy bar chart (syntax / runtime / assertion / timeout / no-code).
   - Throughput (TPS) comparison bar chart.
6. Writes a formatted results table to a `.txt` file using `tabulate`.

**Libraries:** `pandas`, `numpy`, `scipy`, `matplotlib`, `seaborn`, `tabulate`, `json`, `glob`, `argparse`, `pathlib`

---

### Analysis and Validation Scripts (`step4_evaluation/`)

| Script | Purpose |
|--------|---------|
| `create_failure_heatmaps.py` | Generates failure-type heatmaps by model and task. |
| `create_mutation_subset.py` | Stratified sampling for mutation testing (documented above). |
| `analyze_assertion_quality.py` | Parses generated tests with `ast` to count and classify assertion statements. |
| `analyze_test_smells.py` | Detects common test smell patterns (magic numbers, missing assertions, god tests) via AST and regex. |
| `predict_failures_from_complexity.py` | Fits logistic regression (scikit-learn) to predict task failure from Radon complexity features. |
| `chi_square_failure_analysis.py` | Tests independence between failure type and difficulty/model using `scipy.stats.chi2_contingency`. |
| `validate_difficulty_metric.py` | Validates the Radon-based difficulty labeling against observed pass rates. |
| `validate_llm_judge.py` | Computes Cohen's Kappa between LLM judge verdicts and human annotations. |
| `analyze_judge_results.py` | Aggregates `llm_as_judge.py` output into win-rate tables. |
| `export_failures_for_review.py` | Exports failing test cases to Excel/CSV for manual inspection. |
| `audit_evaluation_results.py` | Cross-checks evaluation output files for missing tasks or inconsistent records. |
| `analyze_manual_error_results.py` | Processes manually annotated error classification spreadsheets into summary counts. |
| `create_manual_error_analysis_report.py` | Generates a formatted error taxonomy report from manual annotations. |

---

## Models

### Final Evaluation Set (5 models)

| Model | Size | Quantization |
|-------|------|-------------|
| `google/gemma-3-4b-it` | 4B | None |
| `cyankiwi/Ministral-3-8B-Instruct-2512-AWQ-8bit` | 8B | AWQ INT8 |
| `mistralai/Ministral-3-3B-Reasoning-2512` | 3B | None |
| `ibm-granite/granite-4.0-micro` | ~4B | None |
| `Qwen/Qwen3-4B-Instruct-2507` | 4B | None |

### Eliminated Models

The following models were excluded after early testing due to low accuracy, deprecation, or replacement by a newer version:

- `Qwen/Qwen2.5-Coder-3B-Instruct`
- `Qwen/Qwen2.5-Coder-7B-Instruct-AWQ`
- `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B`
- `deepseek-ai/deepseek-coder-1.3b-instruct`
- `TheBloke/Mistral-7B-Instruct-v0.2-AWQ`
- `PyrTools/Ministral-8B-Instruct-2410-AWQ`
- `TheBloke/deepseek-coder-6.7B-instruct-AWQ`
- `jakiAJK/DeepSeek-R1-Distill-Qwen-7B_AWQ`
- `TechxGenus/gemma-7b-it-AWQ`
- `TechxGenus/starcoder2-3b-instruct`
- `WeiboAI/VibeThinker-1.5B`
- `ibm-granite/granite-3.3-8b-instruct`

---

## Reproducibility

All experiments run inside Docker containers to ensure identical environments across machines. Running the provided Docker commands reproduces results exactly.

Hardware used for inference: Single NVIDIA RTX 4090 (24 GB VRAM), 12 CPU cores, vLLM 0.12.0, Ubuntu 22.04.5 LTS. Docker image: `kastellan999/katir:v26`.

Mutation testing runs on CPU only. `cosmic-ray` does not expose a random seed flag, which limits full determinism in mutation score computation.

---

## Scope Limitations

This repository is validated for **line coverage analysis only**. All experiments, metrics, and dataset targets are designed around statement coverage.

Branch coverage, execution path analysis, and coverage probability modeling are not supported without code changes and independent validation.

The dataset includes extra metadata fields that are present but unused in current experiments; they can be safely ignored.

---

## Experiment Costs

| Phase | Duration | Cost |
|-------|----------|------|
| Early testing and pipeline fixing | — | ~$80 |
| Initial benchmark (11 models, 3 passes, 2 temps, 3 steps, 210 tasks) | ~6 days | ~$50 |
| Temperature sweep (5 models, 3 passes, 6 temps, 3 steps, 210 tasks) | ~6 days | ~$52 |
| Real-world inference (5 models, T=0.2, 50 tasks) | ~2 days | ~$15 |

Total inference time: approximately 90 hours for SLM runs, 16 hours for Pynguin (temperature sweep), 2 hours for Pynguin (real-world). Mutation testing ran for approximately 45 hours per evaluation pass on CPU.

---

## Notes

- Temperature is not fully deterministic at T=0 on vLLM: 0–2% variation on pass@1 is observed across runs on some models.
- Pynguin (DynaMOSA) treats source code as correct and writes assertions to lock in existing behavior. LLMs test for intended behavior. If real-world functions contain bugs, Pynguin may pass while LLMs fail — and vice versa. Results for both are reported separately.
- Pynguin's DynaMOSA generates `@pytest.mark.xfail(strict=True)` tests for negative cases. These contribute to coverage but do not improve mutation scores because expected failures still fail under mutation. Metrics are reported separately for tests with and without `xfail` markers.
- Models that generate assertion-free tests (e.g., `assert True`) can achieve high pass rates and coverage without meaningful fault detection. Mutation testing exists specifically to surface this failure mode.
- The 23.81% (±0.00) result for Ministral-3-3B-Reasoning at T=0.8 is valid: five of twenty-one tasks passed consistently across two runs, with token counts varying — confirming independent executions. Zero variance on a 21-task set is a statistical artifact, not a reproducibility failure.

---

## How Model Performance Differences Will Be Explained in the Paper

Most of the models in this benchmark are open-source but lack a published architectural paper or technical report describing their internal design in detail. Architecture-level explanation is therefore not available for these models in the same way it would be for GPT-4 or Gemini. This section documents the behavioral analysis methodology that will be used when writing the discussion section of the paper, following the precedent set by Wang et al. (2025a, "TestEval"), who similarly explained performance differences through observed output patterns rather than internal model weights.

### 1. Three-Tier Failure Funnel (Wang et al. 2025a Taxonomy)

Every generated test is classified at one of three failure tiers: Syntactic → Execution → Assertion. The proportion of models reaching each tier gives a per-model failure profile:

- **Syntactic failure rate**: Models that frequently emit malformed Python (missing colons, mismatched brackets, truncated outputs, or redundant commas in argument lists) will show a high share of tasks stuck at tier one. This correlates with a model's instruction-following fidelity for code format — not its reasoning capability.
- **Execution failure rate**: A model that passes syntactic checks but fails at runtime often has errors in import resolution, incorrect use of the `Solution` class wrapper, or fabricated method calls (hallucinated API usage). These failures distinguish models with shallow familiarity with Python idioms from models with stronger code understanding.
- **Assertion failure rate**: A model that generates syntactically and executably correct tests that still fail assertions understands the structure of a test but misreasoned about the expected return value or edge case behavior. This is the most informative failure mode because it is not a formatting error — the model attempted a semantic claim and was wrong.

Each model's funnel shape will be plotted and discussed individually in the paper.

### 2. Output Repetition and Diversity (Pass@10 vs Pass@1 Gap)

For the stochastic condition (T=0.2, 10 runs), the gap between Pass@10 and Pass@1 quantifies how much re-sampling helps a model. A small gap (Pass@10 ≈ Pass@1) means the model generates consistently — it either reliably gets a task right or reliably gets it wrong. A large gap (Pass@10 >> Pass@1) means the model has high variance: it sometimes succeeds but not repeatably, which is less useful for CI integration.

A secondary signal is whether a model generates repetitive outputs across 10 runs despite stochastic decoding — analogous to what Wang et al. (2025a) observed with Starcoder-2-Instruct, which "frequently repeats previously generated cases despite being instructed to generate different ones." If any of our models show near-zero diversity at T=0.2 (identical or near-identical tests across all 10 runs), this will be flagged as a behavioral finding and compared against its Pass@10/Pass@1 gap.

### 3. Reasoning Model vs Instruct Model Comparison (Ministral 3B Reasoning vs Ministral 8B Instruct)

The evaluation set includes two models from the same family but different training paradigms: `Ministral-3-3B-Reasoning-2512` (reasoning-optimized, 3B) and `Ministral-3-8B-Instruct-2512-AWQ-8bit` (instruction-tuned, 8B, quantized INT8). This pairing allows a controlled behavioral comparison:

- **Reasoning disconnect**: Wang et al. (2025a) found that GPT-4o, despite correctly identifying the mathematical constraints needed to cover a specific branch in its chain-of-thought, then failed to produce code that satisfied those constraints. A reasoning-optimized SLM may exhibit the same pattern at smaller scale: the `<think>` trace identifies the correct input condition but the final generated test fails the assertion. The paper will inspect reasoning model outputs on tasks where the test failed at the assertion level to check for this planning-execution disconnect.
- **Scale vs paradigm tradeoff**: If the 3B reasoning model outperforms the 8B instruct model on structured CoT tasks despite its parameter disadvantage, this suggests that reasoning-oriented training transfers usefully to test generation even at small scale. The converse — the 8B instruct outperforming the 3B reasoning model on assertion correctness — would suggest that broader instruction coverage at larger scale matters more than reasoning specialization for this task.
- **Quantization cost**: The 8B model is AWQ INT8 quantized, which introduces a small quality loss relative to the full-precision version. Since no full-precision 8B baseline is available for comparison, quantization impact will be discussed qualitatively (citing known INT8 degradation literature) rather than through direct measurement.

### 4. Code-Specialized vs General-Instruct Models (Granite 4.0 Micro vs Gemma 3 4B and Qwen3 4B)

IBM Granite 4.0 Micro is trained specifically for code tasks. Gemma-3-4B-it and Qwen3-4B-Instruct are general-purpose instruction models with code capability but without code-first pretraining at this scale. If Granite shows higher assertion correctness on structurally complex tasks (medium/hard cyclomatic complexity tier), this supports the hypothesis that code-specialization matters at sub-5B scales. If general-instruct models match or exceed Granite on simpler tasks but fall behind on harder ones, this would suggest a complexity-dependent advantage for code-specialized models — a nuanced finding relevant to SME model selection.

### 5. One-Step vs Two-Step CoT Planning Effect

For each model, the paper will report the pass rate delta between the one-step (direct test generation) and two-step (generate input condition first, then generate test) prompting strategies. Following Wang et al. (2025a), who found that GPT-4-series models improved by 10–15% on targeted tasks under additional reasoning guidance while smaller models did not benefit or regressed, the prediction is that reasoning-capable models will show a positive delta from two-step CoT while weaker instruction-following models may produce worse results (the intermediate reasoning step adds noise rather than precision). McNemar's test on paired pass/fail outcomes per task will determine statistical significance of the planning-step effect per model.

### 6. What We Cannot Infer Without Architectural Details

The following claims will be explicitly excluded from the paper's discussion because the architectural information required to support them is not publicly available:

- Attention mechanism type (e.g., GQA vs MHA) and its effect on long-context coherence in test generation.
- Training data composition and whether any model was trained on TestEval-adjacent LeetCode data, which would constitute data contamination rather than generalization.
- RLHF/DPO alignment recipe differences between instruct variants, which affect instruction-following compliance but not raw code generation capability.
- Tokenization differences between models that may cause consistent off-by-one errors in assertion values for numeric outputs.

The discussion will explicitly state this scope limitation and recommend future work that pairs behavioral benchmarking with model internals analysis (e.g., probing studies or logit attribution) to close the gap.
