# FAILURE LOG: linecov_Qwen3-8B-AWQ_temp_0.8.jsonl

## TASK: 591
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_591_elm34_mt
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_isValid_line27 FAILED                            [100%]

================================== FAILURES ===================================
_____________________________ test_isValid_line27 _____________________________

    def test_isValid_line27():
        solution = Solution()
>       assert not solution.isVali
                   ^^^^^^^^^^^^^^^
E       AttributeError: 'Solution' object has no attribute 'isVali'. Did you mean: 'isValid'?

test_generated.py:38: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_isValid_line27 - AttributeError: 'Solution' ob...
============================== 1 failed in 0.18s ==============================
```

### Code
```python
def test_isValid_line27():
    solution = Solution()
    assert not solution.isVali
```
---## TASK: 1604
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_1604_hh2bzsgi
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_alertNames_line22 FAILED                         [100%]

================================== FAILURES ===================================
___________________________ test_alertNames_line22 ____________________________

    def test_alertNames_line22():
        solution = Solution()
>       assert solution.alertNames(['Alice'], ['10:00', '10:20', '10:40']) == ['Alice']
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
    assert solution.alertNames(['Alice'], ['10:00', '10:20', '10:40']) == ['Alice']
```
---## TASK: 3001
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_3001_rd7krqjy
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_minMovesToCaptureTheQueen_line20 FAILED          [100%]

================================== FAILURES ===================================
____________________ test_minMovesToCaptureTheQueen_line20 ____________________

    def test_minMovesToCaptureTheQueen_line20():
        solution = Solution()
>       assert solution.minMovesToCapture
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'Solution' object has no attribute 'minMovesToCapture'

test_generated.py:38: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_minMovesToCaptureTheQueen_line20 - AttributeEr...
============================== 1 failed in 0.12s ==============================
```

### Code
```python
def test_minMovesToCaptureTheQueen_line20():
    solution = Solution()
    assert solution.minMovesToCapture
```
---