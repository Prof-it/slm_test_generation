import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# 1. Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 2. Import the module
from step4_evaluation import evaluate_results as target_module

# --- Fixtures ---

@pytest.fixture
def mock_path_globals(monkeypatch):
    """Mock global paths."""
    mock_root = Path("/fake/root")
    monkeypatch.setattr(target_module, 'PROJECT_ROOT', mock_root)
    monkeypatch.setattr(target_module, 'DEFAULT_PREDICTIONS_DIR', mock_root / "TestEval/predictions")
    monkeypatch.setattr(target_module, 'DEFAULT_RESULTS_DIR', mock_root / "evaluation_results")

@pytest.fixture
def sample_task_data():
    return {
        'task_id': 'task_1_line_10',
        'func_name': 'my_func',
        'solution_code': 'def my_func(x): return x * 2',
        'raw_test_code': 'def test_case():\n    assert my_func(2) == 4',
        'mutation_enabled': False,
        'mutation_timeout': 60
    }

# --- Unit Tests: Helper Functions ---

def test_clean_jsonl_line():
    valid = '{"a": 1}'
    assert target_module.clean_jsonl_line(valid) == {"a": 1}
    
    # Test auto-repair
    missing_brace = '{"a": 1'
    assert target_module.clean_jsonl_line(missing_brace) == {"a": 1}
    
    invalid = '{bad_json}'
    assert target_module.clean_jsonl_line(invalid) is None

def test_strip_markdown():
    # Plain code
    assert target_module.strip_markdown("import os") == "import os"
    
    # Markdown block
    md = "```python\nprint('hello')\n```"
    assert target_module.strip_markdown(md) == "print('hello')"
    
    # Thinking block
    think = "<think>Some reasoning</think>```python\nx=1```"
    assert target_module.strip_markdown(think) == "x=1"

    # Already-valid Python containing a ``` sequence inside a string literal
    # (observed with Pynguin: it copies the SUT's own docstring, including
    # any markdown usage example the docstring embeds, into a test's
    # string-literal input data). The fence-stripping regexes below search
    # anywhere in the text, not just at the boundaries, so without the
    # early-return this misfires and corrupts otherwise-valid code.
    pynguin_style = (
        "import under_test as module_0\n\n\n"
        "def test_case_0():\n"
        "    str_0 = 'Usage:\\n    ```python\\n    foo()\\n    ```\\n'\n"
        "    solution_0 = module_0.Solution()\n"
        "    var_0 = solution_0.describe(str_0)\n"
        "    assert var_0 == str_0\n"
    )
    assert target_module.strip_markdown(pynguin_style) == pynguin_style.strip()

    # A genuinely fenced LLM response must still be cleaned correctly even
    # when the code itself also contains a ``` inside a string literal --
    # the outer response-level fence takes priority since the raw text
    # (conversational preamble + fence markers) does not parse as valid
    # Python on its own, so the early-return above does not fire.
    fenced_with_inner_backticks = (
        "Here is the test:\n"
        "```python\n"
        "def test_case_0():\n"
        "    doc = 'example:\\n    ```\\n    foo()\\n    ```\\n'\n"
        "    assert doc\n"
        "```\n"
    )
    cleaned = target_module.strip_markdown(fenced_with_inner_backticks)
    assert cleaned.startswith("def test_case_0():")

def test_fix_relative_imports():
    import ast

    # Single-line relative import: existing behavior, must stay unchanged.
    single = "from .broker import get_broker"
    fixed = target_module.fix_relative_imports(single)
    ast.parse(fixed)
    assert "get_broker = _MagicMock()" in fixed

    # Multi-line parenthesized relative import (observed in task 916895's
    # reference module: a lazy `from ...pkg import (\n    a,\n    b,\n)`
    # inside a function body). The line-by-line regex previously only saw
    # the opening line, producing names_str == "(" and emitting a corrupt
    # `( = _MagicMock()` statement while orphaning the continuation lines,
    # a SyntaxError ("'(' was never closed").
    multiline = (
        "def f():\n"
        "    from ...window_state_ports.pane_state import (\n"
        "        get_pane_projection,\n"
        "        upsert_pane,\n"
        "    )\n"
        "    return get_pane_projection\n"
    )
    fixed = target_module.fix_relative_imports(multiline)
    ast.parse(fixed)  # must not raise SyntaxError
    assert "get_pane_projection = _MagicMock()" in fixed
    assert "upsert_pane = _MagicMock()" in fixed

def test_check_for_assertions():
    assert target_module.check_for_assertions("assert 1 == 1") is True
    assert target_module.check_for_assertions("self.assertTrue(True)") is True
    assert target_module.check_for_assertions("print('hello')") is False
    assert target_module.check_for_assertions("invalid syntax :") is False

def test_standardize_func_name():
    code = "def wrong_name(): pass"
    fixed = target_module._standardize_func_name(code, "test_target")
    assert "def test_target():" in fixed

# --- Unit Tests: Worker Logic (evaluate_single_test_worker) ---

@patch(f'{target_module.__name__}.subprocess.run')
@patch(f'{target_module.__name__}.tempfile.mkdtemp')
@patch(f'{target_module.__name__}.shutil.rmtree')
@patch(f'{target_module.__name__}.Path') # Mock Path completely to intercept write_text
def test_evaluate_worker_pass(mock_path_cls, mock_rmtree, mock_mkdtemp, mock_run, sample_task_data):
    """Test a successful test execution scenario."""
    
    # Setup Paths
    mock_tmp_dir = MagicMock()
    mock_mkdtemp.return_value = "/tmp/fake"
    mock_path_cls.return_value = mock_tmp_dir
    
    # Setup Subprocess (Pass)
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "Success"
    mock_proc.stderr = ""
    mock_run.return_value = mock_proc
    
    # Act
    result, log = target_module.evaluate_single_test_worker(sample_task_data)
    
    # Assert
    assert result['status'] == target_module.EvaluationResult.PASS
    assert result['has_assertions'] is True
    assert log is None # No log on success unless mutation error
    
    # Verify file writes happened
    # write_text is called on the Path objects returned by / operator
    assert (mock_tmp_dir / "under_test.py").write_text.called
    assert (mock_tmp_dir / "test_generated.py").write_text.called

@patch(f'{target_module.__name__}.subprocess.run')
@patch(f'{target_module.__name__}.tempfile.mkdtemp')
@patch(f'{target_module.__name__}.shutil.rmtree')
@patch(f'{target_module.__name__}.Path')
def test_evaluate_worker_fail(mock_path_cls, mock_rmtree, mock_mkdtemp, mock_run, sample_task_data):
    """Test a failing test execution (Assertion Error)."""
    
    mock_tmp_dir = MagicMock()
    mock_path_cls.return_value = mock_tmp_dir
    
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = "Failure"
    mock_proc.stderr = "AssertionError: 4 != 5"
    mock_run.return_value = mock_proc
    
    # Act
    result, log = target_module.evaluate_single_test_worker(sample_task_data)
    
    # Assert
    assert result['status'] == target_module.EvaluationResult.ASSERTION_ERROR
    assert log is not None
    assert log['status'] == target_module.EvaluationResult.ASSERTION_ERROR
    assert "AssertionError" in log['output']

@patch(f'{target_module.__name__}.run_cosmic_ray_analysis')
@patch(f'{target_module.__name__}.subprocess.run')
@patch(f'{target_module.__name__}.tempfile.mkdtemp')
@patch(f'{target_module.__name__}.shutil.rmtree')
@patch(f'{target_module.__name__}.Path')
def test_evaluate_worker_with_mutation(mock_path_cls, mock_rmtree, mock_mkdtemp, mock_run, mock_mutation, sample_task_data):
    """Test worker with mutation enabled."""
    
    # Enable mutation in task
    sample_task_data['mutation_enabled'] = True
    
    mock_tmp_dir = MagicMock()
    mock_path_cls.return_value = mock_tmp_dir
    
    # Mock Run 1: Test Execution (Pass)
    mock_proc_exec = MagicMock(returncode=0, stdout="OK", stderr="")
    
    # Mock Run 2: Coverage (Mock that it succeeds)
    mock_proc_cov = MagicMock(returncode=0)
    
    mock_run.side_effect = [mock_proc_exec, mock_proc_cov]
    
    # Mock Mutation Result
    mock_mutation.return_value = {
        "mutation_score": 85.0,
        "total_mutants": 10,
        "killed_mutants": 8,
        "survived_mutants": 2,
        "error": None
    }
    
    # We need to mock the coverage.json read context
    cov_json = json.dumps({"totals": {"percent_covered": 100.0}})
    
    # The worker logic does: (tmp_dir / "coverage.json").exists()
    # Then open(tmp_dir / "coverage.json")
    
    # Since we mocked Path class, the instances returned by it are Mocks.
    # We configure the specific "coverage.json" mock
    mock_cov_path = MagicMock()
    mock_cov_path.exists.return_value = True
    
    def path_truediv_side_effect(arg):
        if str(arg) == "coverage.json": return mock_cov_path
        return MagicMock() # generic path
    
    mock_tmp_dir.__truediv__.side_effect = path_truediv_side_effect
    
    with patch("builtins.open", mock_open(read_data=cov_json)):
        result, log = target_module.evaluate_single_test_worker(sample_task_data)
        
        # Assert Mutation was run
        assert mock_mutation.called
        assert result['mutation_score'] == 85.0
        assert result['mutation_stats']['total'] == 10

# --- Unit Tests: Mutation Runner (run_cosmic_ray_analysis) ---

@patch(f'{target_module.__name__}.subprocess.run')
@patch(f'{target_module.__name__}.tempfile.mkdtemp')
@patch(f'{target_module.__name__}.Path')
def test_run_cosmic_ray_analysis(mock_path_cls, mock_mkdtemp, mock_run):
    """Test the mutation runner orchestration."""
    mock_mkdtemp.return_value = "/tmp/cr"
    mock_work_dir = MagicMock()
    mock_path_cls.return_value = mock_work_dir
    
    # We expect 3 subprocess calls: Init, Exec, Dump
    mock_init = MagicMock(returncode=0)
    mock_exec = MagicMock(returncode=0)
    
    # Mock Dump output (list of mutants)
    dump_json = json.dumps([
        {"test_outcome": {"outcome": "killed"}},
        {"test_outcome": {"outcome": "survived"}}
    ])
    mock_dump = MagicMock(returncode=0, stdout=dump_json)
    
    mock_run.side_effect = [mock_init, mock_exec, mock_dump]
    
    res = target_module.run_cosmic_ray_analysis("source", "test")
    
    assert res['total_mutants'] == 2
    assert res['killed_mutants'] == 1
    assert res['mutation_score'] == 50.0

# --- Integration Test: File Processing Loop ---

@patch(f'{target_module.__name__}.ProcessPoolExecutor')
def test_process_file_loop(mock_executor):
    """Test the data loading and job submission logic in process_file."""
    
    # Input JSON content
    input_content = json.dumps({
        "task_num": "1",
        "func_name": "foo",
        "code": "def foo(): pass",
        "tests": {"line_1": "assert foo()"}
    }) + "\n"
    
    # Define a side_effect for open() to handle read vs write
    # We want 'read' mode to return input_content, 'write' mode to return a dummy file
    mock_read_file = mock_open(read_data=input_content)
    mock_write_file = mock_open()
    
    def open_side_effect(file, mode='r', **kwargs):
        if 'r' in mode:
            return mock_read_file(file, mode, **kwargs)
        else:
            return mock_write_file(file, mode, **kwargs)

    # Mock Arguments
    args = MagicMock()
    args.limit = None
    args.mutation_subset = None
    args.run_mutation = False
    args.workers = 1
    args.mutation_timeout = 60
    
    # Mock Executor & Future
    mock_future = MagicMock()
    mock_future.result.return_value = ({"status": "Pass"}, None)
    
    mock_pool = MagicMock()
    mock_pool.submit.return_value = mock_future
    
    mock_executor.return_value.__enter__.return_value = mock_pool
    
    with patch("builtins.open", side_effect=open_side_effect) as mocked_open_call:
        # Patch as_completed to return our mock_future
        with patch(f'{target_module.__name__}.as_completed', return_value=[mock_future]):
            
            target_module.process_file(Path("in.jsonl"), Path("out.jsonl"), args)
            
            # Verify submit was called once (because 1 task was read)
            assert mock_pool.submit.call_count == 1
            
            # Verify write happened
            # The write file handle is returned by open with mode 'w'
            handle = mock_write_file()
            assert handle.write.called

@patch(f'{target_module.__name__}.process_file')
@patch(f'{target_module.__name__}.Path.rglob')
def test_main_recursive_scan(mock_rglob, mock_process, mock_path_globals):
    """Test the main entry point's recursive directory scanning."""
    
    # Setup CLI args
    with patch(f'{target_module.__name__}.parse_arguments') as mock_args:
        mock_args.return_value = MagicMock(
            input_file=None, 
            input_dir=None, # Uses default
            output_dir=None
        )
        
        # Setup File System Mock
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_file.stem = "test_run"
        mock_file.relative_to.return_value = Path("subdir/test_run.jsonl")
        
        mock_rglob.return_value = [mock_file]
        
        target_module.main()
        
        # Assert process_file was called
        mock_process.assert_called_once()
        
        # Check output path logic
        args, _ = mock_process.call_args
        out_path = args[1]
        assert "subdir" in str(out_path)