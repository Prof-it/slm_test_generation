# Pynguin Historical-vs-Recent Negative Control

## Status: complete

Pynguin has no pretraining-data exposure to any task in this benchmark (it is a search-based generator, not a language model), so it cannot exhibit training-data memorization. Comparing its historical-pool vs. recent-pool Pass@1 tests whether the SLM cohort's historical-pool advantage (Section RQ3, OR=1.69 clean set) reflects a task-intrinsic property of the historical pool (which would also affect Pynguin) or is specific to LLM memorization (which would not).

## Raw pooled Pass@1, clean set (n=562 obs = 300 tasks x 2 seeds, 19 broken tasks excluded)

- Historical pool (n=120): 55.83%
- Recent pool (n=442): 49.10%
- Raw gap: +6.74 points

## Logistic regression (passed ~ leaked + cc + loc + C(level)), clustered by task_num

| Spec                                     |   N_obs |   N_clusters |   OR_leaked_historical |   OR_ci_lo |   OR_ci_hi |   p_value |
|:-----------------------------------------|--------:|-------------:|-----------------------:|-----------:|-----------:|----------:|
| Full set (600 obs = 300 tasks x 2 seeds) |     600 |          300 |                  1.431 |      0.799 |      2.562 |  0.227749 |
| Clean set (19 broken tasks excluded)     |     562 |          281 |                  1.19  |      0.659 |      2.149 |  0.56442  |

## Interpretation

The result is directionally consistent but statistically inconclusive, and should not be read as confirming either explanation cleanly. Pynguin's historical pool has a higher raw Pass@1 (55.83% vs. 49.10%, +6.74 points) and a positive odds ratio in both specifications (1.43 full set, 1.19 clean set) — the same direction as the SLM cohort's OR=1.69. But neither Pynguin estimate reaches significance (p=0.23 full set, p=0.56 clean set), and the 95% CIs are wide and include 1 in both cases (clean set: [0.66, 2.15]).

This is most plausibly an underpowered comparison rather than a genuine null: the SLM regression pools 9,000 observations across 30 model/pipeline/tier configurations sharing 300 tasks, while this comparison has only 300 tasks x 2 seeds (562 clean-set observations after exclusions), an order of magnitude less statistical power to detect the same effect size. A positive, non-significant OR of similar direction to but smaller magnitude than the SLM figure is consistent with a real but modest task-intrinsic component to the historical-pool advantage (which would also affect a non-memorizing tool like Pynguin) existing alongside a memorization-specific component that inflates the SLM cohort's effect further — but the data here cannot distinguish that combined story from pure sampling noise around a true null for Pynguin. We report this as a directionally suggestive but non-significant negative control, not as confirmation that the SLM recency effect is (or is not) task-intrinsic.
