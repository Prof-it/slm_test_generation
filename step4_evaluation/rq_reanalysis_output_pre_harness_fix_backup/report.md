# RQ Re-analysis Report

Computed directly from existing evaluated JSONL files -- no new inference runs.

## 1. Single-step vs Two-step, pooled across tiers (Experiment B)

| Model                         | Pipeline    |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:------------------------------|:------------|----:|-------:|-----------:|------------:|------------:|
| Qwen3-4B-Thinking-2507        | Single-call | 900 |    158 |      17.56 |       15.21 |       20.18 |
| Qwen3-4B-Thinking-2507        | Two-stage   | 900 |    138 |      15.33 |       13.13 |       17.83 |
| Qwen3.5-4B                    | Single-call | 900 |    146 |      16.22 |       13.96 |       18.77 |
| Qwen3.5-4B                    | Two-stage   | 900 |    224 |      24.89 |       22.17 |       27.82 |
| gemma-4-E4B-it                | Single-call | 900 |    248 |      27.56 |       24.74 |       30.57 |
| gemma-4-E4B-it                | Two-stage   | 900 |    391 |      43.44 |       40.24 |       46.7  |
| granite-4.0-micro             | Single-call | 900 |    167 |      18.56 |       16.15 |       21.23 |
| granite-4.0-micro             | Two-stage   | 900 |    249 |      27.67 |       24.84 |       30.68 |
| Ministral-3-3B-Reasoning-2512 | Single-call | 900 |    111 |      12.33 |       10.34 |       14.64 |
| Ministral-3-3B-Reasoning-2512 | Two-stage   | 900 |    149 |      16.56 |       14.27 |       19.13 |

## 2. Tier x Dependency-Level cross-tab (Experiment B) -- RQ3

| Tier   | Level   |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:-------|:--------|----:|-------:|-----------:|------------:|------------:|
| A      | L0      | 750 |    172 |      22.93 |       20.07 |       26.08 |
| A      | L1      | 750 |    223 |      29.73 |       26.57 |       33.1  |
| A      | L2      | 750 |    164 |      21.87 |       19.06 |       24.96 |
| A      | L3      | 750 |    102 |      13.6  |       11.33 |       16.24 |
| B      | L0      | 750 |    152 |      20.27 |       17.54 |       23.29 |
| B      | L1      | 750 |    240 |      32    |       28.76 |       35.42 |
| B      | L2      | 750 |    159 |      21.2  |       18.43 |       24.27 |
| B      | L3      | 750 |     93 |      12.4  |       10.23 |       14.95 |
| C      | L0      | 750 |    164 |      21.87 |       19.06 |       24.96 |
| C      | L1      | 750 |    238 |      31.73 |       28.5  |       35.15 |
| C      | L2      | 750 |    174 |      23.2  |       20.32 |       26.35 |
| C      | L3      | 750 |    100 |      13.33 |       11.09 |       15.95 |

## 3. Failure modes by level and pipeline (Experiment B)

| Pipeline    | Level   |    N |   Pass |   Pass_% |   Pytest Error |   Pytest Error_% |   Assertion Error |   Assertion Error_% |   Runtime Error |   Runtime Error_% |   Timeout |   Timeout_% |   No Code |   No Code_% | _other_statuses_seen   |
|:------------|:--------|-----:|-------:|---------:|---------------:|-----------------:|------------------:|--------------------:|----------------:|------------------:|----------:|------------:|----------:|------------:|:-----------------------|
| Single-call | L0      | 1125 |    221 |     19.6 |              4 |              0.4 |               150 |                13.3 |             731 |              65   |         1 |         0.1 |        18 |         1.6 | []                     |
| Single-call | L1      | 1125 |    305 |     27.1 |             10 |              0.9 |               214 |                19   |             574 |              51   |         1 |         0.1 |        21 |         1.9 | []                     |
| Single-call | L2      | 1125 |    198 |     17.6 |             20 |              1.8 |               144 |                12.8 |             744 |              66.1 |         2 |         0.2 |        17 |         1.5 | []                     |
| Single-call | L3      | 1125 |    106 |      9.4 |             29 |              2.6 |                79 |                 7   |             893 |              79.4 |         3 |         0.3 |        15 |         1.3 | []                     |
| Two-stage   | L0      | 1125 |    267 |     23.7 |              4 |              0.4 |               172 |                15.3 |             666 |              59.2 |         0 |         0   |        16 |         1.4 | []                     |
| Two-stage   | L1      | 1125 |    396 |     35.2 |              5 |              0.4 |               166 |                14.8 |             534 |              47.5 |         0 |         0   |        24 |         2.1 | []                     |
| Two-stage   | L2      | 1125 |    299 |     26.6 |              6 |              0.5 |               148 |                13.2 |             654 |              58.1 |         2 |         0.2 |        16 |         1.4 | []                     |
| Two-stage   | L3      | 1125 |    189 |     16.8 |             12 |              1.1 |               110 |                 9.8 |             788 |              70   |         0 |         0   |        26 |         2.3 | []                     |

## 4. Wilson 95% CIs for Experiment A Table 1

| Model                         | Pipeline    |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:------------------------------|:------------|----:|-------:|-----------:|------------:|------------:|
| Qwen3-4B-Thinking-2507        | Single-call | 210 |    181 |      86.19 |       80.87 |       90.21 |
| Qwen3-4B-Thinking-2507        | Two-stage   | 210 |    158 |      75.24 |       68.98 |       80.59 |
| Qwen3.5-4B                    | Single-call | 210 |    164 |      78.1  |       72.02 |       83.16 |
| Qwen3.5-4B                    | Two-stage   | 210 |    154 |      73.33 |       66.97 |       78.86 |
| gemma-4-E4B-it                | Single-call | 210 |    101 |      48.1  |       41.43 |       54.83 |
| gemma-4-E4B-it                | Two-stage   | 210 |    143 |      68.1  |       61.51 |       74.03 |
| granite-4.0-micro             | Single-call | 210 |    117 |      55.71 |       48.95 |       62.27 |
| granite-4.0-micro             | Two-stage   | 210 |    101 |      48.1  |       41.43 |       54.83 |
| Ministral-3-3B-Reasoning-2512 | Single-call | 210 |    107 |      50.95 |       44.23 |       57.64 |
| Ministral-3-3B-Reasoning-2512 | Two-stage   | 210 |     76 |      36.19 |       29.99 |       42.88 |

## 5a. McNemar (paired) Single-call vs Two-stage, Experiment A, Holm-Bonferroni over 5 models

| Model                         |   n_common |   both_pass |   both_fail |   single_only_pass |   two_stage_only_pass |   odds_ratio_single_over_two |   statistic |     p_value |      p_holm | significant_holm_0.05   |
|:------------------------------|-----------:|------------:|------------:|-------------------:|----------------------:|-----------------------------:|------------:|------------:|------------:|:------------------------|
| Qwen3-4B-Thinking-2507        |        210 |         140 |          11 |                 41 |                    18 |                     2.27778  |          18 | 0.00379371  | 0.0113811   | True                    |
| Qwen3.5-4B                    |        210 |         125 |          17 |                 39 |                    29 |                     1.34483  |          29 | 0.27499     | 0.27499     | False                   |
| gemma-4-E4B-it                |        210 |          75 |          41 |                 26 |                    68 |                     0.382353 |          26 | 1.73169e-05 | 8.65846e-05 | True                    |
| granite-4.0-micro             |        210 |          75 |          67 |                 42 |                    26 |                     1.61538  |          26 | 0.0681187   | 0.136237    | False                   |
| Ministral-3-3B-Reasoning-2512 |        210 |          53 |          80 |                 54 |                    23 |                     2.34783  |          23 | 0.00053878  | 0.00215512  | True                    |

## 5b. McNemar (paired) Single-call vs Two-stage, Experiment B, Holm-Bonferroni over 15 model x tier tests

| Model                         | Tier   |   n_common |   both_pass |   both_fail |   single_only_pass |   two_stage_only_pass |   odds_ratio_single_over_two |   statistic |     p_value |      p_holm | significant_holm_0.05   |
|:------------------------------|:-------|-----------:|------------:|------------:|-------------------:|----------------------:|-----------------------------:|------------:|------------:|------------:|:------------------------|
| Qwen3-4B-Thinking-2507        | A      |        299 |          28 |         218 |                 27 |                    26 |                     1.03846  |          26 | 1           | 1           | False                   |
| Qwen3-4B-Thinking-2507        | B      |        299 |          29 |         225 |                 24 |                    21 |                     1.14286  |          21 | 0.765992    | 1           | False                   |
| Qwen3-4B-Thinking-2507        | C      |        299 |          27 |         242 |                 23 |                     7 |                     3.28571  |           7 | 0.00522288  | 0.0522288   | False                   |
| Qwen3.5-4B                    | A      |        299 |          12 |         201 |                 15 |                    71 |                     0.211268 |          15 | 7.07606e-10 | 9.90648e-09 | True                    |
| Qwen3.5-4B                    | B      |        299 |          31 |         192 |                 33 |                    43 |                     0.767442 |          33 | 0.301872    | 1           | False                   |
| Qwen3.5-4B                    | C      |        299 |          23 |         200 |                 32 |                    44 |                     0.727273 |          32 | 0.206737    | 1           | False                   |
| gemma-4-E4B-it                | A      |        299 |          40 |         149 |                 25 |                    85 |                     0.294118 |          25 | 7.83222e-09 | 1.01819e-07 | True                    |
| gemma-4-E4B-it                | B      |        299 |          33 |         139 |                 25 |                   102 |                     0.245098 |          25 | 3.12067e-12 | 4.681e-11   | True                    |
| gemma-4-E4B-it                | C      |        299 |          63 |         106 |                 62 |                    68 |                     0.911765 |          62 | 0.66117     | 1           | False                   |
| granite-4.0-micro             | A      |        299 |          32 |         167 |                 47 |                    53 |                     0.886792 |          47 | 0.617299    | 1           | False                   |
| granite-4.0-micro             | B      |        299 |          18 |         195 |                 20 |                    66 |                     0.30303  |          20 | 6.66978e-07 | 8.00373e-06 | True                    |
| granite-4.0-micro             | C      |        299 |          21 |         192 |                 27 |                    59 |                     0.457627 |          27 | 0.00073171  | 0.00804881  | True                    |
| Ministral-3-3B-Reasoning-2512 | A      |        299 |           7 |         220 |                 26 |                    46 |                     0.565217 |          26 | 0.0244609   | 0.220148    | False                   |
| Ministral-3-3B-Reasoning-2512 | B      |        299 |           8 |         220 |                 30 |                    41 |                     0.731707 |          30 | 0.235098    | 1           | False                   |
| Ministral-3-3B-Reasoning-2512 | C      |        299 |          11 |         225 |                 29 |                    34 |                     0.852941 |          29 | 0.614655    | 1           | False                   |

## 6. Mutation score: conditional (cMut) vs unconditional (uMut), Experiment A

| Model                         | Pipeline    |   N |   n_mutation_completed |   cMut_%_conditional_on_pass |   uMut_%_unconditional |
|:------------------------------|:------------|----:|-----------------------:|-----------------------------:|-----------------------:|
| Qwen3-4B-Thinking-2507        | Single-call | 210 |                    181 |                        19.35 |                  16.68 |
| Qwen3-4B-Thinking-2507        | Two-stage   | 210 |                    157 |                        19.79 |                  14.8  |
| Qwen3.5-4B                    | Single-call | 210 |                    152 |                         6.27 |                   4.54 |
| Qwen3.5-4B                    | Two-stage   | 210 |                    154 |                        12.31 |                   9.03 |
| gemma-4-E4B-it                | Single-call | 210 |                     97 |                        12.35 |                   5.71 |
| gemma-4-E4B-it                | Two-stage   | 210 |                    143 |                        22.15 |                  15.08 |
| granite-4.0-micro             | Single-call | 210 |                    110 |                         9.91 |                   5.19 |
| granite-4.0-micro             | Two-stage   | 210 |                    101 |                        18.94 |                   9.11 |
| Ministral-3-3B-Reasoning-2512 | Single-call | 210 |                    105 |                        10.69 |                   5.35 |
| Ministral-3-3B-Reasoning-2512 | Two-stage   | 210 |                     76 |                        20.24 |                   7.32 |

## 7. Wall-clock / tokens / GPU-hours per model x pipeline

| Experiment                          | Model                         | Pipeline    |   N_tasks |   Total_tokens |   Total_GPU_seconds |   Total_GPU_hours |   Avg_tokens_per_task |   Avg_seconds_per_task |
|:------------------------------------|:------------------------------|:------------|----------:|---------------:|--------------------:|------------------:|----------------------:|-----------------------:|
| Experiment A (TestEval)             | Qwen3-4B-Thinking-2507        | Single-call |       210 |        1087461 |             21377.9 |             5.938 |                5178.4 |                 101.8  |
| Experiment A (TestEval)             | Qwen3-4B-Thinking-2507        | Two-stage   |       210 |        1426225 |             25319.3 |             7.033 |                6791.5 |                 120.57 |
| Experiment A (TestEval)             | Qwen3.5-4B                    | Single-call |       210 |        1387909 |             24367   |             6.769 |                6609.1 |                 116.03 |
| Experiment A (TestEval)             | Qwen3.5-4B                    | Two-stage   |       210 |        1611240 |             23505.8 |             6.529 |                7672.6 |                 111.93 |
| Experiment A (TestEval)             | gemma-4-E4B-it                | Single-call |       210 |          22966 |               434   |             0.121 |                 109.4 |                   2.07 |
| Experiment A (TestEval)             | gemma-4-E4B-it                | Two-stage   |       210 |         250172 |              4370.2 |             1.214 |                1191.3 |                  20.81 |
| Experiment A (TestEval)             | granite-4.0-micro             | Single-call |       210 |          14083 |               186.7 |             0.052 |                  67.1 |                   0.89 |
| Experiment A (TestEval)             | granite-4.0-micro             | Two-stage   |       210 |         109795 |              1673.7 |             0.465 |                 522.8 |                   7.97 |
| Experiment A (TestEval)             | Ministral-3-3B-Reasoning-2512 | Single-call |       210 |         128026 |              1094.9 |             0.304 |                 609.6 |                   5.21 |
| Experiment A (TestEval)             | Ministral-3-3B-Reasoning-2512 | Two-stage   |       210 |         188497 |              2190.5 |             0.608 |                 897.6 |                  10.43 |
| Experiment B (RealWorldTests-Py v2) | Qwen3-4B-Thinking-2507        | Single-call |       900 |        3571192 |             35590.9 |             9.886 |                3968   |                  39.55 |
| Experiment B (RealWorldTests-Py v2) | Qwen3-4B-Thinking-2507        | Two-stage   |       900 |        5909114 |             60415   |            16.782 |                6565.7 |                  67.13 |
| Experiment B (RealWorldTests-Py v2) | Qwen3.5-4B                    | Single-call |       900 |        1127020 |             11392.5 |             3.165 |                1252.2 |                  12.66 |
| Experiment B (RealWorldTests-Py v2) | Qwen3.5-4B                    | Two-stage   |       900 |        4112892 |             41929.3 |            11.647 |                4569.9 |                  46.59 |
| Experiment B (RealWorldTests-Py v2) | gemma-4-E4B-it                | Single-call |       900 |         174716 |              2017.7 |             0.56  |                 194.1 |                   2.24 |
| Experiment B (RealWorldTests-Py v2) | gemma-4-E4B-it                | Two-stage   |       900 |         404881 |              4669.2 |             1.297 |                 449.9 |                   5.19 |
| Experiment B (RealWorldTests-Py v2) | granite-4.0-micro             | Single-call |       900 |         113635 |               979.8 |             0.272 |                 126.3 |                   1.09 |
| Experiment B (RealWorldTests-Py v2) | granite-4.0-micro             | Two-stage   |       900 |         388963 |              3331.1 |             0.925 |                 432.2 |                   3.7  |
| Experiment B (RealWorldTests-Py v2) | Ministral-3-3B-Reasoning-2512 | Single-call |       900 |         203941 |              1691.1 |             0.47  |                 226.6 |                   1.88 |
| Experiment B (RealWorldTests-Py v2) | Ministral-3-3B-Reasoning-2512 | Two-stage   |       900 |        1113010 |              9348.8 |             2.597 |                1236.7 |                  10.39 |

## 8. Logistic regression, Pass ~ leaked + CC + LOC + level (cluster-robust SE by task_num; N=9000 obs, 299 clusters)

|       coef |   std_err_cluster |         z |     p_value |   odds_ratio |   OR_ci_lo |   OR_ci_hi |
|-----------:|------------------:|----------:|------------:|-------------:|-----------:|-----------:|
| -1.37944   |        0.174683   | -7.89682  | 2.86104e-15 |     0.251719 |   0.178742 |   0.354492 |
|  0.37723   |        0.180579   |  2.089    | 0.036708    |     1.45824  |   1.02357  |   2.07749  |
| -0.0858741 |        0.166371   | -0.516159 | 0.605743    |     0.91771  |   0.662353 |   1.27151  |
| -0.718973  |        0.16521    | -4.35186  | 1.34987e-05 |     0.487252 |   0.352474 |   0.673568 |
|  0.679769  |        0.139327   |  4.87895  | 1.06651e-06 |     1.97342  |   1.50184  |   2.59308  |
|  0.0511831 |        0.0202797  |  2.52386  | 0.0116073   |     1.05252  |   1.0115   |   1.09519  |
| -0.0110583 |        0.00453545 | -2.43819  | 0.0147608   |     0.989003 |   0.98025  |   0.997833 |

## 9a. Historical vs Recent pool -- CC/LOC balance

|   ('cyclomatic_complexity', 'mean') |   ('cyclomatic_complexity', 'median') |   ('cyclomatic_complexity', 'std') |   ('cyclomatic_complexity', 'min') |   ('cyclomatic_complexity', 'max') |   ('loc', 'mean') |   ('loc', 'median') |   ('loc', 'std') |   ('loc', 'min') |   ('loc', 'max') |
|------------------------------------:|--------------------------------------:|-----------------------------------:|-----------------------------------:|-----------------------------------:|------------------:|--------------------:|-----------------:|-----------------:|-----------------:|
|                             5.52542 |                                     5 |                            2.56875 |                                  3 |                                 12 |           24.8475 |                  22 |          14.9549 |                5 |               73 |
|                             5.77083 |                                     4 |                            3.89957 |                                  3 |                                 23 |           25.0625 |                  20 |          16.6944 |                5 |               75 |

## 9b. Historical vs Recent pool -- dependency-level distribution (row %)

|    L0 |    L1 |    L2 |    L3 |
|------:|------:|------:|------:|
| 10.17 | 25.42 | 35.59 | 28.81 |
| 28.75 | 24.58 | 22.5  | 24.17 |

## 9c. Historical vs Recent pool -- domain distribution (row %)

|   cli |   data |    ml |   serialization |   web |
|------:|-------:|------:|----------------:|------:|
| 13.56 |  18.64 | 32.2  |            0    | 35.59 |
| 31.25 |  30.83 | 12.92 |            8.33 | 16.67 |

## 9d. Pool sizes (unique tasks)

|   n_unique_tasks |
|-----------------:|
|              240 |
|               59 |
