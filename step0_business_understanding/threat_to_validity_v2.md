# Threats to Validity — RealWorldTests-Py v2

## Internal Validity

### Tier B context inflation is limited for L0/L1/L2 functions (72% of dataset)
The dependency-stub builder (Phase 4) extracts stubs only for same-file function/class
definitions referenced by the focal function. For L0 (builtins), L1 (stdlib), and L2
(third-party) functions, there are no same-file stubs to extract, so Tier B card ==
Tier A card for 215/300 functions (72%). The A→B ablation only has statistical power
on the 85 L3 functions. This is disclosed in the analysis: the A→B effect is reported
separately for L3 (meaningful comparison) vs L0/L1/L2 (trivially zero difference).

**Mitigation (future work):** Extend Tier B to include third-party API stubs fetched
from the installed package (stub generators like `mypy stubgen` or `pyright`).

### Async functions require asyncio.run() in generated tests
26/300 focal functions are async. The evaluation harness (pytest) does not install
pytest-asyncio. The system prompts instruct models to wrap async calls in
`asyncio.run()`, but a model that generates `async def test_X():` will produce a test
that pytest silently skips. Results for async functions may understate model capability.

**Mitigation:** System prompts explicitly forbid async test functions and require
`asyncio.run()`. Reported pass-rates for async functions should be read as a lower bound.

### Contamination split is 20% leaked / 80% unleaked (target was 50/50)
The per-repo cap (max 15 functions per repo) reduces the leaked contribution because
the leaked pool has only 80 candidates across 12 repos. With the cap, at most 60 leaked
functions can be selected (4 levels × 15 = 60). The unleaked pool is large enough to
fill the remaining 240 slots. The 20/80 split provides better statistical power for the
unleaked side but limits the contamination gap estimate on the leaked side.

**Mitigation:** The contamination analysis reports both point estimates and CIs. The
leaked results should be interpreted as preliminary (n=60 per split) with wider CIs.

### Dependency level classification uses heuristic AST analysis
Phase 3 uses a heuristic import-map classifier rather than full jedi inference (which
would be correct for aliases, dynamic imports, and monkeypatching). Manual audit of 30
items showed 90% agreement (3 disagreements, none in final 300). The 3 errors were all
in the same repo (tyxak/remotepower) and suggest the heuristic misses `self.x` patterns
when `x` is a network client. The published dataset labels should be treated as
approximate for L0/L3 boundary cases.

### Single-call coverage target (target_lines=[1])
The inference script prompts models to "cover line 1" of the tier card, which is always
the function's `def` line. This is satisfied by any call to the function, so the
coverage guidance is weaker than in the original TestEval (which targets specific
branches). Tests generated for v2 may be broader but shallower than targeted-line tests.

## External Validity

### Domain distribution is uneven
- data: 86 (29%), cli: 83 (28%), web: 61 (20%), ml: 50 (17%), serialization: 20 (7%)
Serialization is underrepresented because fewer recently-active repos with MIT/Apache
licenses publish in this domain on GitHub. Results for the serialization domain have
wider CIs and should be treated as exploratory.

### Fail-to-pass subset is empty
Automated mining of bug-fix commits across 25 full-history repos yielded 0 qualified
pairs. The recently-active repos selected for the unleaked pool follow agile commit
patterns (many small commits) rather than the "fix bug + add test in same commit"
pattern found in mature OSS projects. The regression-catching metric is not reported
for v2; this is listed as future work.

### Leaked pool is a known limitation
The 12 leaked repos (scikit-learn, requests, pandas, etc.) are well-known Python
libraries that appear in virtually all LLM pretraining corpora. They serve as a
contamination floor: performance on leaked functions provides an upper bound estimate
of what a model can achieve by memorisation. The leaked/unleaked gap measures
contamination but cannot be attributed solely to memorisation (the leaked functions may
also be structurally simpler).
