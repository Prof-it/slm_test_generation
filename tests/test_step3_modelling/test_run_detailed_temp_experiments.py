import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 2. Import via the package structure
from step3_modelling import run_detailed_temp_experiments as target_module

# 3. Define the string path for @patch to find the module
MODULE_PATH = 'step3_modelling.run_detailed_temp_experiments'

# --- Fixtures ---

@pytest.fixture
def mock_subprocess():
    """Mocks subprocess.run to prevent actual script execution."""
    with patch(f'{MODULE_PATH}.subprocess.run') as mock:
        yield mock

@pytest.fixture
def mock_shutil():
    """Mocks shutil to prevent actual disk deletion."""
    with patch(f'{MODULE_PATH}.shutil') as mock:
        yield mock

@pytest.fixture
def mock_os_ops():
    """Mocks OS operations like makedirs and system sync."""
    with patch(f'{MODULE_PATH}.os.makedirs') as mock_makedir, \
         patch(f'{MODULE_PATH}.os.system') as mock_system, \
         patch(f'{MODULE_PATH}.os.path.exists') as mock_exists:
        
        # Default behavior: assume paths exist so cleanup logic triggers
        mock_exists.return_value = True 
        
        yield {
            'makedirs': mock_makedir,
            'system': mock_system,
            'exists': mock_exists
        }

# --- Unit Tests ---

def test_cleanup_disk_space(mock_shutil, mock_os_ops):
    """
    Verifies that cleanup_disk_space attempts to remove the specific cache paths
    and runs a system sync.
    """
    target_module.cleanup_disk_space()

    # The paths defined in your script
    expected_paths = [
        "/workspace/huggingface_cache/hub",
        "/root/.cache/vllm",
        "/root/.cache/huggingface/hub"
    ]

    # Verify rmtree was called for these paths
    assert mock_shutil.rmtree.call_count == 3
    
    # Check that os.system("sync") was called
    mock_os_ops['system'].assert_called_with("sync")

def test_run_experiment_success(mock_subprocess):
    """Verifies run_experiment calls subprocess with correct environment/blocking."""
    cmd = ["python", "dummy.py", "--output-file", "test.json"]
    
    target_module.run_experiment(cmd)
    
    mock_subprocess.assert_called_once_with(
        cmd,
        check=True,
        text=True,
        encoding='utf-8',
        cwd=target_module.TESTEVAL_PATH
    )

def test_run_experiment_failure(mock_subprocess, caplog):
    """Verifies that subprocess failures are caught and logged, not raising python errors."""
    cmd = ["python", "fail.py", "--output-file", "fail.json"]
    
    # Simulate an error (exit code 1)
    mock_subprocess.side_effect = target_module.subprocess.CalledProcessError(1, cmd)
    
    target_module.run_experiment(cmd)
    
    # Check log for error message
    assert "failed with exit code 1" in caplog.text

# --- Integration / Logic Tests (Mocking Main) ---

@patch(f'{MODULE_PATH}.parse_args')
@patch(f'{MODULE_PATH}.run_experiment')
@patch(f'{MODULE_PATH}.cleanup_disk_space')
def test_main_quick_test_logic(mock_cleanup, mock_run, mock_args, mock_os_ops):
    """
    Test --quick-test logic:
    - Should only run the 1st model.
    - Should only run at temperature 0.2.
    - Should pass '--quick-test' flag to subprocesses.
    """
    # Fix: Ensure 'passes' is present even in quick test, as script logs it at the end
    mock_args.return_value = MagicMock(quick_test=True, passes=1)
    
    # Run main
    target_module.main()
    
    # Logic: 1 model * 1 temp * 2 scripts (linecov + cot) = 2 calls
    assert mock_run.call_count == 2
    
    # Inspect arguments of the first call
    args_passed = mock_run.call_args_list[0][0][0]
    
    # Verify strict temp 0.2
    assert "--temperature" in args_passed
    assert "0.2" in args_passed
    
    # Verify flags passed down
    assert "--quick-test" in args_passed
    
    # Verify it used the first model in the global list
    first_model = target_module.MODELS_TO_RUN[0]
    assert first_model in args_passed

@patch(f'{MODULE_PATH}.parse_args')
@patch(f'{MODULE_PATH}.run_experiment')
@patch(f'{MODULE_PATH}.cleanup_disk_space')
def test_main_full_benchmark_seeding(mock_cleanup, mock_run, mock_args, mock_os_ops):
    """
    Test the sequential passes logic:
    - Pass 1 should have Seed 42.
    - Pass 2 should have Seed 43.
    - Pass 3 should have Seed 44.
    """
    # Configure 3 passes
    mock_args.return_value = MagicMock(quick_test=False, passes=3)
    
    # Reduce search space to 1 model and 1 temp for this test
    # We patch the module attributes directly
    with patch.object(target_module, 'MODELS_TO_RUN', ["test/model"]), \
         patch.object(target_module, 'GLOBAL_TEMPERATURES', [0.0]):
         
        target_module.main()
        
        # Calls math: 3 Passes * 1 Model * 1 Temp * 2 Scripts = 6 Calls
        assert mock_run.call_count == 6
        
        # Get calls
        calls = mock_run.call_args_list
        
        # Calls 0,1 -> Pass 1 (Seed 42)
        cmd_pass_1 = calls[0][0][0]
        seed_idx_1 = cmd_pass_1.index("--seed") + 1
        assert cmd_pass_1[seed_idx_1] == "42"
        
        # Calls 2,3 -> Pass 2 (Seed 43)
        cmd_pass_2 = calls[2][0][0]
        seed_idx_2 = cmd_pass_2.index("--seed") + 1
        assert cmd_pass_2[seed_idx_2] == "43"

        # Calls 4,5 -> Pass 3 (Seed 44)
        cmd_pass_3 = calls[4][0][0]
        seed_idx_3 = cmd_pass_3.index("--seed") + 1
        assert cmd_pass_3[seed_idx_3] == "44"

        # Verify output directories created for all 3 runs
        path_base = target_module.PREDICTIONS_PATH
        mock_os_ops['makedirs'].assert_any_call(os.path.join(path_base, "run_1"), exist_ok=True)
        mock_os_ops['makedirs'].assert_any_call(os.path.join(path_base, "run_2"), exist_ok=True)
        mock_os_ops['makedirs'].assert_any_call(os.path.join(path_base, "run_3"), exist_ok=True)

@patch(f'{MODULE_PATH}.parse_args')
@patch(f'{MODULE_PATH}.run_experiment')
@patch(f'{MODULE_PATH}.cleanup_disk_space')
def test_gemma_dtype_handling(mock_cleanup, mock_run, mock_args, mock_os_ops):
    """
    Test that Gemma models force 'bfloat16' and others default to 'float16'.
    """
    mock_args.return_value = MagicMock(quick_test=False, passes=1)
    
    # Inject one gemma model and one regular model
    test_models = ["google/gemma-3-4b-it", "mistralai/Ministral-3-3B"]
    test_temps = [0.0]
    
    with patch.object(target_module, 'MODELS_TO_RUN', test_models), \
         patch.object(target_module, 'GLOBAL_TEMPERATURES', test_temps):
        
        target_module.main()
        
        calls = mock_run.call_args_list
        
        # 1. Check Gemma Command (First 2 calls)
        cmd_gemma = calls[0][0][0]
        assert "google/gemma-3-4b-it" in cmd_gemma
        
        # Extract dtype
        if "--dtype" in cmd_gemma:
            idx = cmd_gemma.index("--dtype") + 1
            assert cmd_gemma[idx] == "bfloat16", "Gemma-3 should use bfloat16"
        else:
            pytest.fail("dtype argument missing for Gemma")

        # 2. Check Mistral Command (Next 2 calls)
        cmd_mistral = calls[2][0][0]
        assert "mistralai/Ministral-3-3B" in cmd_mistral
        
        if "--dtype" in cmd_mistral:
            idx = cmd_mistral.index("--dtype") + 1
            assert cmd_mistral[idx] == "float16", "Standard models should use float16"