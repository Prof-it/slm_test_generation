# `constraints.md`

*   **Time:** The project is time-bound to a specific 20-week timeline (November to March), which dictates the number of experiments that can be run.
*   **Data:** The study is constrained to the `TestEval` benchmark, which focuses on method-level test generation. The findings may not be generalizable to repository-level or more complex testing scenarios.
*   **Technology:** The project is limited by the inherent capabilities of current SLMs, specifically their context window size (<32k tokens). This technical limitation prevents the use of benchmarks that require analysis of larger codebases (e.g., `TestGenEval`).
*   **Environment:** All experiments must be conducted within a standardized Docker environment to ensure consistency and reproducibility, limiting flexibility in system configuration.