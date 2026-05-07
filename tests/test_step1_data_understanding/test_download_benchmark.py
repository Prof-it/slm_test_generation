import os
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

from step1_data_understanding import download_benchmark


def test_download_benchmark_directory_exists(capsys, monkeypatch):
    """
    Tests the case where the target directory already exists.
    It should print a "skipping" message and not attempt to clone.
    """
    # Arrange:
    # 1. Mock `os.path.isdir` to always return True, simulating that the dir exists.
    monkeypatch.setattr(os.path, 'isdir', lambda path: True)

    # 2. Create a mock for `subprocess.run` that will fail the test if it's ever called.
    # This ensures we are NOT trying to clone when the directory exists.
    mock_run = MagicMock(side_effect=AssertionError("subprocess.run should not be called"))
    monkeypatch.setattr(subprocess, 'run', mock_run)

    # Act:
    download_benchmark.download_benchmark()

    # Assert:
    # 1. Check that `subprocess.run` was never called. The mock's side_effect handles this.
    mock_run.assert_not_called()

    # 2. Capture the output and check if the correct "skipping" message was printed.
    captured = capsys.readouterr()
    assert f"Directory '{download_benchmark.DATA_DIR}' already exists, skipping download." in captured.out
    assert "Benchmark Download is complete." in captured.out

@patch('subprocess.run')
@patch('os.path.isdir', return_value=False)
def test_download_successful_clone(mock_isdir, mock_run, capsys):
    """
    Tests the successful cloning case where the directory does not exist.
    It should call `subprocess.run` with the correct git command.
    """
    # Arrange: Mocks are already set up by the @patch decorators.
    # `mock_isdir` will return False.
    # `mock_run` will accept any call without doing anything.

    # Act:
    download_benchmark.download_benchmark()

    # Assert:
    # 1. Check that `os.path.isdir` was called with the correct directory path.
    mock_isdir.assert_called_once_with(download_benchmark.DATA_DIR)

    # 2. Check that `subprocess.run` was called exactly once with the expected command.
    expected_command = [
        "git",
        "clone",
        download_benchmark.TESTEVAL_REPO,
        download_benchmark.DATA_DIR,
    ]
    mock_run.assert_called_once_with(
        expected_command,
        check=True,
        capture_output=True,
        text=True
    )

    # 3. Check for the correct success messages in the output.
    captured = capsys.readouterr()
    assert f"Directory '{download_benchmark.DATA_DIR}' does not exist" in captured.out
    assert f"Successfully cloned repository into '{download_benchmark.DATA_DIR}'" in captured.out

@patch('subprocess.run')
@patch('os.path.isdir', return_value=False)
def test_clone_fails_git_not_found(mock_isdir, mock_run, capsys):
    """
    Tests the error handling when the 'git' command is not found.
    It should catch FileNotFoundError, print to stderr, and exit.
    """
    # Arrange:
    # Configure the `subprocess.run` mock to raise a FileNotFoundError.
    mock_run.side_effect = FileNotFoundError

    # Act & Assert:
    # Use pytest.raises to assert that the code calls sys.exit(1),
    # which raises a SystemExit exception.
    with pytest.raises(SystemExit) as e:
        download_benchmark.download_benchmark()

    # Check that the exit code is 1.
    assert e.type == SystemExit
    assert e.value.code == 1

    # Check that the correct error message was printed to stderr.
    captured = capsys.readouterr()
    assert "Error: 'git' command not found." in captured.err

@patch('subprocess.run')
@patch('os.path.isdir', return_value=False)
def test_clone_fails_called_process_error(mock_isdir, mock_run, capsys):
    """
    Tests the error handling when the git clone command fails.
    It should catch CalledProcessError, print stderr, and exit.
    """
    # Arrange:
    # Create a realistic CalledProcessError instance to be raised by the mock.
    error_message = "fatal: repository not found"
    error = subprocess.CalledProcessError(
        returncode=128,
        cmd=["git", "clone", "bad-repo-url"],
        stderr=error_message
    )
    mock_run.side_effect = error

    # Act & Assert:
    with pytest.raises(SystemExit) as e:
        download_benchmark.download_benchmark()

    assert e.type == SystemExit
    assert e.value.code == 1

    # Check that the specific error messages were printed to stderr.
    captured = capsys.readouterr()
    assert "Error: Failed to clone repository." in captured.err
    assert f"Git stderr: {error_message}" in captured.err