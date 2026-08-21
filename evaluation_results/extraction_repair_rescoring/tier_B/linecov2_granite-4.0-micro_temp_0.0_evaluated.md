# FAILURE LOG: linecov2_granite-4.0-micro_temp_0.0.jsonl

## TASK: 916895
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_916895_u5sgzb9i
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestSolution::test_record_pane_state_line2 FAILED     [100%]

================================== FAILURES ===================================
__________________ TestSolution.test_record_pane_state_line2 __________________

self = <test_generated.TestSolution testMethod=test_record_pane_state_line2>

    def test_record_pane_state_line2(self):
        result = self.solution_instance.record_pane_state(window_id='win123', pane_id='pan456', new_state=PaneStateName.OPEN, provider='svc789', last_active_ts=1633072800.0)
>       self.assertIsNone(result)
E       AssertionError: <MagicMock name='mock().state' id='2327296942944'> is not None

test_generated.py:49: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::TestSolution::test_record_pane_state_line2 - Assert...
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import unittest

class PaneStateName(str):
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'

class TestSolution(unittest.TestCase):

    def setUp(self):
        self.solution_instance = Solution()

    def test_record_pane_state_line2(self):
        result = self.solution_instance.record_pane_state(window_id='win123', pane_id='pan456', new_state=PaneStateName.OPEN, provider='svc789', last_active_ts=1633072800.0)
        self.assertIsNone(result)
if __name__ == '__main__':
    unittest.main()
```
---## TASK: 896053
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_896053_z6xncvdt
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestSolution::test_convert_voc_bbox_called_line2 FAILED [100%]

================================== FAILURES ===================================
_______________ TestSolution.test_convert_voc_bbox_called_line2 _______________

self = <test_generated.TestSolution testMethod=test_convert_voc_bbox_called_line2>

    def test_convert_voc_bbox_called_line2(self):
        coords = [100.0, 150.0, 200.0, 250.0]
        img_size = (800, 600)
        target = 'some_target'
>       self.sol.convert_voc_bbox(coords, img_size, target)

test_generated.py:47: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000001BFF23F1D90>
coords = [100.0, 150.0, 200.0, 250.0], img_size = (800, 600)
target = 'some_target'

    def convert_voc_bbox(self,
        coords: Sequence[float],
        img_size: Sequence[int],
        target: BBoxType,
    ) -> list[float]:
        """Convert the PASCAL VOC bounding box coordinates to other formats."""
        if target == "albumentations":
            return [
                coords[0] / img_size[0],
                coords[1] / img_size[1],
                coords[2] / img_size[0],
                coords[3] / img_size[1],
            ]
        if target == "coco":
            return [
                coords[0],
                coords[1],
                coords[2] - coords[0],
                coords[3] - coords[1],
            ]
        if target == "voc":
            return list(coords)
        if target == "yolo":
            return [
                (coords[0] + coords[2]) / 2 / img_size[0],
                (coords[1] + coords[3]) / 2 / img_size[1],
                (coords[2] - coords[0]) / img_size[0],
                (coords[3] - coords[1]) / img_size[1],
            ]
>       raise ValueError(f"Unsupported target format: {target}")
E       ValueError: Unsupported target format: some_target

under_test.py:48: ValueError
=========================== short test summary info ===========================
FAILED test_generated.py::TestSolution::test_convert_voc_bbox_called_line2 - ...
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import unittest

class TestSolution(unittest.TestCase):

    def setUp(self):
        self.sol = Solution()

    def test_convert_voc_bbox_called_line2(self):
        coords = [100.0, 150.0, 200.0, 250.0]
        img_size = (800, 600)
        target = 'some_target'
        self.sol.convert_voc_bbox(coords, img_size, target)
```
---## TASK: 363593
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_363593_dv854s1l
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestNearVector::test_near_vector_invoked_line2 FAILED [100%]

================================== FAILURES ===================================
________________ TestNearVector.test_near_vector_invoked_line2 ________________

self = <test_generated.TestNearVector testMethod=test_near_vector_invoked_line2>

    def test_near_vector_invoked_line2(self):
>       result = self.solution.near_vector([0.1, 0.2, 0.3])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:51: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x00000193F8DCE630>
near_vector = [0.1, 0.2, 0.3], filters = None, limit = 10
return_metadata = None

    def near_vector(
        self,
        near_vector: List[float],
        filters: Optional[Filter] = None,
        limit: int = 10,
        return_metadata: Optional[MetadataQuery] = None,
    ) -> QueryResult:
        """Perform vector similarity search."""
        results = []
    
>       for uuid, data in self.collection._storage.items():
                          ^^^^^^^^^^^^^^^
E       AttributeError: 'Solution' object has no attribute 'collection'

under_test.py:50: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::TestNearVector::test_near_vector_invoked_line2 - At...
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import unittest
from typing import List, Optional

class MockMetadataQuery:
    pass

class MockFilter:
    pass

class TestNearVector(unittest.TestCase):

    def setUp(self):
        self.solution = Solution()

    def test_near_vector_invoked_line2(self):
        result = self.solution.near_vector([0.1, 0.2, 0.3])
        self.assertIsNotNone(result)
if __name__ == '__main__':
    unittest.main()
```
---## TASK: 162266
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_162266_z7c_5_og
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_cf_has_standard_names_line2 FAILED               [100%]

================================== FAILURES ===================================
______________________ test_cf_has_standard_names_line2 _______________________

    def test_cf_has_standard_names_line2():
        sol = Solution()
>       assert sol.cf_has_standard_names(xray, ('temperature', 'pressure'))
                                         ^^^^
E       NameError: name 'xray' is not defined

test_generated.py:38: NameError
=========================== short test summary info ===========================
FAILED test_generated.py::test_cf_has_standard_names_line2 - NameError: name ...
============================== 1 failed in 0.25s ==============================
```

### Code
```python
def test_cf_has_standard_names_line2():
    sol = Solution()
    assert sol.cf_has_standard_names(xray, ('temperature', 'pressure'))
```
---## TASK: 25953
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_25953_vme02huj
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_shares_add_line2 FAILED                          [100%]

================================== FAILURES ===================================
____________________________ test_shares_add_line2 ____________________________

solution = <under_test.Solution object at 0x0000019AEFA983B0>

    def test_shares_add_line2(solution):
>       result = solution.shares_add(object_type='example', object_id='123')
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:43: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x0000019AEFA983B0>
object_type = 'example', object_id = '123'
email = <typer.models.ArgumentInfo object at 0x0000019AEFF4BC20>
permission = <typer.models.OptionInfo object at 0x0000019AEFF4BBF0>
expires = <typer.models.OptionInfo object at 0x0000019AEFF4BC80>
as_json = <typer.models.OptionInfo object at 0x0000019AEFF4BCB0>

    def shares_add(self,
        object_type: str = typer.Argument(..., help=_SHARE_OBJECT_TYPES),
        object_id: str = typer.Argument(...),
        email: str = typer.Argument(..., help="Recipient email (pending until they sign up)."),
        permission: str = typer.Option("read", "--permission", help="read | comment | write"),
        expires: str = typer.Option(
            None, "--expires", help="ISO-8601 expiry, e.g. 2026-12-31T00:00:00Z (omit = never)."
        ),
        as_json: bool = typer.Option(False, "--json"),
    ):
        """Share an object with a person by email."""
>       with _client() as c:
             ^^^^^^^
E       NameError: name '_client' is not defined

under_test.py:117: NameError
=========================== short test summary info ===========================
FAILED test_generated.py::test_shares_add_line2 - NameError: name '_client' i...
============================== 1 failed in 0.33s ==============================
```

### Code
```python
import pytest

@pytest.fixture
def solution():
    return Solution()

def test_shares_add_line2(solution):
    result = solution.shares_add(object_type='example', object_id='123')
    assert result is None
```
---## TASK: 51723
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_51723_2ef9flpr
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
ImportError while importing test module 'C:\Users\cbark\AppData\Local\Temp\eval_51723_2ef9flpr\test_generated.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Program Files\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
test_generated.py:37: in <module>
    from zarr.storage import ChunkedStore
E   ModuleNotFoundError: No module named 'zarr'
=========================== short test summary info ===========================
ERROR test_generated.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.45s ===============================
```

### Code
```python
import numpy as np
from zarr.storage import ChunkedStore

class ZarrArray:

    def test_line2(self, data):
        self.data = data
store = ChunkedStore('temp')
array_data = np.array([[1, 2], [3, 4]], dtype=np.int32)
zarr_array = ZarrArray(array_data)
solution_instance = Solution()
assert isinstance(solution_instance.get_dtype(zarr_array), str)
```
---## TASK: 119665
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_119665_758tmqi5
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
test_generated.py:64: in <module>
    result = solution_instance._run_async(dataset=DataSet(), udf=Iterable(), roi=RoiT(), corrections=None, progress=True, backends=Backends(), plots=Plots(), iterate=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
under_test.py:206: in _run_async
    sync_generator = self._run_sync(
                     ^^^^^^^^^^^^^^
E   AttributeError: 'Solution' object has no attribute '_run_sync'. Did you mean: '_run_async'?
=========================== short test summary info ===========================
ERROR test_generated.py - AttributeError: 'Solution' object has no attribute ...
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.48s ===============================
```

### Code
```python
import asyncio

class DataSet:
    pass

class UDF:
    pass

class Iterable:

    def test_line2(self):
        yield 'mock_udf'

class RoiT:
    pass

class CorrectionSet:
    pass

class ProgressReporter:
    pass

class Backends:
    pass

class Plots:
    pass
solution_instance = Solution()
result = solution_instance._run_async(dataset=DataSet(), udf=Iterable(), roi=RoiT(), corrections=None, progress=True, backends=Backends(), plots=Plots(), iterate=True)
assert result is not None
```
---## TASK: 718898
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_718898_ugfmq5yg
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_get_tasksmaster_line2 FAILED                     [100%]

================================== FAILURES ===================================
_________________________ test_get_tasksmaster_line2 __________________________

my_solution = <test_generated.my_solution.<locals>.Solution object at 0x000002B19111ECC0>

    def test_get_tasksmaster_line2(my_solution):
>       result = my_solution().get_tasksmaster()
                 ^^^^^^^^^^^^^
E       TypeError: 'Solution' object is not callable

test_generated.py:48: TypeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_get_tasksmaster_line2 - TypeError: 'Solution' ...
============================== 1 failed in 0.15s ==============================
```

### Code
```python
import pytest

@pytest.fixture
def my_solution():

    class Solution:

        def get_tasksmaster(self):
            pass
    return Solution()

def test_get_tasksmaster_line2(my_solution):
    result = my_solution().get_tasksmaster()
    assert result is not None
```
---## TASK: 235598
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_235598_i0e50kby
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 2 items

test_generated.py::test_from_msgpack_line2[cls_obj0-\x82\xa42\x01] FAILED [ 50%]
test_generated.py::test_from_msgpack_line2[cls_obj1-\x93\xa4a\x01] FAILED [100%]

================================== FAILURES ===================================
_______________ test_from_msgpack_line2[cls_obj0-\x82\xa42\x01] _______________

cls_obj = [<class 'int'>, <class 'float'>], packed_data = b'\x82\xa42\x01'

    @pytest.mark.parametrize('cls_obj, packed_data', [([int, float], b'\x82\xa42\x01'), ({'a': 1}, b'\x93\xa4a\x01')])
    def test_from_msgpack_line2(cls_obj, packed_data):
        solution = Solution()
        result = solution.from_msgpack(cls_obj, packed_data)
>       assert isinstance(result, cls_obj)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union

test_generated.py:42: TypeError
_______________ test_from_msgpack_line2[cls_obj1-\x93\xa4a\x01] _______________

cls_obj = {'a': 1}, packed_data = b'\x93\xa4a\x01'

    @pytest.mark.parametrize('cls_obj, packed_data', [([int, float], b'\x82\xa42\x01'), ({'a': 1}, b'\x93\xa4a\x01')])
    def test_from_msgpack_line2(cls_obj, packed_data):
        solution = Solution()
        result = solution.from_msgpack(cls_obj, packed_data)
>       assert isinstance(result, cls_obj)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union

test_generated.py:42: TypeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_from_msgpack_line2[cls_obj0-\x82\xa42\x01] - T...
FAILED test_generated.py::test_from_msgpack_line2[cls_obj1-\x93\xa4a\x01] - T...
============================== 2 failed in 0.13s ==============================
```

### Code
```python
import pytest

@pytest.mark.parametrize('cls_obj, packed_data', [([int, float], b'\x82\xa42\x01'), ({'a': 1}, b'\x93\xa4a\x01')])
def test_from_msgpack_line2(cls_obj, packed_data):
    solution = Solution()
    result = solution.from_msgpack(cls_obj, packed_data)
    assert isinstance(result, cls_obj)
```
---## TASK: 577470
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_577470_aeg1ov25
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_to_json_line2 FAILED                             [100%]

================================== FAILURES ===================================
_____________________________ test_to_json_line2 ______________________________

instance = <under_test.Solution object at 0x000002ECE0261DC0>

    def test_to_json_line2(instance):
        """
        Test that calling Solution.to_json triggers line 2 of the method.
    
        Conditions met:
        1. Function `to_json` exists.
        2. Parameter signature matches exactly.
        3. No early returns before line 2.
        4. Invocation reaches line 2.
        """
>       result = instance.to_json(DaskArray(), SerializationInfo())
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:58: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000002ECE0261DC0>
cls = <test_generated.DaskArray object at 0x000002ECE28E9730>
array = <test_generated.SerializationInfo object at 0x000002ECE28E9760>
info = None

    def to_json(self,
        cls, array: DaskArray, info: SerializationInfo | None = None
    ) -> list | DaskJsonDict:
        """
        Convert an array to a JSON serializable array by first converting to a numpy
        array and then to a list.
    
        .. note::
    
            This is likely a very memory intensive operation if you are using dask for
            large arrays. This can't be avoided, since the creation of the json string
            happens in-memory with Pydantic, so you are likely looking for a different
            method of serialization here using the python object itself rather than
            its JSON representation.
        """
        np_array = np.array(array)
        as_json = np_array.tolist()
        if not isinstance(as_json, list):
            as_json = [as_json]
>       if info.round_trip:
           ^^^^^^^^^^^^^^^
E       AttributeError: 'NoneType' object has no attribute 'round_trip'

under_test.py:83: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::test_to_json_line2 - AttributeError: 'NoneType' obj...
============================== 1 failed in 0.40s ==============================
```

### Code
```python
import pytest

class DaskArray:
    pass

class SerializationInfo:
    pass

@pytest.fixture
def instance():
    return Solution()

def test_to_json_line2(instance):
    """
    Test that calling Solution.to_json triggers line 2 of the method.

    Conditions met:
    1. Function `to_json` exists.
    2. Parameter signature matches exactly.
    3. No early returns before line 2.
    4. Invocation reaches line 2.
    """
    result = instance.to_json(DaskArray(), SerializationInfo())
    assert isinstance(result, (list, dict))
```
---## TASK: 432562
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_432562_qve1l1tl
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_select_designs_line2 FAILED                      [100%]

================================== FAILURES ===================================
__________________________ test_select_designs_line2 __________________________

    def test_select_designs_line2():
        solution = Solution()
        configs = [{'design_id': 'A', 'score': 0.85}, {'design_id': 'B', 'score': 0.9}]
        raw_results = [{'design_id': 'A'}, {'design_id': 'B'}]
>       df_result = solution.select_designs(configs=configs, raw_results=raw_results)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:42: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000001AB6BBFC200>
configs = [{'design_id': 'A', 'score': 0.85}, {'design_id': 'B', 'score': 0.9}]
raw_results = [{'design_id': 'A'}, {'design_id': 'B'}], top_n = 84
isoelectric_point_max = 6.0

    def select_designs(self,
        configs: list[dict],
        raw_results: list,
        top_n: int = TOP_N,
        isoelectric_point_max: float = ISOELECTRIC_POINT_MAX,
    ):
        """Join per-job result frames, filter to plausible designs, and keep the top per group.
    
        Each design's score is the average of two terms:
    
        - `iptm_score` -- mean ipTM across hero critics (calibrated by Biohub).
        - `iptm_proxy_score` -- mean distogram-iPTM-proxy across scaling critics
          (uncalibrated but cheap, so we run a larger ensemble of them).
    
        Antibodies use the CDR-restricted distogram proxy; minibinders use the full
        one. With no scaling critics in the sweep, only `iptm_score` is non-zero.
    
        Returns a `pandas.DataFrame` of selected designs with `target_name` and
        `binder_name` as columns (suitable for parquet round-trips).
        """
        try:
            import pandas as pd
        except (ImportError, ModuleNotFoundError):
            from unittest.mock import MagicMock as _MagicMock
            pd = _MagicMock()
        try:
            from Bio.SeqUtils.ProtParam import ProteinAnalysis
        except (ImportError, ModuleNotFoundError):
            from unittest.mock import MagicMock as _MagicMock
            ProteinAnalysis = _MagicMock()
        try:
            from tqdm.auto import tqdm
        except (ImportError, ModuleNotFoundError):
            from unittest.mock import MagicMock as _MagicMock
            tqdm = _MagicMock()
    
        # Each `design` call returns (best_sequences, trajectory, critic_results);
        # we only need critic_results for selection, broadcast with config metadata.
        df_result = pd.concat(
>           [pd.DataFrame(r[2]).assign(**cfg) for cfg, r in zip(configs, raw_results)],
                          ^^^^
            ignore_index=True,
        )
E       KeyError: 2

under_test.py:56: KeyError
=========================== short test summary info ===========================
FAILED test_generated.py::test_select_designs_line2 - KeyError: 2
============================== 1 failed in 0.90s ==============================
```

### Code
```python
import pandas as pd

def test_select_designs_line2():
    solution = Solution()
    configs = [{'design_id': 'A', 'score': 0.85}, {'design_id': 'B', 'score': 0.9}]
    raw_results = [{'design_id': 'A'}, {'design_id': 'B'}]
    df_result = solution.select_designs(configs=configs, raw_results=raw_results)
    expected_columns = ['target_name', 'binder_name']
    assert set(df_result.columns) == expected_columns
```
---