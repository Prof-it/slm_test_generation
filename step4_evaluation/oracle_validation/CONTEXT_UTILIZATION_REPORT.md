# Context-Utilization Analysis (Tier B/C dependency stubs and mock hints)

## Status: complete

Answers the supervisor's concern directly: does the paper's "context tier did not
help" finding reflect models genuinely engaging with the extra material and failing
to benefit, or extra context that was simply never used? Both, it turns out, but
mostly the latter — a large share of generated tests never reference the material
Tier B/C actually supplied.

Script: `step4_evaluation/context_utilization_analysis.py`. Fully isolated — reuses
`evaluate_results.py`'s own `_combine_tests_for_task`/`strip_markdown` helpers,
imported not reimplemented; does not modify `evaluate_results.py`, `assertion_gate.py`,
`gated_reanalysis.py`, `oracle_analysis.py`, or any legacy result/paper file.

## Method (static, associational — measures *reference*, not *correct use*)

- Tier B/C predictions carry their own `context_card` field (the exact text sent to
  the model), so no separate lookup table is needed.
- **Dependency-stub usage:** parse every `def <name>(` inside the `"--- Dependency
  stubs ---"` section of `context_card['B']['text']`; a test "uses" the context if
  any stub name appears as a whole-word token anywhere in the generated, combined
  test source.
- **Mock-hint usage:** parse the `patch '<target>'` string from
  `context_card['C']['text']` (e.g. `requests.get`, `os.environ`, `http.client`);
  a test "uses" the hint if that target string (or its trailing attribute name)
  appears in the test source. For the generic fallback hint (no specific pattern
  detected upstream), usage is credited if the test calls `unittest.mock.patch`,
  `MagicMock`, or otherwise touches `unittest.mock` at all.
- Tier A is excluded by construction — it carries no dependency stubs or mock hints
  to utilize.
- Joined against the same evaluated jsonl files RQ3's dependency-level script uses,
  for model x pipeline x tier x dependency-level x execution-pass-status breakdowns.
- 5,901 (task_num, model, pipeline, tier) rows analyzed across both tiers.

## Headline numbers

| | Dependency-stub used | Mock-hint used |
|---|---:|---:|
| Tier B (n=808 with stubs supplied) | 59.0% | n/a |
| Tier C (n=802 with stubs; n=2,943 with a hint) | 61.7% | 72.6% |

So roughly **2 in 5 Tier B/C generations never touch the dependency stubs at all**,
even though the stubs were placed directly in the prompt. Mock-hint usage is higher
(72.6%) but still leaves over a quarter of Tier C generations ignoring the hint
entirely.

## By model x pipeline (Tier B, dependency-stub usage)

Usage varies enormously by model and, within a model, by pipeline — this is not a
uniform "context ignored" story:

| Model | Single-step | Two-step |
|---|---:|---:|
| Qwen3-4B-Thinking | 76.5% | 80.2% |
| gemma-4-E4B-it | 78.0% | 51.9% |
| Qwen3.5-4B | 73.2% | 42.3% |
| Ministral-3-3B-Reasoning | 74.1% | 46.8% |
| granite-4.0-micro | 50.6% | 15.9% |

Two-step pipelines consistently use dependency context *less* than single-step for
every model except Qwen3-4B-Thinking — plausible mechanism: by the second stage the
dependency stubs are further back in the running context, or the two-step prompt
restructuring de-emphasizes them. granite-4.0-micro is the extreme case: 15.9%
dependency-stub usage on two-step, the lowest of any cell.

## By execution-pass status (associational only — not causal)

| Tier | Failed suites | Passed suites |
|---|---:|---:|
| B, dependency-stub used | 61.1% | 46.4% |
| C, dependency-stub used | 62.9% | 55.7% |
| C, mock-hint used | 76.0% | 61.4% |

**Passing suites use the supplied context *less* than failing suites, in every
comparison.** This does not mean using context causes failure — plausibly, tasks
solvable without engaging the dependency material are also the easier tasks to pass
in general, and harder tasks (higher genuine need for the stubs/hints) are also
harder to pass regardless of whether the context was used. But it does directly
rule out the naive alternative explanation for the paper's tier-based "context
tier does not reliably improve Pass@1" finding — it is not simply that models
"tried to use the context and failed anyway"; a large fraction of the extra
material supplied is not engaged with by the generated test at all, whether the
suite ultimately passes or not. This should be reported as an association, not a
causal claim about context use hurting outcomes.

## By dependency level (Tier B/C, dependency-stub usage)

| Level | Tier B | Tier C |
|---|---:|---:|
| L0 | 56.4% | 68.8% |
| L1 | 71.1% | 72.9% |
| L2 | 44.9% | 44.9% |
| L3 | 57.4% | 58.6% |

Not monotonic in dependency level — L2 has the lowest usage rate in both tiers,
L1 the highest. (L0 tasks having any measurable "dependency-stub usage" at all
reflects that the stub-detection heuristic in `build_context_cards.py` is based on
observed call sites in the focal function, which is a weaker signal than the
benchmark's own L0-L3 dependency-level label; the two classifications are related
but not identical by design.)

## Full breakdown

Per-row data (5,901 rows: model, pipeline, tier, dependency_level, passed,
has_dep_stubs, dep_used, has_mock_hint, mock_used) in
`step4_evaluation/oracle_validation/context_utilization_rows.json` for anyone
wiring additional cuts into the paper.

## What this does and does not license

- **Does license:** the paper's Discussion/RQ (context-tier) section citing actual
  usage rates rather than treating context tier purely as an input condition;
  reporting the pass/fail usage association as suggestive evidence against the
  "models engaged with context and it just didn't help" reading, in favor of
  "much of the supplied context goes unused, which is itself part of why tier
  assignment alone doesn't predict Pass@1."
- **Does not license:** any causal claim that using context reduces Pass@1, or
  that not using context is a "failure" of the model — some tasks are genuinely
  solvable without the dependency material, and usage vs. non-usage is not the
  same as correct vs. incorrect use.
- **Does not license:** touching mutation, coverage, or the oracle-taxonomy Pass@1
  gates — this pass is scoped to context-material reference detection only.
