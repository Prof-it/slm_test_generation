# FAILURE LOG: linecov2_Qwen3-4B-Thinking-2507_temp_0.2.jsonl

## TASK: 1489
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_1489_fkix5suw
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_findCriticalAndPseudoCriticalEdges_line22 FAILED [100%]

================================== FAILURES ===================================
_______________ test_findCriticalAndPseudoCriticalEdges_line22 ________________

    def test_findCriticalAndPseudoCriticalEdges_line22():
        solution = Solution()
>       assert solution.findCriticalAndP
               ^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'Solution' object has no attribute 'findCriticalAndP'

test_generated.py:38: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_findCriticalAndPseudoCriticalEdges_line22 - At...
============================== 1 failed in 0.17s ==============================
```

### Code
```python
def test_findCriticalAndPseudoCriticalEdges_line22():
    solution = Solution()
    assert solution.findCriticalAndP
```
---## TASK: 770
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_770_6eh2sxo1
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_basicCalculatorIV_line14 FAILED                  [100%]

================================== FAILURES ===================================
________________________ test_basicCalculatorIV_line14 ________________________

    def test_basicCalculatorIV_line14():
        solution = Solution()
>       assert solution.basicCalculatorIV('y', [], []) == ['y']
E       AssertionError: assert ['1*y'] == ['y']
E         
E         At index 0 diff: '1*y' != 'y'
E         
E         Full diff:
E           [
E         -     'y',
E         +     '1*y',
E         ?      ++
E           ]

test_generated.py:38: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::test_basicCalculatorIV_line14 - AssertionError: ass...
============================== 1 failed in 0.19s ==============================
```

### Code
```python
def test_basicCalculatorIV_line14():
    solution = Solution()
    assert solution.basicCalculatorIV('y', [], []) == ['y']
```
---## TASK: 1604
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_1604_lcr4akr0
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_alertNames_line22 FAILED                         [100%]

================================== FAILURES ===================================
___________________________ test_alertNames_line22 ____________________________

    def test_alertNames_line22():
        solution = Solution()
>       assert solution.alertNames(['Alice'], ['00:00', '00:10', '00:20']) == ['Alice']
E       AssertionError: assert [] == ['Alice']
E         
E         Right contains one more item: 'Alice'
E         
E         Full diff:
E         + []
E         - [
E         -     'Alice',
E         - ]

test_generated.py:38: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::test_alertNames_line22 - AssertionError: assert [] ...
============================== 1 failed in 0.18s ==============================
```

### Code
```python
def test_alertNames_line22():
    solution = Solution()
    assert solution.alertNames(['Alice'], ['00:00', '00:10', '00:20']) == ['Alice']
```
---## TASK: 1681
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_1681_lqwf5ap4
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_line31 FAILED                                    [100%]

================================== FAILURES ===================================
_________________________________ test_line31 _________________________________

    def test_line31():
>       maxi = max(maxi, num)
                   ^^^^
E       UnboundLocalError: cannot access local variable 'maxi' where it is not associated with a value

test_generated.py:37: UnboundLocalError
=========================== short test summary info ===========================
FAILED test_generated.py::test_line31 - UnboundLocalError: cannot access loca...
============================== 1 failed in 0.15s ==============================
```

### Code
```python
def test_line31():
    maxi = max(maxi, num)
```
---## TASK: 2932
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_2932_59e97mvm
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_line40 FAILED                                    [100%]

================================== FAILURES ===================================
_________________________________ test_line40 _________________________________

    def test_line40():
>       node = node.children[bit]  #43
               ^^^^
E       UnboundLocalError: cannot access local variable 'node' where it is not associated with a value

test_generated.py:37: UnboundLocalError
=========================== short test summary info ===========================
FAILED test_generated.py::test_line40 - UnboundLocalError: cannot access loca...
============================== 1 failed in 0.13s ==============================
```

### Code
```python
def test_line40():
    node = node.children[bit]  #43
```
---## TASK: 2976
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_2976_n71p1wq5
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 2 items

test_generated.py::test_line25 FAILED                                    [ 50%]
test_generated.py::test_line26 FAILED                                    [100%]

================================== FAILURES ===================================
_________________________________ test_line25 _________________________________

    def test_line25():
>       for s, t in zip(source, target):  #28
                        ^^^^^^
E       NameError: name 'source' is not defined

test_generated.py:37: NameError
_________________________________ test_line26 _________________________________

    def test_line26():
>       if dist[u][v] == math.inf:
           ^^^^
E       NameError: name 'dist' is not defined

test_generated.py:42: NameError
=========================== short test summary info ===========================
FAILED test_generated.py::test_line25 - NameError: name 'source' is not defined
FAILED test_generated.py::test_line26 - NameError: name 'dist' is not defined
============================== 2 failed in 0.12s ==============================
```

### Code
```python
def test_line25():
    for s, t in zip(source, target):  #28
      if s == t:  #29
        continue  #30

def test_line26():
    if dist[u][v] == math.inf:
        return -1  # line 34
```
---## TASK: 2901
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_2901_spj84x2s
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_getWordsInLongestSubsequence_line23 FAILED       [100%]

================================== FAILURES ===================================
__________________ test_getWordsInLongestSubsequence_line23 ___________________

    def test_getWordsInLongestSubsequence_line23():
        solution = Solution()
>       assert solution.getWordsInLong
               ^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'Solution' object has no attribute 'getWordsInLong'

test_generated.py:38: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_getWordsInLongestSubsequence_line23 - Attribut...
============================== 1 failed in 0.12s ==============================
```

### Code
```python
def test_getWordsInLongestSubsequence_line23():
    solution = Solution()
    assert solution.getWordsInLong
```
---