# FAILURE LOG: linecov_granite-4.0-micro_temp_0.0.jsonl

## TASK: 896053
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_896053_d0rc3xg3
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestSolution::test_convert_voc_bbox_line2 FAILED      [100%]

================================== FAILURES ===================================
__________________ TestSolution.test_convert_voc_bbox_line2 ___________________

self = <test_generated.TestSolution testMethod=test_convert_voc_bbox_line2>

    def test_convert_voc_bbox_line2(self):
        solution = Solution()
        coords = [10.0, 20.0, 30.0, 40.0]
        img_size = (100, 200)
        target = 'xywh'
        expected_output = [10.0, 20.0, 20.0, 20.0]
>       result = solution.convert_voc_bbox(coords, img_size, target)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:47: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000001A522CE17F0>
coords = [10.0, 20.0, 30.0, 40.0], img_size = (100, 200), target = 'xywh'

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
E       ValueError: Unsupported target format: xywh

under_test.py:48: ValueError
=========================== short test summary info ===========================
FAILED test_generated.py::TestSolution::test_convert_voc_bbox_line2 - ValueEr...
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import unittest
from typing import List

class TestSolution(unittest.TestCase):

    def test_convert_voc_bbox_line2(self):
        solution = Solution()
        coords = [10.0, 20.0, 30.0, 40.0]
        img_size = (100, 200)
        target = 'xywh'
        expected_output = [10.0, 20.0, 20.0, 20.0]
        result = solution.convert_voc_bbox(coords, img_size, target)
        self.assertEqual(result, expected_output)
if __name__ == '__main__':
    unittest.main()
```
---## TASK: 916895
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_916895_q_ic954l
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestRecordPaneState::test_record_pane_state_line2 FAILED [100%]

================================== FAILURES ===================================
______________ TestRecordPaneState.test_record_pane_state_line2 _______________

self = <test_generated.TestRecordPaneState testMethod=test_record_pane_state_line2>

    def test_record_pane_state_line2(self):
        solution = Solution()
        result = solution.record_pane_state('win123', 'pane456', 'active')
>       self.assertIsNone(result)
E       AssertionError: <MagicMock name='mock().state' id='2646140998368'> is not None

test_generated.py:44: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::TestRecordPaneState::test_record_pane_state_line2
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import unittest
from unittest.mock import MagicMock

class TestRecordPaneState(unittest.TestCase):

    def test_record_pane_state_line2(self):
        solution = Solution()
        result = solution.record_pane_state('win123', 'pane456', 'active')
        self.assertIsNone(result)
```
---## TASK: 119665
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_119665_12dv8l7f
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestSolution::test__run_async_line2 FAILED            [100%]

================================== FAILURES ===================================
_____________________ TestSolution.test__run_async_line2 ______________________

self = <test_generated.TestSolution testMethod=test__run_async_line2>

    def test__run_async_line2(self):
        solution = Solution()
>       dataset = MagicMock(spec_set)
                            ^^^^^^^^
E       NameError: name 'spec_set' is not defined

test_generated.py:43: NameError
=========================== short test summary info ===========================
FAILED test_generated.py::TestSolution::test__run_async_line2 - NameError: na...
============================== 1 failed in 0.35s ==============================
```

### Code
```python
import unittest
from unittest.mock import MagicMock

class TestSolution(unittest.TestCase):

    def test__run_async_line2(self):
        solution = Solution()
        dataset = MagicMock(spec_set)
        udf = [MagicMock(), MagicMock()]
        roi = MagicMock()
        corrections = None
        progress = True
        backends = []
        plots = {}
        iterate = False
        gen_or_result = solution._run_async(dataset, udf, roi, corrections, progress, backends, plots, iterate)
        self.assertIsInstance(gen_or_result, (types.AsyncGeneratorType, object))
```
---## TASK: 25953
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_25953_89sm_3y3
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestSharesAdd::test_shares_add_line2 FAILED           [100%]

================================== FAILURES ===================================
_____________________ TestSharesAdd.test_shares_add_line2 _____________________

self = <test_generated.TestSharesAdd object at 0x0000013FF7878470>

    def test_shares_add_line2(self):
        solution = Solution()
>       result = solution.shares_add(object_type='document', object_id='12345', email='recipient@example.com', permission='read', expires=None, as_json=False)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:42: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x0000013FF78C0890>
object_type = 'document', object_id = '12345', email = 'recipient@example.com'
permission = 'read', expires = None, as_json = False

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
FAILED test_generated.py::TestSharesAdd::test_shares_add_line2 - NameError: n...
============================== 1 failed in 0.36s ==============================
```

### Code
```python
import pytest

class TestSharesAdd:

    def test_shares_add_line2(self):
        solution = Solution()
        result = solution.shares_add(object_type='document', object_id='12345', email='recipient@example.com', permission='read', expires=None, as_json=False)
        assert result == None
```
---## TASK: 51723
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_51723_jtkrourq
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

self = <[AttributeError('_mock_methods') raised in repr()] MagicMock object at 0x12fec7a57f0>
spec = <MagicMock id='1305648856768'>, spec_set = None
_spec_as_instance = False, _eat_self = False

    def _mock_add_spec(self, spec, spec_set, _spec_as_instance=False,
                       _eat_self=False):
        if _is_instance_mock(spec):
>           raise InvalidSpecError(f'Cannot spec a Mock object. [object={spec!r}]')
E           unittest.mock.InvalidSpecError: Cannot spec a Mock object. [object=<MagicMock id='1305648856768'>]

C:\Program Files\Python312\Lib\unittest\mock.py:511: InvalidSpecError
=========================== short test summary info ===========================
FAILED test_generated.py::TestGetDtype::test_get_dtype_line2 - unittest.mock....
============================== 1 failed in 0.42s ==============================
```

### Code
```python
import unittest
from unittest.mock import MagicMock

class TestGetDtype(unittest.TestCase):

    def test_get_dtype_line2(self):
        solution = Solution()
        array_mock = MagicMock(spec=ZarrArray)
        result = solution.get_dtype(array_mock)
        self.assertIsNotNone(result)
```
---## TASK: 872607
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_872607_9fb5r6sg
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_test_line2 FAILED                                [100%]

================================== FAILURES ===================================
_______________________________ test_test_line2 _______________________________

    def test_test_line2():
        solution = Solution()
    
        @patch('Solution.test')
        async def test_mocked_test(mock_test):
            await asyncio.sleep(0)
            return True
>       result = asyncio.run(solution.test())
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:46: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Program Files\Python312\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Program Files\Python312\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Program Files\Python312\Lib\asyncio\base_events.py:691: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x0000013D545E96A0>, test_timeout = 10800
content = None, twice = True

    async def test(self, test_timeout=3 * HOURS, content=None, twice=True):
        """Test the model serving endpoint"""
>       url = await Server.get_url.aio()
                    ^^^^^^
E       NameError: name 'Server' is not defined

under_test.py:36: NameError
=========================== short test summary info ===========================
FAILED test_generated.py::test_test_line2 - NameError: name 'Server' is not d...
============================== 1 failed in 0.44s ==============================
```

### Code
```python
import asyncio
from unittest.mock import patch

def test_test_line2():
    solution = Solution()

    @patch('Solution.test')
    async def test_mocked_test(mock_test):
        await asyncio.sleep(0)
        return True
    result = asyncio.run(solution.test())
    assert result == True
```
---## TASK: 234352
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_234352_qr_8rl6k
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestAssertIsInstance::test_assert_isinstance_line2 FAILED [100%]

================================== FAILURES ===================================
______________ TestAssertIsInstance.test_assert_isinstance_line2 ______________

self = <test_generated.TestAssertIsInstance testMethod=test_assert_isinstance_line2>

    def test_assert_isinstance_line2(self):
        solution = Solution()
>       self.assertEqual(type(solution.assert_isinstance(42, int)), int)
E       AssertionError: <class 'bool'> != <class 'int'>

test_generated.py:42: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::TestAssertIsInstance::test_assert_isinstance_line2
============================== 1 failed in 0.13s ==============================
```

### Code
```python
import unittest

class TestAssertIsInstance(unittest.TestCase):

    def test_assert_isinstance_line2(self):
        solution = Solution()
        self.assertEqual(type(solution.assert_isinstance(42, int)), int)
        with self.assertRaises(AssertionError):
            solution.assert_isinstance('hello', list)
if __name__ == '__main__':
    unittest.main()
```
---## TASK: 235598
**STATUS:** Assertion Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_235598_vwth5tho
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::TestFromMsgpack::test_from_msgpack_line2 FAILED       [100%]

================================== FAILURES ===================================
___________________ TestFromMsgpack.test_from_msgpack_line2 ___________________

self = <test_generated.TestFromMsgpack object at 0x00000206EAD2FCB0>

    def test_from_msgpack_line2(self):
        solution = Solution()
        packed_data = b'\x93\xa52\x04'
        result = solution.from_msgpack(int, packed_data)
>       assert result == 42
E       AssertionError: assert <MagicMock name='mock()' id='2228733187024'> == 42

test_generated.py:44: AssertionError
=========================== short test summary info ===========================
FAILED test_generated.py::TestFromMsgpack::test_from_msgpack_line2 - Assertio...
============================== 1 failed in 0.14s ==============================
```

### Code
```python
import pytest

class TestFromMsgpack:

    def test_from_msgpack_line2(self):
        solution = Solution()
        packed_data = b'\x93\xa52\x04'
        result = solution.from_msgpack(int, packed_data)
        assert result == 42
```
---## TASK: 577470
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_577470_4ktc86n3
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_to_json_line2[None-array0-None-expected0] FAILED [100%]

================================== FAILURES ===================================
_______________ test_to_json_line2[None-array0-None-expected0] ________________

cls = None, array = [1, 2, 3], info = None, expected = [1, 2, 3]

    @pytest.mark.parametrize('cls, array, info, expected', [(None, [1, 2, 3], None, [1, 2, 3])])
    def test_to_json_line2(cls, array, info, expected):
        solution = Solution()
>       result = solution.to_json(cls, array, info)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:41: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x000002423755F230>, cls = None
array = [1, 2, 3], info = None

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
FAILED test_generated.py::test_to_json_line2[None-array0-None-expected0] - At...
============================== 1 failed in 0.30s ==============================
```

### Code
```python
import pytest

@pytest.mark.parametrize('cls, array, info, expected', [(None, [1, 2, 3], None, [1, 2, 3])])
def test_to_json_line2(cls, array, info, expected):
    solution = Solution()
    result = solution.to_json(cls, array, info)
    assert result == expected
```
---## TASK: 432562
**STATUS:** Runtime Error

### Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- C:\Repos\slm_test_generation\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\cbark\AppData\Local\Temp\eval_432562_8_7fvsz8
plugins: anyio-4.13.0, cov-5.0.0
collecting ... collected 1 item

test_generated.py::test_select_designs_line2 FAILED                      [100%]

================================== FAILURES ===================================
__________________________ test_select_designs_line2 __________________________

    def test_select_designs_line2():
        configs = [{'target': 'A', 'design_type': 'antibody'}, {'target': 'B', 'design_type': 'minibinder'}]
        raw_results = [{'target_name': 'A', 'binder_name': 'X', 'iptm_score': 0.85, 'iptm_proxy_score': 0.75}, {'target_name': 'A', 'binder_name': 'Y', 'iptm_score': 0.9, 'iptm_proxy_score': 0.8}, {'target_name': 'B', 'binder_name': 'Z', 'iptm_score': 0.7, 'iptm_proxy_score': 0.65}]
        expected_output = pd.DataFrame({'target_name': ['A', 'B'], 'binder_name': ['Y', 'Z']})
        solution = Solution()
>       result = solution.select_designs(configs, raw_results)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_generated.py:43: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <under_test.Solution object at 0x0000023B29106390>
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
============================== 1 failed in 0.82s ==============================
```

### Code
```python
import pandas as pd

def test_select_designs_line2():
    configs = [{'target': 'A', 'design_type': 'antibody'}, {'target': 'B', 'design_type': 'minibinder'}]
    raw_results = [{'target_name': 'A', 'binder_name': 'X', 'iptm_score': 0.85, 'iptm_proxy_score': 0.75}, {'target_name': 'A', 'binder_name': 'Y', 'iptm_score': 0.9, 'iptm_proxy_score': 0.8}, {'target_name': 'B', 'binder_name': 'Z', 'iptm_score': 0.7, 'iptm_proxy_score': 0.65}]
    expected_output = pd.DataFrame({'target_name': ['A', 'B'], 'binder_name': ['Y', 'Z']})
    solution = Solution()
    result = solution.select_designs(configs, raw_results)
    assert result.equals(expected_output)
```
---