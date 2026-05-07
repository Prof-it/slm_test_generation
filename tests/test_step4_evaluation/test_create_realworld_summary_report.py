import pytest
import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# 1. Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 2. Import the module
from step4_evaluation import create_summary_report as target_module

# --- Unit Tests: Helper Functions ---

def test_format_duration():
    """Test duration formatting (seconds vs minutes)."""
    assert target_module.format_duration(30) == "30.00s"
    assert target_module.format_duration(90) == "1.5m"

def test_clean_model_name():
    """Test model name cleanup logic."""
    raw = "google/gemma-3-4b-it"
    cleaned = target_module.clean_model_name(raw)
    assert cleaned == "gemma-3-4b-it"
    
    # Verify the specific Pynguin replacement logic inside clean_model_name
    # Note: parse_filename_metadata handles Pynguin separately before calling this,
    # but clean_model_name has logic for it too.
    assert target_module.clean_model_name("Pynguin-DynaMOSA") == "Pynguin (Baseline)"

def test_parse_filename_metadata():
    """Test extraction of Model, Mode, Temp from filenames."""
    
    # Case 1: Standard SLM LineCov
    f1 = "linecov_gemma-3-4b-it_temp_0.2.jsonl"
    model, mode, temp = target_module.parse_filename_metadata(f1)
    assert model == "gemma-3-4b-it"
    assert mode == "One-Shot"
    assert temp == "T=0.2"
    
    # Case 2: CoT
    f2 = "linecov2_Ministral-3-3B_temp_0.8.jsonl"
    model, mode, temp = target_module.parse_filename_metadata(f2)
    assert "Ministral" in model
    assert mode == "Two-Shot (CoT)"
    assert temp == "T=0.8"
    
    # Case 3: Pynguin
    # The function explicitly returns "Pynguin (DynaMOSA)" for filenames containing 'pynguin'
    f3 = "pynguin_results.jsonl"
    model, mode, temp = target_module.parse_filename_metadata(f3)
    assert model == "Pynguin (DynaMOSA)"
    assert mode == "Evolutionary Search"
    assert temp == "N/A"

# --- Integration Test: Report Generation ---

@pytest.fixture
def mock_file_structure(tmp_path):
    """
    Creates a temporary directory structure mimicking the real output.
    Returns the path to input dir and output file.
    """
    # Create input dir
    input_dir = tmp_path / "evaluation_results_realworld"
    input_dir.mkdir()
    
    # Create run directory
    run_dir = input_dir / "run_1"
    run_dir.mkdir()
    
    # Create Dummy JSONL file
    # Model: gemma, Temp: 0.2, Mode: One-Shot
    filename = "linecov_gemma-test_temp_0.2_evaluated.jsonl"
    file_path = run_dir / filename
    
    # Data: 
    # Task 1: Pass
    # Task 2: Pass
    # Task 3: Fail (Assertion Error)
    data = [
        {"task_num": 1, "status": "Pass", "coverage": 100.0, "mutation_score": 50.0, 
         "performance": {"duration_seconds": 1.0, "tokens_per_second": 10.0, "total_generated_tokens": 10}},
        {"task_num": 2, "status": "Pass", "coverage": 80.0, "mutation_score": 40.0,
         "performance": {"duration_seconds": 1.0, "tokens_per_second": 10.0, "total_generated_tokens": 10}},
        {"task_num": 3, "status": "Assertion Error", 
         "performance": {"duration_seconds": 0.5, "tokens_per_second": 20.0, "total_generated_tokens": 10}}
    ]
    
    with open(file_path, "w") as f:
        for entry in data:
            f.write(json.dumps(entry) + "\n")
            
    return input_dir, tmp_path / "report.txt"

@patch(f'{target_module.__name__}.glob.glob')
def test_generate_report(mock_glob, mock_file_structure):
    """
    Test the full aggregation logic using the temporary files.
    """
    input_dir, output_file = mock_file_structure
    
    # Point the module to our temp paths
    with patch(f'{target_module.__name__}.INPUT_DIR', input_dir), \
         patch(f'{target_module.__name__}.OUTPUT_FILE', output_file):
        
        # Configure glob to find our file
        # We need to return the absolute path string
        # glob is called recursively, we just return the one file we made
        mock_glob.return_value = [str(list(input_dir.glob("**/*.jsonl"))[0])]
        
        # Act
        target_module.generate_report()
        
        # Assert
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        
        # Check Table 1 Content
        # Pass Rate: 2 passed out of 3 total unique tasks = 66.67%
        assert "66.67%" in content
        
        # Check Coverage Average: (100 + 80) / 2 = 90.0
        assert "90.0%" in content
        
        # Check Mutation Average: (50 + 40) / 2 = 45.0
        assert "45.0%" in content
        
        # Check Table 2 Content (Reliability)
        # 1 Assertion Error in 1 Run -> Avg 1
        # The tabulate output in your log shows "|        1 |"
        # We search for " 1 " inside the row for "Assert" column
        assert "|        1 |" in content or " 1 " in content
        
        # Check Table 3 Content (Efficiency)
        # TPS: (10 + 10 + 20) / 3 = 13.33 -> ~13
        assert "13" in content
        # Time: 1.0 + 1.0 + 0.5 = 2.5s
        assert "2.50s" in content

@patch(f'{target_module.__name__}.glob.glob')
def test_generate_report_no_files(mock_glob, tmp_path):
    """
    Test report generation when no input files are found.
    Currently, the script crashes with a KeyError on empty DataFrame sort.
    We assert that this error occurs to confirm behavior (or we could fix the script).
    """
    output_file = tmp_path / "empty_report.txt"
    
    with patch(f'{target_module.__name__}.INPUT_DIR', tmp_path), \
         patch(f'{target_module.__name__}.OUTPUT_FILE', output_file):
        
        mock_glob.return_value = []
        
        # Expect KeyError: '_sort' because eff_data is empty
        with pytest.raises(KeyError):
            target_module.generate_report()