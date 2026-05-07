import argparse
import pandas as pd
import pytest
from unittest.mock import patch, mock_open

# Importing all the functions from the script we want to test
from step1_data_understanding.data_understanding import (
    _calculate_all_metrics,
    calculate_code_metrics,
    load_benchmark,
    save_plots,
    parse_command_line_arguments,
)

# --- Group 1: Tests for _calculate_all_metrics (No Mocking Needed) ---

def test_calculate_all_metrics_happy_path():
    """Tests the function with a simple, valid code snippet."""
    simple_valid_code = """
def find_max(a, b):
    if a > b:
        return a
    return b
"""
    expected_keys = {
        'char_length', 'lines_of_code', 'num_functions',
        'cyclomatic_complexity_sum', 'maintainability_index',
        'halstead_difficulty', 'halstead_effort'
    }
    result = _calculate_all_metrics(simple_valid_code)

    assert isinstance(result, dict)
    assert set(result.keys()) == expected_keys
    for _, value in result.items():
        assert isinstance(value, (int, float))
    assert result['char_length'] > 0
    assert result['lines_of_code'] > 0

def test_calculate_all_metrics_with_empty_string_returns_zeros():
    """Verifies the function's guard clause for an empty string input."""
    result = _calculate_all_metrics("")
    assert all(value == 0 for value in result.values())

def test_calculate_all_metrics_with_whitespace_string_returns_zeros():
    """Verifies the function's guard clause for a string containing only whitespace."""
    result = _calculate_all_metrics("   \n\t  ")
    assert all(value == 0 for value in result.values())

def test_calculate_all_metrics_with_invalid_syntax_returns_zeros():
    """Verifies the try...except block handles syntax errors gracefully."""
    invalid_code = "def my_func(:"
    result = _calculate_all_metrics(invalid_code)
    assert all(value == 0 for value in result.values())

# --- Group 2: Tests for calculate_code_metrics (Mocking the Helper) ---

@patch('step1_data_understanding.data_understanding._calculate_all_metrics')
def test_calculate_code_metrics_with_valid_dataframe(mock_calculator):
    """Verifies new metric columns are correctly added to a standard DataFrame."""
    # Arrange
    mock_calculator.return_value = {'lines_of_code': 10} # Simplified mock return
    data = {'python_solution': ['def hello(): pass', 'def world(): pass']}
    df = pd.DataFrame(data)

    # Act
    _, combined_df = calculate_code_metrics(df)

    # Assert
    assert mock_calculator.call_count == 2
    assert 'lines_of_code' in combined_df.columns
    assert all(combined_df['lines_of_code'] == 10)

@patch('step1_data_understanding.data_understanding._calculate_all_metrics')
def test_calculate_code_metrics_with_empty_dataframe(mock_calculator):
    """Verifies the function handles an empty DataFrame without errors."""
    df = pd.DataFrame({'python_solution': []})
    metrics_df, combined_df = calculate_code_metrics(df)
    assert mock_calculator.call_count == 0
    assert metrics_df.empty
    assert 'code_str' in combined_df.columns

@patch('step1_data_understanding.data_understanding._calculate_all_metrics')
def test_calculate_code_metrics_handles_non_string_solutions(mock_calculator):
    """Verifies non-string values are converted to empty strings before analysis."""
    data = {'python_solution': [None, 'def hello(): pass']}
    df = pd.DataFrame(data)

    calculate_code_metrics(df)

    # Assert that the first call was with an empty string, and the second with the actual code
    assert mock_calculator.call_args_list[0].args == ('',)
    assert mock_calculator.call_args_list[1].args == ('def hello(): pass',)


# --- Group 3: Tests for load_benchmark (Mocking File I/O) ---

def test_load_benchmark_successfully_loads_valid_jsonl_file():
    """Verifies the function can read a correctly formatted JSONL file into a DataFrame."""
    # Arrange: Fake file content and mock args
    jsonl_content = '{"problem": "A"}\n{"problem": "B"}'
    mock_args = argparse.Namespace(input_file="fake/path.jsonl")

    # Act: Use mock_open to simulate reading the file
    with patch('builtins.open', mock_open(read_data=jsonl_content)) as mock_file:
        df = load_benchmark(mock_args)

    # Assert
    mock_file.assert_called_once_with("fake/path.jsonl", 'r', encoding='utf-8')
    assert len(df) == 2
    assert list(df['problem']) == ['A', 'B']

def test_load_benchmark_raises_file_not_found_for_missing_file():
    """Verifies that FileNotFoundError is propagated."""
    mock_args = argparse.Namespace(input_file="nonexistent/file.jsonl")

    # Patch 'open' to raise an error when called
    with patch('builtins.open') as mock_file:
        mock_file.side_effect = FileNotFoundError

        # Assert that the expected exception is raised
        with pytest.raises(FileNotFoundError):
            load_benchmark(mock_args)


# --- Group 4: Tests for save_plots (Mocking Plotting and File System) ---

@patch('step1_data_understanding.data_understanding.plt')
def test_save_plots_calls_savefig_for_each_metric(mock_plt):
    """Verifies that a plot is generated and saved for every metric."""
    df = pd.DataFrame({
        'metric1': list(range(30)), 
        'metric2': list(range(30))
    })
    metrics_to_analyze = ['metric1', 'metric2']
    mock_args = argparse.Namespace(output_dir="fake/plots")

    save_plots(metrics_to_analyze, df, mock_args)

    assert mock_plt.savefig.call_count == 2
    # Check that it tried to save files with the correct names
    first_call_args = mock_plt.savefig.call_args_list[0].args[0]
    assert 'metric1_distribution.png' in first_call_args

@patch('step1_data_understanding.data_understanding.plt')
@patch('step1_data_understanding.data_understanding.sns')
def test_save_plots_uses_histplot_for_continuous_data(mock_sns, _):
    """Verifies histplot is chosen for metrics with many unique values."""
    df = pd.DataFrame({'continuous_metric': list(range(50))}) # > 25 unique values
    mock_args = argparse.Namespace(output_dir="fake/plots")
    
    save_plots(['continuous_metric'], df, mock_args)

    mock_sns.histplot.assert_called_once()
    mock_sns.countplot.assert_not_called()

@patch('step1_data_understanding.data_understanding.plt')
@patch('step1_data_understanding.data_understanding.sns')
def test_save_plots_uses_countplot_for_discrete_data(mock_sns, _):
    """Verifies countplot is chosen for metrics with few unique values."""
    df = pd.DataFrame({'discrete_metric': [1, 1, 2, 3]}) # < 25 unique values
    mock_args = argparse.Namespace(output_dir="fake/plots")

    save_plots(['discrete_metric'], df, mock_args)

    mock_sns.countplot.assert_called_once()
    mock_sns.histplot.assert_not_called()


# --- Group 5: Tests for parse_command_line_arguments (Mocking sys.argv) ---

@patch('sys.argv', ['script_name.py'])
def test_parse_command_line_arguments_uses_default_values():
    """Verifies correct default paths when no arguments are provided."""
    args = parse_command_line_arguments()
    assert args.output_dir == "1.data_understanding/analysis/plots"
    assert args.input_file == "./TestEval/data/leetcode-py.jsonl"

@patch('sys.argv', ['script_name.py', '--output-dir', '/custom/out', '--input-file', 'custom.jsonl'])
def test_parse_command_line_arguments_with_custom_values():
    """Verifies parsing of custom command-line arguments."""
    args = parse_command_line_arguments()
    assert args.output_dir == '/custom/out'
    assert args.input_file == 'custom.jsonl'