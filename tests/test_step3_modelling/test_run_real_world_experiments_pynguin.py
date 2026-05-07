import pytest
import sys
import os
import json
import subprocess
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# 1. Setup path to import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import based on the filename provided in your logs
from step3_modelling import run_real_world_experiments_pynguin as target_module

# Define module path for patching
MODULE_PATH = 'step3_modelling.run_real_world_experiments_pynguin'

# --- Fixtures ---

@pytest.fixture
def mock_path_globals(monkeypatch):
    """Mock global path constants."""
    mock_root = Path("/fake/root")
    monkeypatch.setattr(target_module, 'PROJECT_ROOT', mock_root)
    monkeypatch.setattr(target_module, 'TESTEVAL_DIR', mock_root / "TestEval")
    monkeypatch.setattr(target_module, 'DATA_PATH', mock_root / "TestEval/data/realworld-py.jsonl")
    monkeypatch.setattr(target_module, 'OUTPUT_DIR', mock_root / "TestEval/predictions_pynguin")

@pytest.fixture
def sample_task():
    """Returns a sample task dictionary mimicking the input dataset."""
    return {
        "task_num": 12345,
        "task_title": "Test::Func",
        "func_name": "target_func",
        "python_solution": "def target_func(): return 1",
        "target_lines": [2, 3]
    }

# --- Unit Tests ---

@patch(f'{MODULE_PATH}.subprocess.run')
def test_check_pynguin_availability_success(mock_run):
    """Test that function passes silently if pynguin returns 0."""
    mock_run.return_value = MagicMock(returncode=0)
    target_module.check_pynguin_availability()

@patch(f'{MODULE_PATH}.subprocess.run')
def test_check_pynguin_availability_failure(mock_run):
    """Test that function exits if pynguin fails."""
    mock_run.side_effect = subprocess.CalledProcessError(1, ["cmd"], stderr="Error!")
    
    with pytest.raises(SystemExit) as excinfo:
        target_module.check_pynguin_availability()
    assert excinfo.value.code == 1


@patch(f'{MODULE_PATH}.subprocess.run')
def test_run_pynguin_timeout(mock_run, sample_task):
    """Test handling of subprocess timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="pynguin", timeout=120)

    with patch(f'{MODULE_PATH}.tempfile.TemporaryDirectory'), \
         patch(f'{MODULE_PATH}.Path'):
         
         result = target_module.run_pynguin_for_task(sample_task, seed=99)

    assert result['status'] == "TIMEOUT"
    assert result['timed_out'] is True

# --- Integration Tests: Main Loop ---

@patch(f'{MODULE_PATH}.run_pynguin_for_task')
@patch(f'{MODULE_PATH}.check_pynguin_availability')
@patch(f'{MODULE_PATH}.argparse.ArgumentParser.parse_args')
def test_main_execution_flow(mock_args, mock_check, mock_process_task, mock_path_globals):
    """
    Test the main loop processing.
    """
    mock_args.return_value = MagicMock(quick_test=True, passes=2)
    
    fake_dataset_content = json.dumps({"task_num": 1, "func_name": "A"}) + "\n" + \
                           json.dumps({"task_num": 2, "func_name": "B"}) + "\n"
    
    mock_data_path = MagicMock()
    mock_data_path.exists.return_value = True
    
    # Mock Output Directory Logic
    mock_out_dir = MagicMock()
    
    # IMPORTANT: Mock the output file check so it returns False (Not Exists).
    # Chain: OUTPUT_DIR / run_id / file_name -> .exists()
    # If this returns True (default for Mocks), the script skips tasks.
    mock_out_dir.__truediv__.return_value.__truediv__.return_value.exists.return_value = False

    # Mock success return
    mock_process_task.return_value = {"task_num": 1, "status": "Pass"}

    with patch(f'{MODULE_PATH}.DATA_PATH', mock_data_path), \
         patch(f'{MODULE_PATH}.OUTPUT_DIR', mock_out_dir), \
         patch("builtins.open", mock_open(read_data=fake_dataset_content)) as mock_file:
        
        target_module.main()
        
        # Assertions
        mock_check.assert_called_once()
        
        # Expect 4 calls: 2 dataset items * 2 passes
        assert mock_process_task.call_count == 4
        
        # Verify seed increment
        seed_arg_1 = mock_process_task.call_args_list[0][0][1]
        seed_arg_2 = mock_process_task.call_args_list[2][0][1]
        assert seed_arg_1 == 42
        assert seed_arg_2 == 43