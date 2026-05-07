# `testeval.md`

In this Markdown I am inspecting and taking notes about the finer details of the `TESTEVAL: Benchmarking Large Language Models for Test Case Generation` paper and the Repo `https://deepwiki.com/LLM4SoftwareTesting/TestEval`.

# The TestEval Paper
* overall coverage
* targeted line/branch coverage (decision): 12/16 LLMs performance did not significantly improved compared to target line information is not given.
* targeted path coverage (given possible input output pairs)

New metric to measure llms test generation performance cov@1 measure line/branch coverage with a subset of generated test cases of k<M where we randomly split M executable test cases into max(|_M/K_|,1) subsets. For each subsets we calculate overall line/branch coverage.

Note: ETS@k is a slightly improved version of cov@k. Cov@k could show perfect with zero assertion generations which is a higher possibility with SLMs so to handle that case ETS@k is introduced, a lightweight, assertion-aware alternative to coverage metrics that distinguishes between merely running code and genuinely testing it.
ETS = (line coverage% + branch coverage% /2) * log2(1+assertion count)

LLMs have a higher
cov@2 and cov@5 compared with cov@1 because LLMs can generate different test cases.

filter any non-code content that may have been generated outside testing function retaining only python code block test case in each query round to ensure fair comparison.

All test case undergo correctness check including syntactic correctness execution correctness and assertion correctness.


we observe that
most models can achieve high syntactical and acceptable execution correctness, but all models have
much lower assertion correctness.

LLMs are able to generate test cases that
cover over 80% lines/branches per program under
test.

Notably, the latest GPT-4o achieves the best
overall line (98.65%) and branch (97.16%) coverage.


### Results
As targeted line coverage most models do 99%.

GPT4o: assertion 67%
Llama 3.1 8b: 48%
Deepseek coder 5.7B: 45%

Ours is 4bit version of these.
Are we using targeted or non-targeted line.

targeted line and targeted branch prompts improve accuracy only on the largest LLMs.

targeted path coverage is harder than overall coverage and targeted line and branch coverage.

explicit two step cot is tried on targeted line coverage. Not all llms ran with cot. For most models cot can improve performance on target line coverage.

Not all models accuracy improves, accuracy improvement with cot and model size does not correlate so it might be about models unique data since llama 3.1 8b improved better than gpt-4o.

# The TestEval Repo



