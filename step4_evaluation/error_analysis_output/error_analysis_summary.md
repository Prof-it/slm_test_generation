# Manual Error Analysis — Summary Report

This report summarizes the manually categorized failure analysis across
all datasets and models.


---

## TestEval — Initial Experiment (T=0.0, N=1, all 11 SLMs + Pynguin)

**Total failures analyzed:** 232

### Overall Root Cause Distribution

| Root Cause | Count | % |
|---|---|---|
| IncorrectAssertion | 135 | 58.2% |
| SemanticMisunderstanding | 73 | 31.5% |
| APIHallucination | 8 | 3.4% |
| MissingDefinition | 8 | 3.4% |
| MalformedSyntax | 6 | 2.6% |
| MissingImport | 2 | 0.9% |

### Overall Proximity to Success

| Proximity | Count | % |
|---|---|---|
| high | 131 | 56.5% |
| near | 86 | 37.1% |
| moderate | 1 | 0.4% |
| low | 8 | 3.4% |
| far | 6 | 2.6% |

### Root Cause by Model (counts)

| Root Cause | Llama-3.2-3B-Instruct | Meta-Llama-3.1-8B-Instruct-AWQ-INT4 | Ministral-3-3B-Instruct-2512 | Ministral-3-3B-Reasoning-2512 | Ministral-3-8B-Instruct-2512-AWQ-4bit | Ministral-3-8B-Instruct-2512-AWQ-8bit | Qwen3-4B-Instruct-2507 | Qwen3-4B-Thinking-2507 | Qwen3-8B-AWQ | gemma-3-4b-it | granite-4.0-micro | pynguin_results |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IncorrectAssertion | 10 | 11 | 10 | 10 | 10 | 10 | 13 | 10 | 14 | 12 | 10 | 15 |
| SemanticMisunderstanding | 5 | 7 | 8 | 9 | 9 | 6 | 6 | 6 | 1 | 6 | 10 | 0 |
| APIHallucination | 2 | 0 | 2 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 0 | 0 |
| MissingDefinition | 3 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| MalformedSyntax | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 5 | 0 | 0 | 0 |
| MissingImport | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 17 | 20 | 20 | 20 | 15 |

### Proximity to Success by Model

| Proximity | Llama-3.2-3B-Instruct | Meta-Llama-3.1-8B-Instruct-AWQ-INT4 | Ministral-3-3B-Instruct-2512 | Ministral-3-3B-Reasoning-2512 | Ministral-3-8B-Instruct-2512-AWQ-4bit | Ministral-3-8B-Instruct-2512-AWQ-8bit | Qwen3-4B-Instruct-2507 | Qwen3-4B-Thinking-2507 | Qwen3-8B-AWQ | gemma-3-4b-it | granite-4.0-micro | pynguin_results |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| high | 13 | 13 | 11 | 10 | 10 | 13 | 14 | 10 | 14 | 12 | 11 | 0 |
| near | 7 | 5 | 4 | 10 | 10 | 7 | 6 | 1 | 6 | 7 | 8 | 15 |
| moderate | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| low | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| far | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 0 | 0 |

#### Llama-3.2-3B-Instruct

- **Failures analyzed:** 20
- **Recurring failures:** 14

**Root Cause Breakdown:**

- IncorrectAssertion: 10 (50.0%) ██████████
- SemanticMisunderstanding: 5 (25.0%) █████
- MissingDefinition: 3 (15.0%) ███
- APIHallucination: 2 (10.0%) ██

**Proximity to Success:**

- high: 13 (65.0%)
- near: 7 (35.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (10 recurring):
  - Test asserts minDifference(...) == [9, 8] but correct answer is [1, 1]. (task: 1906)
  - Test asserts minimumOperations('125') == 3 but correct answer is 0. (task: 2844)
  - Test asserts numDifferentIntegers('123a7') == 3 but correct answer is 2. (task: 1805)
  - Test asserts maxPoints(...) == [1, 0, 1] but correct answer is [9, 7, 8]. (task: 2503)
  - Test asserts minimumIncompatibility(...) == 15 but correct answer is -1. (task: 1681)
  - ... and 5 more
- **MissingDefinition** (3 recurring):
  - Test calls solution.maxDistance(...) without instantiating the solution object. (task: 1162)
  - Test calls solution.resultGrid(...) without instantiating the solution object. (task: 3030)
  - Test calls solution.maxTrailingZeros(...) without instantiating the solution object. (task: 2245)
- **SemanticMisunderstanding** (1 recurring):
  - Test provides a time string of length 2 ("??") instead of the expected length 5 format ("HH:MM"), causing an IndexError. (task: 2437)

#### Meta-Llama-3.1-8B-Instruct-AWQ-INT4

- **Failures analyzed:** 20
- **Recurring failures:** 16

**Root Cause Breakdown:**

- IncorrectAssertion: 11 (55.0%) ███████████
- SemanticMisunderstanding: 7 (35.0%) ███████
- MissingImport: 2 (10.0%) ██

**Proximity to Success:**

- high: 13 (65.0%)
- near: 5 (25.0%)
- far: 2 (10.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (11 recurring):
  - Test asserts collectTheCoins(...) == 4 but correct answer is 0. (task: 2603)
  - Test asserts shortestBeautifulSubstring(...) == '001' but correct answer is '11'. (task: 2904)
  - Test asserts canMakePalindromeQueries(...) == [True, False] but correct answer is [True, True]. (task: 2983)
  - Test asserts checkIfPrerequisite(...) == [True, False, True] but correct answer is [True, True, True]. (task: 1462)
  - Test asserts maximumStrongPairXor([5, 10, 25]) == 29 but correct answer is 15. (task: 2932)
  - ... and 6 more
- **MissingImport** (2 recurring):
  - Test uses a placeholder from your_module import Solution which fails in the test harness. (task: 1938)
  - Test uses a placeholder from your_module import Solution which fails in the test harness. (task: 3072)
- **SemanticMisunderstanding** (3 recurring):
  - Test provides a receiver array containing value 10, which is out of bounds for an array of size 10 (indices 0-9), causing an IndexError. (task: 2836)
  - Test triggers an infinite loop or excessive computation, resulting in a timeout. (task: 310)
  - Test triggers an infinite loop or excessive computation, resulting in a timeout. (task: 786)

#### Ministral-3-3B-Instruct-2512

- **Failures analyzed:** 20
- **Recurring failures:** 16

**Root Cause Breakdown:**

- IncorrectAssertion: 10 (50.0%) ██████████
- SemanticMisunderstanding: 8 (40.0%) ████████
- APIHallucination: 2 (10.0%) ██

**Proximity to Success:**

- high: 11 (55.0%)
- near: 4 (20.0%)
- low: 5 (25.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (10 recurring):
  - Test asserts countPalindromicSubsequences('aaa') == 6 but correct answer is 3. (task: 730)
  - Test asserts findLengthOfShortestSubarray(...) == 2 but correct answer is 3. (task: 1574)
  - Test asserts maxGeneticDifference(...) == [4, 2, 6, 0] but correct answer is [5, 3, 7, 3]. (task: 1938)
  - Test asserts numberOfCombinations('123') == 1 but correct answer is 3. (task: 1977)
  - Test asserts kthSmallestProduct(...) == -10 but correct answer is -6. (task: 2040)
  - ... and 5 more
- **SemanticMisunderstanding** (6 recurring):
  - Test function is defined with a 'self' parameter which Pytest incorrectly tries to resolve as a fixture. (task: 2932)
  - Test function is defined with a 'self' parameter which Pytest incorrectly tries to resolve as a fixture. (task: 2851)
  - Test function is defined with a 'self' parameter which Pytest incorrectly tries to resolve as a fixture. (task: 1489)
  - Test function is defined with a 'self' parameter which Pytest incorrectly tries to resolve as a fixture. (task: 1786)
  - Test function is defined with a 'self' parameter which Pytest incorrectly tries to resolve as a fixture. (task: 3029)
  - ... and 1 more

#### Ministral-3-3B-Reasoning-2512

- **Failures analyzed:** 20
- **Recurring failures:** 14

**Root Cause Breakdown:**

- IncorrectAssertion: 10 (50.0%) ██████████
- SemanticMisunderstanding: 9 (45.0%) █████████
- MissingDefinition: 1 (5.0%) █

**Proximity to Success:**

- high: 10 (50.0%)
- near: 10 (50.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (10 recurring):
  - Test asserts trapRainWater(...) == 10 but correct answer is 3. (task: 407)
  - Test asserts threeSum(...) returns a list of lists but the function returns a list of tuples. (task: 15)
  - Test asserts maximumStrongPairXor([1, 2, 3]) == 2 but correct answer is 3. (task: 2932)
  - Test asserts minimumOperations([1, 2, 3], 0, 1) == 2 but correct answer is 1. (task: 2059)
  - Test asserts largestComponentSize(...) == 4 but correct answer is 8. (task: 952)
  - ... and 5 more
- **SemanticMisunderstanding** (4 recurring):
  - Test provides equations like "a=b" instead of "a==b" or "a!=b", causing a ValueError upon unpacking to 4 characters. (task: 990)
  - Test provides a time string of length 4 ("2?00") instead of the expected length 5 format ("HH:MM"), causing an IndexError. (task: 2437)
  - Test provides a receiver array containing value 5, which is out of bounds for an array of size 5, causing an IndexError. (task: 2836)
  - Test provides a time string of length 2 ("2?") instead of the expected length 5 format ("HH:MM"), causing an IndexError. (task: 2437)

#### Ministral-3-8B-Instruct-2512-AWQ-4bit

- **Failures analyzed:** 20
- **Recurring failures:** 16

**Root Cause Breakdown:**

- IncorrectAssertion: 10 (50.0%) ██████████
- SemanticMisunderstanding: 9 (45.0%) █████████
- MissingDefinition: 1 (5.0%) █

**Proximity to Success:**

- high: 10 (50.0%)
- near: 10 (50.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (10 recurring):
  - Test asserts palindromePairs(...) == [[0, 1], [1, 0]] but correct answer contains more pairs. (task: 336)
  - Test asserts reconstructMatrix(...) == [[1, 0, 0], [0, 1, 0]] but correct answer is an empty list []. (task: 1253)
  - Test asserts minimumMoves(...) == 5 but correct answer is inf (represented as a float in python). (task: 2850)
  - Test asserts mostProfitablePath(...) == 10 but correct answer is 13. (task: 2467)
  - Test asserts smallestSubsequence('abacaba', 5, 'a', 2) == 'aabac' but correct answer is 'aaaba'. (task: 2030)
  - ... and 5 more
- **MissingDefinition** (1 recurring):
  - Test calls solution.pathsWithMaxScore(...) without instantiating the solution object. (task: 1301)
- **SemanticMisunderstanding** (5 recurring):
  - Test provides a preferences array where node 2 prefers itself, causing a KeyError. (task: 1583)
  - Test provides equations like "a=b" and "a!d" instead of "a==b" or "a!=b", causing a ValueError upon unpacking to 4 characters. (task: 990)
  - Test provides a time string of length 4 ("1?15") instead of the expected length 5 format ("HH:MM"), causing an IndexError. (task: 2437)
  - Test uses 1-based node indices (up to 6) for a UnionFind initialized with size 6 (allowing only 0-5), causing an IndexError. (task: 2092)
  - Test provides a receiver array containing value 5, which is out of bounds for an array of size 5, causing an IndexError. (task: 2836)

#### Ministral-3-8B-Instruct-2512-AWQ-8bit

- **Failures analyzed:** 20
- **Recurring failures:** 15

**Root Cause Breakdown:**

- IncorrectAssertion: 10 (50.0%) ██████████
- SemanticMisunderstanding: 6 (30.0%) ██████
- APIHallucination: 3 (15.0%) ███
- MissingDefinition: 1 (5.0%) █

**Proximity to Success:**

- high: 13 (65.0%)
- near: 7 (35.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (10 recurring):
  - Test asserts minimumChanges('abxba', 2) == 1 but correct answer is 2. (task: 2911)
  - Test asserts findRedundantConnection(...) == [6, 1] but correct answer is [2, 3]. (task: 684)
  - Test asserts minimumTimeToInitialState('ababab', 2) == 2 but correct answer is 1. (task: 3029)
  - Test asserts reconstructMatrix(...) == [[1, 1, 1], [0, 1, 1]] but correct answer is an empty list []. (task: 1253)
  - Test asserts minCost(...) == 3 but correct answer is 4. (task: 1928)
  - ... and 5 more
- **MissingDefinition** (1 recurring):
  - Test calls solution.highestRankedKItems(...) without instantiating the solution object. (task: 2146)
- **SemanticMisunderstanding** (4 recurring):
  - Test provides a preferences array where node 3 prefers itself, causing a KeyError. (task: 1583)
  - Test provides a receiver array containing value 5, which is out of bounds for an array of size 5, causing an IndexError. (task: 2836)
  - Test provides equations like "a=b" instead of "a==b" or "a!=b", causing a ValueError upon unpacking to 4 characters. (task: 990)
  - Test provides an edge with node 4 but the amount array has size 4 (nodes 0-3), causing an IndexError. (task: 2467)

#### Qwen3-4B-Instruct-2507

- **Failures analyzed:** 20
- **Recurring failures:** 17

**Root Cause Breakdown:**

- IncorrectAssertion: 13 (65.0%) █████████████
- SemanticMisunderstanding: 6 (30.0%) ██████
- APIHallucination: 1 (5.0%) █

**Proximity to Success:**

- high: 14 (70.0%)
- near: 6 (30.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (13 recurring):
  - Test asserts countPalindromicSubsequences("aab") == 4 but correct answer is 3. (task: 730)
  - Test asserts checkPalindromeFormation("abc", "cba") == False but correct answer is True. (task: 1616)
  - Test asserts an incorrect expected grid for highestPeak. (task: 1765)
  - Test asserts minJumps(...) == 3 but correct answer is 1. (task: 1345)
  - Test asserts maximumGain('abba', 1, 2) == 4 but correct answer is 3. (task: 1717)
  - ... and 8 more
- **SemanticMisunderstanding** (4 recurring):
  - Test provides a preferences array where node 0 prefers itself, causing a KeyError. (task: 1583)
  - Test provides a receiver array containing value 5, which is out of bounds for an array of size 5, causing an IndexError. (task: 2836)
  - Test provides a preferences array where node 1 prefers itself and omits node 0, causing a KeyError. (task: 1583)
  - Test provides an edge with node 4 but the cost array size implies nodes 0-3, causing an IndexError. (task: 2973)

#### Qwen3-4B-Thinking-2507

- **Failures analyzed:** 17
- **Recurring failures:** 15

**Root Cause Breakdown:**

- IncorrectAssertion: 10 (58.8%) ██████████
- SemanticMisunderstanding: 6 (35.3%) ██████
- MalformedSyntax: 1 (5.9%) █

**Proximity to Success:**

- high: 10 (58.8%)
- near: 1 (5.9%)
- low: 3 (17.6%)
- far: 3 (17.6%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (10 recurring):
  - Test asserts threeSum(...) == [] but correct answer is [(-1, 0, 1)]. (task: 15)
  - Test asserts maxDistance(...) == 1 but correct answer is 2. (task: 1162)
  - Test asserts checkIfPrerequisite(...) == [False] but correct answer is [True]. (task: 1462)
  - Test asserts alertNames(...) == ['Test'] but correct answer is []. (task: 1604)
  - Test asserts matrixRankTransform(...) returns a 2x2 matrix but the correct answer is a 2x1 matrix [[1], [1]]. (task: 1632)
  - ... and 5 more
- **SemanticMisunderstanding** (5 recurring):
  - Model generates a test for twoSum instead of the requested gameOfLife function. (task: 289)
  - Model generates a snippet of internal function logic instead of a proper unit test calling the Solution class. (task: 1681)
  - Model generates a snippet of internal function logic instead of a proper unit test calling the Solution class. (task: 2132)
  - Model generates a snippet of internal function logic instead of a proper unit test calling the Solution class. (task: 2467)
  - Model generates a test for twoSum instead of the requested resultGrid function. (task: 3030)

#### Qwen3-8B-AWQ

- **Failures analyzed:** 20
- **Recurring failures:** 14

**Root Cause Breakdown:**

- IncorrectAssertion: 14 (70.0%) ██████████████
- MalformedSyntax: 5 (25.0%) █████
- SemanticMisunderstanding: 1 (5.0%) █

**Proximity to Success:**

- high: 14 (70.0%)
- near: 6 (30.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (14 recurring):
  - Test asserts reachableNodes(...) == 5 but correct answer is 4. (task: 882)
  - Test asserts knightProbability(...) == 0.125 but correct answer is 0.25. (task: 688)
  - Test asserts highestPeak([[1, 0], [0, 0]]) == [[0, 1], [1, -1]] but correct answer is [[0, 1], [1, 2]]. (task: 1765)
  - Test asserts minimumCost(3, [[0, 1, 1], [1, 2, 2]], [[0, 2]]) == [1] but correct answer is [0]. (task: 3108)
  - Test asserts waysToFillArray([[10, 2]]) == [1000000007] but correct answer is [10]. (task: 1735)
  - ... and 9 more

#### gemma-3-4b-it

- **Failures analyzed:** 20
- **Recurring failures:** 17

**Root Cause Breakdown:**

- IncorrectAssertion: 12 (60.0%) ████████████
- SemanticMisunderstanding: 6 (30.0%) ██████
- MissingDefinition: 2 (10.0%) ██

**Proximity to Success:**

- high: 12 (60.0%)
- near: 7 (35.0%)
- far: 1 (5.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (12 recurring):
  - Test asserts numberOfGoodSubsets([1, 2, 3, 4]) == 8 but correct answer is 6. (task: 1994)
  - Test asserts findNumberOfLIS([1, 2, 3, 4, 5]) == 3 but correct answer is 1. (task: 673)
  - Test asserts an incorrect list of coordinates for pacificAtlantic. (task: 417)
  - Test asserts maximumGain('cabxbae', 1, 2) == 15 but correct answer is 3. (task: 1717)
  - Test asserts boxDelivering(...) == 2 but correct answer is 8. (task: 1687)
  - ... and 7 more
- **MissingDefinition** (2 recurring):
  - Test calls solution.catMouseGame(...) without instantiating the solution object. (task: 913)
  - Test calls solution.isPrintable(...) without instantiating the solution object. (task: 1591)
- **SemanticMisunderstanding** (3 recurring):
  - Test uses 1-based node indices (up to 4) for a graph initialized with size 4, causing an IndexError. (task: 1489)
  - Test provides a time string of length 4 ("2?3?") instead of the expected length 5 format ("HH:MM"), causing an IndexError. (task: 2437)
  - Test triggers an infinite loop or excessive computation, resulting in a timeout. (task: 786)

#### granite-4.0-micro

- **Failures analyzed:** 20
- **Recurring failures:** 15

**Root Cause Breakdown:**

- IncorrectAssertion: 10 (50.0%) ██████████
- SemanticMisunderstanding: 10 (50.0%) ██████████

**Proximity to Success:**

- high: 11 (55.0%)
- near: 8 (40.0%)
- moderate: 1 (5.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (10 recurring):
  - Test asserts minimumTotalCost([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == -1 but correct answer is 10. (task: 2499)
  - Test asserts areConnected(6, 2, [[1, 4], [2, 5], [3, 6]]) == [False, False, False] but correct answer is [False, False, True]. (task: 1627)
  - Test asserts pacificAtlantic(...) returns a specific list of coordinates but correct answer contains a different list of pairs. (task: 417)
  - Test asserts minimumChanges("abcabc", 2) == 1 but correct answer is 2. (task: 2911)
  - Test asserts maximumSafenessFactor([[1, 0, 2], [0, 0, 0], [0, 0, 1]]) == 1 but correct answer is 0. (task: 2812)
  - ... and 5 more
- **SemanticMisunderstanding** (5 recurring):
  - Test uses 1-based node indices (up to 4) for a UnionFind initialized with size 4, causing an IndexError. (task: 3108)
  - Test provides a graph with a node index 4 but n=4 (allowing only indices 0-3), causing an IndexError. (task: 1334)
  - Test provides an edge with node 3 but specifies n=3 (allowing only indices 0-2), causing an IndexError. (task: 1976)
  - Test provides a receiver array containing value 3, which is out of bounds for an array of size 3, causing an IndexError. (task: 2836)
  - Test provides a preferences array where node 2 prefers itself and omits node 1, causing a KeyError. (task: 1583)

#### pynguin_results

- **Failures analyzed:** 15
- **Recurring failures:** 15

**Root Cause Breakdown:**

- IncorrectAssertion: 15 (100.0%) ███████████████

**Proximity to Success:**

- near: 15 (100.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (15 recurring):
  - Test asserts the module name of the UnionFind object is 'solution_pkg.UnionFind' instead of 'under_test.UnionFind'. (task: 684)
  - Test is marked as xfail(strict=True) expecting an exception, but it runs successfully and passes. (task: 939)
  - Test asserts the module name of the UnionFind object is 'solution_pkg.UnionFind' instead of 'under_test.UnionFind'. (task: 952)
  - Test asserts the module name of the UnionFind object is 'solution_pkg.UnionFind' instead of 'under_test.UnionFind'. (task: 1489)
  - Test asserts the module name of the UnionFind object is 'solution_pkg.UnionFind' instead of 'under_test.UnionFind'. (task: 1579)
  - ... and 10 more

---

## Real-World Dataset (all failures, N=1, N=226)

**Total failures analyzed:** 106

### Overall Root Cause Distribution

| Root Cause | Count | % |
|---|---|---|
| MockingError | 28 | 26.4% |
| IncorrectAssertion | 26 | 24.5% |
| SemanticMisunderstanding | 17 | 16.0% |
| MissingDefinition | 16 | 15.1% |
| EnvironmentMismatch | 11 | 10.4% |
| APIHallucination | 3 | 2.8% |
| MissingImport | 2 | 1.9% |
| MalformedSyntax | 2 | 1.9% |
| Unknown | 1 | 0.9% |

### Overall Proximity to Success

| Proximity | Count | % |
|---|---|---|
| high | 29 | 27.4% |
| near | 62 | 58.5% |
| moderate | 12 | 11.3% |
| low | 2 | 1.9% |
| far | 1 | 0.9% |

### Root Cause by Model (counts)

| Root Cause | Ministral-3-3B-Reasoning-2512 | Ministral-3-8B-Instruct-2512-AWQ-8bit | Qwen3-4B-Instruct-2507 | gemma-3-4b-it | granite-4.0-micro | pynguin_results |
|---|---|---|---|---|---|---|
| MockingError | 1 | 8 | 6 | 10 | 3 | 0 |
| IncorrectAssertion | 5 | 7 | 6 | 2 | 5 | 1 |
| SemanticMisunderstanding | 3 | 1 | 5 | 5 | 2 | 1 |
| MissingDefinition | 5 | 1 | 3 | 0 | 6 | 1 |
| EnvironmentMismatch | 4 | 1 | 0 | 1 | 2 | 3 |
| APIHallucination | 1 | 1 | 0 | 1 | 0 | 0 |
| MissingImport | 0 | 0 | 0 | 1 | 1 | 0 |
| MalformedSyntax | 1 | 0 | 0 | 0 | 1 | 0 |
| Unknown | 0 | 1 | 0 | 0 | 0 | 0 |
| **Total** | 20 | 20 | 20 | 20 | 20 | 6 |

### Proximity to Success by Model

| Proximity | Ministral-3-3B-Reasoning-2512 | Ministral-3-8B-Instruct-2512-AWQ-8bit | Qwen3-4B-Instruct-2507 | gemma-3-4b-it | granite-4.0-micro | pynguin_results |
|---|---|---|---|---|---|---|
| high | 6 | 6 | 5 | 2 | 8 | 2 |
| near | 12 | 11 | 10 | 15 | 10 | 4 |
| moderate | 1 | 2 | 5 | 3 | 1 | 0 |
| low | 1 | 0 | 0 | 0 | 1 | 0 |
| far | 0 | 1 | 0 | 0 | 0 | 0 |

#### Ministral-3-3B-Reasoning-2512

- **Failures analyzed:** 20
- **Recurring failures:** 11

**Root Cause Breakdown:**

- MissingDefinition: 5 (25.0%) █████
- IncorrectAssertion: 5 (25.0%) █████
- EnvironmentMismatch: 4 (20.0%) ████
- SemanticMisunderstanding: 3 (15.0%) ███
- MockingError: 1 (5.0%) █
- MalformedSyntax: 1 (5.0%) █
- APIHallucination: 1 (5.0%) █

**Proximity to Success:**

- high: 6 (30.0%)
- near: 12 (60.0%)
- moderate: 1 (5.0%)
- low: 1 (5.0%)

**Recurring Failure Patterns:**

- **EnvironmentMismatch** (4 recurring):
  - Test attempts to use a relative import, which fails because the test script is executed as a top-level script in a temporary directory. (task: 36011)
  - Test attempts a relative import which fails in the pytest execution context. (task: 92186)
  - Test fails because it attempts to use a relative import in a standalone pytest execution environment. (task: 48404)
  - Test executes argparse.ArgumentParser.parse_args() without arguments, causing it to consume pytest's command-line arguments and exit. (task: 35202)
- **IncorrectAssertion** (3 recurring):
  - Test asserts that the fragment is kept, but strip_url strips the fragment by default. (task: 22716)
  - Test asserts a hash mismatch because it serializes the input using the default pickle protocol, whereas the function uses HIGHEST_PROTOCOL. (task: 90722)
  - Test expects the port and a hallucinated/typo'd fragment (#farg) to be retained, but the function strips the port and fragment. (task: 22716)
- **MalformedSyntax** (1 recurring):
  - Test generates too many nested with patch(...) blocks, exceeding Python's maximum indentation limit. (task: 37301)
- **MissingDefinition** (2 recurring):
  - Test fails because the module-level constant WEEKDAYS is missing from the test execution environment. (task: 15497)
  - Test fails because the module-level dictionary ACT2FN is missing from the scope of the function under test. (task: 68859)
- **SemanticMisunderstanding** (1 recurring):
  - Test expects dict_to_sequence to return a list, but it returns an odict_items view object. (task: 34966)

#### Ministral-3-8B-Instruct-2512-AWQ-8bit

- **Failures analyzed:** 20
- **Recurring failures:** 9

**Root Cause Breakdown:**

- MockingError: 8 (40.0%) ████████
- IncorrectAssertion: 7 (35.0%) ███████
- MissingDefinition: 1 (5.0%) █
- APIHallucination: 1 (5.0%) █
- EnvironmentMismatch: 1 (5.0%) █
- Unknown: 1 (5.0%) █
- SemanticMisunderstanding: 1 (5.0%) █

**Proximity to Success:**

- high: 6 (30.0%)
- near: 11 (55.0%)
- moderate: 2 (10.0%)
- far: 1 (5.0%)

**Recurring Failure Patterns:**

- **EnvironmentMismatch** (1 recurring):
  - Test attempts to import Solution from a placeholder/hallucinated module name your_module. (task: 15497)
- **IncorrectAssertion** (2 recurring):
  - Test asserts a hallucinated or incorrect hardcoded SHA256 digest byte string for the input 42. (task: 90722)
  - Test asserts an incorrect, hallucinated CBOR-encoded SHA256 digest for the string "hello". (task: 76687)
- **MockingError** (5 recurring):
  - Test attempts to patch 'Solution._ngettext', which incorrectly assumes Solution is a registered top-level module instead of a class. (task: 79446)
  - Test attempts to patch 'Solution.sha256', which incorrectly interprets Solution as a top-level module rather than a class in the current scope. (task: 92301)
  - Test uses @patch.dict('Solution.ACT2FN', ...) which fails because Solution is not a top-level module. (task: 68859)
  - Test tries to mock functions on Solution by using patch with module paths that treat Solution as a top-level package. (task: 37301)
  - Test attempts to patch _xxhash_digest on __main__, which does not exist in the test runner's context. (task: 67890)
- **SemanticMisunderstanding** (1 recurring):
  - Test expects dict_to_sequence to return a list, but it returns an odict_items view object. (task: 34966)

#### Qwen3-4B-Instruct-2507

- **Failures analyzed:** 20
- **Recurring failures:** 7

**Root Cause Breakdown:**

- MockingError: 6 (30.0%) ██████
- IncorrectAssertion: 6 (30.0%) ██████
- SemanticMisunderstanding: 5 (25.0%) █████
- MissingDefinition: 3 (15.0%) ███

**Proximity to Success:**

- high: 5 (25.0%)
- near: 10 (50.0%)
- moderate: 5 (25.0%)

**Recurring Failure Patterns:**

- **IncorrectAssertion** (2 recurring):
  - Test asserts that the query parameter is stripped, but strip_url does not strip query parameters by default. (task: 22716)
  - Test asserts that the path and query are stripped, but the function retains them. (task: 22716)
- **MissingDefinition** (2 recurring):
  - Test fails because _xxhash_digest is missing from the execution environment. (task: 67890)
  - Test fails because the module-level dictionary ACT2FN is not defined in the scope of under_test.py. (task: 68859)
- **SemanticMisunderstanding** (3 recurring):
  - Test expects the mocked proxies to be transformed into environment proxies, but the function returned an empty dictionary. (task: 56372)
  - Test expects the function to return a populated dictionary of proxies, but it returns an empty dictionary. (task: 56372)
  - Test expects dict_to_sequence to return a tuple, but it returns a dict_items view object. (task: 34966)

#### gemma-3-4b-it

- **Failures analyzed:** 20
- **Recurring failures:** 5

**Root Cause Breakdown:**

- MockingError: 10 (50.0%) ██████████
- SemanticMisunderstanding: 5 (25.0%) █████
- IncorrectAssertion: 2 (10.0%) ██
- EnvironmentMismatch: 1 (5.0%) █
- MissingImport: 1 (5.0%) █
- APIHallucination: 1 (5.0%) █

**Proximity to Success:**

- high: 2 (10.0%)
- near: 15 (75.0%)
- moderate: 3 (15.0%)

**Recurring Failure Patterns:**

- **EnvironmentMismatch** (1 recurring):
  - Test calls argparse.ArgumentParser.parse_args() without arguments, which mistakenly parses the pytest command-line arguments and exits. (task: 20164)
- **MockingError** (4 recurring):
  - Test attempts to patch _xxhash_digest on __main__, but it is not available in the pytest runner's __main__ module. (task: 67890)
  - Test attempts to patch a method on __main__.Solution, but Solution is not located in __main__ during pytest execution. (task: 46427)
  - Test attempts to patch sha256 on __main__, which does not exist in the pytest execution context. (task: 92301)
  - Test attempts to patch should_bypass_proxies on __main__, which does not exist. (task: 42659)

#### granite-4.0-micro

- **Failures analyzed:** 20
- **Recurring failures:** 6

**Root Cause Breakdown:**

- MissingDefinition: 6 (30.0%) ██████
- IncorrectAssertion: 5 (25.0%) █████
- MockingError: 3 (15.0%) ███
- SemanticMisunderstanding: 2 (10.0%) ██
- EnvironmentMismatch: 2 (10.0%) ██
- MissingImport: 1 (5.0%) █
- MalformedSyntax: 1 (5.0%) █

**Proximity to Success:**

- high: 8 (40.0%)
- near: 10 (50.0%)
- moderate: 1 (5.0%)
- low: 1 (5.0%)

**Recurring Failure Patterns:**

- **EnvironmentMismatch** (2 recurring):
  - Test attempts to import Solution from a placeholder module name your_module. (task: 48404)
  - Test attempts to import Solution from a placeholder module name your_module. (task: 46905)
- **IncorrectAssertion** (2 recurring):
  - Test asserts that strip_url keeps the #fragment by default, but the function strips it. (task: 22716)
  - Test asserts an incorrect hardcoded byte string for the sha256_cbor hash of [1, 2, 3]. (task: 76687)
- **MalformedSyntax** (1 recurring):
  - Test exceeds Python's maximum indentation/nesting depth limit (20 blocks) by chaining too many with patch: contexts. (task: 19075)
- **MissingDefinition** (1 recurring):
  - Test fails because the module-level helper _xxhash_digest is not defined in the test harness scope. (task: 67890)

#### pynguin_results

- **Failures analyzed:** 6
- **Recurring failures:** 4

**Root Cause Breakdown:**

- EnvironmentMismatch: 3 (50.0%) ███
- IncorrectAssertion: 1 (16.7%) █
- SemanticMisunderstanding: 1 (16.7%) █
- MissingDefinition: 1 (16.7%) █

**Proximity to Success:**

- high: 2 (33.3%)
- near: 4 (66.7%)

**Recurring Failure Patterns:**

- **EnvironmentMismatch** (3 recurring):
  - Test fails during import because the external dependency dramatiq is missing from the test environment. (task: 36011)
  - Test fails during import because the external dependency dramatiq is missing from the test environment. (task: 95673)
  - Test fails during import because the external dependency dramatiq is missing from the test environment. (task: 92186)
- **MissingDefinition** (1 recurring):
  - Test execution hits a NameError because _xxhash_digest is missing from the module scope. (task: 67890)

---

## Grand Summary Across All Datasets

**Total failures analyzed:** 338
**Total recurring:** 226

> **Note:** The grand totals combine stratified samples (TestEval, 50 each)
> with an exhaustive census (Real-World, 226). The real-world dataset
> therefore dominates the aggregate counts. Per-dataset tables above
> should be preferred for cross-dataset comparisons.

### Root Cause Distribution (All Datasets)

| Root Cause | Count | % |
|---|---|---|
| IncorrectAssertion | 161 | 47.6% |
| SemanticMisunderstanding | 90 | 26.6% |
| MockingError | 28 | 8.3% |
| MissingDefinition | 24 | 7.1% |
| APIHallucination | 11 | 3.3% |
| EnvironmentMismatch | 11 | 3.3% |
| MalformedSyntax | 8 | 2.4% |
| MissingImport | 4 | 1.2% |
| Unknown | 1 | 0.3% |

### Proximity to Success (All Datasets)

| Proximity | Count | % |
|---|---|---|
| high | 160 | 47.3% |
| near | 148 | 43.8% |
| moderate | 13 | 3.8% |
| low | 10 | 3.0% |
| far | 7 | 2.1% |

### Key Findings

1. **Top root causes:** IncorrectAssertion (47.6%), SemanticMisunderstanding (26.6%), MockingError (8.3%)
2. **Potentially fixable (high+near proximity):** 308 (91.1%)
3. **Hard failures (low+far proximity):** 17 (5.0%)
4. **Recurring patterns:** 226 failures flagged as recurring