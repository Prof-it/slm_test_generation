import pytest
import sys
import os
import ast
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# 1. Setup path to import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from step3_modelling import run_real_world_experiments_inference as target_module

# Define module path for patching
MODULE_PATH = 'step3_modelling.run_real_world_experiments_inference'

# --- Fixtures ---

@pytest.fixture
def mock_path_globals(monkeypatch):
    """
    Mock the global path constants so tests don't touch real disk locations.
    """
    mock_root = Path("/fake/root")
    monkeypatch.setattr(target_module, 'PROJECT_ROOT', mock_root)
    monkeypatch.setattr(target_module, 'TESTEVAL_DIR', mock_root / "TestEval")
    monkeypatch.setattr(target_module, 'REAL_WORLD_SRC_DIR', mock_root / "TestEval/data/real_world")
    monkeypatch.setattr(target_module, 'DATASET_BASE', mock_root / "TestEval/data/realworld-py.jsonl")
    monkeypatch.setattr(target_module, 'DATASET_ALL', mock_root / "TestEval/data/realworld-py-all.jsonl")
    monkeypatch.setattr(target_module, 'PREDICTIONS_PATH', "/fake/predictions")

# --- Unit Tests: Code Analysis Logic ---

def test_analyze_code_simple():
    """Test difficulty scoring on simple code."""
    # Simple function: Low Cyclomatic Complexity, Low Nesting
    code = "def foo():\n    return 1"
    
    # Mock radon to return simple complexity
    mock_cc_obj = MagicMock()
    mock_cc_obj.complexity = 1
    
    with patch(f'{MODULE_PATH}.cc_visit', return_value=[mock_cc_obj]):
        score = target_module.analyze_code(code)
        # Expect Low difficulty (1)
        assert score == 1

def test_analyze_code_complex():
    """Test difficulty scoring on complex code logic."""
    # Complex function: High nesting, many vars
    code = """
def complex_algo(x, y):
    result = 0
    if x > 0:
        for i in range(10):
            if y < 5:
                while True:
                    result += 1
                    break
    return result
    """
    
    # Mock radon to return higher complexity
    mock_cc_obj = MagicMock()
    mock_cc_obj.complexity = 10 
    
    with patch(f'{MODULE_PATH}.cc_visit', return_value=[mock_cc_obj]):
        # The DifficultyAnalyzer should find depth=4 (func > if > for > if > while)
        # and vars (x, y, result, i). 
        # Score calculation: min(10) + ceil(10) + 4 (vars) + 4 (depth) = 28 -> Hard (3)
        score = target_module.analyze_code(code)
        assert score == 3

def test_block_extractor():
    """Test that if-blocks are identified correctly."""
    code = """
def check(x):
    if x > 0:
        print("pos")
    else:
        print("neg")
    """
    tree = ast.parse(code)
    func_node = tree.body[0] # FunctionDef
    
    extractor = target_module.BlockExtractor(func_node.lineno)
    extractor.visit(func_node)
    
    # Expecting 1 'if' block and 1 'else' block
    assert len(extractor.blocks) == 2
    assert extractor.blocks[0]['type'] == 'if'
    assert extractor.blocks[1]['type'] == 'else'

# --- Unit Tests: Code Transformation ---


# --- Integration Tests: Main Orchestration ---

@patch(f'{MODULE_PATH}.generate_real_world_datasets')
@patch(f'{MODULE_PATH}.run_experiment')
@patch(f'{MODULE_PATH}.cleanup_disk_space')
@patch(f'{MODULE_PATH}.os.makedirs')
@patch(f'{MODULE_PATH}.argparse.ArgumentParser.parse_args')
def test_main_quick_test(mock_args, mock_mkdirs, mock_cleanup, mock_run, mock_gen, mock_path_globals):
    """
    Test main execution flow in Quick Test mode.
    """
    # Arrange
    mock_args.return_value = MagicMock(
        quick_test=True, 
        passes=3, 
        generate_data=False
    )
    # Mock that datasets exist
    with patch(f'{MODULE_PATH}.Path.exists', return_value=True):
        
        # Act
        target_module.main()
        
        # Assert
        # Logic: 1 Model * 1 Temp (0.2) * 2 commands (Line + CoT) = 2 calls
        assert mock_run.call_count == 2
        
        args_first_call = mock_run.call_args_list[0][0][0]
        assert "--quick-test" in args_first_call
        assert "0.2" in args_first_call

@patch(f'{MODULE_PATH}.generate_real_world_datasets')
@patch(f'{MODULE_PATH}.run_experiment')
@patch(f'{MODULE_PATH}.cleanup_disk_space')
@patch(f'{MODULE_PATH}.os.makedirs')
@patch(f'{MODULE_PATH}.argparse.ArgumentParser.parse_args')
def test_main_full_benchmark(mock_args, mock_mkdirs, mock_cleanup, mock_run, mock_gen, mock_path_globals):
    """
    Test main execution flow in Full Benchmark mode.
    """
    # Arrange
    mock_args.return_value = MagicMock(
        quick_test=False, 
        passes=2, # Testing 2 passes 
        generate_data=False
    )
    
    # Mock datasets exist
    with patch(f'{MODULE_PATH}.Path.exists', return_value=True):
        # Override global models/temps for speed
        with patch.object(target_module, 'MODELS_TO_RUN', ["test/model"]), \
             patch.object(target_module, 'GLOBAL_TEMPERATURES', [0.5]):
             
            # Act
            target_module.main()
            
            # Assert
            # Logic: 2 Passes * 1 Model * 1 Temp * 2 Commands = 4 calls
            assert mock_run.call_count == 4
            assert mock_cleanup.call_count == 2 # Once per model loop

@patch(f'{MODULE_PATH}.CodeAnalyzer')
def test_generate_real_world_datasets(mock_analyzer_cls, mock_path_globals):
    """
    Test the data generation function verifies directory scanning and JSON writing.
    """
    # Setup Mocks
    mock_file = MagicMock()
    
    # Mock glob to return 1 file
    with patch(f'{MODULE_PATH}.Path.glob', return_value=[mock_file]), \
         patch(f'{MODULE_PATH}.Path.exists', return_value=True), \
         patch("builtins.open", new_callable=mock_open) as mock_file_open:
        
        # Mock CodeAnalyzer instance
        mock_instance = mock_analyzer_cls.return_value
        # Return one dummy task tuple (base, rich)
        mock_instance.extract_tasks.return_value = [({"id": 1}, {"id": 1, "code": "rich"})]
        
        # Act
        result = target_module.generate_real_world_datasets()
        
        # Assert
        assert result is True
        # Should open DATASET_BASE and DATASET_ALL for writing
        assert mock_file_open.call_count == 2
        # Verify writing happened
        mock_file_open().write.assert_called()

def test_main_fails_missing_data(mock_path_globals, caplog):
    """Test that main returns early if data generation fails or files missing."""
    with patch(f'{MODULE_PATH}.generate_real_world_datasets', return_value=False), \
         patch(f'{MODULE_PATH}.Path.exists', return_value=False), \
         patch(f'{MODULE_PATH}.argparse.ArgumentParser.parse_args', return_value=MagicMock(generate_data=True)):
        
        target_module.main()
        
        assert "Data generation failed" in caplog.text