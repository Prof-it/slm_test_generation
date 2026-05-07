# `success_criteria.md`

Success will be measured by a combination of quantitative Key Performance Indicators (KPIs) and qualitative assessments:

*   **`Pass@1`:** The percentage of problems for which a syntactically correct and passing test suite is generated on the first attempt. A higher percentage indicates better generation capability.
*   **`Code Coverage@pass`:** For passing test suites, the average percentage of code lines in the function-under-test that are executed. A higher score indicates more thorough tests.
*   **`Mutation Score@pass`:** For passing test suites, the percentage of generated mutants (artificial bugs) that are detected. This is a key indicator of the test suite's fault-detection effectiveness.
*   **Qualitative Score (LLM-as-Judge):** High ratings from a powerful LLM judge on criteria like readability, simplicity, and adherence to conventions for a random sample of generated tests.