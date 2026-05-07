"""
Shared Utility Functions for Evaluation Report Generation
This module contains common helper functions used across multiple evaluation scripts.
Functions include data parsing, formatting, and visualization styling utilities.
"""

import numpy as np
import seaborn as sns
from pathlib import Path


def format_duration(seconds):
    """Format a duration in seconds to a readable string (e.g., "15.20s" or "5.2m")."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    return f"{seconds/60:.1f}m"


def clean_model_name(raw_name):
    """Clean raw HuggingFace model strings for publication figures.

    Strips quantization suffixes, vendor prefixes, and version tags.
    E.g. "google/gemma-3-4b-it-2507-AWQ-8bit" -> "gemma-3-4b-it-8bit".
    """
    if "/" in raw_name:
        name = raw_name.split("/", 1)[1]
    else:
        name = raw_name

    name = (name
            .replace("-2507", "")
            .replace("-2512", "")
            .replace("-v0.1", "")
            .replace("google_", "")
            .replace("meta-llama_", "")
            .replace("ibm-granite_", "")
            .replace("Pynguin-DynaMOSA", "Pynguin (Baseline)")
           )

    name = (name
            .replace("-AWQ-INT4", "-4bit")
            .replace("-AWQ-8bit", "-8bit")
            .replace("-AWQ-4bit", "-4bit")
            .replace("-AWQ", "-4bit")
           )

    return name


def extract_performance_data(perf_dict, calculate_tps=True):
    """Robustly extract (total_tokens, duration_seconds, tokens_per_second) from a
    performance dict, handling schema variations across log formats.

    Set calculate_tps=False for batch-level TPS calculation to avoid masking timeouts.
    """
    if not perf_dict:
        return 0.0, 0.0, 0.0

    tok = perf_dict.get('total_generated_tokens', 0)
    if not tok:
        tok = perf_dict.get('total_tokens_conditions', 0) + perf_dict.get('total_tokens_tests', 0)

    dur = perf_dict.get('duration_seconds', 0)
    if not dur:
        dur = perf_dict.get('duration_conditions_sec', 0) + perf_dict.get('duration_tests_sec', 0)

    if calculate_tps:
        tps = perf_dict.get('tokens_per_second', 0)
        if tps == 0 and dur > 0:
            tps = tok / dur
    else:
        # For batch-level calculation (prevents instantaneous speed from masking timeouts)
        tps = 0.0

    return float(tok), float(dur), float(tps)


def parse_filename_metadata(filename, clean_name=True):
    """Extract (model_name, mode, temperature) from a JSONL filename.

    mode is "One-Step", "Two-Step", or "Evolutionary Search" (Pynguin).
    temperature is always float (np.nan if not found) — format as f"T={temp}" for display.
    Set clean_name=False when raw names are needed for baseline comparison.
    """
    name = Path(filename).stem.replace("_evaluated", "")

    # Special handling for Pynguin (baseline has no temperature concept)
    if "pynguin" in name.lower():
        return "Pynguin (Baseline)", "Evolutionary Search", np.nan

    # Determine Mode
    mode = "Two-Step" if ("linecov2" in name) else "One-Step"

    # Extract Temperature as float
    temp_float = np.nan
    try:
        if "temp_" in name:
            temp_str = name.split('temp_')[1].split('_')[0].replace('.jsonl', '')
            temp_float = float(temp_str)
        elif "_T" in name:
            temp_str = name.split('_T')[1].split('.jsonl')[0]
            temp_float = float(temp_str)
    except (ValueError, IndexError):
        pass

    # Extract Model Name
    model_raw = (name
                 .replace("linecov2_", "")
                 .replace("linecov_", "")
                 .replace("dogfood_", "")
                 .split("_temp")[0]
                 .split("_T")[0])

    # Clean model name if requested
    model_name = clean_model_name(model_raw) if clean_name else model_raw

    return model_name, mode, temp_float


def format_stat_with_std(values, decimal=1, suffix=""):
    """Return "mean±std" formatted string (e.g., "85.0% (±4.1)"), or "-" if no valid values."""
    if not values:
        return "-"

    valid_values = [v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if not valid_values:
        return "-"

    avg = np.mean(valid_values)
    std = np.std(valid_values)

    return f"{avg:.{decimal}f}{suffix} (±{std:.{decimal}f})"


def get_style_maps(df):
    """Return (palette_dict, markers_dict) with consistent colors/markers per model.

    Uses a fixed mapping across initial, temp, and realworld reports for visual consistency.
    Falls back to bright palette colors for unknown models.
    """

    FIXED_COLORS = {
        "Pynguin (Baseline)": "#000000",  # Black (always)
        "gemma-3-4b-it": "#e74c3c",  # Red
        "granite-4.0-micro": "#3498db",  # Blue
        "Qwen3-4B-Instruct": "#2ecc71",  # Green
        "Ministral-3-8B-Instruct": "#f39c12",  # Orange
        "Ministral-3-8B-Instruct-8bit": "#f39c12",  # Orange
        "Ministral-3-8B-Instruct-4bit": "#9b59b6",  # Purple
        "Ministral-3-3B-Instruct": "#1abc9c",  # Turquoise
        "Ministral-3-3B-Reasoning": "#e67e22",  # Dark Orange
        "Llama-3.2-3B-Instruct": "#95a5a6",  # Gray
        "Meta-Llama-3.1-8B-Instruct-4bit": "#34495e",  # Dark Gray
        "Qwen3-8B-4bit": "#16a085",  # Dark Turquoise
        "Qwen3-4B-Thinking": "#d35400",  # Pumpkin
    }

    FIXED_MARKERS = {
        "Pynguin (Baseline)": "^",  # Triangle (baseline)
        "gemma-3-4b-it": "o",  # Circle
        "granite-4.0-micro": "s",  # Square
        "Qwen3-4B-Instruct": "D",  # Diamond
        "Ministral-3-8B-Instruct": "v",  # Triangle down
        "Ministral-3-8B-Instruct-8bit": "v",  # Triangle down
        "Ministral-3-8B-Instruct-4bit": "X",  # X
        "Ministral-3-3B-Instruct": "P",  # Plus
        "Ministral-3-3B-Reasoning": "*",  # Star
        "Llama-3.2-3B-Instruct": "h",  # Hexagon
        "Meta-Llama-3.1-8B-Instruct-4bit": "d",  # Thin diamond
        "Qwen3-8B-4bit": "p",  # Pentagon
        "Qwen3-4B-Thinking": "<",  # Triangle left
    }

    unique_models = df["Model"].unique()

    palette_dict = {}
    markers_dict = {}

    fallback_colors = sns.color_palette("bright", n_colors=20)
    fallback_markers = ['o', 's', '^', 'D', 'v', 'X', 'P', '*', 'h', 'd', 'p', '<', '>']
    fallback_idx = 0

    for model in unique_models:
        if model in FIXED_COLORS:
            palette_dict[model] = FIXED_COLORS[model]
            markers_dict[model] = FIXED_MARKERS[model]
        else:
            palette_dict[model] = fallback_colors[fallback_idx % len(fallback_colors)]
            markers_dict[model] = fallback_markers[fallback_idx % len(fallback_markers)]
            fallback_idx += 1

    return palette_dict, markers_dict