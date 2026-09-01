# Tests That Run but Do Not Test

### Assertion gating and small language models for Python unit-test generation

[![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Artifact](https://img.shields.io/badge/artifact-research%20replication-6f42c1)](#replication-guide)

This repository is the replication package for an empirical study of automated
Python unit-test generation with five open-weight small language models (SLMs,
at most 5B parameters). The study asks a deliberately stricter question than
whether generated tests merely execute: **did a passing test actually reach a
non-trivial oracle?**

The package contains the two benchmarks, context-tier construction pipeline,
stored model generations, isolated execution harness, assertion and oracle
classifiers, mutation-analysis outputs, statistical analyses, Pynguin baseline,
and blinded manual-validation materials.

> **Release status:** pre-publication research artifact. The experiment outputs
> are frozen, but the manuscript and second-rater agreement results are still
> being finalised. See [Known limitations](#known-limitations) before reusing the
> reported estimates.

## Study at a glance

| Dimension | Design |
|---|---|
| Benchmarks | TestEval (210 algorithmic tasks) and TestContextBench-Py (300 real-world functions) |
| Primary real-world analysis | 281 importable tasks; 8,430 SLM generations |
| Models | 5 open-weight checkpoints, each at most 5B parameters |
| Prompting | Single-step generation and Two-step planning |
| Context | Tiers A, B, and C, from focal-only context to dependency stubs and mock hints |
| Dependency strata | L0 built-ins/literals, L1 standard library, L2 third party, L3 project local |
| Primary quality outcome | Runtime Non-trivial Pass@1: passing execution plus at least one runtime-reached WEAK or STRONG oracle |
| Baseline | Pynguin SIMPLE mode, 60-second budget, 2 seeds |
| Execution environment | Network-isolated Python 3.10 Docker harness |

### Headline results

- Runtime assertion gating removes **11.30%** of TestEval execution passes and
  **44.95%** of defect-excluded real-world execution passes.
- On the 67-task retained real-world mutation subset, unconditional mutation
  score (uMut) ranges from **1.58% to 5.46%** across the ten model-pipeline
  configurations.
- On the real-world benchmark, the strongest Execution Pass@1 configuration
  reaches **43.53%**, whereas the strongest Runtime Non-trivial Pass@1
  configuration reaches **22.06%**.
- The richer context tiers span only **2.1 percentage points** in pooled
  defect-excluded Execution Pass@1.

These are descriptive results for the frozen study cohort, not general performance
guarantees for all SLMs. Machine-readable supporting tables are under
[`step4_evaluation/oracle_validation/clean_set_reanalysis/`](step4_evaluation/oracle_validation/clean_set_reanalysis/).

## Artifact map

| Location | Contents |
|---|---|
| [`TestEval/data/`](TestEval/data/) | TestEval and TestContextBench-Py datasets, including context-tier variants |
| [`sources/`](sources/) | Source-repository metadata, candidate functions, audits, and exclusion information |
| [`cards/`](cards/) | Materialised context cards used for real-world prompting |
| [`downloaded_predictions/`](downloaded_predictions/) | Frozen generated-test outputs used by the final analyses |
| [`evaluation_results/`](evaluation_results/) | Executed-suite results for SLM and Pynguin experiments |
| [`step2_data_preperation/`](step2_data_preperation/) | Dataset extraction, dependency classification, and context construction |
| [`step3_modelling/`](step3_modelling/) | Inference orchestration and judge-related tooling |
| [`step4_evaluation/`](step4_evaluation/) | Execution, oracle analysis, mutation analysis, statistics, and reports |
| [`step5_deployment/`](step5_deployment/) | Pinned Docker definitions and evaluation requirements |
| [`manual_validation/`](manual_validation/) | Blinded second-rater packages, protocols, provenance, and agreement tooling |
| [`paper/`](paper/) | Manuscript-supporting tables and figures mirrored in the repository |
| [`tests/`](tests/) | Regression and package-integrity tests |
| [`gold/`](gold/) | Explanation of the intentionally empty fail-to-pass artifact |

## Replication guide

### 1. Clone and create an environment

```bash
git clone https://github.com/Prof-it/slm_test_generation.git
cd slm_test_generation
python -m venv .venv
```

Activate the environment, then install the project dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The final evaluation harness targets Python 3.10. Dataset and analysis utilities may
run on newer Python versions, but result reproduction should use the pinned Docker
environment rather than relying on the host interpreter.

### 2. Build the isolated evaluation image

```bash
docker build \
  -f step5_deployment/Dockerfile.evaluate_results_v2 \
  -t slm-test-evaluation:v2 .
```

The harness disables network access when executing generated tests. Exact experiment
configuration is recorded alongside the scripts in
[`step4_evaluation/`](step4_evaluation/) and the Docker definitions in
[`step5_deployment/`](step5_deployment/).

### 3. Inspect or rebuild analysis artefacts

The final paper-facing outputs are already committed. The principal analysis entry
points are:

```bash
python step4_evaluation/rq_reanalysis.py
python step4_evaluation/full_corpus_oracle_reanalysis.py
python step4_evaluation/clean_set_reanalysis.py
```

These scripts consume the frozen datasets, predictions, and evaluation outputs in
this repository. Some full recomputations are CPU- and storage-intensive; mutation
testing is substantially slower than table regeneration.

### 4. Run repository checks

```bash
python -m pytest tests/test_manual_validation_packages.py \
  tests/test_step4_evaluation/test_oracle_analysis.py
```

## Manual validation and second-rater workflow

Two independent-review packages are indexed in
[`manual_validation/README.md`](manual_validation/README.md):

1. **Dependency levels:** 30 focal functions rated as L0-L3.
2. **Oracle classes:** 250 generated-test oracle sites rated as TRIVIAL, WEAK,
   STRONG, or UNKNOWN.

For an independent rating, provide only the relevant `PROTOCOL.md` and
`second_rater_sheet.csv`. Do not expose `first_rater_labels.csv` or automated
classifier predictions before the second rater has returned a completed sheet.

After rating:

```bash
python manual_validation/calculate_agreement.py dependency_levels
python manual_validation/calculate_agreement.py oracle_classes
```

The calculator reports the original sample size, paired/rateable denominator,
administrative exclusions, raw agreement, and unweighted Cohen's kappa. Agreement is
calculated from the original independent ratings before adjudication. The package
builder refuses to overwrite sheets containing reviewer responses.

See [`manual_validation/VALIDATION_REPORT.md`](manual_validation/VALIDATION_REPORT.md)
for the sampling and provenance audit.

## Benchmark construction

TestContextBench-Py contains 300 functions balanced across four dependency levels
(75 per level), with a global cap of 15 functions per source repository. Eligible
functions have a non-empty docstring, cyclomatic complexity of at least 3, and 3-80
lines of code. The three nested context tiers are:

- **Tier A:** focal signature and docstring.
- **Tier B:** Tier A plus same-file dependency stubs without implementations.
- **Tier C:** Tier B plus mock and fixture hints.

The frozen design is recorded in [`design.yaml`](design.yaml). The public dataset is
[`TestEval/data/realworld-py-v2.jsonl`](TestEval/data/realworld-py-v2.jsonl), with
tier-specific variants in the same directory.

## Metric definitions

- **Execution Pass@1:** the generated suite finishes with `pytest` exit code 0.
- **Static-presence Pass@1:** an execution pass containing an assertion-like Abstract
  Syntax Tree construct; retained as a legacy sensitivity measure.
- **Runtime Non-trivial Pass@1:** an execution pass with at least one runtime-reached
  oracle classified as WEAK or STRONG. This is the primary assertion-quality outcome.
- **Conditional mutation score (cMut):** mutation score among passing suites only;
  its denominator varies by configuration.
- **Unconditional mutation score (uMut):** non-passing suites in the common mutation
  sample receive zero mutation credit, preserving the same task population across
  configurations.

## Known limitations

- Nineteen real-world reference modules fail the frozen Python 3.10 importability
  audit independently of generated-suite outcomes. Primary real-world results use the
  same 281-task exclusion manifest for every configuration; full-sample and alternative
  exclusion analyses are retained as sensitivities.
- The 73-task real-world mutation sample contains six of those excluded tasks, leaving
  67 tasks in the primary defect-excluded mutation analysis. The sample is not powered
  to rank configurations separated by only a few percentage points.
- The dependency-validation evidence is complete for all 30 reviewed items, but the
  original historical candidate snapshot and ordering are unavailable. The reviewed
  row set can be inspected and re-rated; the original seed-42 draw cannot be replayed
  exactly.
- The oracle-class sample is exactly reproducible from the recorded 6,879-site
  population, sampling script, stratification procedure, and seed 20260821.
- Automated fail-to-pass mining produced zero qualifying pairs. No fail-to-pass metric
  is reported; [`gold/README.md`](gold/README.md) documents the empty artifact.
- Human-human agreement values remain pending until the blinded second-rater exercise
  is complete. Historical classifier-versus-first-rater agreement must not be presented
  as inter-rater agreement.

## Reuse and citation

The manuscript is under review. Until its final bibliographic record is available,
please cite this repository and pin the exact Git commit used in your analysis:

```text
Özer, C. B., and Lu, T. Tests That Run but Do Not Test:
Rethinking Correctness Metrics for Small Language Models in Python Unit Test
Generation. Research artifact, 2026.
https://github.com/Prof-it/slm_test_generation
```

When reusing TestContextBench-Py, also retain each task's source-repository, commit,
path, and license metadata.

## License

Repository code is released under the [Apache License 2.0](LICENSE). Third-party
datasets, source snippets, model outputs, and cloned project material remain subject
to their original licenses and terms. Consult the per-item metadata before
redistribution.

## Contact

- Cahit Barkın Özer — `c.barkinozer@gmail.com`
- Tianxiang Lu — `tianxiang.lu@iu.org`
