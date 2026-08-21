# FAILURE LOG: linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0.jsonl

## TASK: 872607
**STATUS:** Pytest Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_872607_hk8ayrwn
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
C:\Repos\slm_test_generation\.venv\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Repos\slm_test_generation\.venv\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Program Files\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Repos\slm_test_generation\.venv\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Repos\slm_test_generation\.venv\Lib\site-packages\_pytest\assertion\rewrite.py:359: in _rewrite_test
    co = compile(tree, strfn, "exec", dont_inherit=True)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E     File "C:\Users\cbark\AppData\Local\Temp\eval_872607_hk8ayrwn\test_generated.py", line 43
E       await solution.test()
E       ^^^^^^^^^^^^^^^^^^^^^
E   SyntaxError: 'await' outside async function
=========================== short test summary info ===========================
ERROR test_generated.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.40s ===============================
```

### Code
```python
import asyncio

def test_test_line2():
    from unittest.mock import patch, MagicMock
    import time
    solution = Solution()
    with patch('asyncio.get_event_loop') as mock_get_event_loop, patch('asyncio.run', new_callable=lambda *args, **kwargs: None):
        await solution.test()
```
---## TASK: 896053
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_896053_tg4w7tin
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items

============================ no tests ran in 0.05s ============================
```

### Code
```python
import sys
sys.path.append('.')
from typing import List, Tuple, Optional
BBoxType = Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]

class Solution:

    def test_line2(self, coords: List[float], img_size: List[int], target: BBoxType) -> List[float]:
        xmin, ymin, xmax, ymax = coords[:4]
        w, h = img_size
        x_center = (xmin + xmax) / 2
        y_center = (ymin + ymax) / 2
        x_half = (xmax - xmin) / 2
        y_half = (ymax - ymin) / 2
        x_scale = x_half / w
        y_scale = y_half / h
        x_offset = x_center - w / 2
        y_offset = y_center - h / 2
        x_final = x_scale * x_offset
        y_final = y_scale * y_offset
        return [x_final, y_final]
```
---## TASK: 363593
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_363593_2lwmfk7l
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestNearVector::test_near_vector_basic_line2 FAILED   [100%]

================================== FAILURES ===================================
_________________ TestNearVector.test_near_vector_basic_line2 _________________

self = <test_generated.TestNearVector testMethod=test_near_vector_basic_line2>

    def test_near_vector_basic_line2(self):
        filter_obj = Filter()
        meta_query = MetadataQuery()
>       result = self.solution.near_vector(near_vector=[1.0, 2.0, 3.0], filters=filter_obj, limit=5, return_metadata=True)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:56: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000002106016C1D0>
near_vector = [1.0, 2.0, 3.0]
filters = <test_generated.Filter object at 0x000002106016C980>, limit = 5
return_metadata = True

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
FAILED test_generated.py::TestNearVector::test_near_vector_basic_line2 - Attr...
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import unittest
from typing import List, Optional

class Filter:
    pass

class MetadataQuery:
    pass

class QueryResult:
    pass

class TestNearVector(unittest.TestCase):

    def setUp(self):
        self.solution = Solution()

    def test_near_vector_basic_line2(self):
        filter_obj = Filter()
        meta_query = MetadataQuery()
        result = self.solution.near_vector(near_vector=[1.0, 2.0, 3.0], filters=filter_obj, limit=5, return_metadata=True)
        self.assertIsInstance(result, QueryResult)
```
---## TASK: 916895
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_916895_9h0j2uu3
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
test_generated.py:39: in <module>
    class PaneStateName(enum.Enum):
                        ^^^^
E   NameError: name 'enum' is not defined. Did you forget to import 'enum'
=========================== short test summary info ===========================
ERROR test_generated.py - NameError: name 'enum' is not defined. Did you forg...
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.24s ===============================
```

### Code
```python
import pytest
from typing import Optional

class PaneStateName(enum.Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'

class WindowState:
    panes = {}

@pytest.fixture
def solution() -> 'Solution':
    return Solution()

def test_record_pane_state_line2(solution):
    result = solution.record_pane_state(window_id='win1', pane_id='pane1', new_state=PaneStateName.ACTIVE, provider='my_provider', last_active_ts=123.45)
    assert result is not None
    result = solution.record_pane_state(window_id='win2', pane_id='pane2', new_state=PaneStateName.INACTIVE)
    assert result is not None
    result = solution.record_pane_state(window_id='win3', pane_id='pane3', new_state=PaneStateName.ACTIVE, last_active_ts=None)
    assert result is not None
    try:
        solution.record_pane_state('', '', PaneStateName.ACTIVE)
        assert False, 'Expected TypeError for empty window_id or pane_id'
    except TypeError as e:
        pass
    try:
        solution.record_pane_state('win4', 'pane4', 'invalid')
        assert False, 'Expected TypeError for invalid state'
    except TypeError as e:
        pass
```
---## TASK: 162266
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_162266_lq788v5l
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_cf_has_standard_names_line2 FAILED               [100%]

================================== FAILURES ===================================
______________________ test_cf_has_standard_names_line2 _______________________

    def test_cf_has_standard_names_line2():
>       from xarray import DataArray, Dataset
E       ModuleNotFoundError: No module named 'xarray'

test_generated.py:37: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED test_generated.py::test_cf_has_standard_names_line2 - ModuleNotFoundEr...
============================== 1 failed in 0.26s ==============================
```

### Code
```python
def test_cf_has_standard_names_line2():
    from xarray import DataArray, Dataset
    from typing import Tuple
    from unittest.mock import MagicMock, patch
    with patch('cf_xarray') as mock_cf_xarray:
        mock_data_array = MagicMock(spec=DataArray)
        mock_dataset = MagicMock(spec=Dataset)
        mock_data_array.cf = {'time': 1, 'lat': 2, 'lon': 3}
        mock_dataset.cf = {'time': 1, 'lat': 2, 'lon': 3}
        solution = Solution()
        result = solution.cf_has_standard_names(mock_data_array, ('time', 'lat'))
        assert result is True
        result = solution.cf_has_loaded_dataset(mock_dataset, ('time', 'lat'))
        assert result is True
```
---## TASK: 119665
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_119665_4vcau6fg
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items

============================ no tests ran in 0.23s ============================
```

### Code
```python
import unittest
from typing import Optional, Union, List, Tuple, Dict, Any
from unittest.mock import patch, MagicMock

class DataSet:
    pass

class UDF:
    pass

class RoiT:
    pass

class CorrectionSet:
    pass

class ProgressReporter:
    pass

class BackendConfig:
    pass

class PlotSettings:
    pass

class Solution:

    def test_line2(self, dataset: DataSet, udf: Union[UDF, List[UDF]], roi: RoiT, corrections: Optional[CorrectionSet], progress: Union[bool, ProgressReporter], backends: List[BackendConfig], plots: Optional[List[PlotSettings]], iterate: bool):
        """Wraps :code:`_run_sync` into an asynchronous generator,
        and either returns the generator itself, or the end result."""
        print('Line 2 executed')
```
---## TASK: 51723
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_51723_8i0y2zs0
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
ImportError while importing test module 'C:\Users\cbark\AppData\Local\Temp\eval_51723_8i0y2zs0\test_generated.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Program Files\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
test_generated.py:37: in <module>
    from zarr import ZarrArray
E   ModuleNotFoundError: No module named 'zarr'
=========================== short test summary info ===========================
ERROR test_generated.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.47s ===============================
```

### Code
```python
import numpy as np
from zarr import ZarrArray

class Solution:

    def test_line2(self, array: ZarrArray) -> 'DtypeType':
        """Override base dtype getter to handle zarr's string-as-object encoding."""
        ...
```
---## TASK: 718898
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_718898_ori61dc5
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
ImportError while importing test module 'C:\Users\cbark\AppData\Local\Temp\eval_718898_ori61dc5\test_generated.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Program Files\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
test_generated.py:48: in <module>
    with patch('module.TasksMaster') as mock_tasksmaster:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Program Files\Python312\Lib\unittest\mock.py:1451: in __enter__
    self.target = self.getter()
                  ^^^^^^^^^^^^^
C:\Program Files\Python312\Lib\pkgutil.py:513: in resolve_name
    mod = importlib.import_module(modname)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Program Files\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'module'
=========================== short test summary info ===========================
ERROR test_generated.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.33s ===============================
```

### Code
```python
import unittest
from unittest.mock import patch

class TestCase(unittest.TestCase):

    @patch('some_module.BackgroundScheduler')
    def test_get_tasksmaster_line2(self, mock_scheduler):
        mock_instance = MagicMock(spec=BackgroundScheduler)
        mock_scheduler.return_value = mock_instance
        tasks_master = Solution().get_tasksmaster()
        self.assertEqual(mock_scheduler.call_count, 1)
        self.assertIsInstance(tasks_master, TasksMaster)
with patch('module.TasksMaster') as mock_tasksmaster:
    mock_tasksmaster.return_value = MagicMock(spec=TasksMaster)
```
---## TASK: 234352
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_234352_kit9d7f5
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
test_generated.py:38: in <module>
    class Solution:
test_generated.py:40: in Solution
    def test_line2(self, instance: T.Any, cls: T.Type[T.TYPE], message: str | None=None) -> T.TypeGuard[T.TYPE]:
                                                      ^^^^^^
E   AttributeError: module 'typing' has no attribute 'TYPE'. Did you mean: 'Type'?
=========================== short test summary info ===========================
ERROR test_generated.py - AttributeError: module 'typing' has no attribute 'T...
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.21s ===============================
```

### Code
```python
import typing as T

class Solution:

    def test_line2(self, instance: T.Any, cls: T.Type[T.TYPE], message: str | None=None) -> T.TypeGuard[T.TYPE]:
        """
        A TypeGuard function that is equivalent to `assert instance, cls, message`
        that hides nasty MyPy or IDE warnings.

        :param instance: the instance that is checked against cls.
        :param cls: the class
        :param message: any message that is displayed when the assert check fails.
        :return: the type of cls.
        """
        if isinstance(instance, cls):
            return True
        else:
            raise AssertionError(message)
```
---## TASK: 235598
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_235598_0ylojt9q
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
ImportError while importing test module 'C:\Users\cbark\AppData\Local\Temp\eval_235598_0ylojt9q\test_generated.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Program Files\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
test_generated.py:39: in <module>
    from msgpack import MsgPackDeserializer, packb, unpackb, ExtType
E   ImportError: cannot import name 'MsgPackDeserializer' from 'msgpack' (C:\Repos\slm_test_generation\.venv\Lib\site-packages\msgpack\__init__.py)
=========================== short test summary info ===========================
ERROR test_generated.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.21s ===============================
```

### Code
```python
import sys
sys.path.append('.')
from typing import Any, Dict, Type, Optional, Union, List
from msgpack import MsgPackDeserializer, packb, unpackb, ExtType
from msgpack.exceptions import MsgPackError

class Deserializer(bytes):
    pass

class MyDeserializer(MsgPackDeserializer):
    pass

class Solution:

    def from_msgpack(self, c: Any, s: bytes, de: type[Deserializer]=MsgPackDeserializer, named: bool=True, ext_dict: Optional[Dict[int, Type[Any]]]=None, skip_none: bool=False, **opts: Any) -> Any:
        """
        Deserialize from MsgPack into the object.
        c is a class object and s is MsgPack binary. If ext_dict option is specified,
        c is ignored and type is inferred from msgpack.ExtType If you supply other keyword
        arguments, they will be passed in msgpack.unpackb function.
        If you want to use the other msgpack package, you can subclass MsgPackDeserializer
        and implement your own logic.
        """
        try:
            if ext_dict is not None:
                result = unpackb(s, de, named=named, ext_dict=ext_dict, skip_none=skip_none, **opts)
            else:
                result = unpackb(s, de, named=named, **opts)
        except MsgPackError as e:
            raise ValueError(f'Invalid MsgPack data: {e}')
        return result

def test_from_msgpack_line2():
    solution = Solution()
    data = {'key': 'value', 'number': 42}
    packed_data = packb(data, de=MyDeserializer())
    assert solution.from_msgpack(Solution, packed_data, de=MyDeserializer(), named=True, ext_dict={}) == data
```
---## TASK: 577470
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_577470_ubeycn7j
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
_____________________ ERROR collecting test_generated.py ______________________
ImportError while importing test module 'C:\Users\cbark\AppData\Local\Temp\eval_577470_ubeycn7j\test_generated.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Program Files\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
test_generated.py:36: in <module>
    import dask.array as da
E   ModuleNotFoundError: No module named 'dask'
=========================== short test summary info ===========================
ERROR test_generated.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.42s ===============================
```

### Code
```python
import dask.array as da

class SomeClass:
    pass

def test_to_json_line2():
    from unittest.mock import MagicMock
    cls_instance = MagicMock(spec=SomeClass)
    dask_array = da.ones((10,))
    result = cls_instance.to_json(cls_instance, dask_array)
    assert isinstance(result, (list, type(None)))
```
---## TASK: 432562
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_432562_ukrncds3
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_select_designs_line2 FAILED                      [100%]

================================== FAILURES ===================================
__________________________ test_select_designs_line2 __________________________

    def test_select_designs_line2():
        solution = Solution()
        configs = [{'type': 'antibody'}, {'type': 'minibinder'}]
        raw_results = [{'ipTM': [0.5, 0.6], 'distogram_iPTM_proxies': [0.4, 0.5]}, {'ipTM': [0.7, 0.8], 'distogram_iPTM_proxies': [0.6, 0.7]}]
        top_n = 1
        isoelectric_point_max = 10.0
>       assert solution.select_designs(configs, raw_results, top_n, isoelectric_point_max) == [[0, 0]]
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:44: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000002BAFED68380>
configs = [{'type': 'antibody'}, {'type': 'minibinder'}]
raw_results = [{'distogram_iPTM_proxies': [0.4, 0.5], 'ipTM': [0.5, 0.6]}, {'distogram_iPTM_proxies': [0.6, 0.7], 'ipTM': [0.7, 0.8]}]
top_n = 1, isoelectric_point_max = 10.0

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
============================== 1 failed in 0.79s ==============================
```

### Code
```python
import pandas as pd

def test_select_designs_line2():
    solution = Solution()
    configs = [{'type': 'antibody'}, {'type': 'minibinder'}]
    raw_results = [{'ipTM': [0.5, 0.6], 'distogram_iPTM_proxies': [0.4, 0.5]}, {'ipTM': [0.7, 0.8], 'distogram_iPTM_proxies': [0.6, 0.7]}]
    top_n = 1
    isoelectric_point_max = 10.0
    assert solution.select_designs(configs, raw_results, top_n, isoelectric_point_max) == [[0, 0]]
```
---