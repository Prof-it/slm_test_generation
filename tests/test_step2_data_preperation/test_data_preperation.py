import os
import subprocess
import logging
from unittest.mock import patch, mock_open, call, Mock
import pytest
import sys

from step2_data_preperation import data_preperation


@pytest.fixture(autouse=True)
def mock_constants(monkeypatch):
    """Automatically mock the path constants for all tests."""
    monkeypatch.setattr(data_preperation, 'PROJECT_ROOT', '/fake/project')
    monkeypatch.setattr(data_preperation, 'TESTEVAL_DIR', '/fake/project/TestEval')
    monkeypatch.setattr(data_preperation, 'TESTEVAL_REPO_URL', 'https://fake.repo/url.git')
    monkeypatch.setattr(data_preperation, 'PREDICTIONS_DIR', '/fake/project/TestEval/predictions')

# -- Tests for check_and_clone_repo --

@patch('step2_data_preperation.data_preperation.subprocess.run')
@patch('step2_data_preperation.data_preperation.os.path.exists', return_value=True)
def test_check_and_clone_repo_exists(mock_exists, mock_run, caplog):
    """Test that cloning is skipped if the directory already exists."""
    # FIX: Set log level to INFO so caplog can capture the message.
    caplog.set_level(logging.INFO)
    data_preperation.check_and_clone_repo()

    mock_exists.assert_called_once_with('/fake/project/TestEval')
    mock_run.assert_not_called()
    assert "TestEval repository already exists. Skipping download." in caplog.text

@patch('step2_data_preperation.data_preperation.subprocess.run')
@patch('step2_data_preperation.data_preperation.os.path.exists', return_value=False)
def test_check_and_clone_repo_success(mock_exists, mock_run, caplog):
    """Test successful cloning when the directory does not exist."""
    caplog.set_level(logging.INFO)
    data_preperation.check_and_clone_repo()

    mock_exists.assert_called_once_with('/fake/project/TestEval')
    expected_command = ["git", "clone", "https://fake.repo/url.git", "/fake/project/TestEval"]
    mock_run.assert_called_once_with(
        expected_command, check=True, capture_output=True, text=True
    )
    assert "Successfully cloned the TestEval repository." in caplog.text

@patch('step2_data_preperation.data_preperation.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'cmd', stderr='fatal error'))
@patch('step2_data_preperation.data_preperation.os.path.exists', return_value=False)
def test_check_and_clone_repo_fails(mock_exists, mock_run, caplog):
    """Test that sys.exit is called if the clone command fails."""
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as e:
        data_preperation.check_and_clone_repo()
    assert e.value.code == 1
    assert "Failed to clone repository. Git error:\nfatal error" in caplog.text

# -- Tests for verify_benchmark_data --

@patch('step2_data_preperation.data_preperation.os.path.exists', return_value=True)
def test_verify_benchmark_data_success(mock_exists, caplog):
    """Test successful verification when the key file is found."""
    caplog.set_level(logging.INFO)
    data_preperation.verify_benchmark_data()

    expected_path = os.path.join('/fake/project/TestEval', "data", "leetcode-py.jsonl")
    mock_exists.assert_called_once_with(expected_path)
    assert "Verification successful." in caplog.text

@patch('step2_data_preperation.data_preperation.os.path.exists', return_value=False)
def test_verify_benchmark_data_fails(mock_exists, caplog):
    """Test that sys.exit is called if the key file is missing."""
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as e:
        data_preperation.verify_benchmark_data()
    assert e.value.code == 1
    assert "Verification failed. Key data file not found" in caplog.text

# -- Tests for install_dependencies --

def test_install_dependencies_success(tmp_path, monkeypatch, caplog):
    """
    Tests the success path for install_dependencies where both requirements
    files exist and the pip install command succeeds.
    """
    # 1. ARRANGE: Set up a controlled, temporary environment
    
    # Set the logging level so we can capture INFO messages
    caplog.set_level(logging.INFO)

    # Create a fake project structure inside the temp directory provided by pytest
    project_root = tmp_path
    testeval_dir = project_root / "TestEval"
    testeval_dir.mkdir()

    # Create dummy requirements files with some content
    req_root_path = project_root / "requirements.txt"
    req_testeval_path = testeval_dir / "requirements.txt"
    req_root_path.write_text("package-from-root==1.0")
    req_testeval_path.write_text("package-from-testeval==1.0")
    
    # Use monkeypatch to redirect the script's global variables to our fake paths
    monkeypatch.setattr(data_preperation, 'PROJECT_ROOT', str(project_root))
    monkeypatch.setattr(data_preperation, 'TESTEVAL_DIR', str(testeval_dir))

    # Mock the external command `subprocess.run` to avoid actually running pip
    with patch('step2_data_preperation.data_preperation.subprocess.run') as mock_subprocess_run:
        
        # 2. ACT: Call the function we are testing
        data_preperation.install_dependencies()

        # 3. ASSERT: Verify the behavior was correct
        
        # Assert that subprocess.run was called twice, once for each file
        assert mock_subprocess_run.call_count == 2
        
        # Define the exact calls we expect to have been made
        expected_calls = [
            call(
                [sys.executable, "-m", "pip", "install", "-r", str(req_root_path)],
                check=True,
                capture_output=True,
                text=True
            ),
            call(
                [sys.executable, "-m", "pip", "install", "-r", str(req_testeval_path)],
                check=True,
                capture_output=True,
                text=True
            )
        ]
        # Verify that both calls were made, in the correct order
        mock_subprocess_run.assert_has_calls(expected_calls, any_order=False)

        # Assert that the log messages reflect the successful execution
        log_output = caplog.text
        assert "Installing dependencies from" in log_output
        assert str(req_root_path) in log_output
        assert str(req_testeval_path) in log_output
        assert "Successfully installed dependencies from" in log_output

@patch('step2_data_preperation.data_preperation.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'cmd', stderr='pip error'))
@patch('step2_data_preperation.data_preperation.os.path.exists', return_value=True)
def test_install_dependencies_fails(mock_exists, mock_run, caplog):
    """Test that sys.exit is called if pip install fails."""
    caplog.set_level(logging.ERROR)
    with patch("builtins.open", mock_open(read_data="package==1.0")):
        with pytest.raises(SystemExit) as e:
            data_preperation.install_dependencies()
    assert e.value.code == 1
    assert "Failed to install dependencies" in caplog.text
    assert "pip error" in caplog.text

# -- Tests for create_output_directories --

@patch('step2_data_preperation.data_preperation.os.makedirs')
def test_create_output_directories_success(mock_makedirs, caplog):
    """Test successful directory creation."""
    caplog.set_level(logging.INFO)
    data_preperation.create_output_directories()

    mock_makedirs.assert_called_once_with('/fake/project/TestEval/predictions', exist_ok=True)
    assert "Ensured output directory exists" in caplog.text

@patch('step2_data_preperation.data_preperation.os.makedirs', side_effect=OSError("Permission denied"))
def test_create_output_directories_fails(mock_makedirs, caplog):
    """Test that sys.exit is called if directory creation fails."""
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as e:
        data_preperation.create_output_directories()
    assert e.value.code == 1
    assert "Failed to create directory" in caplog.text
    assert "Permission denied" in caplog.text

# -- Tests for validate_environment_variables --

def test_validate_env_vars_success(monkeypatch, caplog):
    """Test successful validation when all env vars are set."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "fake_token_value")
    data_preperation.validate_environment_variables()
    assert "All required environment variables are set." in caplog.text

def test_validate_env_vars_missing(monkeypatch, caplog):
    """Test failure when an environment variable is missing."""
    caplog.set_level(logging.ERROR)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
    with pytest.raises(SystemExit) as e:
        data_preperation.validate_environment_variables()
    assert e.value.code == 1
    assert "The following environment variables are not set:" in caplog.text
    assert "- HUGGINGFACE_TOKEN" in caplog.text

# -- Integration Test for the main function --

@patch('step2_data_preperation.data_preperation.validate_environment_variables')
@patch('step2_data_preperation.data_preperation.create_output_directories')
@patch('step2_data_preperation.data_preperation.install_dependencies')
@patch('step2_data_preperation.data_preperation.verify_benchmark_data')
@patch('step2_data_preperation.data_preperation.check_and_clone_repo')
def test_main_function_calls_all_steps(
    mock_clone, mock_verify, mock_install, mock_create, mock_validate, caplog
):
    """Test that the main function calls all preparation steps in order."""
    caplog.set_level(logging.INFO)
    manager = Mock()
    manager.attach_mock(mock_clone, 'clone')
    manager.attach_mock(mock_verify, 'verify')
    manager.attach_mock(mock_install, 'install')
    manager.attach_mock(mock_create, 'create')
    manager.attach_mock(mock_validate, 'validate')

    data_preperation.main()

    expected_calls = [
        call.clone(),
        call.verify(),
        call.install(),
        call.create(),
        call.validate()
    ]
    assert manager.mock_calls == expected_calls
    assert "--- Starting Data Preparation Phase ---" in caplog.text
    assert "--- Data Preparation Complete ---" in caplog.text