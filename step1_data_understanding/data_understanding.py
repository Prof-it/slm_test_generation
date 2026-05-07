"""
Data Understanding

Performs Exploratory Data Analysis (EDA) on the TestEval benchmark.
The script generates summary statistics and plots to help understand the dataset's composition.
The aim of this script is to provide insight into benchmark's code complexity to inform the modelling phase.

It analyzes the following code features using the `radon` library:
*   **Code Size:** Character length, lines of code (LOC), number of functions.
*   **Complexity:** Cyclomatic, Cognitive, and NPath complexity; max nesting depth.
*   **Maintainability:** Maintainability Index, Halstead difficulty, and effort.

To run in the terminal:
python 1.data_understanding/data_understanding.py --output-dir ./plots
"""

import argparse
import json
import os
from typing import Any, Dict, List
import matplotlib.pyplot as plt
import pandas as pd
from radon import raw, complexity, metrics as radon_metrics
import seaborn as sns

def parse_command_line_arguments() -> argparse:
    """Command line arguments are parsed."""
    parser = argparse.ArgumentParser(
        description="Run Explorator Data Analysis on TestEval.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="1.data_understanding/analysis/plots",
        help="Directory to save the generated plots."
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="./TestEval/data/leetcode-py.jsonl",
        help="TestEval benchmark path."
    )
    args = parser.parse_args()
    return args

def load_benchmark(args) -> pd.DataFrame:
    """Benchmark data is saved."""
    print("Loading Data:")
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data : List[Dict[str, Any]] = [json.loads(line) for line in f]
    df = pd.DataFrame(data)
    print(f"Successfully loaded {len(df)} problems from '{args.input_file}'")
    return df

def calculate_code_metrics(df:pd.DataFrame) -> pd.DataFrame:
    print("Calculating Code Complexity Metrics:")
    # get focal code string handling TestEvak's simple string format
    df['code_str'] = df['python_solution'].apply(lambda x: x if isinstance(x, str) else '')

    # apply the metric calculation function to each code snippet
    metrics_list = [_calculate_all_metrics(code) for code in df['code_str']]
    metrics_df = pd.DataFrame(metrics_list, index=df.index)
    df = pd.concat([df, metrics_df], axis=1)
    return metrics_df, df

def _calculate_all_metrics(code:str) -> Dict[str, float]:
    """Calculates a comprehensive set of software metrics for a given code snippet."""
    if not code.strip():
        return {
            'char_length': 0,
            'lines_of_code': 0,
            'num_functions': 0,
            'cyclomatic_complexity_sum': 0,
            'maintainability_index': 0,
            'halstead_difficulty': 0,
            'halstead_effort': 0
        }
    try:
        # analysis for complexity and nesting
        raw_analysis = raw.analyze(code)
        cc_analysis = complexity.cc_visit(code)
        mi_score = radon_metrics.mi_visit(code, multi=True)
        h_visit_result = radon_metrics.h_visit(code)

        # Aggregate metrics
        lines_of_code = raw_analysis.loc
        num_functions = len(cc_analysis)
        cyclo_sum = sum(f.complexity for f in cc_analysis)
        h_visit_result = radon_metrics.h_visit(code)

        # halstead metrics are returned in a list, typically with one result for the module
        halstead_difficulty = h_visit_result[0].difficulty if h_visit_result else 0
        halstead_effort = h_visit_result[0].effort if h_visit_result else 0

        return {
            'char_length': len(code),
            'lines_of_code': lines_of_code,
            'num_functions': num_functions,
            'cyclomatic_complexity_sum': cyclo_sum,
            'maintainability_index': mi_score,
            'halstead_difficulty': halstead_difficulty,
            'halstead_effort': halstead_effort,
        }
    except Exception as e:
            # if any library fails to parse return zeros to avoid crashing
            print(f"Analysis failed for a code snippet. Error: {e}")
            return {key:0 for key in _calculate_all_metrics("").keys()}


def save_plots(metrics_to_analyze: list, df:pd.DataFrame, args:argparse) -> None:
    "Save the generated plots."
    print("Generating and saving plots:")
    for metric in metrics_to_analyze:
        plt.figure(figsize=(12,6))

        # use a count plot for discrete metrics with few unique values
        if df[metric].nunique() < 25 and df[metric].dtype in ['int64', 'float64']:
            sns.countplot(x=df[metric])
        else:
            sns.histplot(df[metric], bins=50, kde=True)

        title = metric.replace("_", " ").title()
        plt.title(f"Distribution of {title}")
        plt.xlabel(title)
        plot_path = os.path.join(args.output_dir, f'{metric}_distribution.png')
        plt.savefig(plot_path, bbox_inches='tight')
        plt.close()
        print(f"Saved plot: {plot_path}")


def main() -> None:
    """
    The main aim is to load the benchmark data, claculate metrics, and save plots.
    """
    
    args = parse_command_line_arguments()
    # create output directory if it does not exist
    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Plots will be saved to: {args.output_dir}")
    # set plot style for consistency
    sns.set_theme(style="whitegrid")
    
    df = load_benchmark(args=args)
    metrics_df, df = calculate_code_metrics(df=df)
    metrics_to_analyze = list(metrics_df.columns)
    print("Summary statistics for code complexity metrics")
    print(df[metrics_to_analyze].describe().round(2))
    save_plots(metrics_to_analyze=metrics_to_analyze, df=df, args=args)

    print("\n Performing data quality check")
    # Check for empty or non-string code snippets directly
    empty_code_count = df['python_solution'].apply(lambda x: not isinstance(x, str) or not x.strip()).sum()
    print(f"Problems with empty or invalid python_solution: {empty_code_count}")


if __name__=="__main__":
    main()