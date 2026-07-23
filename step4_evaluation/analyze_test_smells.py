"""
Test Code Smell Analysis for SLM-Generated Unit Tests

Detects 8 classic test smells using static AST analysis:
  1. Assertion Roulette     - multiple asserts, none with failure messages
  2. Eager Test             - SUT function called more than once in a single test
  3. Mystery Guest          - test uses external resources (files, network, DB)
  4. Magic Number Test      - unexplained numeric literals in assertions
  5. Obscure Test           - test function too long or too many local variables
  6. General Fixture        - setUp / @pytest.fixture creates ≥3 objects
  7. Conditional Test Logic - if / for / while / try inside test body
  8. Fragile Test           - time.sleep, datetime.now(), unseeded random, hardcoded paths

Literature references:
  van Deursen et al. (2001) "Refactoring Test Code"
  Palomba et al. (2018) "Automatic Test Smell Detection"

Usage:
    python analyze_test_smells.py [--output-dir OUTPUT_DIR]
                                  [--dataset {initial,temperature,realworld,all}]
"""

import ast
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np


DEFAULT_BASE_DIR = Path(__file__).parent.parent

PREFIXES = ["linecov", "linecov2"]

def _classify_dataset(dir_name: str) -> str:
    """Map a predictions_* directory name to a logical dataset label."""
    if "realworld" in dir_name:
        return "realworld"
    if "temperature" in dir_name:
        return "temperature"
    if "initial" in dir_name:
        return "initial"
    return dir_name


def discover_prediction_files(base_dir: Path, target_datasets=None):
    """
    Yield (dataset_label, run_label, model, temperature, approach, jsonl_path) tuples
    by scanning all TestEval/predictions_*/run_*/ directories.

    File naming convention: {prefix}_{model}_temp_{temp}.jsonl
    Approach is "One-Step" (linecov_) or "Two-Step" (linecov2_).
    """
    testeval_dir = base_dir / "TestEval"
    if not testeval_dir.exists():
        return

    for pred_dir in sorted(testeval_dir.glob("predictions_*")):
        if not pred_dir.is_dir():
            continue
        # Skip non-SLM directories
        if "judgellm" in pred_dir.name:
            continue
        # For initial and realworld, only use N=1 (single representative run)
        name = pred_dir.name
        if re.search(r'_(initial|realworld)_\d+$', name):
            if not re.search(r'_(initial|realworld)_1$', name):
                continue

        dataset = _classify_dataset(pred_dir.name)
        if target_datasets and dataset not in target_datasets:
            continue

        for run_dir in sorted(pred_dir.glob("run_*")):
            if not run_dir.is_dir():
                continue
            run_label = run_dir.name

            for jsonl_path in sorted(run_dir.glob("*.jsonl")):
                stem = jsonl_path.stem  # e.g. linecov2_Qwen3-4B_temp_0.2
                if "pynguin" in stem:
                    continue
                # Parse prefix_model_temp_T from filename
                m = re.match(r'^(linecov2?_)(.+)_temp_(\d+\.\d+)$', stem)
                if not m:
                    continue
                prefix_str = m.group(1).rstrip('_')  # "linecov" or "linecov2"
                approach = "Two-Step" if prefix_str == "linecov2" else "One-Step"
                model = m.group(2)
                temperature = m.group(3)
                yield dataset, run_label, model, temperature, approach, jsonl_path

SMELL_NAMES = [
    "assertion_roulette",
    "eager_test",
    "mystery_guest",
    "magic_number_test",
    "obscure_test",
    "general_fixture",
    "conditional_test_logic",
    "fragile_test",
    "unknown_test",
    "trivial_assertion",
    "duplicated_setup",
]

SMELL_LABELS = {
    "assertion_roulette":     "Assertion\nRoulette",
    "eager_test":             "Eager\nTest",
    "mystery_guest":          "Mystery\nGuest",
    "magic_number_test":      "Magic\nNumber Test",
    "obscure_test":           "Obscure\nTest",
    "general_fixture":        "Lack of\nCohesion",
    "conditional_test_logic": "Conditional\nTest Logic",
    "fragile_test":           "External\nDependency",
    "unknown_test":           "Unverified\nAction",
    "trivial_assertion":      "Trivial\nAssertion",
    "duplicated_setup":       "Duplicated\nSetup",
}


MYSTERY_GUEST_BASE_MODULES = {
    'requests', 'httpx', 'socket', 'ftplib', 'aiohttp',
    'sqlite3', 'sqlalchemy', 'pymongo', 'psycopg2', 'pymysql', 'motor',
    'subprocess',
    'boto3', 'google', 'azure',
}


MYSTERY_GUEST_FULL_MODULES = {
    'urllib.request',       # HTTP/FTP requests
    'urllib.robotparser',   # robots.txt fetch (does network I/O)
    'http.client',          # low-level HTTP connection
    'http.server',          # HTTP server (listening on a port)
}

MYSTERY_GUEST_FS_CALLS = {
    # os module — actual I/O operations only; 'replace' removed (FP: str.replace())
    'listdir', 'scandir', 'remove', 'unlink', 'rmdir', 'makedirs', 'mkdir',
    'rename', 'stat', 'lstat', 'access',
    # pathlib.Path methods (duplicates from os section removed)
    'read_text', 'read_bytes', 'write_text', 'write_bytes', 'iterdir',
    'glob', 'rglob',
    # shutil — filesystem copy/move/delete operations
    'rmtree', 'copytree', 'copyfile', 'copy2',
    # tempfile module — creates real files on disk
    'mkstemp', 'mkdtemp', 'NamedTemporaryFile', 'TemporaryFile', 'TemporaryDirectory',
    # io / builtins
    'open',
}

# Numeric literals that are NOT magic numbers.
# 0, 1, -1 are universally context-free; 2/-2 are nearly so (pairs, sign-flips).
# van Deursen (2001) defines "magic" as unexplained — not every non-zero literal.
# Keeping the set narrow avoids masking genuine smells while reducing FPs on
# common length/index/count assertions like `assert len(result) == 2`.
EXEMPT_NUMBERS = {0, 0.0, 1, -1, 2, -2}



# Data classes
@dataclass
class SmellRecord:
    """Analysis result for a single (prediction, target_line) pair."""
    dataset: str
    model: str
    temperature: str
    approach: str
    run: str
    task_num: str
    task_title: str
    func_name: str
    target_line: str
    smells: Dict[str, bool] = field(default_factory=dict)
    smell_details: Dict[str, str] = field(default_factory=dict)
    parseable: bool = True

    def any_smell(self) -> bool:
        return any(self.smells.values())

    def smell_count(self) -> int:
        return sum(1 for v in self.smells.values() if v)



# Utility helpers
def load_jsonl(filepath: Path) -> List[Dict]:
    """Load a JSONL file, returning list of parsed JSON objects."""
    if not filepath.exists():
        return []
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse line {line_num} in {filepath}: {e}")
    return data


def clean_markdown(text: str) -> str:
    """Strip markdown code-block fences."""
    if not text:
        return text
    text = re.sub(r'```python\s*\n?', '', text)
    text = re.sub(r'```\s*\n?', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()


def _get_test_functions(tree: ast.Module) -> List[ast.FunctionDef]:
    """
    Return all test_* functions reachable from the module level.

    Covers:
      - Top-level functions:     def test_foo(): ...
      - Async top-level:         async def test_foo(): ...
      - TestCase methods:        class TestFoo(unittest.TestCase): def test_foo(self): ...
      - Async TestCase methods:  async def test_foo(self): ...
      - Nested TestCase classes: class Outer: class Inner: def test_foo(self): ...
    """
    _TEST_FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
    funcs: List[ast.FunctionDef] = []

    def _collect(nodes, depth: int = 0) -> None:
        for node in nodes:
            if isinstance(node, _TEST_FUNC_TYPES) and node.name.startswith('test'):
                funcs.append(node)
            elif isinstance(node, ast.ClassDef) and depth < 3:
                _collect(ast.iter_child_nodes(node), depth + 1)

    _collect(ast.iter_child_nodes(tree))
    return funcs


def _walk_skip_nested(node: ast.AST):
    """Walk AST nodes but do not descend into nested FunctionDef/AsyncFunctionDef."""
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield from _walk_skip_nested(child)


# Smell detectors
def detect_assertion_roulette(func: ast.FunctionDef) -> Tuple[bool, str]:
    """
    Assertion Roulette: >1 assertion and none carry an explanatory message.

    Two assertion styles are counted:
      - pytest/plain style:   assert expr  /  assert expr, "msg"
      - unittest style:       self.assertEqual(a, b)  /  self.assertEqual(a, b, msg="...")

    Message detection:
      - pytest:    assert expr, "msg"   → ast.Assert.msg is not None
      - unittest:  self.assertEqual(a, b, msg="x")  → keyword arg named 'msg'
                   self.assertEqual(a, b, "x")       → positional 3rd argument
    """
    # --- pytest / plain assert ---
    assert_nodes = [n for n in _walk_skip_nested(func) if isinstance(n, ast.Assert)]
    pytest_has_msg = any(n.msg is not None for n in assert_nodes)

    # --- unittest self.assert*() calls ---
    unittest_nodes = []
    for node in _walk_skip_nested(func):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr.startswith('assert')):
            continue
        if not (isinstance(f.value, ast.Name) and f.value.id == 'self'):
            continue
        unittest_nodes.append(node)

    def _unittest_has_msg(call: ast.Call) -> bool:
        # keyword arg named 'msg'
        if any(kw.arg == 'msg' for kw in call.keywords):
            return True
        
        _RAISES_LIKE = {
            'assertRaises', 'assertRaisesRegex', 'assertRaisesRegexp',
            'assertWarns', 'assertWarnsRegex', 'assertWarnsRegexp',
        }
        if call.func.attr not in _RAISES_LIKE and len(call.args) >= 3:
            return True
        return False

    unittest_has_msg = any(_unittest_has_msg(n) for n in unittest_nodes)

    total = len(assert_nodes) + len(unittest_nodes)
    if total <= 1:
        return False, ""

    has_any_msg = pytest_has_msg or unittest_has_msg
    if not has_any_msg:
        return True, f"{total} assertions ({len(assert_nodes)} assert, {len(unittest_nodes)} unittest), none carry a failure message"
    return False, ""


def detect_eager_test(func: ast.FunctionDef, func_name: str) -> Tuple[bool, str]:
    """
    Eager Test: the test invokes the function-under-test more than once.

    Handles both direct calls (func_name(...)) and method calls
    (solution.func_name(...), self.func_name(...), obj.func_name(...)).
    """
    if not func_name:
        return False, ""
    call_count = 0
    for node in _walk_skip_nested(func):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == func_name:
            call_count += 1
        elif isinstance(node.func, ast.Attribute) and node.func.attr == func_name:
            call_count += 1
    if call_count > 1:
        return True, f"'{func_name}' called {call_count} times in one test"
    return False, ""


def detect_mystery_guest(func: ast.FunctionDef, tree: ast.Module) -> Tuple[bool, str]:
    """
    Mystery Guest: the test uses external resources (files, network, databases).

    Two complementary checks are applied:

    1. Module-level import check: guest-module imports (network, DB, subprocess)
       are collected at file level, but the smell fires only when a name from those
       imports is actually *used* within this specific test function body. This
       prevents flagging every test in a file just because one test at the top
       imports requests.

    2. Function-call check (MYSTERY_GUEST_FS_CALLS): specific filesystem operations
       called anywhere in the test body, regardless of which module they originate
       from. This catches pathlib.Path.read_text(), os.listdir(), open(), etc.
    """
    def _is_guest_import(dotted_name: str) -> bool:
        base = dotted_name.split('.')[0]
        if base in MYSTERY_GUEST_BASE_MODULES:
            return True
        parts = dotted_name.split('.')
        for i in range(1, len(parts) + 1):
            if '.'.join(parts[:i]) in MYSTERY_GUEST_FULL_MODULES:
                return True
        return False

    # 1. Collect local names bound by guest-module imports at module level.
    #    local_name → evidence string for reporting.
    guest_names: Dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_guest_import(alias.name):
                    local = alias.asname if alias.asname else alias.name.split('.')[0]
                    guest_names[local] = f"uses '{alias.name}'"
        elif isinstance(node, ast.ImportFrom):
            if node.module and _is_guest_import(node.module):
                for alias in node.names:
                    local = alias.asname if alias.asname else alias.name
                    guest_names[local] = f"uses '{node.module}.{alias.name}'"

    # Check whether this function body actually references any guest name.
    if guest_names:
        for node in _walk_skip_nested(func):
            if isinstance(node, ast.Name) and node.id in guest_names:
                return True, guest_names[node.id]
            if (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in guest_names):
                return True, guest_names[node.value.id]

    # 2. Filesystem call within the test function body.
    for node in _walk_skip_nested(func):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        # bare open() / direct imported name (e.g. from pathlib import Path; Path.open)
        if isinstance(f, ast.Name) and f.id in MYSTERY_GUEST_FS_CALLS:
            return True, f"calls {f.id}()"
        # attribute call: obj.read_text(), os.listdir(), path.open(), etc.
        if isinstance(f, ast.Attribute) and f.attr in MYSTERY_GUEST_FS_CALLS:
            return True, f"calls .{f.attr}()"

    return False, ""


def _has_magic_number(subtree: ast.AST) -> Optional[str]:
    """Return an evidence string if subtree contains a magic numeric literal."""
    for child in ast.walk(subtree):
        if isinstance(child, ast.Constant):
            val = child.value
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)) and val not in EXEMPT_NUMBERS:
                return f"magic number {val!r} in assertion"
    return None


def detect_magic_number_test(func: ast.FunctionDef) -> Tuple[bool, str]:
    """
    Magic Number Test: an assertion contains a numeric literal whose meaning
    is not self-evident.

    Exempt values: 0, 0.0, 1, -1, 2, -2 (see EXEMPT_NUMBERS), and booleans.
    Flags any other int or float found inside:
      - pytest-style:          assert expr
      - unittest-style:        self.assertEqual(a, b) / self.assertAlmostEqual(a, b)
      - @pytest.mark.parametrize parameter lists (applies same standard to both styles)
    """
    # Check @pytest.mark.parametrize argument values so parametrized tests are
    # subject to the same standard as inline assertion tests.
    for dec in func.decorator_list:
        if (isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == 'parametrize'
                and len(dec.args) >= 2):
            evidence = _has_magic_number(dec.args[1])
            if evidence:
                return True, f"magic number in @parametrize: {evidence}"

    for node in _walk_skip_nested(func):
        # pytest / plain assert
        if isinstance(node, ast.Assert):
            evidence = _has_magic_number(node.test)
            if evidence:
                return True, evidence

        # unittest self.assert*() — inspect the comparison arguments
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr.startswith('assert')
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'self'):
            # Scan all positional args except the last one when it acts as a msg.
            # Use all args because we cannot reliably exclude only the msg position
            # without a full method-signature map — a magic number in the expected
            # value slot is always a smell regardless.
            for arg in node.args:
                evidence = _has_magic_number(arg)
                if evidence:
                    return True, evidence

    return False, ""


def detect_obscure_test(func: ast.FunctionDef) -> Tuple[bool, str]:
    """
    Obscure Test: the test is difficult to understand at a glance.

    Heuristics:
      - Function body has more than 15 AST statements, OR
      - Function body has more than 5 local assignments
    """
    def _is_docstring_expr(n: ast.AST) -> bool:
        return (isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str))

    # Count only the statements *inside* the function body, not the def line itself
    stmt_count = sum(
        1 for n in _walk_skip_nested(func)
        if isinstance(n, ast.stmt) and n is not func and not _is_docstring_expr(n)
    )
    assign_count = sum(
        1 for n in _walk_skip_nested(func)
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign))
    )
    if stmt_count > 15:
        return True, f"{stmt_count} statements (threshold: 15)"
    if assign_count > 5:
        return True, f"{assign_count} assignments (threshold: 5)"
    return False, ""


_SETUP_METHODS = frozenset({
    'setUp', 'setUpClass', 'setUpModule',
    'setup_method', 'setup_function', 'setup',
})


def detect_general_fixture(tree: ast.Module) -> Tuple[bool, str]:
    """
    General Fixture: the test setup initialises more objects than any individual
    test actually needs.

    Heuristic: a setup function/method contains ≥3 assignments.

    Covers setUp, setUpClass, setUpModule, setup_method, setup_function, setup,
    and @pytest.fixture functions.
    """
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            continue

        # Recurse into unittest.TestCase class (all setup variants)
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef) and child.name in _SETUP_METHODS:
                    count = sum(
                        1 for n in ast.walk(child)
                        if isinstance(n, (ast.Assign, ast.AnnAssign))
                    )
                    if count >= 3:
                        return True, f"{child.name} has {count} assignments"

        if not isinstance(node, ast.FunctionDef):
            continue

        # Module-level setup functions (setUp, setUpModule, setup_function, etc.)
        if node.name in _SETUP_METHODS:
            count = sum(
                1 for n in ast.walk(node)
                if isinstance(n, (ast.Assign, ast.AnnAssign))
            )
            if count >= 3:
                return True, f"{node.name} has {count} assignments"

        # @pytest.fixture functions
        for dec in node.decorator_list:
            is_fixture = (
                (isinstance(dec, ast.Name) and dec.id == 'fixture')
                or (isinstance(dec, ast.Attribute) and dec.attr == 'fixture')
                or (isinstance(dec, ast.Call) and (
                    (isinstance(dec.func, ast.Name) and dec.func.id == 'fixture')
                    or (isinstance(dec.func, ast.Attribute) and dec.func.attr == 'fixture')
                ))
            )
            if is_fixture:
                count = sum(
                    1 for n in ast.walk(node)
                    if isinstance(n, (ast.Assign, ast.AnnAssign))
                )
                if count >= 3:
                    return True, f"fixture '{node.name}' has {count} assignments"

    return False, ""


def detect_conditional_test_logic(func: ast.FunctionDef) -> Tuple[bool, str]:
    """
    Conditional Test Logic: the test body contains control-flow constructs
    (if, for, while, try/except) which obscure its intent and make it
    non-deterministic in what it actually exercises.
    """
    for node in _walk_skip_nested(func):
        if node is func:
            continue
        if isinstance(node, ast.If):
            return True, "contains if statement"
        if isinstance(node, ast.For):
            return True, "contains for loop"
        if isinstance(node, ast.While):
            return True, "contains while loop"
        if isinstance(node, (ast.Try, ast.TryStar)):
            return True, "contains try/except"
        if isinstance(node, ast.IfExp):
            return True, "contains conditional expression (ternary)"
    return False, ""


def detect_fragile_test(func: ast.FunctionDef, tree: ast.Module) -> Tuple[bool, str]:
    """
    Fragile Test: the test depends on external, time-varying, or random state
    that can cause it to break without any code changes.

    Checks:
      - time.sleep() — introduces timing dependency
      - datetime.now() / datetime.today() / datetime.utcnow() — clock dependency
      - random.* calls without a preceding random.seed() in the test file
      - Hardcoded absolute file paths in string literals
    """

    # Scope seed check to this function only — a seed in another test must not
    # suppress the fragile smell here.
    has_random_seed = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == 'seed'
        and (
            # random.seed()
            (isinstance(n.func.value, ast.Name)
             and n.func.value.id == 'random')
            # np.random.seed() / numpy.random.seed()
            or (isinstance(n.func.value, ast.Attribute)
                and n.func.value.attr == 'random')
        )
        for n in _walk_skip_nested(func)
    )

    for node in _walk_skip_nested(func):
        if not isinstance(node, ast.Call):
            # Check hardcoded absolute paths in string constants
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Windows absolute path (C:\...) OR Unix path rooted at a known FS
                # prefix.  The prefix whitelist avoids FPs on URL path segments like
                # /api/endpoint, /v1/resource, or /health.
                _UNIX_FS_PREFIXES = (
                    '/home/', '/root/', '/Users/', '/usr/', '/etc/',
                    '/opt/', '/var/lib/', '/var/log/', '/srv/',
                    '/data/', '/mnt/', '/media/', '/tmp/',
                )
                val = node.value
                is_windows_abs = re.match(r'^[A-Za-z]:\\', val)
                is_unix_fs = any(val.startswith(p) for p in _UNIX_FS_PREFIXES)
                if (is_windows_abs or is_unix_fs) and len(val) > 4:
                    return True, f"hardcoded absolute path: {val[:60]!r}"
            continue

        func_node = node.func
        if not isinstance(func_node, ast.Attribute):
            continue

        attr = func_node.attr

        # time.sleep() / asyncio.sleep()  — timing dependency
        if attr == 'sleep':
            caller = func_node.value
            if isinstance(caller, ast.Name) and caller.id in {'time', 'asyncio'}:
                return True, f"calls {caller.id}.sleep()"


        _CLOCK_READS = {
            'time', 'perf_counter', 'monotonic', 'process_time', 'thread_time',
            'gmtime', 'localtime', 'mktime', 'strftime', 'ctime',
        }
        if attr in _CLOCK_READS:
            caller = func_node.value
            if isinstance(caller, ast.Name) and caller.id == 'time':
                return True, f"calls time.{attr}() (clock read)"

        # uuid.*() — generates non-deterministic identifiers
        if attr in {'uuid4', 'uuid1', 'uuid3', 'uuid5'}:
            caller = func_node.value
            if isinstance(caller, ast.Name) and caller.id == 'uuid':
                return True, f"calls uuid.{attr}() (non-deterministic)"

        if attr == 'getenv':
            caller = func_node.value
            if isinstance(caller, ast.Name) and caller.id == 'os':
                return True, "calls os.getenv() (external environment dependency)"


        if attr in {'now', 'today', 'utcnow'}:
            caller = func_node.value
            if isinstance(caller, ast.Name) and caller.id in {'datetime', 'date'}:
                return True, f"calls {caller.id}.{attr}()"
            # datetime.datetime.now() / datetime.date.today()
            if isinstance(caller, ast.Attribute) and caller.attr in {'datetime', 'date'}:
                return True, f"calls {caller.attr}.{attr}()"

        # random.*() without seed — standard library random module
        _RANDOM_FUNCS = {'random', 'randint', 'choice', 'shuffle', 'sample', 'uniform',
                         'gauss', 'randrange', 'choices', 'expovariate'}
        if attr in _RANDOM_FUNCS and not has_random_seed:
            caller = func_node.value
            if isinstance(caller, ast.Name) and caller.id == 'random':
                return True, f"calls random.{attr}() without seed"

        if attr in _RANDOM_FUNCS and not has_random_seed:
            caller = func_node.value
            if (isinstance(caller, ast.Attribute)
                    and caller.attr == 'random'
                    and isinstance(caller.value, ast.Name)
                    and caller.value.id in {'np', 'numpy'}):
                return True, f"calls np.random.{attr}() without seed"


    for node in _walk_skip_nested(func):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name == 'sleep':
            return True, "calls sleep() (from time import sleep)"


    for node in _walk_skip_nested(func):
        if (isinstance(node, ast.Attribute)
                and node.attr == 'environ'
                and isinstance(node.value, ast.Name)
                and node.value.id == 'os'):
            return True, "accesses os.environ (external environment dependency)"

    return False, ""


def detect_unknown_test(func: ast.FunctionDef) -> Tuple[bool, str]:
    """
    Unknown Test / Unverified Action: the test function contains no assertions
    at all, providing a false sense of coverage while verifying nothing.

    Assertion forms counted:
      - pytest / plain:       ast.Assert nodes
      - unittest:             self.assert*() method calls
      - pytest.raises()/warns() context managers

    """
    assert_count = sum(1 for n in _walk_skip_nested(func) if isinstance(n, ast.Assert))

    all_assert_calls = sum(
        1 for n in _walk_skip_nested(func)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr.startswith('assert')
    )

    # pytest.raises() / pytest.warns() used as context managers count as assertions
    pytest_raises_count = 0
    for node in _walk_skip_nested(func):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            ctx = item.context_expr
            if (isinstance(ctx, ast.Call)
                    and isinstance(ctx.func, ast.Attribute)
                    and ctx.func.attr in {'raises', 'warns', 'deprecated_call'}
                    and isinstance(ctx.func.value, ast.Name)
                    and ctx.func.value.id == 'pytest'):
                pytest_raises_count += 1


    fail_count = sum(
        1 for n in _walk_skip_nested(func)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == 'fail'
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id in {'self', 'pytest'}
    )

    if assert_count + all_assert_calls + pytest_raises_count + fail_count == 0:
        return True, "test function contains no assertions"
    return False, ""


def _is_trivial_assert(node: ast.Assert) -> bool:
    """
    Return True if the assert expression matches a trivially weak pattern.

    Patterns (mirroring TRIVIAL_PATTERNS from analyze_assertion_quality.py):
      assert True / assert False          — hardcoded boolean
      assert x is None / is not None      — null check only
      assert isinstance(x, T)             — type check only
      assert x                            — bare variable (no comparison)
      assert x == None                    — equality-to-None
      assert x == [] / {} / ""            — empty container / string
    """
    test = node.test

    # assert True / assert False
    if isinstance(test, ast.Constant) and isinstance(test.value, bool):
        return True

    if isinstance(test, ast.Name):
        return True

    # assert isinstance(x, T)
    if (isinstance(test, ast.Call)
            and isinstance(test.func, ast.Name)
            and test.func.id == 'isinstance'):
        return True

    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        op = test.ops[0]
        comp = test.comparators[0]

        # assert x is None / is not None
        if isinstance(op, (ast.Is, ast.IsNot)) and isinstance(comp, ast.Constant) and comp.value is None:
            return True

        # assert x == None / assert x != None  (should use `is`/`is not`)
        if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None:
            return True

        # assert x == [] / {} / set() / ""
        if isinstance(op, ast.Eq):
            if isinstance(comp, (ast.List, ast.Set)) and not comp.elts:
                return True
            if isinstance(comp, ast.Dict) and not comp.keys:
                return True
            if isinstance(comp, ast.Constant) and comp.value == "":
                return True

    return False


def _is_trivial_unittest_call(call: ast.Call) -> bool:
    """
    Return True if a self.assert*() call is trivially weak.

    Always trivial:
      assertIsNone / assertIsNotNone     — null checks only
      assertIsInstance                   — type check only

    Conditionally trivial:
      assertTrue(x) / assertFalse(x)    — trivial only if the argument is itself
        a bare variable, a bool constant, or an isinstance() call.
        assertTrue(result > 0) or assertFalse(result != expected) are NOT trivial
        because the argument expresses a meaningful quantitative condition.
    """
    attr = call.func.attr  # caller already verified as self.assert*
    if attr in {'assertIsNone', 'assertIsNotNone', 'assertIsInstance'}:
        return True
    if attr in {'assertTrue', 'assertFalse'} and call.args:
        arg = call.args[0]
        if isinstance(arg, ast.Name):
            return True
        if isinstance(arg, ast.Constant) and isinstance(arg.value, bool):
            return True
        if (isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Name)
                and arg.func.id == 'isinstance'):
            return True
        return False  # meaningful expression inside assertTrue/assertFalse
    return False


def detect_trivial_assertion(func: ast.FunctionDef) -> Tuple[bool, str]:
    """
    Trivial / Suboptimal Assertion: ALL assertions in the test verify only
    trivially weak conditions (null checks, type checks, bare booleans, empty
    containers) rather than meaningful return values or side effects.

    The smell fires only when at least one assertion exists but every single one
    is trivial. A test with NO assertions is Unknown Test, not this smell.

    Alves et al. (2025); Sandoval Alcocer et al. (2026)
    """
    # Collect pytest-style asserts
    assert_nodes = [n for n in _walk_skip_nested(func) if isinstance(n, ast.Assert)]

    # Collect unittest-style self.assert*() calls
    unittest_nodes = [
        n for n in _walk_skip_nested(func)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr.startswith('assert')
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == 'self'
    ]

    total = len(assert_nodes) + len(unittest_nodes)
    if total == 0:
        return False, ""  # unknown_test handles zero-assertion case

    trivial_count = (
        sum(1 for n in assert_nodes if _is_trivial_assert(n))
        + sum(1 for n in unittest_nodes if _is_trivial_unittest_call(n))
    )

    if trivial_count == total:
        return True, f"all {total} assertion(s) are trivially weak (null/type/bool checks)"
    return False, ""


def detect_duplicated_setup(test_funcs: List[ast.FunctionDef]) -> Tuple[bool, str]:
    """
    Duplicated Setup: multiple test functions in the same file share identical
    top-level initialisation assignments, inflating test suite size and
    complicating maintenance (e.g. every function starts with
    `solution = Solution()`).

    Detection: compare direct-child ast.Assign nodes across all test functions.
    Two assignments are considered identical if they have the same target name
    and structurally identical right-hand sides (via ast.dump).

    Only direct-child assignments are checked (not those inside loops/conditions)
    because setup code is typically at the top of the function body.

    Sandoval Alcocer et al. (2026)
    """
    if len(test_funcs) < 2:
        return False, ""

    # assignment_key → list of function names that contain it
    assignment_funcs: Dict[str, List[str]] = defaultdict(list)

    for func in test_funcs:
        seen_in_this_func = set()
        for node in ast.iter_child_nodes(func):  # direct children only
            target = None
            value = None

            if isinstance(node, ast.Assign):
                # Single-target assignments only: x = expr
                if len(node.targets) != 1:
                    continue
                target = node.targets[0]
                value = node.value

            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target = node.target
                value = node.value

            if target is None or value is None:
                continue
            if not isinstance(target, (ast.Name, ast.Attribute)):
                continue
            target_name = target.id if isinstance(target, ast.Name) else target.attr
            key = f"{target_name}={ast.dump(value)}"
            if key not in seen_in_this_func:
                seen_in_this_func.add(key)
                assignment_funcs[key].append(func.name)

    duplicates = {k: funcs for k, funcs in assignment_funcs.items() if len(funcs) >= 2}
    if duplicates:
        # Report the most widespread duplicate
        worst_key = max(duplicates, key=lambda k: len(duplicates[k]))
        target_name = worst_key.split('=')[0]
        count = len(duplicates[worst_key])
        return True, f"'{target_name}' setup repeated identically in {count} test functions"
    return False, ""


# Core analysis entry point
def analyze_test_code(test_code: str, func_name: str) -> Tuple[Dict[str, bool], Dict[str, str], bool]:
    """
    Analyse one test-code string for all 8 smells.

    Returns:
        smells      - dict mapping smell name → bool (True = smell detected)
        details     - dict mapping smell name → evidence string
        parseable   - False if the code could not be parsed
    """
    smells = {s: False for s in SMELL_NAMES}
    details = {s: "" for s in SMELL_NAMES}

    cleaned = clean_markdown(test_code)
    if not cleaned:
        return smells, details, False

    try:
        tree = ast.parse(cleaned)
    except SyntaxError:
        return smells, details, False

    test_funcs = _get_test_functions(tree)

    # Module-level smells (analysed once per file)
    for smell_name, detector in [
        ("general_fixture",  lambda: detect_general_fixture(tree)),
        ("duplicated_setup", lambda: detect_duplicated_setup(test_funcs)),
    ]:
        found, detail = detector()
        smells[smell_name] = found
        details[smell_name] = detail

    # Function-level smells — smell present if ANY test function triggers it
    detectors = [
        ("assertion_roulette",     lambda f: detect_assertion_roulette(f)),
        ("eager_test",             lambda f: detect_eager_test(f, func_name)),
        ("mystery_guest",          lambda f: detect_mystery_guest(f, tree)),
        ("magic_number_test",      lambda f: detect_magic_number_test(f)),
        ("obscure_test",           lambda f: detect_obscure_test(f)),
        ("conditional_test_logic", lambda f: detect_conditional_test_logic(f)),
        ("fragile_test",           lambda f: detect_fragile_test(f, tree)),
        ("unknown_test",           lambda f: detect_unknown_test(f)),
        ("trivial_assertion",      lambda f: detect_trivial_assertion(f)),
    ]

    for func in test_funcs:
        for smell_name, detector in detectors:
            if not smells[smell_name]:
                found, detail = detector(func)
                smells[smell_name] = found
                details[smell_name] = detail

    return smells, details, True


# Data loading & analysis runner
def run_analysis(base_dir: Path, target_datasets: Optional[List[str]] = None) -> List[SmellRecord]:
    """
    Iterate over all JSONL prediction files and return a SmellRecord per
    (prediction, target_line) pair.

    Uses glob-based discovery so the script adapts automatically to whatever
    predictions_* directories exist in TestEval/.
    """
    records: List[SmellRecord] = []
    skipped_no_code = 0
    skipped_parse_error = 0

    for dataset, run, model, temperature, approach, pred_file in discover_prediction_files(
        base_dir, target_datasets=target_datasets
    ):
        for pred in load_jsonl(pred_file):
            task_num = str(pred.get('task_num', ''))
            task_title = pred.get('task_title', '')
            func_name = pred.get('func_name', '')
            tests = pred.get('tests', {})

            if not tests:
                skipped_no_code += 1
                continue

            for target_line, test_data in tests.items():
                if not isinstance(test_data, dict):
                    continue
                test_code = test_data.get('test_code', '')
                if not test_code or not test_code.strip():
                    skipped_no_code += 1
                    continue

                smells, details, parseable = analyze_test_code(test_code, func_name)

                if not parseable:
                    skipped_parse_error += 1

                records.append(SmellRecord(
                    dataset=dataset,
                    model=model,
                    temperature=temperature,
                    approach=approach,
                    run=run,
                    task_num=task_num,
                    task_title=task_title,
                    func_name=func_name,
                    target_line=str(target_line),
                    smells=smells,
                    smell_details=details,
                    parseable=parseable,
                ))

    print(f"\nAnalysis complete: {len(records)} records processed")
    print(f"  Skipped (no code): {skipped_no_code}")
    print(f"  Skipped (parse error): {skipped_parse_error}")
    return records


# Aggregation helpers
def aggregate_by_model(records: List[SmellRecord], dataset_filter: Optional[str] = None) -> pd.DataFrame:
    """
    Return a DataFrame with rows = models, columns = smells + parse_error_rate.

    Smell prevalence is computed over parseable records only (you cannot detect
    smells in code that fails to parse). parse_error_rate uses all generated
    records as the denominator so models with high syntax-error rates are not
    artificially deflated on smell metrics.
    """
    if dataset_filter:
        records = [r for r in records if r.dataset == dataset_filter]

    smell_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    n_parseable: Dict[str, int] = defaultdict(int)
    n_generated: Dict[str, int] = defaultdict(int)  # all records, including unparseable

    for r in records:
        key = f"{r.model} ({r.approach})"
        n_generated[key] += 1
        if not r.parseable:
            continue
        n_parseable[key] += 1
        for smell in SMELL_NAMES:
            if r.smells.get(smell):
                smell_counts[key][smell] += 1

    if not n_generated:
        return pd.DataFrame()

    rows = []
    for key in sorted(n_generated.keys()):
        total_p = n_parseable[key]
        total_g = n_generated[key]
        if total_g == 0:
            continue
        row = {
            "model":            key,
            "n_parseable":      total_p,
            "n_generated":      total_g,
            "parse_error_rate": round((total_g - total_p) / total_g * 100, 1),
        }
        for smell in SMELL_NAMES:
            row[smell] = round(smell_counts[key][smell] / total_p * 100, 1) if total_p > 0 else 0.0
        rows.append(row)

    return pd.DataFrame(rows).set_index("model")


def aggregate_overall(records: List[SmellRecord]) -> Dict[str, float]:
    """Return overall smell prevalence (%) across all parseable records."""
    total_p = sum(1 for r in records if r.parseable)
    total_g = len(records)
    if total_p == 0:
        return {}
    result = {
        smell: round(sum(1 for r in records if r.parseable and r.smells.get(smell)) / total_p * 100, 1)
        for smell in SMELL_NAMES
    }
    result["_parse_error_rate"] = round((total_g - total_p) / total_g * 100, 1) if total_g > 0 else 0.0
    result["_n_parseable"] = total_p
    result["_n_generated"] = total_g
    return result


def collapse_to_task_level(records: List[SmellRecord]) -> List[SmellRecord]:
    """
    Collapse per-target-line SmellRecords to one record per task.

    Multiple target_line records for the same (dataset, model, temperature,
    approach, run, task_num) are not independent — they come from the same
    model call on the same task. Collapsing them satisfies the independence
    assumption required for valid statistical comparisons between models.

    Smell present in the collapsed record if ANY target-line triggered it.
    Parseable if ANY target-line was parseable.

    Use this for all percentage statistics reported in the paper.
    Use the raw records only for per-line granularity in the JSON export.
    """
    groups: Dict[tuple, List[SmellRecord]] = defaultdict(list)
    for r in records:
        key = (r.dataset, r.model, r.temperature, r.approach, r.run, r.task_num)
        groups[key].append(r)

    collapsed: List[SmellRecord] = []
    for key, group in groups.items():
        rep = group[0]
        merged_smells = {
            smell: any(r.smells.get(smell, False) for r in group)
            for smell in SMELL_NAMES
        }
        merged_details = {
            smell: next((r.smell_details[smell] for r in group if r.smell_details.get(smell)), "")
            for smell in SMELL_NAMES
        }
        collapsed.append(SmellRecord(
            dataset=rep.dataset,
            model=rep.model,
            temperature=rep.temperature,
            approach=rep.approach,
            run=rep.run,
            task_num=rep.task_num,
            task_title=rep.task_title,
            func_name=rep.func_name,
            target_line="(task-level)",
            smells=merged_smells,
            smell_details=merged_details,
            parseable=any(r.parseable for r in group),
        ))
    return collapsed


# Report generation
def write_text_report(
    records: List[SmellRecord],
    output_dir: Path,
    task_records: Optional[List[SmellRecord]] = None,
) -> None:
    """Write a human-readable summary to test_smell_analysis_report.txt.

    task_records: pre-collapsed task-level records (from collapse_to_task_level).
    If supplied, a second prevalence table is appended using task-level statistics,
    which satisfy the independence assumption for statistical comparisons.
    """
    report_path = output_dir / "test_smell_analysis_report.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "=" * 72,
        "TEST CODE SMELL ANALYSIS — SLM-GENERATED UNIT TESTS",
        f"Generated: {ts}",
        "=" * 72,
        "",
        "SMELL DEFINITIONS",
        "-" * 40,
        "  Assertion Roulette     >1 assert in test, none carry failure messages",
        "  Eager Test             SUT function called multiple times in one test",
        "  Mystery Guest          Test imports/uses external files, network, or DB",
        "  Magic Number Test      Numeric literal >|1| in assertion (no named const)",
        "  Obscure Test           Test >15 stmts OR >5 local variables",
        "  General Fixture (Lack of Cohesion)  setUp/fixture creates ≥3 objects",
        "  Conditional Test Logic if / for / while / try inside test body",
        "  Fragile Test (Ext.)    time.sleep, datetime.now(), unseeded random, paths",
        "  Unknown Test           Test function has zero assertions (verifies nothing)",
        "  Trivial Assertion      All assertions are null/type/bool checks — no value verified",
        "  Duplicated Setup       Same init assignment repeated in ≥2 test functions",
        "",
    ]

    # Overall summary
    overall = aggregate_overall(records)
    n_gen  = overall.pop("_n_generated", len(records))
    n_par  = overall.pop("_n_parseable", sum(1 for r in records if r.parseable))
    pe_rate = overall.pop("_parse_error_rate", 0.0)
    lines += [
        "OVERALL PREVALENCE (all datasets, all models)",
        "-" * 40,
        f"  Generated:  {n_gen:,}",
        f"  Parseable:  {n_par:,}  ({100 - pe_rate:.1f}%)",
        f"  Parse errors: {n_gen - n_par:,}  ({pe_rate:.1f}%)",
        f"  NOTE: smell rates are computed over parseable records only.",
        f"        Parse error rate uses all generated records as denominator.",
        "",
    ]
    for smell in SMELL_NAMES:
        label = SMELL_LABELS[smell].replace('\n', ' ')
        pct = overall.get(smell, 0)
        bar = "#" * int(pct / 2)
        lines.append(f"  {label:<28} {pct:5.1f}%  {bar}")
    lines.append("")

    # Per-dataset breakdown
    datasets = sorted({r.dataset for r in records})
    for ds in datasets:
        ds_records = [r for r in records if r.dataset == ds and r.parseable]
        if not ds_records:
            continue
        df = aggregate_by_model(records, dataset_filter=ds)
        n_gen_ds  = sum(1 for r in records if r.dataset == ds)
        n_par_ds  = len(ds_records)
        pe_ds     = round((n_gen_ds - n_par_ds) / n_gen_ds * 100, 1) if n_gen_ds > 0 else 0.0
        lines += [
            "",
            f"DATASET: {ds.upper()}",
            "=" * 60,
            f"  Generated: {n_gen_ds:,}  |  Parseable: {n_par_ds:,}  |  Parse errors: {pe_ds:.1f}%",
            "",
            f"  {'Model':<45} ParseErr%  " + "  ".join(
                SMELL_LABELS[s].replace('\n', ' ')[:6] for s in SMELL_NAMES
            ),
            "  " + "-" * 70,
        ]
        for model in df.index:
            row = df.loc[model]
            pe_val = row.get("parse_error_rate", 0.0)
            vals = "  ".join(f"{row[s]:5.1f}%" for s in SMELL_NAMES)
            lines.append(f"  {model:<45} {pe_val:6.1f}%    {vals}")

    # Task-level prevalence table (satisfies independence for statistical tests)
    if task_records:
        task_overall = aggregate_overall(task_records)
        t_n_gen  = task_overall.pop("_n_generated", len(task_records))
        t_n_par  = task_overall.pop("_n_parseable", sum(1 for r in task_records if r.parseable))
        t_pe     = task_overall.pop("_parse_error_rate", 0.0)
        lines += [
            "",
            "=" * 72,
            "TASK-LEVEL PREVALENCE (one record per task — use for statistical tests)",
            "=" * 72,
            "  Each task contributes exactly one observation regardless of how many",
            "  target lines it has, satisfying the independence assumption.",
            "",
            f"  Tasks:    {t_n_gen:,}",
            f"  Parseable:{t_n_par:,}  ({100 - t_pe:.1f}%)",
            "",
        ]
        for smell in SMELL_NAMES:
            label = SMELL_LABELS[smell].replace('\n', ' ')
            pct = task_overall.get(smell, 0)
            bar = "#" * int(pct / 2)
            lines.append(f"  {label:<28} {pct:5.1f}%  {bar}")

        task_datasets = sorted({r.dataset for r in task_records})
        for ds in task_datasets:
            tdf = aggregate_by_model(task_records, dataset_filter=ds)
            if tdf.empty:
                continue
            ds_task = [r for r in task_records if r.dataset == ds and r.parseable]
            lines += [
                "",
                f"  DATASET (task-level): {ds.upper()}  — {len(ds_task):,} tasks",
                "  " + "-" * 55,
            ]
            for model in tdf.index:
                row = tdf.loc[model]
                pe_val = row.get("parse_error_rate", 0.0)
                vals = "  ".join(f"{row[s]:5.1f}%" for s in SMELL_NAMES)
                lines.append(f"  {model:<45} {pe_val:6.1f}%    {vals}")

    lines += ["", "=" * 72, "END OF REPORT", "=" * 72]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {report_path}")


def write_heatmap(
    records: List[SmellRecord],
    output_dir: Path,
    dataset_filter: Optional[str] = None,
) -> None:
    """
    Write a heatmap PNG: rows = models, columns = smells, values = % prevalence.
    """
    df = aggregate_by_model(records, dataset_filter=dataset_filter)
    if df.empty:
        return

    # Drop metadata columns (total, n_*, parse_error_rate); keep only smell columns.
    smell_cols = [s for s in SMELL_NAMES if s in df.columns]
    heatmap_data = df[smell_cols].copy()

    # Shorten model names for readability (key = "ModelName (Approach)")
    heatmap_data.index = [m.replace("Meta-Llama-3.1-8B-Instruct-AWQ-INT4", "Llama3.1-8B (4bit)")
                           .replace("Qwen3-8B-AWQ", "Qwen3-8B (4bit)")
                           .replace("-Instruct-2512-AWQ-8bit", "-8B (8bit)")
                           .replace("-Instruct-2512-AWQ-4bit", "-8B (4bit)")
                           .replace("-Instruct-2512", "")
                           .replace("-Instruct-2507", "")
                           .replace("(One-Step)", "(1S)")
                           .replace("(Two-Step)", "(2S-CoT)")
                           for m in heatmap_data.index]
    heatmap_data.columns = [SMELL_LABELS[s] for s in smell_cols]

    fig_height = max(5, len(heatmap_data) * 0.65 + 2)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    sns.heatmap(
        heatmap_data,
        ax=ax,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        vmin=0,
        vmax=100,
        linewidths=0.5,
        linecolor='white',
        cbar_kws={"label": "Prevalence (%)", "shrink": 0.8},
    )

    ax.set_title(
        "Test Smells",
        fontsize=13,
        pad=14,
    )
    ax.set_xlabel("Test Smell Categories", fontsize=11)
    ax.set_ylabel("Model", fontsize=11)
    ax.tick_params(axis='x', labelsize=9)
    ax.tick_params(axis='y', labelsize=10)
    plt.xticks(rotation=30, ha='right')
    plt.setp(ax.get_yticklabels(), fontweight='bold')
    plt.yticks(rotation=0)
    plt.tight_layout()

    suffix = f"_{dataset_filter}" if dataset_filter else "_all"
    out_path = output_dir / f"test_smell_heatmap{suffix}.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Heatmap written: {out_path}")


def write_json_results(records: List[SmellRecord], output_dir: Path) -> None:
    """Dump per-record results to JSON for reproducibility."""
    out = []
    for r in records:
        out.append({
            "dataset": r.dataset,
            "model": r.model,
            "temperature": r.temperature,
            "approach": r.approach,
            "run": r.run,
            "task_num": r.task_num,
            "task_title": r.task_title,
            "func_name": r.func_name,
            "target_line": r.target_line,
            "parseable": r.parseable,
            "smells": r.smells,
            "smell_details": r.smell_details,
            "smell_count": r.smell_count(),
        })
    out_path = output_dir / "test_smell_analysis_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Raw results written: {out_path}")


# CLI entry point
def main():
    parser = argparse.ArgumentParser(
        description="Detect test code smells in SLM-generated unit tests."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "test_smell_analysis_output",
        help="Directory for output files (default: step4_evaluation/test_smell_analysis_output/)",
    )
    parser.add_argument(
        "--dataset",
        choices=["initial", "temperature", "realworld", "all"],
        default="all",
        help="Which dataset(s) to analyse (default: all)",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help="Repository root directory",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    target_datasets = None if args.dataset == "all" else [args.dataset]

    print(f"Base dir : {args.base_dir}")
    print(f"Dataset  : {args.dataset}")
    print(f"Output   : {args.output_dir}")
    print()

    records = run_analysis(args.base_dir, target_datasets=target_datasets)

    if not records:
        print("No records found — check that prediction files exist.")
        return

    task_records = collapse_to_task_level(records)
    print(f"Task-level records: {len(task_records)} "
          f"(collapsed from {len(records)} target-line records)")

    write_text_report(records, args.output_dir, task_records=task_records)
    write_json_results(records, args.output_dir)

    # Heatmaps: one per dataset + one overall
    datasets = sorted({r.dataset for r in records})
    for ds in datasets:
        write_heatmap(records, args.output_dir, dataset_filter=ds)
    if len(datasets) > 1:
        write_heatmap(records, args.output_dir, dataset_filter=None)


if __name__ == "__main__":
    main()
