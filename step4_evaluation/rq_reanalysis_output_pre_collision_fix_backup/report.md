# RQ Re-analysis Report

Computed directly from existing evaluated JSONL files -- no new inference runs.

## 1. Single-step vs Two-step, pooled across tiers (Experiment B)

| Model                         | Pipeline    |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:------------------------------|:------------|----:|-------:|-----------:|------------:|------------:|
| Qwen3-4B-Thinking-2507        | Single-call | 897 |    167 |      18.62 |       16.21 |       21.3  |
| Qwen3-4B-Thinking-2507        | Two-stage   | 897 |    151 |      16.83 |       14.53 |       19.42 |
| Qwen3.5-4B                    | Single-call | 897 |    192 |      21.4  |       18.85 |       24.21 |
| Qwen3.5-4B                    | Two-stage   | 897 |    233 |      25.98 |       23.21 |       28.94 |
| gemma-4-E4B-it                | Single-call | 897 |    248 |      27.65 |       24.82 |       30.67 |
| gemma-4-E4B-it                | Two-stage   | 897 |    391 |      43.59 |       40.38 |       46.86 |
| granite-4.0-micro             | Single-call | 897 |    181 |      20.18 |       17.68 |       22.93 |
| granite-4.0-micro             | Two-stage   | 897 |    265 |      29.54 |       26.65 |       32.61 |
| Ministral-3-3B-Reasoning-2512 | Single-call | 897 |    116 |      12.93 |       10.89 |       15.29 |
| Ministral-3-3B-Reasoning-2512 | Two-stage   | 897 |    143 |      15.94 |       13.69 |       18.48 |

## 2. Tier x Dependency-Level cross-tab (Experiment B) -- RQ3

| Tier   | Level   |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:-------|:--------|----:|-------:|-----------:|------------:|------------:|
| A      | L0      | 750 |    182 |      24.27 |       21.33 |       27.46 |
| A      | L1      | 740 |    255 |      34.46 |       31.12 |       37.96 |
| A      | L2      | 750 |    188 |      25.07 |       22.1  |       28.29 |
| A      | L3      | 750 |    105 |      14    |       11.7  |       16.67 |
| B      | L0      | 750 |    156 |      20.8  |       18.05 |       23.85 |
| B      | L1      | 740 |    262 |      35.41 |       32.04 |       38.92 |
| B      | L2      | 750 |    164 |      21.87 |       19.06 |       24.96 |
| B      | L3      | 750 |     92 |      12.27 |       10.11 |       14.81 |
| C      | L0      | 750 |    168 |      22.4  |       19.56 |       25.52 |
| C      | L1      | 740 |    247 |      33.38 |       30.07 |       36.85 |
| C      | L2      | 750 |    169 |      22.53 |       19.69 |       25.66 |
| C      | L3      | 750 |     99 |      13.2  |       10.96 |       15.81 |

## 3. Failure modes by level and pipeline (Experiment B)

| Pipeline    | Level   |    N |   Pass |   Pass_% |   Pytest Error |   Pytest Error_% |   Assertion Error |   Assertion Error_% |   Runtime Error |   Runtime Error_% |   Timeout |   Timeout_% |   No Code |   No Code_% | _other_statuses_seen   |
|:------------|:--------|-----:|-------:|---------:|---------------:|-----------------:|------------------:|--------------------:|----------------:|------------------:|----------:|------------:|----------:|------------:|:-----------------------|
| Single-call | L0      | 1125 |    230 |     20.4 |              4 |              0.4 |               159 |                14.1 |             714 |              63.5 |         0 |         0   |        18 |         1.6 | []                     |
| Single-call | L1      | 1110 |    345 |     31.1 |             10 |              0.9 |               216 |                19.5 |             517 |              46.6 |         1 |         0.1 |        21 |         1.9 | []                     |
| Single-call | L2      | 1125 |    217 |     19.3 |             20 |              1.8 |               145 |                12.9 |             726 |              64.5 |         0 |         0   |        17 |         1.5 | []                     |
| Single-call | L3      | 1125 |    112 |     10   |             29 |              2.6 |                76 |                 6.8 |             892 |              79.3 |         1 |         0.1 |        15 |         1.3 | []                     |
| Two-stage   | L0      | 1125 |    276 |     24.5 |              4 |              0.4 |               183 |                16.3 |             646 |              57.4 |         0 |         0   |        16 |         1.4 | []                     |
| Two-stage   | L1      | 1110 |    419 |     37.7 |              5 |              0.5 |               168 |                15.1 |             494 |              44.5 |         0 |         0   |        24 |         2.2 | []                     |
| Two-stage   | L2      | 1125 |    304 |     27   |              6 |              0.5 |               143 |                12.7 |             656 |              58.3 |         0 |         0   |        16 |         1.4 | []                     |
| Two-stage   | L3      | 1125 |    184 |     16.4 |             12 |              1.1 |               104 |                 9.2 |             799 |              71   |         0 |         0   |        26 |         2.3 | []                     |

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
| Qwen3-4B-Thinking-2507        | A      |        299 |          28 |         208 |                 31 |                    32 |                     0.96875  |          31 | 1           | 1           | False                   |
| Qwen3-4B-Thinking-2507        | B      |        299 |          31 |         219 |                 26 |                    23 |                     1.13043  |          23 | 0.77545     | 1           | False                   |
| Qwen3-4B-Thinking-2507        | C      |        299 |          28 |         239 |                 23 |                     9 |                     2.55556  |           9 | 0.0200616   | 0.202767    | False                   |
| Qwen3.5-4B                    | A      |        299 |          29 |         174 |                 36 |                    60 |                     0.6      |          36 | 0.0184334   | 0.202767    | False                   |
| Qwen3.5-4B                    | B      |        299 |          33 |         186 |                 37 |                    43 |                     0.860465 |          37 | 0.576431    | 1           | False                   |
| Qwen3.5-4B                    | C      |        299 |          24 |         198 |                 33 |                    44 |                     0.75     |          33 | 0.254305    | 1           | False                   |
| gemma-4-E4B-it                | A      |        299 |          40 |         149 |                 25 |                    85 |                     0.294118 |          25 | 7.83222e-09 | 1.09651e-07 | True                    |
| gemma-4-E4B-it                | B      |        299 |          35 |         137 |                 26 |                   101 |                     0.257426 |          26 | 1.24366e-11 | 1.86549e-10 | True                    |
| gemma-4-E4B-it                | C      |        299 |          62 |         109 |                 60 |                    68 |                     0.882353 |          60 | 0.536269    | 1           | False                   |
| granite-4.0-micro             | A      |        299 |          36 |         155 |                 54 |                    54 |                     1        |          54 | 1           | 1           | False                   |
| granite-4.0-micro             | B      |        299 |          21 |         188 |                 21 |                    69 |                     0.304348 |          21 | 3.88182e-07 | 5.04636e-06 | True                    |
| granite-4.0-micro             | C      |        299 |          22 |         187 |                 27 |                    63 |                     0.428571 |          27 | 0.000187756 | 0.00225307  | True                    |
| Ministral-3-3B-Reasoning-2512 | A      |        299 |           8 |         220 |                 29 |                    42 |                     0.690476 |          29 | 0.153913    | 1           | False                   |
| Ministral-3-3B-Reasoning-2512 | B      |        299 |          10 |         221 |                 32 |                    36 |                     0.888889 |          32 | 0.716301    | 1           | False                   |
| Ministral-3-3B-Reasoning-2512 | C      |        299 |          11 |         226 |                 26 |                    36 |                     0.722222 |          26 | 0.252854    | 1           | False                   |

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
| Experiment B (RealWorldTests-Py v2) | Qwen3-4B-Thinking-2507        | Single-call |       897 |        3560862 |             35488.8 |             9.858 |                3969.7 |                  39.56 |
| Experiment B (RealWorldTests-Py v2) | Qwen3-4B-Thinking-2507        | Two-stage   |       897 |        5889052 |             60210.3 |            16.725 |                6565.3 |                  67.12 |
| Experiment B (RealWorldTests-Py v2) | Qwen3.5-4B                    | Single-call |       897 |        1125576 |             11378   |             3.161 |                1254.8 |                  12.68 |
| Experiment B (RealWorldTests-Py v2) | Qwen3.5-4B                    | Two-stage   |       897 |        4096931 |             41766.6 |            11.602 |                4567.4 |                  46.56 |
| Experiment B (RealWorldTests-Py v2) | gemma-4-E4B-it                | Single-call |       897 |         174382 |              2013.8 |             0.559 |                 194.4 |                   2.25 |
| Experiment B (RealWorldTests-Py v2) | gemma-4-E4B-it                | Two-stage   |       897 |         403784 |              4656.6 |             1.293 |                 450.1 |                   5.19 |
| Experiment B (RealWorldTests-Py v2) | granite-4.0-micro             | Single-call |       897 |         113498 |               978.5 |             0.272 |                 126.5 |                   1.09 |
| Experiment B (RealWorldTests-Py v2) | granite-4.0-micro             | Two-stage   |       897 |         387563 |              3319.1 |             0.922 |                 432.1 |                   3.7  |
| Experiment B (RealWorldTests-Py v2) | Ministral-3-3B-Reasoning-2512 | Single-call |       897 |         203690 |              1689   |             0.469 |                 227.1 |                   1.88 |
| Experiment B (RealWorldTests-Py v2) | Ministral-3-3B-Reasoning-2512 | Two-stage   |       897 |        1112205 |              9342.3 |             2.595 |                1239.9 |                  10.42 |

## 8. Logistic regression, Pass ~ leaked + CC + LOC + level (cluster-robust SE by task_num; N=8970 obs, 299 clusters)

|       coef |   std_err_cluster |        z |     p_value |   odds_ratio |   OR_ci_lo |   OR_ci_hi |
|-----------:|------------------:|---------:|------------:|-------------:|-----------:|-----------:|
| -1.31221   |        0.167261   | -7.8453  | 4.31923e-15 |     0.269225 |   0.193973 |   0.373669 |
|  0.501962  |        0.172935   |  2.90261 | 0.00370071  |     1.65196  |   1.17706  |   2.31847  |
| -0.030358  |        0.161943   | -0.18746 | 0.8513      |     0.970098 |   0.706267 |   1.33248  |
| -0.732098  |        0.166306   | -4.40212 | 1.07197e-05 |     0.480899 |   0.347132 |   0.666214 |
|  0.551479  |        0.139761   |  3.94587 | 7.95117e-05 |     1.73582  |   1.31989  |   2.28281  |
|  0.0584135 |        0.0164179  |  3.55792 | 0.000373808 |     1.06015  |   1.02658  |   1.09482  |
| -0.0131963 |        0.00434397 | -3.03783 | 0.00238285  |     0.98689  |   0.978524 |   0.995329 |

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
