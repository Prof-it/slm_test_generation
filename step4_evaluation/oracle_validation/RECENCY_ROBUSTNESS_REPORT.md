# Recency-Effect Robustness Checks (Step 1, no re-execution)

## Full-set vs. clean-set vs. partial-exclusion sensitivity

| Spec                                                    |   N_obs |   N_clusters |   OR_leaked_historical |   OR_ci_lo |   OR_ci_hi |     p_value |
|:--------------------------------------------------------|--------:|-------------:|-----------------------:|-----------:|-----------:|------------:|
| Full set (N=300 tasks, existing paper spec)             |    9000 |          300 |                  1.694 |      1.287 |      2.231 | 0.000172453 |
| Clean set (19 broken tasks excluded)                    |    8430 |          281 |                  1.667 |      1.264 |      2.198 | 0.000295314 |
| Sensitivity: exclude only 15 genuine extraction defects |    8550 |          285 |                  1.677 |      1.273 |      2.209 | 0.000236228 |
| Sensitivity: exclude only 4 Python-3.11-only artifacts  |    8880 |          296 |                  1.684 |      1.278 |      2.219 | 0.000214775 |

## Clustering-level check (task_num vs. repo), clean set

| Spec                                    |   N_obs |   N_clusters |   OR_leaked_historical |   OR_ci_lo |   OR_ci_hi |     p_value |
|:----------------------------------------|--------:|-------------:|-----------------------:|-----------:|-----------:|------------:|
| Clustered by task_num (existing choice) |    8430 |          281 |                  1.667 |      1.264 |      2.198 | 0.000295314 |
| Clustered by repo                       |    8430 |           33 |                  1.667 |      1.212 |      2.292 | 0.0016671   |

## Per-model recency effect (pool x model interaction), clean set

| Model                              |   OR_leaked |       p_value |   p_value_diff_vs_reference |
|:-----------------------------------|------------:|--------------:|----------------------------:|
| Qwen3-4B-Thinking-2507 (reference) |       3.518 |   7.66405e-07 |                    nan      |
| Qwen3.5-4B                         |       1.415 | nan           |                      0.0001 |
| gemma-4-E4B-it                     |       1.431 | nan           |                      0      |
| granite-4.0-micro                  |       1.123 | nan           |                      0      |
| Ministral-3-3B-Reasoning-2512      |       1.975 | nan           |                      0.0558 |

## Continuous code-age sensitivity: feasibility

Historical pool: 1 distinct commit_date value(s) (['pre-2026-06-10']) -- all historical tasks share the placeholder 'pre-2026-06-10' inherited from TestEval, not real per-task dates. Recent pool: 7 distinct dates spanning 2026-06-17 to 2026-06-28. A continuous code-age regression is NOT feasible: the historical pool has no real dates at all (binary pool membership is the only available signal), and the recent pool's 7 distinct values span only a few days, far too narrow to estimate a meaningful continuous slope. This sensitivity analysis is not run; the binary historical/recent split is the only date granularity the data actually supports.
