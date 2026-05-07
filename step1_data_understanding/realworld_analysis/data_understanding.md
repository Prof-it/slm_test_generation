# `data_understanding.md`

In this capstone section of the Data Understanding phase of the CRISP-DM process, all final observations about the data sources are presented. This includes a deep dive into the **TestEval** benchmark and the introduction of a curated **RealWorld-Py** mini validation set. The section covers data sources, quantitative analysis of code complexity, and a qualitative analysis of the prompt-engineering strategies employed.

## 1. Information from the Source Publications

The project utilizes two distinct datasets to ensure the results are robust across both competitive programming puzzles and realistic software development scenarios.

### 1.1 Dataset A: The "TESTEVAL" Benchmark (Primary)
The following is a summary of the benchmark's creation and structure as described in the original paper, "TESTEVAL: Benchmarking Large Language Models for Test Case Generation."

#### 1.1.1 Core Purpose and Goal
*   **Objective:** To provide a standardized benchmark for evaluating and comparing the test case generation capabilities of Language Models (LMs), specifically for Python programs.
*   **Focus:** The benchmark is designed to assess an LM's ability to reason about complex program execution behaviors, logic, and paths, rather than just simple code synthesis.

#### 1.1.2 Data Source and Filtering
*   **Primary Source:** Publicly available Python solutions to programming problems from **LeetCode**, collected from the `walkccc/LeetCode` GitHub repository.
*   **Initial Pool:** 3,123 programs collected up to April 2024.
*   **Filtering Process:**
    1.  **Complexity-based Filtering:** Programs with a cyclomatic complexity of **≥ 10** were selected to eliminate trivial cases.
    2.  **Manual Curation:** The remaining programs were de-duplicated to remove identical solutions, resulting in **210 unique Python programs**.

#### 1.1.3 Composition
*   **Total Programs:** 210
*   **Difficulty:** 9 Easy, 100 Medium, 101 Hard.
*   **Characteristics:** High branching and control flow complexity (Avg Cyclomatic Complexity: 13.35). Code is preprocessed to be self-contained (comments removed, imports added).

---

### 1.2 Dataset B: "RealWorld-Py" (Validation)
To validate that model performance is not strictly tied to LeetCode-style algorithms, we generated a secondary dataset focused on realistic software utility logic.

#### 1.2.1 Core Purpose and Goal
*   **Objective:** To evaluate model performance on code structures found in open-source projects rather than competitive coding platforms.
*   **Focus:** The selection criteria prioritized **logically complex** files with **low external dependencies**. The goal is to evaluate the model's ability to generate meaningful **assertions** based on internal logic, rather than evaluating its ability to mock complex external libraries.

#### 1.2.2 Data Source and Composition
*   **Total Size:** 50 Functions extracted from 14 source files (~1/4 the size of TestEval).
*   **Sources:** Public module-level functions (no class methods, no `_` prefix, >= 3 lines) extracted from:
    *   2 private/internal files (`our_evaluate_results.py`, `our_run_experiments.py`) to allow for internal code evaluation control.
    *   12 files selected from large, established open-source Python projects spanning multiple domains:
        *   **ML/DL:** pandas, PyTorch, Transformers, vLLM, scikit-learn
        *   **Web:** Requests, Scrapy, HTTPX/Encode
        *   **Scheduling:** APScheduler
        *   **Task Queue:** Dramatiq
        *   **Humanization:** Humanize
*   **Processing:** The dataset treats individual functions within these files as distinct tasks. A balancing algorithm (`balance_dataset()`) enforces per-file caps (`--max-per-file=5`) and difficulty stratification to reach the target count (`--target-count=50`).
*   **Difficulty Distribution:** The specific difficulty was calculated using a custom `DifficultyAnalyzer` that accounts for State Space Cardinality (SSC) and Control Flow Graph (CFG) depth.
    *   **Easy:** 20 (40%)
    *   **Medium:** 15 (30%)
    *   **Hard:** 15 (30%)

#### 1.2.3 Per-File Distribution
| Source File | Functions | Easy | Medium | Hard |
| --- | --- | --- | --- | --- |
| humanize_time.py | 5 | 0 | 1 | 4 |
| our_evaluate_results.py | 5 | 1 | 1 | 3 |
| pandas_common.py | 5 | 2 | 2 | 1 |
| requests_utils.py | 5 | 2 | 2 | 1 |
| scikit_validation.py | 5 | 2 | 2 | 1 |
| scrapy_url.py | 5 | 2 | 2 | 1 |
| vllm_hashing.py | 5 | 4 | 1 | 0 |
| encode__utils.py | 4 | 1 | 2 | 1 |
| our_run_experiments.py | 4 | 1 | 2 | 1 |
| dramatiq_message.py | 3 | 3 | 0 | 0 |
| apscheduler_expressions.py | 1 | 1 | 0 | 0 |
| pandas_numeric.py | 1 | 0 | 0 | 1 |
| pytorch_utils.py | 1 | 0 | 0 | 1 |
| transformers_activations.py | 1 | 1 | 0 | 0 |

---

## 2. Exploratory Data Analysis (EDA)
To gain a quantitative understanding of the differences between the algorithmic (TestEval) and realistic (RealWorld-Py) code, an EDA was performed using the `radon` library and custom AST analysis.

### 2.1 Summary Statistics: TestEval (Algorithm Focus)
| Metric                      | Mean    | Std Dev | Median  | Max     |
| --------------------------- | ------- | ------- | ------- | ------- |
| Character Length            | 1083.13 | 390.15  | 975.00  | 3545.00 |
| Lines of Code (LOC)         | 43.84   | 13.98   | 40.50   | 142.00  |
| Cyclomatic Complexity (Sum) | 23.03   | 6.56    | 21.00   | 59.00   |
| Maintainability Index       | **47.71**   | 4.43    | 47.99   | 63.81   |
| Halstead Difficulty         | **5.67**    | 2.12    | 5.50    | 11.73   |
| Halstead Effort             | 1854.83 | 1589.00 | 1490.35 | 9161.00  |

### 2.2 Summary Statistics: RealWorld-Py (Utility Focus)
| Metric                      | Mean    | Std Dev | Median  | Max      |
| --------------------------- | ------- | ------- | ------- | -------- |
| Character Length            | 2642.54 | 3673.63 | 1289.50 | 20089.00 |
| Lines of Code (LOC)         | 68.24   | 85.61   | 36.00   | 440.00   |
| Cyclomatic Complexity (Sum) | 18.76   | 28.41   | 7.00    | 143.00   |
| Maintainability Index       | **83.28**   | 17.74   | 88.50   | 100.00   |
| Halstead Difficulty         | **2.06**    | 3.27    | 0.78    | 12.81    |
| Halstead Effort             | 1057.20 | 3024.21 | 9.80    | 13007.44 |

### 2.3 Key Findings and Comparisons
*   **Maintainability Gap:** The most striking difference is the Maintainability Index. TestEval averages **47.71** (hard to maintain), while RealWorld-Py averages **83.28** (highly maintainable). This confirms that TestEval represents dense, "spaghetti-code" puzzles, while RealWorld-Py represents cleaner, structured production code.
*   **Complexity Profile:** RealWorld-Py has a lower average Halstead difficulty (2.06 vs 5.67) and a lower median cyclomatic complexity (7 vs 21), but includes high-complexity outliers (max CC=143 for `check_array`). The files were specifically chosen for *logical* complexity (nesting and state space) rather than syntactic difficulty.
*   **Size Distribution:** RealWorld-Py functions are on average larger (68.24 vs 43.84 LOC) with higher variance (std 85.61), reflecting the diversity of real-world code. The median (36 LOC) is closer to TestEval, but the right tail extends to 440 LOC for complex validation functions.
*   **Right-Skewed Distributions:** Most RealWorld-Py metrics exhibit strong right skew. The majority of functions are small and simple (median 36 LOC, median CC=7), but a subset of complex functions (e.g., `check_array`, `get_handle`, `to_numeric`) pull the means upward significantly.
*   **Data Quality:** Checks confirm all 50 RealWorld functions contain valid, non-empty, parsable Python code.

---

## 3. Analysis of Prompting Strategies
The prompts are a critical component of the data, determining how the SLMs approach the problem. Both datasets utilize the exact same set of templates to ensure fair comparison.

#### 3.1 System Prompts & Persona Setting
*   `system.txt`: Sets a general persona ("You are a professional...").
*   `system_exec.txt`: Sets an expert persona ("You are an expert Python programmer..."), used for complex reasoning tasks.

#### 3.2 Zero-Shot Prompts
*   **Basic Zero-Shot (`template_base.txt`):** Asks for a test case given the code.
*   **Constrained Zero-Shot:** Adds hard constraints (e.g., `Your test case must cover line {lineno}`). This tests instruction following.

#### 3.3 Few-Shot Chain-of-Thought (CoT) Prompts
A "plan-then-write" strategy:
1.  **Step 1 (Reasoning):** The model identifies logical conditions required to reach a specific line.
2.  **Step 2 (Generation):** The model generates the test case using the code *and* its own reasoning trace from Step 1.

---

## 4. Synthesis and Hypothesis for Modeling

### 4.1 Synthesis
The combination of **TestEval** (210 problems) and **RealWorld-Py** (50 functions) creates a comprehensive evaluation suite. TestEval provides statistically significant volume on hard algorithmic problems, while RealWorld-Py provides a "reality check" on cleaner, utility-focused code from 14 diverse open-source projects. The datasets diverge significantly in maintainability and structural complexity, while the balanced difficulty distribution (40/30/30) in RealWorld-Py enables meaningful per-difficulty analysis.

### 4.2 Hypothesis
Based on the data characteristics and the proposed prompt strategies, we formulate the following hypothesis:

**Cross-Domain Correlation:** We hypothesize that model performance on **RealWorld-Py** will strongly correlate with performance on **TestEval**. However, we expect higher raw coverage scores on RealWorld-Py due to its higher Maintainability Index (83.28), making the control flow easier for models to traverse than the dense LeetCode algorithms.