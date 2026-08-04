# RQ Re-analysis Report

Computed directly from existing evaluated JSONL files -- no new inference runs.

## 1. Single-step vs Two-step, pooled across tiers (Experiment B)

| Model                         | Pipeline    |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:------------------------------|:------------|----:|-------:|-----------:|------------:|------------:|
| Qwen3-4B-Thinking-2507        | Single-call | 900 |    167 |      18.56 |       16.15 |       21.23 |
| Qwen3-4B-Thinking-2507        | Two-stage   | 900 |    151 |      16.78 |       14.48 |       19.36 |
| Qwen3.5-4B                    | Single-call | 900 |    192 |      21.33 |       18.78 |       24.13 |
| Qwen3.5-4B                    | Two-stage   | 900 |    234 |      26    |       23.24 |       28.96 |
| gemma-4-E4B-it                | Single-call | 900 |    248 |      27.56 |       24.74 |       30.57 |
| gemma-4-E4B-it                | Two-stage   | 900 |    391 |      43.44 |       40.24 |       46.7  |
| granite-4.0-micro             | Single-call | 900 |    183 |      20.33 |       17.83 |       23.09 |
| granite-4.0-micro             | Two-stage   | 900 |    265 |      29.44 |       26.56 |       32.5  |
| Ministral-3-3B-Reasoning-2512 | Single-call | 900 |    116 |      12.89 |       10.86 |       15.24 |
| Ministral-3-3B-Reasoning-2512 | Two-stage   | 900 |    145 |      16.11 |       13.85 |       18.66 |

## 2. Tier x Dependency-Level cross-tab (Experiment B) -- RQ3

| Tier   | Level   |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:-------|:--------|----:|-------:|-----------:|------------:|------------:|
| A      | L0      | 750 |    182 |      24.27 |       21.33 |       27.46 |
| A      | L1      | 750 |    257 |      34.27 |       30.96 |       37.74 |
| A      | L2      | 750 |    188 |      25.07 |       22.1  |       28.29 |
| A      | L3      | 750 |    105 |      14    |       11.7  |       16.67 |
| B      | L0      | 750 |    156 |      20.8  |       18.05 |       23.85 |
| B      | L1      | 750 |    264 |      35.2  |       31.87 |       38.69 |
| B      | L2      | 750 |    164 |      21.87 |       19.06 |       24.96 |
| B      | L3      | 750 |     92 |      12.27 |       10.11 |       14.81 |
| C      | L0      | 750 |    168 |      22.4  |       19.56 |       25.52 |
| C      | L1      | 750 |    248 |      33.07 |       29.79 |       36.51 |
| C      | L2      | 750 |    169 |      22.53 |       19.69 |       25.66 |
| C      | L3      | 750 |     99 |      13.2  |       10.96 |       15.81 |

## 3. Failure modes by level and pipeline (Experiment B)

| Pipeline    | Level   |    N |   Pass |   Pass_% |   Pytest Error |   Pytest Error_% |   Assertion Error |   Assertion Error_% |   Runtime Error |   Runtime Error_% |   Timeout |   Timeout_% |   No Code |   No Code_% | _other_statuses_seen   |
|:------------|:--------|-----:|-------:|---------:|---------------:|-----------------:|------------------:|--------------------:|----------------:|------------------:|----------:|------------:|----------:|------------:|:-----------------------|
| Single-call | L0      | 1125 |    230 |     20.4 |              4 |              0.4 |               159 |                14.1 |             714 |              63.5 |         0 |         0   |        18 |         1.6 | []                     |
| Single-call | L1      | 1125 |    347 |     30.8 |             10 |              0.9 |               216 |                19.2 |             530 |              47.1 |         1 |         0.1 |        21 |         1.9 | []                     |
| Single-call | L2      | 1125 |    217 |     19.3 |             20 |              1.8 |               145 |                12.9 |             726 |              64.5 |         0 |         0   |        17 |         1.5 | []                     |
| Single-call | L3      | 1125 |    112 |     10   |             29 |              2.6 |                76 |                 6.8 |             892 |              79.3 |         1 |         0.1 |        15 |         1.3 | []                     |
| Two-stage   | L0      | 1125 |    276 |     24.5 |              4 |              0.4 |               183 |                16.3 |             646 |              57.4 |         0 |         0   |        16 |         1.4 | []                     |
| Two-stage   | L1      | 1125 |    422 |     37.5 |              5 |              0.4 |               169 |                15   |             505 |              44.9 |         0 |         0   |        24 |         2.1 | []                     |
| Two-stage   | L2      | 1125 |    304 |     27   |              6 |              0.5 |               143 |                12.7 |             656 |              58.3 |         0 |         0   |        16 |         1.4 | []                     |
| Two-stage   | L3      | 1125 |    184 |     16.4 |             12 |              1.1 |               104 |                 9.2 |             799 |              71   |         0 |         0   |        26 |         2.3 | []                     |

## 4. Wilson 95% CIs for Experiment A Table 1

| Model                         | Pipeline    |   N |   Pass |   Pass@1_% |   Wilson_lo |   Wilson_hi |
|:------------------------------|:------------|----:|-------:|-----------:|------------:|------------:|
| Qwen3-4B-Thinking-2507        | Single-call | 210 |    181 |      86.19 |       80.87 |       90.21 |
| Qwen3-4B-Thinking-2507        | Two-stage   | 210 |    171 |      81.43 |       75.62 |       86.11 |
| Qwen3.5-4B                    | Single-call | 210 |    164 |      78.1  |       72.02 |       83.16 |
| Qwen3.5-4B                    | Two-stage   | 210 |    154 |      73.33 |       66.97 |       78.86 |
| gemma-4-E4B-it                | Single-call | 210 |    102 |      48.57 |       41.9  |       55.3  |
| gemma-4-E4B-it                | Two-stage   | 210 |    143 |      68.1  |       61.51 |       74.03 |
| granite-4.0-micro             | Single-call | 210 |    117 |      55.71 |       48.95 |       62.27 |
| granite-4.0-micro             | Two-stage   | 210 |    101 |      48.1  |       41.43 |       54.83 |
| Ministral-3-3B-Reasoning-2512 | Single-call | 210 |    110 |      52.38 |       45.64 |       59.03 |
| Ministral-3-3B-Reasoning-2512 | Two-stage   | 210 |     76 |      36.19 |       29.99 |       42.88 |

## 5a. McNemar (paired) Single-call vs Two-stage, Experiment A, Holm-Bonferroni over 5 models

| Model                         |   n_common |   both_pass |   both_fail |   single_only_pass |   two_stage_only_pass |   odds_ratio_single_over_two |   statistic |     p_value |      p_holm | significant_holm_0.05   |
|:------------------------------|-----------:|------------:|------------:|-------------------:|----------------------:|-----------------------------:|------------:|------------:|------------:|:------------------------|
| Qwen3-4B-Thinking-2507        |        210 |         153 |          11 |                 28 |                    18 |                      1.55556 |          18 | 0.183925    | 0.36785     | False                   |
| Qwen3.5-4B                    |        210 |         125 |          17 |                 39 |                    29 |                      1.34483 |          29 | 0.27499     | 0.36785     | False                   |
| gemma-4-E4B-it                |        210 |          76 |          41 |                 26 |                    67 |                      0.38806 |          26 | 2.52582e-05 | 0.000126291 | True                    |
| granite-4.0-micro             |        210 |          75 |          67 |                 42 |                    26 |                      1.61538 |          26 | 0.0681187   | 0.204356    | False                   |
| Ministral-3-3B-Reasoning-2512 |        210 |          55 |          79 |                 55 |                    21 |                      2.61905 |          21 | 0.000120629 | 0.000482516 | True                    |

## 5b. McNemar (paired) Single-call vs Two-stage, Experiment B, Holm-Bonferroni over 15 model x tier tests

| Model                         | Tier   |   n_common |   both_pass |   both_fail |   single_only_pass |   two_stage_only_pass |   odds_ratio_single_over_two |   statistic |     p_value |      p_holm | significant_holm_0.05   |
|:------------------------------|:-------|-----------:|------------:|------------:|-------------------:|----------------------:|-----------------------------:|------------:|------------:|------------:|:------------------------|
| Qwen3-4B-Thinking-2507        | A      |        300 |          28 |         209 |                 31 |                    32 |                     0.96875  |          31 | 1           | 1           | False                   |
| Qwen3-4B-Thinking-2507        | B      |        300 |          31 |         220 |                 26 |                    23 |                     1.13043  |          23 | 0.77545     | 1           | False                   |
| Qwen3-4B-Thinking-2507        | C      |        300 |          28 |         240 |                 23 |                     9 |                     2.55556  |           9 | 0.0200616   | 0.202767    | False                   |
| Qwen3.5-4B                    | A      |        300 |          29 |         175 |                 36 |                    60 |                     0.6      |          36 | 0.0184334   | 0.202767    | False                   |
| Qwen3.5-4B                    | B      |        300 |          33 |         186 |                 37 |                    44 |                     0.840909 |          37 | 0.505236    | 1           | False                   |
| Qwen3.5-4B                    | C      |        300 |          24 |         199 |                 33 |                    44 |                     0.75     |          33 | 0.254305    | 1           | False                   |
| gemma-4-E4B-it                | A      |        300 |          40 |         150 |                 25 |                    85 |                     0.294118 |          25 | 7.83222e-09 | 1.09651e-07 | True                    |
| gemma-4-E4B-it                | B      |        300 |          35 |         138 |                 26 |                   101 |                     0.257426 |          26 | 1.24366e-11 | 1.86549e-10 | True                    |
| gemma-4-E4B-it                | C      |        300 |          62 |         110 |                 60 |                    68 |                     0.882353 |          60 | 0.536269    | 1           | False                   |
| granite-4.0-micro             | A      |        300 |          36 |         155 |                 55 |                    54 |                     1.01852  |          54 | 1           | 1           | False                   |
| granite-4.0-micro             | B      |        300 |          21 |         189 |                 21 |                    69 |                     0.304348 |          21 | 3.88182e-07 | 5.04636e-06 | True                    |
| granite-4.0-micro             | C      |        300 |          22 |         187 |                 28 |                    63 |                     0.444444 |          28 | 0.000312839 | 0.00375407  | True                    |
| Ministral-3-3B-Reasoning-2512 | A      |        300 |           8 |         220 |                 29 |                    43 |                     0.674419 |          29 | 0.124918    | 1           | False                   |
| Ministral-3-3B-Reasoning-2512 | B      |        300 |          10 |         221 |                 32 |                    37 |                     0.864865 |          32 | 0.630456    | 1           | False                   |
| Ministral-3-3B-Reasoning-2512 | C      |        300 |          11 |         227 |                 26 |                    36 |                     0.722222 |          26 | 0.252854    | 1           | False                   |

## 6. Mutation score: conditional (cMut) vs unconditional (uMut), Experiment A

| Model                         | Pipeline    |   N |   n_mutation_completed |   cMut_%_conditional_on_pass |   uMut_%_unconditional |
|:------------------------------|:------------|----:|-----------------------:|-----------------------------:|-----------------------:|
| Qwen3-4B-Thinking-2507        | Single-call | 210 |                     54 |                        21.6  |                   5.55 |
| Qwen3-4B-Thinking-2507        | Two-stage   | 210 |                     55 |                        23.15 |                   6.06 |
| Qwen3.5-4B                    | Single-call | 210 |                     57 |                        15.43 |                   4.19 |
| Qwen3.5-4B                    | Two-stage   | 210 |                     48 |                        21.71 |                   4.96 |
| gemma-4-E4B-it                | Single-call | 210 |                     34 |                        25.55 |                   4.14 |
| gemma-4-E4B-it                | Two-stage   | 210 |                     45 |                        24.29 |                   5.21 |
| granite-4.0-micro             | Single-call | 210 |                     37 |                        23.39 |                   4.12 |
| granite-4.0-micro             | Two-stage   | 210 |                     34 |                        22.92 |                   3.71 |
| Ministral-3-3B-Reasoning-2512 | Single-call | 210 |                     35 |                        13.94 |                   2.32 |
| Ministral-3-3B-Reasoning-2512 | Two-stage   | 210 |                     23 |                        22.62 |                   2.48 |

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

## 8. Logistic regression, Pass ~ leaked + CC + LOC + level (cluster-robust SE by task_num; N=9000 obs, 300 clusters)

|       coef |   std_err_cluster |         z |     p_value |   odds_ratio |   OR_ci_lo |   OR_ci_hi |
|-----------:|------------------:|----------:|------------:|-------------:|-----------:|-----------:|
| -1.31379   |        0.167266   | -7.85449  | 4.01416e-15 |     0.2688   |   0.193666 |   0.373084 |
|  0.488161  |        0.173185   |  2.81873  | 0.00482139  |     1.62932  |   1.16035  |   2.28781  |
| -0.0253881 |        0.162088   | -0.156631 | 0.875535    |     0.974931 |   0.709584 |   1.3395   |
| -0.728893  |        0.166132   | -4.38744  | 1.14691e-05 |     0.482443 |   0.348365 |   0.668124 |
|  0.527179  |        0.140346   |  3.75629  | 0.000172453 |     1.69415  |   1.28673  |   2.23056  |
|  0.0585332 |        0.0164005  |  3.56898  | 0.000358371 |     1.06028  |   1.02674  |   1.09492  |
| -0.013035  |        0.00433911 | -3.00408  | 0.00266385  |     0.98705  |   0.978691 |   0.99548  |

## 9a. Historical vs Recent pool -- CC/LOC balance

|   ('cyclomatic_complexity', 'mean') |   ('cyclomatic_complexity', 'median') |   ('cyclomatic_complexity', 'std') |   ('cyclomatic_complexity', 'min') |   ('cyclomatic_complexity', 'max') |   ('loc', 'mean') |   ('loc', 'median') |   ('loc', 'std') |   ('loc', 'min') |   ('loc', 'max') |
|------------------------------------:|--------------------------------------:|-----------------------------------:|-----------------------------------:|-----------------------------------:|------------------:|--------------------:|-----------------:|-----------------:|-----------------:|
|                             5.5     |                                     5 |                            2.55449 |                                  3 |                                 12 |           24.65   |                21.5 |          14.9063 |                5 |               73 |
|                             5.77083 |                                     4 |                            3.89957 |                                  3 |                                 23 |           25.0625 |                20   |          16.6944 |                5 |               75 |

## 9b. Historical vs Recent pool -- dependency-level distribution (row %)

|    L0 |    L1 |   L2 |    L3 |
|------:|------:|-----:|------:|
| 10    | 26.67 | 35   | 28.33 |
| 28.75 | 24.58 | 22.5 | 24.17 |

## 9c. Historical vs Recent pool -- domain distribution (row %)

|   cli |   data |    ml |   serialization |   web |
|------:|-------:|------:|----------------:|------:|
| 13.33 |  20    | 31.67 |            0    | 35    |
| 31.25 |  30.83 | 12.92 |            8.33 | 16.67 |

## 9d. Pool sizes (unique tasks)

|   n_unique_tasks |
|-----------------:|
|              240 |
|               60 |
