# FAILURE LOG: linecov_Qwen3-8B-AWQ_temp_0.0.jsonl

## TASK: 581
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm-python-unit-test-benchmark\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_581_cvnbl_5z
plugins: anyio-4.12.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_findUnsortedSubarray_line27 FAILED               [100%]

================================== FAILURES ===================================
______________________ test_findUnsortedSubarray_line27 _______________________

    def test_findUnsortedSubarray_line27():
        solution = Solution()
>       assert solution.findUnsorted
               ^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'Solution' object has no attribute 'findUnsorted'

test_generated.py:38: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_findUnsortedSubarray_line27 - AttributeError: ...
============================== 1 failed in 0.10s ==============================
```

### Code
```python
def test_findUnsortedSubarray_line27():
    solution = Solution()
    assert solution.findUnsorted
```
---