import pytest
import logging
import subprocess
import os
import sys
from unittest.mock import patch, MagicMock
import argparse

# Ensure we can import the module from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from step3_modelling import run_experiments
MODULE_PATH = 'step3_modelling.run_experiments'

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """
    Automatically mock the path constants and Global lists for all tests.
    This prevents the tests from creating real folders on your disk.
    """
    monkeypatch.setattr(run_experiments, 'TESTEVAL_PATH', '/fake/project/TestEval')
    monkeypatch.setattr(run_experiments, 'PREDICTIONS_PATH', '/fake/project/predictions')
    # Mock the list of models to a single item for predictable testing
    monkeypatch.setattr(run_experiments, 'MODELS_TO_RUN', ["TestOrg/Test-Model-1B"])

@pytest.fixture(autouse=True)
def mock_os_system():
    """
    Mock os.system to prevent 'sync' errors on Windows during cleanup tests.
    """
    with patch(f'{MODULE_PATH}.os.system') as mock:
        yield mock

# --- Tests for run_experiment ---

@patch(f'{MODULE_PATH}.subprocess.run')
def test_run_experiment_success(mock_run, caplog):
    """
    Test that run_experiment executes the subprocess successfully.
    Note: run_experiment itself does NOT create directories, main() does.
    """
    caplog.set_level(logging.INFO)
    
    # Arrange
    test_command = ["python", "dummy_script.py", "--output-file", "predictions/result.jsonl"]
    
    # Act
    run_experiments.run_experiment(test_command)

    # Assert
    # Check subprocess execution
    mock_run.assert_called_once_with(
        test_command, 
        check=True, 
        text=True, 
        encoding='utf-8', 
        cwd='/fake/project/TestEval'
    )
    
    # Check logging
    assert "Starting/Resuming: result.jsonl" in caplog.text

@patch(f'{MODULE_PATH}.subprocess.run')
def test_run_experiment_failure(mock_run, caplog):
    """
    Test that the script catches subprocess errors and logs them 
    instead of crashing the whole pipeline.
    """
    caplog.set_level(logging.ERROR)
    
    # Arrange: Simulate a script failure (exit code 1)
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
    test_command = ["python", "fail_script.py", "--output-file", "out.jsonl"]

    # Act
    run_experiments.run_experiment(test_command)

    # Assert
    assert "failed with exit code 1" in caplog.text

# --- Tests for Argument Parsing ---

def test_parse_args_defaults():
    """Test that default arguments are set correctly."""
    with patch('sys.argv', ['script_name']):
        args = run_experiments.parse_args()
        assert args.quick_test is False
        assert args.passes == 3

def test_parse_args_quick_test():
    """Test that the --quick-test flag is detected."""
    with patch('sys.argv', ['script_name', '--quick-test']):
        args = run_experiments.parse_args()
        assert args.quick_test is True

# --- Integration Tests for main() ---

@patch(f'{MODULE_PATH}.cleanup_disk_space')
@patch(f'{MODULE_PATH}.run_experiment')
@patch(f'{MODULE_PATH}.os.makedirs') # main calls makedirs, so we mock it here
@patch(f'{MODULE_PATH}.parse_args')
def test_main_full_benchmark(mock_parse_args, mock_makedirs, mock_run_experiment, mock_cleanup, caplog):
    """
    Test the main loop in Full Benchmark mode.
    Should run 2 temperatures per model.
    """
    caplog.set_level(logging.INFO)
    
    # Arrange: Mock arguments to be False (Full Run)
    # IMPORTANT: Must include 'passes' because main() logs it at the end
    mock_parse_args.return_value = argparse.Namespace(quick_test=False, passes=2)
    
    # Act
    run_experiments.main()

    # Assert
    # We mocked MODELS_TO_RUN to 1 model.
    # Logic: 2 Passes * 1 Model * 2 Global Temps (0.2, 0.8) * 2 Experiment Types (LineCov, CoT) = 8 calls
    assert mock_run_experiment.call_count == 8
    
    # Verify the generated commands contain expected values
    args, _ = mock_run_experiment.call_args_list[0]
    command = args[0]
    assert "0.2" in command  # First temp
    assert "--quick-test" not in command
    
    assert "FULL BENCHMARK MODE" in caplog.text
    assert "All 2 Benchmark Runs Completed" in caplog.text

@patch(f'{MODULE_PATH}.cleanup_disk_space')
@patch(f'{MODULE_PATH}.run_experiment')
@patch(f'{MODULE_PATH}.os.makedirs')
@patch(f'{MODULE_PATH}.parse_args')
def test_main_quick_test(mock_parse_args, mock_makedirs, mock_run_experiment, mock_cleanup, caplog):
    """
    Test the main loop in Quick Test mode.
    Should run only 1 temperature (0.2) and pass the --quick-test flag.
    """
    caplog.set_level(logging.INFO)
    
    # Arrange: Mock arguments to be True (Quick Test)
    # IMPORTANT: Must include 'passes' because main() logs it at the end
    mock_parse_args.return_value = argparse.Namespace(quick_test=True, passes=3)
    
    # Act
    run_experiments.main()

    # Assert
    # Logic: 1 Model * 1 Temp (0.2) * 2 Experiment Types = 2 calls
    assert mock_run_experiment.call_count == 2
    
    # Verify the generated commands pass the flag down
    args, _ = mock_run_experiment.call_args_list[0]
    command = args[0]
    assert "--quick-test" in command
    assert "0.2" in command
    
    # Ensure temp 0.8 was NOT run
    for call_obj in mock_run_experiment.call_args_list:
        cmd = call_obj[0][0]
        assert "0.8" not in cmd

    assert "QUICK TEST MODE ENABLED" in caplog.text