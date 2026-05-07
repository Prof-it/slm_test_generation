# `scope.md`

#### **Included:**

*   **Models:** A selection of 10+ open-source SLMs with fewer than 7 billion parameters (e.g., Qwen, Llama3, Deepseek, Phi, Gemma families).
*   **Language:** Python only.
*   **Task:** Generation of unit tests for individual functions (method-level).
*   **Benchmark:** Exclusively uses the `TestEval` benchmark.
*   **Methodology:** Experiments will be run in isolated Docker containers using single-step and two-step (plan-then-write).
*   **Evaluation:** Performance is measured by quantitative metrics (Pass@1, Code Coverage, Mutation Score) and supplemented by a qualitative LLM-as-Judge assessment and an expert sanity check with dogfooding (test generation for 3 scripts of this project).

#### **Excluded:**

*   Programming languages other than Python.
*   Large Language Models (LLMs, >7B parameters) are not the subject of the evaluation.
*   Other benchmarks like `TestGenEval` due to the context length limitations of current SLMs.
*   A detailed financial audit of operational costs; "cost-effectiveness" is framed by computational feasibility and accessibility.
*   Development of novel techniques, implementation of three or four step agentic approaches, fragment inference to handle larger contexts or heavy post processing.
*   MoE models because some older GPU architectures do not support them.