import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from step4_evaluation.oracle_analysis import (
    OracleClass, classify_oracles, gate_outcomes, instrument_oracles, suite_category,
)


@pytest.mark.parametrize(("source", "expected"), [
    ("assert True", OracleClass.TRIVIAL),
    ("assert 1", OracleClass.TRIVIAL),
    ("assert 2 + 2 == 4", OracleClass.TRIVIAL),
    ("x = True\nassert x", OracleClass.UNKNOWN),
    ("result = sut()\nassert result", OracleClass.WEAK),
    ("result = sut()\nx = result\nassert x", OracleClass.WEAK),
    ("result = sut()\nassert result is not None", OracleClass.WEAK),
    ("result = sut()\nassert isinstance(result, dict)", OracleClass.WEAK),
    ("result = sut()\nassert result == {'x': 1}", OracleClass.STRONG),
    ("result = sut()\nassert len(result) == 3", OracleClass.STRONG),
    ("result = sut()\nassert result > 0", OracleClass.STRONG),
    ("result = sut()\nexpected = 42\nassert result == expected", OracleClass.STRONG),
    ("result = sut()\nassert helper(result)", OracleClass.UNKNOWN),
    ("result = sut()\nassert result is result", OracleClass.UNKNOWN),
    ("with pytest.raises(ValueError):\n    sut()", OracleClass.STRONG),
    ("with pytest.warns(UserWarning):\n    sut()", OracleClass.STRONG),
    ("mock = MagicMock()\nmock.assert_called_once_with(x)", OracleClass.STRONG),
])
def test_classification_cases(source, expected):
    sites = classify_oracles(source, sut_names={"sut"})
    assert len(sites) == 1
    assert sites[0].oracle_class is expected


def test_multiline_assertion_and_stable_ids():
    sites = classify_oracles("result = sut()\nassert (\n result == 42\n)\nassert result")
    assert [s.oracle_id for s in sites] == ["oracle_0001", "oracle_0002"]
    assert [s.oracle_class for s in sites] == [OracleClass.STRONG, OracleClass.WEAK]


def test_instrumentation_records_reached_oracles(tmp_path):
    source = "def sut(): return 42\ndef test_x():\n    result = sut()\n    assert result == 42\n"
    instrumented, sites = instrument_oracles(source, sut_names={"sut"})
    script = tmp_path / "instrumented.py"
    events = tmp_path / "events.jsonl"
    script.write_text(instrumented + "\ntest_x()\n", encoding="utf-8")
    env = os.environ.copy()
    env["ORACLE_EXECUTION_FILE"] = str(events)
    subprocess.run([sys.executable, str(script)], check=True, env=env)
    rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"oracle_id": sites[0].oracle_id}]


def test_failed_oracle_is_still_recorded(tmp_path):
    source = "def test_x():\n    result = 1\n    assert result == 2\n"
    instrumented, sites = instrument_oracles(source)
    script = tmp_path / "instrumented.py"
    events = tmp_path / "events.jsonl"
    script.write_text(instrumented + "\ntest_x()\n", encoding="utf-8")
    env = os.environ.copy()
    env["ORACLE_EXECUTION_FILE"] = str(events)
    proc = subprocess.run([sys.executable, str(script)], env=env)
    assert proc.returncode != 0
    assert json.loads(events.read_text(encoding="utf-8").splitlines()[0])["oracle_id"] == sites[0].oracle_id


def test_instrumentation_survives_global_open_patch(tmp_path):
    """Regression test for a real corpus pattern (task 206871 in the runtime
    instrumentation pilot): a test that does `with patch('builtins.open')`
    around the oracle site. Before this fix, the recorder's own `open()` call
    for writing to ORACLE_EXECUTION_FILE was silently intercepted by the
    patch, so the execution was never recorded even though pass/fail was
    unaffected -- a correctness bug for the executed-oracle gate fields, not
    a pass/fail divergence."""
    source = (
        "from unittest.mock import patch\n"
        "def sut(): return 1\n"
        "def test_x():\n"
        "    with patch('builtins.open') as mock_open:\n"
        "        result = sut()\n"
        "        assert result == 1\n"
    )
    instrumented, sites = instrument_oracles(source, sut_names={"sut"})
    script = tmp_path / "instrumented.py"
    events = tmp_path / "events.jsonl"
    script.write_text(instrumented + "\ntest_x()\n", encoding="utf-8")
    env = os.environ.copy()
    env["ORACLE_EXECUTION_FILE"] = str(events)
    subprocess.run([sys.executable, str(script)], check=True, env=env)
    rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"oracle_id": sites[0].oracle_id}]


def test_instrumentation_survives_global_os_environ_patch(tmp_path):
    """Regression test for a real corpus pattern (task 252302 in the runtime
    instrumentation pilot): `with patch('os.environ') as mock_environ:`
    replaces the whole os.environ object with a MagicMock. Because
    MagicMock.__index__() defaults to 1, an unconfigured
    `os.environ.get("ORACLE_EXECUTION_FILE")` returns a MagicMock that
    open() would silently reinterpret as file descriptor 1 (stdout),
    potentially closing it when the recorder's `with` block exits. The
    recorder must reject a non-string path rather than pass it to open()."""
    source = (
        "from unittest.mock import patch\n"
        "def sut(): return 1\n"
        "def test_x():\n"
        "    with patch('os.environ') as mock_environ:\n"
        "        result = sut()\n"
        "        assert result == 1\n"
    )
    instrumented, sites = instrument_oracles(source, sut_names={"sut"})
    script = tmp_path / "instrumented.py"
    events = tmp_path / "events.jsonl"
    script.write_text(instrumented + "\ntest_x()\nimport sys\nprint('stdout survived', file=sys.stdout)\n",
                       encoding="utf-8")
    env = os.environ.copy()
    env["ORACLE_EXECUTION_FILE"] = str(events)
    proc = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "stdout survived" in proc.stdout
    # No event file is expected: os.environ.get() returns a MagicMock inside
    # the patch block, which the isinstance(str) guard correctly rejects.
    assert not events.exists() or events.read_text(encoding="utf-8") == ""


def test_instrumentation_survives_builtin_name_shadowing(tmp_path):
    """Regression test for a real corpus pattern (task 252302): the production
    harness's fix_relative_imports/fix_absolute_imports wraps unresolvable
    imports in `try: from .compat import str, ... except: str = MagicMock()`
    (a real requests-library-style compat shim). Because the harness then does
    `from under_test import *`, this MagicMock silently shadows the builtin
    `str` for the whole test module -- including inside the recorder function,
    which lives in the same module namespace. The recorder must resolve `str`
    from a reference captured before that wildcard import runs, not from a
    bare `str` lookup at call time."""
    source = (
        "try:\n"
        "    from nonexistent_module import str\n"
        "except ImportError:\n"
        "    from unittest.mock import MagicMock\n"
        "    str = MagicMock()\n"
        "\n"
        "def sut(): return 1\n"
        "def test_x():\n"
        "    result = sut()\n"
        "    assert result == 1\n"
    )
    instrumented, sites = instrument_oracles(source, sut_names={"sut"})
    script = tmp_path / "instrumented.py"
    events = tmp_path / "events.jsonl"
    script.write_text(instrumented + "\ntest_x()\n", encoding="utf-8")
    env = os.environ.copy()
    env["ORACLE_EXECUTION_FILE"] = str(events)
    proc = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"oracle_id": sites[0].oracle_id}]


def test_suite_category_and_gates_are_conservative():
    sites = classify_oracles("result = sut()\nassert helper(result)\nassert result is not None")
    ids = {s.oracle_id for s in sites}
    assert suite_category(sites, ids) == "weak-only"
    assert gate_outcomes(True, sites, ids) == {
        "execution_success": True,
        "executed_nontrivial_gate": True,
        "executed_strong_gate": False,
    }
    assert not gate_outcomes(False, sites, ids)["executed_nontrivial_gate"]


@pytest.mark.parametrize("predicate", [
    "solution.sut(x) == expected",
    "solution.sut(x) > 0",
    "solution.sut(x) in allowed",
])
def test_direct_qualified_focal_calls_in_comparisons_are_strong(predicate):
    site = classify_oracles(f"assert {predicate}", sut_names={"sut"})[0]
    assert site.oracle_class is OracleClass.STRONG
    assert site.sut_dependent is True


@pytest.mark.parametrize(("predicate", "expected"), [
    ("isinstance(solution.sut(x), list)", OracleClass.WEAK),
    ("solution.sut(x) is not None", OracleClass.WEAK),
    ("not solution.sut(x)", OracleClass.WEAK),
])
def test_direct_focal_calls_in_coarse_predicates(predicate, expected):
    assert classify_oracles(f"assert {predicate}", sut_names={"sut"})[0].oracle_class is expected


def test_imported_focal_alias_and_async_focal_call_are_derived():
    aliased = "from package import sut as alias\nassert alias() == 3"
    async_call = "async def test_x():\n    assert await solution.sut() == 3"
    assert classify_oracles(aliased, {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(async_call, {"sut"})[0].oracle_class is OracleClass.STRONG


@pytest.mark.parametrize("predicate", [
    'result.startswith("foo")',
    'result.endswith(".json")',
    'result.equals(expected)',
    'result.issubset(expected)',
    'result.exists()',
    'result.is_file()',
    'result.is_dir()',
    'np.allclose(result, expected)',
    'np.array_equal(result, expected)',
])
def test_recognized_properties_of_derived_results_are_strong(predicate):
    source = f"result = solution.sut()\nassert {predicate}"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


@pytest.mark.parametrize("quantifier", ["all", "any"])
def test_quantifier_over_derived_iterable_is_strong(quantifier):
    source = f"result = solution.sut()\nassert {quantifier}(valid(x) for x in result)"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_quantifier_over_unresolved_iterable_remains_unknown():
    assert classify_oracles("assert all(valid(x) for x in items)", {"sut"})[0].oracle_class is OracleClass.UNKNOWN


@pytest.mark.parametrize(("method", "expected"), [
    ("assertEqual(result, expected)", OracleClass.STRONG),
    ("assertNotEqual(result, expected)", OracleClass.STRONG),
    ("assertIn('x', result)", OracleClass.STRONG),
    ("assertGreater(result, 0)", OracleClass.STRONG),
    ("assertIsNone(result)", OracleClass.WEAK),
    ("assertIsInstance(result, dict)", OracleClass.WEAK),
    ("assertTrue(result)", OracleClass.WEAK),
    ("assertFalse(result)", OracleClass.WEAK),
])
def test_unittest_families_require_and_use_provenance(method, expected):
    source = f"result = solution.sut()\nself.{method}"
    assert classify_oracles(source, {"sut"})[0].oracle_class is expected


@pytest.mark.parametrize("source", [
    "self.assertEqual(1, 1)",
    "self.assertIn('x', expected)",
    "self.assertGreater(value, 0)",
])
def test_unittest_strong_names_without_provenance_remain_unknown(source):
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_unittest_truth_constants_follow_constant_policy():
    assert classify_oracles("self.assertTrue(True)", {"sut"})[0].oracle_class is OracleClass.TRIVIAL
    assert classify_oracles("self.assertFalse(False)", {"sut"})[0].oracle_class is OracleClass.TRIVIAL
    assert classify_oracles("self.assertTrue(False)", {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_exception_contract_requires_focal_call_and_supports_match():
    valid = 'with pytest.raises(ValueError, match="bad"):\n    solution.sut()'
    invalid = 'with pytest.raises(ValueError):\n    unrelated()'
    assert classify_oracles(valid, {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(invalid, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_unittest_exception_callable_form_requires_focal_reference():
    assert classify_oracles("self.assertRaises(ValueError, solution.sut, x)", {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles("self.assertRaises(ValueError, helper, x)", {"sut"})[0].oracle_class is OracleClass.UNKNOWN


@pytest.mark.parametrize("method", [
    "assert_called", "assert_called_once", "assert_called_with", "assert_called_once_with",
    "assert_not_called", "assert_has_calls", "assert_awaited_once_with",
])
def test_mock_contract_requires_mock_receiver(method):
    args = "[call(1)]" if method == "assert_has_calls" else "1" if method in {"assert_called_with", "assert_called_once_with", "assert_awaited_once_with"} else ""
    valid = f"mock = MagicMock()\nmock.{method}({args})"
    invalid = f"ordinary.{method}({args})"
    assert classify_oracles(valid, {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(invalid, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_mock_alias_patch_context_and_mock_named_fixture_are_recognized():
    alias = "mock = MagicMock()\nother = mock\nother.assert_called()"
    patched = "with patch('module.dep') as dependency_mock:\n    dependency_mock.assert_called()"
    fixture = "def test_x(mock_client):\n    mock_client.assert_called_once()"
    for source in (alias, patched, fixture):
        assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


@pytest.mark.parametrize("constructor", ["Mock", "MagicMock", "AsyncMock", "PropertyMock"])
def test_supported_mock_constructors_establish_receiver_provenance(constructor):
    source = f"dependency = {constructor}()\ndependency.assert_called()"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_patch_object_context_and_multiple_context_managers():
    source = "with patch.object(Service, 'dep') as dep_mock, pytest.raises(ValueError, match='bad'):\n    solution.sut()"
    sites = classify_oracles(source, {"sut"})
    assert len(sites) == 1
    assert sites[0].oracle_kind == "exception_contract"
    assert sites[0].oracle_class is OracleClass.STRONG


def test_numpy_testing_oracle_requires_provenance():
    valid = "result = solution.sut()\nnp.testing.assert_allclose(result, expected)"
    invalid = "np.testing.assert_allclose(actual, expected)"
    assert classify_oracles(valid, {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(invalid, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_loop_target_comprehension_containers_and_methods_propagate_provenance():
    loop = "result = solution.sut()\nfor item in result:\n    assert item == 3"
    comprehension = "result = solution.sut()\nvalues = [x for x in result]\nassert values == expected"
    container = "result = solution.sut()\nwrapped = {'x': result}\nassert wrapped == expected"
    method = "result = solution.sut()\ntext = result.strip()\nassert text == expected"
    for source in (loop, comprehension, container, method):
        assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


@pytest.mark.parametrize(("predicate", "expected"), [
    ("result is None or result > 0", OracleClass.STRONG),
    ("isinstance(result, str) or result is None", OracleClass.WEAK),
    ("'error' in result and 'detail' in result", OracleClass.STRONG),
    ("result and condition", OracleClass.UNKNOWN),
])
def test_compound_predicates_are_composed_conservatively(predicate, expected):
    source = f"result = solution.sut()\nassert {predicate}"
    assert classify_oracles(source, {"sut"})[0].oracle_class is expected


def test_reassignment_shadowing_clears_provenance():
    source = "result = solution.sut()\nresult = True\nassert result"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_nested_multiple_oracles_keep_source_order():
    source = "result = solution.sut()\nif result:\n    assert result is not None\nassert result == expected"
    sites = classify_oracles(source, {"sut"})
    assert [s.oracle_id for s in sites] == ["oracle_0001", "oracle_0002"]
    assert [s.oracle_class for s in sites] == [OracleClass.WEAK, OracleClass.STRONG]


def test_arbitrary_helper_and_unrelated_property_remain_unknown():
    source = "result = solution.sut()\nassert validate(result)\nassert unrelated.startswith('x')"
    sites = classify_oracles(source, {"sut"})
    assert all(s.oracle_class is OracleClass.UNKNOWN for s in sites)


def test_qualified_unittest_patch_establishes_mock_receiver_provenance():
    source = "with unittest.mock.patch('module.dep') as mocked_dep:\n    solution.sut()\n    mocked_dep.assert_called_once()"
    sites = classify_oracles(source, {"sut"})
    assert sites[0].oracle_class is OracleClass.STRONG


def test_with_block_assignment_propagates_after_guaranteed_block():
    source = "with patch('x'):\n    result = solution.sut()\nassert result == expected"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_mock_state_comparison_requires_mock_provenance():
    valid = "with patch('x') as mock_dep:\n    solution.sut()\n    assert mock_dep.call_count == 1"
    invalid = "assert ordinary.call_count == 1"
    assert classify_oracles(valid, {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(invalid, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_equality_to_none_is_weak_nullity_not_strong():
    source = "result = solution.sut()\nassert result == None"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.WEAK


def test_nested_quantifier_targets_propagate_sequentially():
    source = "result = solution.sut()\nassert all(isinstance(item, dict) for values in result.values() for item in values)"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_focal_call_marks_receiver_and_mutable_arguments_as_post_call_state():
    receiver = "solution.sut()\nassert solution.state == expected"
    argument = "path = Path('x')\nsolution.sut(path)\nassert path.exists()"
    assert classify_oracles(receiver, {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(argument, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_exception_handler_name_is_derived_from_focal_call():
    source = "try:\n    solution.sut()\nexcept ValueError as exc:\n    assert 'bad' in str(exc)"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_local_container_mutated_with_derived_value_becomes_derived():
    source = "values = []\nfor value in solution.sut():\n    values.append(value)\nassert len(values) > 0"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_hasattr_for_exact_focal_member_is_weak():
    source = "assert hasattr(solution, 'sut')"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.WEAK


# --- v4: provenance-resolution fixes found by the v3 AI-assisted audit ---

def test_underscore_prefix_mismatch_between_call_and_focal_name_is_resolved():
    public_call = "result = solution.sut(x)\nassert result == expected"
    private_focal = "result = solution._sut(x)\nassert result == expected"
    assert classify_oracles(public_call, {"_sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(private_focal, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_bare_direct_focal_call_with_unrecognized_call_form_is_weak_truthiness():
    source = "assert solution.sut(x, y)"
    site = classify_oracles(source, {"sut"})[0]
    assert site.oracle_class is OracleClass.WEAK
    assert site.classification_reason == "sut_derived_truthiness_direct_focal_call"


def test_bare_call_to_unrelated_helper_on_sut_instance_remains_unknown():
    # `twoSum` is not the focal function; a call to it via the SUT instance is
    # boilerplate, not evidence the assertion says anything about the SUT.
    source = "assert solution.twoSum([2, 7, 11, 15], 9) == [0, 1]"
    assert classify_oracles(source, {"to_key_val_list"})[0].oracle_class is OracleClass.UNKNOWN


def test_redirect_stdout_target_capturing_focal_side_effect_is_derived():
    source = (
        "f = io.StringIO()\n"
        "with redirect_stdout(f):\n"
        "    solution.sut()\n"
        "assert f.getvalue().strip() == expected\n"
    )
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


def test_redirect_stdout_target_without_focal_call_inside_stays_unknown():
    source = (
        "f = io.StringIO()\n"
        "with redirect_stdout(f):\n"
        "    unrelated()\n"
        "assert f.getvalue().strip() == expected\n"
    )
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_mock_call_args_unpacked_into_names_are_sut_derived():
    source = (
        "with patch.object(service, 'sut') as mock_method:\n"
        "    solution.run()\n"
        "    args, kwargs = mock_method.call_args\n"
        "    assert isinstance(args[0], str)\n"
    )
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.WEAK


def test_os_environ_state_after_focal_call_is_derived():
    equality = "solution.sut()\nassert os.environ['KEY'] == 'value'"
    nullity = "solution.sut()\nassert os.getenv('KEY') is None"
    assert classify_oracles(equality, {"sut"})[0].oracle_class is OracleClass.STRONG
    assert classify_oracles(nullity, {"sut"})[0].oracle_class is OracleClass.WEAK


def test_os_environ_state_without_prior_focal_call_stays_unknown():
    source = "assert os.environ['KEY'] == 'value'"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.UNKNOWN


def test_torch_allclose_of_derived_result_is_strong():
    source = "result = solution.sut(x)\nassert torch.allclose(result, x)"
    assert classify_oracles(source, {"sut"})[0].oracle_class is OracleClass.STRONG


@pytest.mark.parametrize("source", [
    "mock_dep = MagicMock()\nassert mock_dep.called_once_with(x)",
    "with patch('x') as mock_dep:\n    solution.sut()\n    assert mock_dep.called_once",
])
def test_bogus_mock_attribute_names_are_trivial_not_strong_or_unknown(source):
    site = classify_oracles(source, {"sut"})[0]
    assert site.oracle_class is OracleClass.TRIVIAL
    assert site.classification_reason == "bogus_mock_attribute_vacuous"


def test_real_mock_called_attribute_is_unaffected_by_bogus_denylist():
    source = "with patch('x') as mock_dep:\n    solution.sut()\n    assert mock_dep.called"
    site = classify_oracles(source, {"sut"})[0]
    assert site.oracle_class is OracleClass.STRONG
    assert site.classification_reason == "mock_state_contract_called"
