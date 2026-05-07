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
# Adjust the import based on where you saved the provided script.
# Assuming it is saved as step4_evaluation/create_summary_report.py
from step4_evaluation import create_initial_summary_report as target_module

# --- Unit Tests: Helper Functions ---

def test_format_duration():
    """Test duration formatting (seconds vs minutes)."""
    assert target_module.format_duration(45) == "45.00s"
    assert target_module.format_duration(120) == "2.0m"

def test_parse_filename_metadata():
    """Test extraction of Model, Mode, Temp from filenames."""
    
    # Case 1: Standard SLM LineCov
    f1 = "linecov_gemma-3-4b-it_temp_0.2_evaluated.jsonl"
    model, config = target_module.parse_filename_metadata(f1)
    assert model == "gemma-3-4b-it"
    assert "One-Shot" in config
    assert "T=0.2" in config
    
    # Case 2: CoT
    f2 = "linecov2_Ministral-3-3B_temp_0.8_evaluated.jsonl"
    model, config = target_module.parse_filename_metadata(f2)
    assert "Ministral" in model
    assert "Two-Shot (CoT)" in config
    assert "T=0.8" in config
    
    # Case 3: Dogfooding (Self-Correction) filename style
    f3 = "dogfood_Llama-3.2_temp_0.6_evaluated.jsonl"
    model, config = target_module.parse_filename_metadata(f3)
    assert "Llama" in model
    assert "One-Shot" in config # dogfood usually implies one-shot base unless cot specified
    assert "T=0.6" in config

# --- Integration Test: Report Generation ---

@pytest.fixture
def mock_evaluation_dir(tmp_path):
    """
    Creates a temporary directory structure mimicking the real output.
    """
    eval_dir = tmp_path / "evaluation_results"
    eval_dir.mkdir()
    
    # Create run directory
    run_dir = eval_dir / "run_1"
    run_dir.mkdir()
    
    # Create Dummy JSONL file
    filename = "linecov_test-model_temp_0.5_evaluated.jsonl"
    file_path = run_dir / filename
    
    # Data: 
    # Task 1: Pass
    # Task 2: Pass
    # Task 3: Fail (Runtime Error)
    data = [
        {"status": "Pass", "coverage": 100.0, "mutation_score": 80.0, 
         "performance": {"duration_seconds": 2.0, "total_generated_tokens": 20}},
        {"status": "Pass", "coverage": 90.0, "mutation_score": 70.0,
         "performance": {"duration_seconds": 2.0, "total_generated_tokens": 20}},
        {"status": "Runtime Error", 
         "performance": {"duration_seconds": 1.0, "total_generated_tokens": 10}}
    ]
    
    with open(file_path, "w") as f:
        for entry in data:
            f.write(json.dumps(entry) + "\n")
            
    return eval_dir, tmp_path / "summary_report.txt"

@patch(f'{target_module.__name__}.glob.glob')
def test_generate_report(mock_glob, mock_evaluation_dir):
    """
    Test the full aggregation logic using the temporary files.
    """
    input_dir, output_file = mock_evaluation_dir
    
    # Configure glob to find our file
    mock_glob.return_value = [str(list(input_dir.glob("**/*.jsonl"))[0])]
    
    # Act
    target_module.generate_report(eval_dir=str(input_dir), output_file=str(output_file))
    
    # Assert
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    
    # 1. Check Table 1 (Effectiveness)
    # Pass Rate: 2 passed out of 3 total = 66.67%
    assert "66.67%" in content
    # Cov Average: (100+90)/2 = 95.0
    assert "95.0%" in content
    # Mutation Average: (80+70)/2 = 75.0
    assert "75.0%" in content
    
    # 2. Check Table 2 (Reliability)
    # 1 Runtime Error / 1 Run = 1.0
    assert "|        1 |" in content or " 1 " in content # Depending on formatting
    
    # 3. Check Table 3 (Efficiency)
    # TPS: (20+20+10) / (2+2+1) = 50/5 = 10
    assert "10" in content
    # Time: 5.00s
    assert "5.00s" in content
    
    # 4. Check Baselines
    # Verify GPT-4o exists in table
    assert "GPT-4o" in content
    assert "Wang et al." in content
    # Verify DeepSeek exists
    assert "DeepSeek-Coder" in content

@patch(f'{target_module.__name__}.glob.glob')
def test_generate_report_no_files(mock_glob, tmp_path):
    """Test behavior when no files are found."""
    mock_glob.return_value = []
    output_file = tmp_path / "report.txt"
    
    # Act
    target_module.generate_report(eval_dir="fake", output_file=str(output_file))
    
    # Assert
    # Should print "No results found" and NOT create file
    assert not output_file.exists()

@patch(f'{target_module.__name__}.glob.glob')
def test_generate_report_malformed_json(mock_glob, tmp_path, capsys):
    """Test robustness against corrupted JSON lines."""
    # Setup corrupted file
    eval_dir = tmp_path / "bad_results"
    eval_dir.mkdir()
    f_path = eval_dir / "linecov_bad_temp_0.1_evaluated.jsonl"
    f_path.write_text('{"status": "Pass"}\nBAD_JSON_LINE\n{"status": "Fail"}', encoding='utf-8')
    
    mock_glob.return_value = [str(f_path)]
    output_file = tmp_path / "report.txt"
    
    # Act
    target_module.generate_report(eval_dir=str(eval_dir), output_file=str(output_file))
    
    # Assert
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    
    # It should count the 2 valid lines (1 pass, 1 fail->compile/runtime?) 
    # Actually, the loop uses 'try...except' per line, so it just skips the bad line.
    # Total tasks = 2. Passes = 1. Rate = 50%.
    assert "50.00%" in content

def test_literature_baselines_integrity():
    """Verify the hardcoded baseline data structure."""
    baselines = target_module.LITERATURE_BASELINES
    assert isinstance(baselines, list)
    assert len(baselines) >= 5
    
    gpt4 = next(b for b in baselines if b['Model'] == 'GPT-4o')
    assert gpt4['SR'] == 80.97
    assert gpt4['Runs'] == 1