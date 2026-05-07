import pytest
import sys
import os
import json
import pandas as pd
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path

# 1. Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 2. Import the module
from step4_evaluation import create_mutation_subset as target_module

# --- Fixtures ---

@pytest.fixture
def mock_paths(monkeypatch):
    """
    Mock the global path constants in the target module so we don't 
    need real files on disk.
    """
    mock_in = MagicMock(spec=Path)
    mock_out = MagicMock(spec=Path)
    
    monkeypatch.setattr(target_module, 'DATA_PATH', mock_in)
    monkeypatch.setattr(target_module, 'OUTPUT_PATH', mock_out)
    
    return mock_in, mock_out

@pytest.fixture
def sample_jsonl_data():
    """
    Creates a dataset designed to test the sampling logic:
    - 20% sample rate.
    - Difficulty 1: 5 items (20% of 5 = 1.0) -> Expect 1 selected.
    - Difficulty 2: 4 items (20% of 4 = 0.8 -> int(0) -> min logic -> 1) -> Expect 1 selected.
    - Difficulty 3: 10 items (20% of 10 = 2.0) -> Expect 2 selected.
    """
    data = []
    
    # Diff 1: 5 items
    for i in range(1, 6):
        data.append({"task_num": f"d1_{i}", "difficulty": 1})
        
    # Diff 2: 4 items (Test the 'at least 1' logic)
    for i in range(1, 5):
        data.append({"task_num": f"d2_{i}", "difficulty": 2})
        
    # Diff 3: 10 items
    for i in range(1, 11):
        data.append({"task_num": f"d3_{i}", "difficulty": 3})
        
    # Convert to JSONL string format
    return "\n".join([json.dumps(record) for record in data])

# --- Tests ---

def test_missing_input_file(mock_paths, capsys):
    """Test that the script exits gracefully if input file is missing."""
    mock_in, mock_out = mock_paths
    mock_in.exists.return_value = False
    
    target_module.create_subset()
    
    captured = capsys.readouterr()
    assert "Error: Could not find data" in captured.out
    
    # Verify we didn't try to open anything
    assert mock_out.open.call_count == 0

def test_sampling_logic_counts(mock_paths, sample_jsonl_data):
    """
    Test that the correct number of items are sampled per difficulty category.
    """
    mock_in, mock_out = mock_paths
    mock_in.exists.return_value = True
    
    # Setup the file read context
    with patch("builtins.open", mock_open(read_data=sample_jsonl_data)) as mock_file:
        
        target_module.create_subset()
        
        # Verify Write Operation
        # We need to capture what was written to the handle.
        handle = mock_file()
        
        # Combine all write calls to form the full JSON string
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        result_list = json.loads(written_content)
        
        # --- Assertions based on Fixture logic ---
        
        # 1. Check Total Count
        # Diff 1 (5 items) -> 1
        # Diff 2 (4 items) -> 1 (due to min-1 logic)
        # Diff 3 (10 items) -> 2
        # Total = 4
        assert len(result_list) == 4
        
        # 2. Check Distribution
        d1_count = sum(1 for x in result_list if x.startswith("d1_"))
        d2_count = sum(1 for x in result_list if x.startswith("d2_"))
        d3_count = sum(1 for x in result_list if x.startswith("d3_"))
        
        assert d1_count == 1
        assert d2_count == 1
        assert d3_count == 2

def test_coerce_difficulty_types(mock_paths):
    """
    Test that the script handles difficulty stored as strings ("1") 
    or integers (1) correctly.
    """
    mock_in, _ = mock_paths
    mock_in.exists.return_value = True
    
    # Mixed types in JSON
    mixed_data = [
        {"task_num": 101, "difficulty": "1"}, # String
        {"task_num": 102, "difficulty": 1},   # Int
        {"task_num": 103, "difficulty": "2"},
        {"task_num": 104, "difficulty": None} # Should default to -1 and be ignored by loop [1,2,3]
    ]
    jsonl_str = "\n".join([json.dumps(d) for d in mixed_data])
    
    with patch("builtins.open", mock_open(read_data=jsonl_str)) as mock_file:
        target_module.create_subset()
        
        handle = mock_file()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        result_list = json.loads(written_content)
        
        # 20% of 2 items (Diff 1) = 0.4 -> Min 1 logic -> 1 item selected
        # 20% of 1 item (Diff 2) = 0.2 -> Min 1 logic -> 1 item selected
        # Diff None (-1) -> Ignored
        assert len(result_list) == 2
        
        # Verify ID 104 (None diff) is NOT in list
        assert "104" not in result_list

def test_reproducibility(mock_paths, sample_jsonl_data):
    """
    Test that running the function twice with the same seed produces 
    the exact same subset.
    """
    mock_in, _ = mock_paths
    mock_in.exists.return_value = True
    
    results = []
    
    # Run 1
    with patch("builtins.open", mock_open(read_data=sample_jsonl_data)) as mock_file:
        target_module.create_subset()
        handle = mock_file()
        content = "".join(call.args[0] for call in handle.write.call_args_list)
        results.append(json.loads(content))
        
    # Run 2
    with patch("builtins.open", mock_open(read_data=sample_jsonl_data)) as mock_file:
        target_module.create_subset()
        handle = mock_file()
        content = "".join(call.args[0] for call in handle.write.call_args_list)
        results.append(json.loads(content))
        
    assert results[0] == results[1]
    # Ensure they are not empty (sanity check)
    assert len(results[0]) > 0

def test_empty_dataset(mock_paths):
    """
    Test behavior with an empty input file.
    
    Note: The current script raises a KeyError when the dataset is empty 
    because it tries to access columns in an empty DataFrame. 
    This test expects that exception to pass.
    """
    mock_in, _ = mock_paths
    mock_in.exists.return_value = True
    
    with patch("builtins.open", mock_open(read_data="")) as mock_file:
        with pytest.raises(KeyError):
            target_module.create_subset()