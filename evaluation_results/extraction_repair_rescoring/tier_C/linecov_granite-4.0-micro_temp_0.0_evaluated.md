# FAILURE LOG: linecov_granite-4.0-micro_temp_0.0.jsonl

## TASK: 916895
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_916895_q37dq9av
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_record_pane_state_line2 FAILED                   [100%]

================================== FAILURES ===================================
________________________ test_record_pane_state_line2 _________________________

solution = <MagicMock spec='Solution' id='2872346218944'>

    def test_record_pane_state_line2(solution):
        result = solution.record_pane_state('win123', 'pane456', PaneStateName())
>       assert result is None
E       AssertionError: assert <MagicMock name='mock.record_pane_state()' id='2872384498160'> is None

test_generated.py:48: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::test_record_pane_state_line2 - AssertionError: asse...
============================== 1 failed in 0.16s ==============================
```

### Code
```python
import pytest
from unittest.mock import MagicMock

class PaneStateName:
    pass

@pytest.fixture
def solution():
    return MagicMock(spec=Solution)

def test_record_pane_state_line2(solution):
    result = solution.record_pane_state('win123', 'pane456', PaneStateName())
    assert result is None
```
---## TASK: 896053
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_896053_3g3g9fph
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_convert_voc_bbox_line2[coords0-img_size0-target0-result0] FAILED [100%]

================================== FAILURES ===================================
_______ test_convert_voc_bbox_line2[coords0-img_size0-target0-result0] ________

coords = [10.0, 20.0, 30.0, 40.0], img_size = [100, 200]
target = <test_generated.BBoxType object at 0x00000275515426C0>
result = [0.1, 0.1, 0.3, 0.2]

    @pytest.mark.parametrize('coords,img_size,target,result', [([10.0, 20.0, 30.0, 40.0], [100, 200], BBoxType(), [10 / 100, 20 / 200, 30 / 100, 40 / 200])])
    def test_convert_voc_bbox_line2(coords, img_size, target, result):
>       from your_module import Solution
E       ModuleNotFoundError: No module named 'your_module'

test_generated.py:44: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED test_generated.py::test_convert_voc_bbox_line2[coords0-img_size0-target0-result0]
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import pytest
from unittest.mock import MagicMock

class BBoxType:
    pass

@pytest.mark.parametrize('coords,img_size,target,result', [([10.0, 20.0, 30.0, 40.0], [100, 200], BBoxType(), [10 / 100, 20 / 200, 30 / 100, 40 / 200])])
def test_convert_voc_bbox_line2(coords, img_size, target, result):
    from your_module import Solution
    solution = Solution()
    expected_result = MagicMock(spec=solution.convert_voc_bbox.return_value)
    expected_result.__eq__.return_value = True
    solution.convert_voc_bbox.return_value = expected_result
    assert solution.convert_voc_bbox(coords, img_size, target) == result
```
---## TASK: 718898
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_718898_kqemc4_h
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestGetTasksmaster::test_get_tasksmaster_line2 FAILED [100%]

================================== FAILURES ===================================
________________ TestGetTasksmaster.test_get_tasksmaster_line2 ________________

self = <test_generated.TestGetTasksmaster testMethod=test_get_tasksmaster_line2>

    def test_get_tasksmaster_line2(self):
>       from your_module import Solution
E       ModuleNotFoundError: No module named 'your_module'

test_generated.py:42: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED test_generated.py::TestGetTasksmaster::test_get_tasksmaster_line2 - Mo...
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import unittest
from unittest.mock import patch, MagicMock

class TestGetTasksmaster(unittest.TestCase):

    def test_get_tasksmaster_line2(self):
        from your_module import Solution
        tasks_master_mock = MagicMock(spec=Solution.TasksMaster)
        with patch('your_module.Solution.TasksMaster', return_value=tasks_master_mock):
            with patch('__main__.BackgroundScheduler', autospec=True):
                solution = Solution()
                result = solution.get_tasksmaster()
                self.assertIs(result, tasks_master_mock)
                tasks_master_mock.assert_called_once_with(start_server=False)
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
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_162266_s7pz7gg5
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_cf_has_standard_names_line2 FAILED               [100%]

================================== FAILURES ===================================
______________________ test_cf_has_standard_names_line2 _______________________

xr_like_data = <MagicMock id='2326342209984'>

    def test_cf_has_standard_names_line2(xr_like_data):
>       from my_module import Solution
E       ModuleNotFoundError: No module named 'my_module'

test_generated.py:44: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED test_generated.py::test_cf_has_standard_names_line2 - ModuleNotFoundEr...
============================== 1 failed in 0.27s ==============================
```

### Code
```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def xr_like_data():
    return MagicMock()

def test_cf_has_standard_names_line2(xr_like_data):
    from my_module import Solution
    solution = Solution()
    data = xr_like_data
    names = ('standard_name',)
    result = solution.cf_has_standard_names(data, names)
    assert result == True
```
---## TASK: 119665
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_119665_r5i_u8d5
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test__run_async FAILED                                [100%]

================================== FAILURES ===================================
_______________________________ test__run_async _______________________________
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
=========================== short test summary info ===========================
FAILED test_generated.py::test__run_async - Failed: async def functions are n...
============================== 1 failed in 0.25s ==============================
```

### Code
```python
import asyncio
from unittest.mock import MagicMock

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

class Backends:
    pass

class Plots:
    pass

class Solution:

    def __init__(self):
        self._run_sync = MagicMock(return_value=None)

    def test_line2(self, dataset, udf, roi, corrections, progress, backends, plots, iterate):
        ...
solution = Solution()

async def test__run_async():
    await solution._run_async(MagicMock(), MagicMock(), MagicMock(), None, False, Backends(), Plots(), True)
```
---## TASK: 872607
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_872607_hlxli5up
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_test_line2 FAILED                                [100%]

================================== FAILURES ===================================
_______________________________ test_test_line2 _______________________________

    def test_test_line2():
        from datetime import timedelta
        patcher = patch('datetime.timedelta')
        timedelta_mock = patcher.start()
        timedelta_mock.HOURS = timedelta(hours=3)
        patcher.stop()
        solution = Solution()
        loop = asyncio.get_event_loop()
>       result = loop.run_until_complete(solution.test())
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:47: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Program Files\Python312\Lib\asyncio\base_events.py:691: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x0000021222F05880>, test_timeout = 10800
content = None, twice = True

    async def test(self, test_timeout=3 * HOURS, content=None, twice=True):
        """Test the model serving endpoint"""
>       url = await Server.get_url.aio()
                    ^^^^^^
E       NameError: name 'Server' is not defined

under_test.py:36: NameError
============================== warnings summary ===============================
test_generated.py::test_test_line2
  C:\Users\cbark\AppData\Local\Temp\eval_872607_hlxli5up\test_generated.py:46: DeprecationWarning: There is no current event loop
    loop = asyncio.get_event_loop()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED test_generated.py::test_test_line2 - NameError: name 'Server' is not d...
======================== 1 failed, 1 warning in 0.42s =========================
```

### Code
```python
import asyncio
from unittest.mock import patch, MagicMock

def test_test_line2():
    from datetime import timedelta
    patcher = patch('datetime.timedelta')
    timedelta_mock = patcher.start()
    timedelta_mock.HOURS = timedelta(hours=3)
    patcher.stop()
    solution = Solution()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(solution.test())
    loop.close()
```
---## TASK: 51723
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_51723_3y8ow01i
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestGetDtype::test_get_dtype_line2 FAILED             [100%]

================================== FAILURES ===================================
______________________ TestGetDtype.test_get_dtype_line2 ______________________

self = <test_generated.TestGetDtype testMethod=test_get_dtype_line2>

    def test_get_dtype_line2(self):
        solution = Solution()
>       array_mock = MagicMock(spec=ZarrArray)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:43: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Program Files\Python312\Lib\unittest\mock.py:2139: in __init__
    _safe_super(MagicMixin, self).__init__(*args, **kw)
C:\Program Files\Python312\Lib\unittest\mock.py:1121: in __init__
    _safe_super(CallableMixin, self).__init__(
C:\Program Files\Python312\Lib\unittest\mock.py:460: in __init__
    self._mock_add_spec(spec, spec_set, _spec_as_instance, _eat_self)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <[AttributeError('_mock_methods') raised in repr()] MagicMock object at 0x1b83af22960>
spec = <MagicMock id='1890814258464'>, spec_set = None
_spec_as_instance = False, _eat_self = False

    def _mock_add_spec(self, spec, spec_set, _spec_as_instance=False,
                       _eat_self=False):
        if _is_instance_mock(spec):
>           raise InvalidSpecError(f'Cannot spec a Mock object. [object={spec!r}]')
E           unittest.mock.InvalidSpecError: Cannot spec a Mock object. [object=<MagicMock id='1890814258464'>]

C:\Program Files\Python312\Lib\unittest\mock.py:511: InvalidSpecError
=========================== short test summary info ===========================
FAILED test_generated.py::TestGetDtype::test_get_dtype_line2 - unittest.mock....
============================== 1 failed in 0.42s ==============================
```

### Code
```python
import unittest
from unittest.mock import patch, MagicMock

class TestGetDtype(unittest.TestCase):

    def test_get_dtype_line2(self):
        solution = Solution()
        array_mock = MagicMock(spec=ZarrArray)
        result = solution.get_dtype(array_mock)
        self.assertIsInstance(result, DtypeType)
```
---## TASK: 234352
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_234352_qigehusf
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestAssertIsInstance::test_assert_isinstance_line2 FAILED [100%]

================================== FAILURES ===================================
______________ TestAssertIsInstance.test_assert_isinstance_line2 ______________

self = <test_generated.TestAssertIsInstance testMethod=test_assert_isinstance_line2>

    def test_assert_isinstance_line2(self):
        sol = Solution()
>       self.assertTrue(sol.assert_isinstance(42, int))
E       AssertionError: None is not true

test_generated.py:48: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::TestAssertIsInstance::test_assert_isinstance_line2
============================== 1 failed in 0.12s ==============================
```

### Code
```python
import unittest
from typing import Any

class Solution:

    def assert_isinstance(self, instance: Any, cls: type[Any], message: str | None=None) -> bool:
        ...

class TestAssertIsInstance(unittest.TestCase):

    def test_assert_isinstance_line2(self):
        sol = Solution()
        self.assertTrue(sol.assert_isinstance(42, int))
        self.assertFalse(sol.assert_isinstance('hello', int))
```
---## TASK: 235598
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_235598_2_afv9f9
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestFromMsgpack::test_from_msgpack_line2 FAILED       [100%]

================================== FAILURES ===================================
___________________ TestFromMsgpack.test_from_msgpack_line2 ___________________

self = <test_generated.TestFromMsgpack object at 0x000001B776ABFBF0>

    def test_from_msgpack_line2(self):
        solution = Solution()
        deserializer_mock = MagicMock(spec=MagicMock)
>       result = solution.from_msgpack(c=MagicMock(), s=b'\x93\x01\x02', de=deserializer_mock, named=True, ext_dict={}, skip_none=False)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:44: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
under_test.py:74: in from_msgpack
    ext = de.deserialize(s, **opts)
          ^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <MagicMock spec='MagicMock' id='1887481765696'>, name = 'deserialize'

    def __getattr__(self, name):
        if name in {'_mock_methods', '_mock_unsafe'}:
            raise AttributeError(name)
        elif self._mock_methods is not None:
            if name not in self._mock_methods or name in _all_magics:
>               raise AttributeError("Mock object has no attribute %r" % name)
E               AttributeError: Mock object has no attribute 'deserialize'

C:\Program Files\Python312\Lib\unittest\mock.py:660: AttributeError
=========================== short test summary info ===========================
FAILED test_generated.py::TestFromMsgpack::test_from_msgpack_line2 - Attribut...
============================== 1 failed in 0.15s ==============================
```

### Code
```python
import pytest
from unittest.mock import MagicMock

class TestFromMsgpack:

    def test_from_msgpack_line2(self):
        solution = Solution()
        deserializer_mock = MagicMock(spec=MagicMock)
        result = solution.from_msgpack(c=MagicMock(), s=b'\x93\x01\x02', de=deserializer_mock, named=True, ext_dict={}, skip_none=False)
        assert result == expected_result
```
---## TASK: 577470
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_577470_r5lsyjpu
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_to_json_line2 FAILED                             [100%]

================================== FAILURES ===================================
_____________________________ test_to_json_line2 ______________________________

mocks = {'DaskArray': <MagicMock id='1728721736368'>, 'JsonDict': <MagicMock id='1726746457824'>, 'SerializationInfo': <MagicMock id='1726746454080'>}

    def test_to_json_line2(mocks):
>       from your_module import Solution
E       ModuleNotFoundError: No module named 'your_module'

test_generated.py:53: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED test_generated.py::test_to_json_line2 - ModuleNotFoundError: No module...
============================== 1 failed in 0.31s ==============================
```

### Code
```python
import pytest
from unittest.mock import MagicMock

class DaskArray:
    pass

class SerializationInfo:
    pass

class JsonDict:
    pass

@pytest.fixture
def mocks():
    return {'DaskArray': MagicMock(), 'SerializationInfo': MagicMock(), 'JsonDict': MagicMock()}

def test_to_json_line2(mocks):
    from your_module import Solution
    solution = Solution()
    dask_array_mock = mocks['DaskArray']
    serialization_info_mock = mocks['SerializationInfo']
    json_dict_mock = mocks['JsonDict']
    result = solution.to_json(None, dask_array_mock, serialization_info_mock)
    assert isinstance(result, (list, JsonDict))
```
---## TASK: 990106
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_990106_juesgqho
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestMaterializeSession::test_materialize_session_line2 FAILED [100%]

================================== FAILURES ===================================
____________ TestMaterializeSession.test_materialize_session_line2 ____________

self = <test_generated.TestMaterializeSession object at 0x0000023AF6A7B560>

    def test_materialize_session_line2(self):
>       from your_module import Solution, MaterializeSessionRequest, get_current_user
E       ModuleNotFoundError: No module named 'your_module'

test_generated.py:42: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED test_generated.py::TestMaterializeSession::test_materialize_session_line2
============================== 1 failed in 0.48s ==============================
```

### Code
```python
import asyncio
from unittest.mock import patch, MagicMock

class TestMaterializeSession:

    def test_materialize_session_line2(self):
        from your_module import Solution, MaterializeSessionRequest, get_current_user
        http_client_mock = MagicMock(spec=http.client)
        db_session_mock = MagicMock(spec=db.session)
        with patch('your_module.http.client', new=http_client_mock), patch('your_module.db.session', new=db_session_mock), patch('your_module.get_current_user') as get_current_user_patch:
            session_id = 'test-session'
            request = MaterializeSessionRequest()
            user = {'id': 123}
            result = asyncio.run(Solution().materialize_session(session_id, request, user))
            assert result == None
            http_client_mock.assert_called_once_with(...)
            db_session_mock.assert_called_once_with(...)
            get_current_user_patch.assert_called_once_with()
```
---## TASK: 432562
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_432562_9rwvirfa
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_select_designs_line2 FAILED                      [100%]

================================== FAILURES ===================================
__________________________ test_select_designs_line2 __________________________

    def test_select_designs_line2():
        solution = Solution()
        configs = [{'target': 'A', 'design_type': 'antibody'}, {'target': 'B', 'design_type': 'minibinder'}]
        raw_results = [{'target_name': 'A', 'binder_name': 'X', 'iptm_score': 0.85, 'iptm_proxy_score': 0.75}, {'target_name': 'A', 'binder_name': 'Y', 'iptm_score': 0.9, 'iptm_proxy_score': 0.8}, {'target_name': 'B', 'binder_name': 'Z', 'iptm_score': 0.7, 'iptm_proxy_score': 0.65}]
        expected_output = pd.DataFrame({'target_name': ['A', 'B'], 'binder_name': ['Y', 'Z']})
        from io import StringIO
>       actual_output = solution.select_designs(configs=configs, raw_results=raw_results)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:45: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000001813A3095B0>
configs = [{'design_type': 'antibody', 'target': 'A'}, {'design_type': 'minibinder', 'target': 'B'}]
raw_results = [{'binder_name': 'X', 'iptm_proxy_score': 0.75, 'iptm_score': 0.85, 'target_name': 'A'}, {'binder_name': 'Y', 'iptm_pr...core': 0.9, 'target_name': 'A'}, {'binder_name': 'Z', 'iptm_proxy_score': 0.65, 'iptm_score': 0.7, 'target_name': 'B'}]
top_n = 84, isoelectric_point_max = 6.0

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
============================== 1 failed in 0.74s ==============================
```

### Code
```python
import pandas as pd
from unittest.mock import MagicMock

def test_select_designs_line2():
    solution = Solution()
    configs = [{'target': 'A', 'design_type': 'antibody'}, {'target': 'B', 'design_type': 'minibinder'}]
    raw_results = [{'target_name': 'A', 'binder_name': 'X', 'iptm_score': 0.85, 'iptm_proxy_score': 0.75}, {'target_name': 'A', 'binder_name': 'Y', 'iptm_score': 0.9, 'iptm_proxy_score': 0.8}, {'target_name': 'B', 'binder_name': 'Z', 'iptm_score': 0.7, 'iptm_proxy_score': 0.65}]
    expected_output = pd.DataFrame({'target_name': ['A', 'B'], 'binder_name': ['Y', 'Z']})
    from io import StringIO
    actual_output = solution.select_designs(configs=configs, raw_results=raw_results)
    assert actual_output.equals(expected_output)
```
---