import pytest
import sys
import os
import json
import pandas as pd
from unittest.mock import patch

# 1. Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from step4_evaluation import create_temp_summary_report as target_module

# --- Unit Tests: Helper Functions ---

def test_clean_model_name():
    """Test model name cleanup logic."""
    raw = "google/gemma-3-4b-it"
    cleaned = target_module.clean_model_name(raw)
    assert cleaned == "gemma-3-4b-it"

    # Quantization replacement checks
    assert target_module.clean_model_name("MyModel-AWQ-INT4") == "MyModel-4bit"
    assert target_module.clean_model_name("MyModel-AWQ-8bit") == "MyModel"

def test_parse_metadata():
    """Test filename parsing logic."""
    # Case 1: Valid Standard (1-Step)
    f1 = "linecov_gemma-3-4b-it_temp_0.2_evaluated.jsonl"
    model, mode, temp = target_module.parse_metadata(f1)
    assert model == "gemma-3-4b-it"
    assert mode == "Standard (1-Step)"
    assert temp == 0.2

    # Case 2: Valid CoT (2-Step)
    f2 = "linecov2_Ministral-3-3B_temp_1.0_evaluated.jsonl"
    model, mode, temp = target_module.parse_metadata(f2)
    assert "Ministral" in model
    assert mode == "CoT (2-Step)"
    assert temp == 1.0

    # Case 3: Invalid Filename (missing temp)
    f3 = "linecov_gemma-3-4b-it_evaluated.jsonl"
    model, mode, temp = target_module.parse_metadata(f3)
    assert model is None

    # Case 4: Invalid Temp Value
    f4 = "linecov_gemma_temp_xyz_evaluated.jsonl"
    model, mode, temp = target_module.parse_metadata(f4)
    assert model is None

# --- Integration Tests: Data Loading & Processing ---

@pytest.fixture
def mock_input_data(tmp_path):
    """Creates a temporary input directory with sample JSONL files."""
    input_dir = tmp_path / "evaluation_results_temperature"
    input_dir.mkdir()
    
    # Run 1 Directory
    run_dir = input_dir / "run_1"
    run_dir.mkdir()
    
    # Create File 1: Gemma Temp 0.2
    f1 = run_dir / "linecov_gemma-test_temp_0.2_evaluated.jsonl"
    data1 = [
        {"status": "Pass", "coverage": 100.0, "mutation_score": 80.0, 
         "performance": {"total_generated_tokens": 100, "duration_seconds": 10}},
        {"status": "Fail", "performance": {"total_generated_tokens": 50, "duration_seconds": 5}}
    ]
    with open(f1, "w") as f:
        for entry in data1: f.write(json.dumps(entry) + "\n")
        
    # Create File 2: Gemma Temp 0.8
    f2 = run_dir / "linecov_gemma-test_temp_0.8_evaluated.jsonl"
    data2 = [
        {"status": "Pass", "coverage": 90.0, "mutation_score": 70.0,
         "performance": {"total_generated_tokens": 100, "duration_seconds": 10}}
    ]
    with open(f2, "w") as f:
        for entry in data2: f.write(json.dumps(entry) + "\n")
        
    return input_dir

def test_load_data(mock_input_data):
    """Test loading data from the filesystem into a DataFrame."""
    df = target_module.load_data(mock_input_data)
    
    assert not df.empty
    assert len(df) == 2 # 2 files processed
    
    # Check Columns
    assert "Model" in df.columns
    assert "Temperature" in df.columns
    assert "Pass Rate" in df.columns
    assert "TPS" in df.columns
    
    # Check Values
    row_02 = df[df["Temperature"] == 0.2].iloc[0]
    # 1 Pass / 2 Total = 50%
    assert row_02["Pass Rate"] == 50.0
    # TPS: (100+50) / (10+5) = 150/15 = 10
    assert row_02["TPS"] == 10.0

def test_get_style_maps():
    """Test color and marker generation."""
    df = pd.DataFrame({"Model": ["Model A", "Model B", "Model A"]})
    pal, marks = target_module.get_style_maps(df)
    
    assert "Model A" in pal
    assert "Model B" in pal
    assert "Model A" in marks
    assert marks["Model A"] != marks["Model B"]

# --- Integration Tests: Plotting & Report (Mocked Matplotlib) ---

@pytest.fixture
def sample_df():
    """Create a sample DataFrame for plotting tests."""
    return pd.DataFrame([
        {"Model": "Model A", "Mode": "Standard (1-Step)", "Temperature": 0.2, "Run": "run_1", 
         "Pass Rate": 50.0, "Coverage": 80.0, "Mutation Score": 60.0, "TPS": 10.0},
        {"Model": "Model A", "Mode": "Standard (1-Step)", "Temperature": 0.8, "Run": "run_1", 
         "Pass Rate": 40.0, "Coverage": 70.0, "Mutation Score": 50.0, "TPS": 12.0},
        {"Model": "Model B", "Mode": "CoT (2-Step)", "Temperature": 0.2, "Run": "run_1", 
         "Pass Rate": 60.0, "Coverage": 90.0, "Mutation Score": 70.0, "TPS": 5.0}
    ])

@patch(f'{target_module.__name__}.plt.savefig')
@patch(f'{target_module.__name__}.plt.close')
def test_plot_functions(mock_close, mock_save, sample_df, tmp_path):
    """
    Test that plotting functions run without error and attempt to save files.
    We mock plt.savefig to avoid file I/O and GUI dependencies.
    """
    # Setup styles
    pal, marks = target_module.get_style_maps(sample_df)
    
    # 1. Test Stability Trends
    target_module.plot_stability_trends(sample_df, tmp_path, pal, marks)
    assert mock_save.call_count >= 1 # Should save multiple plots (Pass, Mut, TPS)
    
    mock_save.reset_mock()
    
    # 2. Test Quality Quadrant
    target_module.plot_quality_quadrant(sample_df, tmp_path, pal, marks)
    assert mock_save.call_count == 1
    
    mock_save.reset_mock()

    # 3. Test Efficiency Frontier
    target_module.plot_efficiency_frontier(sample_df, tmp_path, pal, marks)
    assert mock_save.call_count == 1

def test_generate_comparative_table(sample_df, tmp_path):
    """Test report text generation."""
    target_module.generate_comparative_table(sample_df, tmp_path)
    
    report_file = tmp_path / "comparative_analysis_report.txt"
    assert report_file.exists()
    
    content = report_file.read_text(encoding="utf-8")
    assert "COMPARATIVE PERFORMANCE REPORT" in content
    assert "Model A" in content
    assert "Model B" in content
    assert "Standard (1-Step)" in content
    assert "CoT (2-Step)" in content

@patch(f'{target_module.__name__}.load_data')
@patch(f'{target_module.__name__}.plot_stability_trends')
@patch(f'{target_module.__name__}.plot_quality_quadrant')
@patch(f'{target_module.__name__}.plot_efficiency_frontier')
@patch(f'{target_module.__name__}.generate_comparative_table')
def test_main_execution(mock_gen_table, mock_eff, mock_qual, mock_trend, mock_load, tmp_path):
    """Test the main function orchestration."""
    
    # Setup Mocks
    mock_load.return_value = pd.DataFrame({"Model": ["A"], "Pass Rate": [10]})
    
    # Point INPUT_DIR to a real path (even if empty, checked before load_data)
    with patch(f'{target_module.__name__}.INPUT_DIR', tmp_path), \
         patch(f'{target_module.__name__}.OUTPUT_DIR', tmp_path):
        
        target_module.main()
        
        mock_load.assert_called_once()
        mock_trend.assert_called_once()
        mock_qual.assert_called_once()
        mock_eff.assert_called_once()
        mock_gen_table.assert_called_once()