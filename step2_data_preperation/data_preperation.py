"""
Data Preparation

This script automates the setup and validation of the experimental environment
for the SLM unit test generation benchmark. It ensures that the project is
ready for the modelling phase by performing the following steps:

1.  Checks for and clones the 'TestEval' benchmark repository if not present.
2.  Verifies the integrity of the downloaded benchmark data.
3.  Installs all required Python dependencies from the project's requirements files.
4.  Creates the necessary output directory ('predictions') for storing experimental results.
5.  Validates that all required API key environment variables are set.

To run this script, execute from the repository's root directory:
    python step2_data_preperation/prepare_data.py
"""

import os
import subprocess
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

TESTEVAL_DIR = os.path.join(PROJECT_ROOT, "TestEval")
TESTEVAL_REPO_URL = "https://github.com/LLM4SoftwareTesting/TestEval.git"
PREDICTIONS_DIR = os.path.join(TESTEVAL_DIR, "predictions")

REQUIRED_ENV_VARS = [
    #"GOOGLE_API_KEY",
    "HUGGINGFACE_TOKEN"
]

def setup_logging():
    """Configures basic logging to print informative messages to the console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def check_and_clone_repo():
    """Checks for the TestEval directory and clones the repository if it doesn't exist."""
    logging.info("Step 1: Checking for TestEval benchmark data...")
    if os.path.exists(TESTEVAL_DIR):
        logging.info("TestEval repository already exists. Skipping download.")
        return

    logging.warning(f"TestEval directory not found at '{TESTEVAL_DIR}'.")
    logging.info(f"Cloning from '{TESTEVAL_REPO_URL}'...")
    try:
        subprocess.run(
            ["git", "clone", TESTEVAL_REPO_URL, TESTEVAL_DIR],
            check=True,
            capture_output=True,
            text=True
        )
        logging.info("Successfully cloned the TestEval repository.")
    except FileNotFoundError:
        logging.error("Git command not found. Please ensure Git is installed and in your system's PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to clone repository. Git error:\n{e.stderr}")
        sys.exit(1)

def verify_benchmark_data():
    """Performs a simple check to verify that key benchmark files are present."""
    logging.info("Step 2: Verifying benchmark data integrity...")
    key_file = os.path.join(TESTEVAL_DIR, "data", "leetcode-py.jsonl")
    if os.path.exists(key_file):
        logging.info(f"Key data file '{os.path.basename(key_file)}' found. Verification successful.")
    else:
        logging.error(f"Verification failed. Key data file not found at '{key_file}'.")
        logging.error("Please try deleting the 'TestEval' directory and running this script again.")
        sys.exit(1)

def install_dependencies():
    """Installs dependencies from the project's requirements.txt files."""
    logging.info("Step 3: Installing Python dependencies...")
    requirements_files = [
        os.path.join(PROJECT_ROOT, "requirements.txt"),
        os.path.join(TESTEVAL_DIR, "requirements.txt")
    ]
    for req_file in requirements_files:
        if os.path.exists(req_file):
            logging.info(f"Installing dependencies from '{req_file}'...")
            try:
                # Ensure the 'textwrap' issue is fixed in TestEval/requirements.txt
                if 'textwrap' in open(req_file).read() and 'TestEval' in req_file:
                    logging.warning(f"Warning: 'textwrap' found in {req_file}. This is a built-in library and should be removed to prevent errors.")

                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file],
                    check=True,
                    capture_output=True,
                    text=True
                )
                logging.info(f"Successfully installed dependencies from '{req_file}'.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to install dependencies from '{req_file}'. Pip error:\n{e.stderr}")
                sys.exit(1)
        else:
            logging.warning(f"Requirements file not found: '{req_file}'. Skipping.")

def create_output_directories():
    """Creates the 'predictions' directory required by the evaluation scripts."""
    logging.info("Step 4: Creating output directories...")
    try:
        os.makedirs(PREDICTIONS_DIR, exist_ok=True)
        logging.info(f"Ensured output directory exists at '{PREDICTIONS_DIR}'.")
    except OSError as e:
        logging.error(f"Failed to create directory '{PREDICTIONS_DIR}'. Error: {e}")
        sys.exit(1)

def validate_environment_variables():
    """Checks if all required API keys are set as environment variables."""
    logging.info("Step 5: Validating environment configuration (API Keys)...")
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]

    if not missing_vars:
        logging.info("All required environment variables are set. Validation successful.")
    else:
        logging.error("Validation failed. The following environment variables are not set:")
        for var in missing_vars:
            logging.error(f"  - {var}")
        logging.error("Please set these variables before running the experiments.")
        sys.exit(1)

def main():
    """Main function to orchestrate the data preparation process."""
    setup_logging()
    logging.info("Starting data preparation...")

    check_and_clone_repo()
    verify_benchmark_data()
    install_dependencies()
    create_output_directories()
    validate_environment_variables()

    logging.info("Data preparation complete.")


if __name__ == "__main__":
    main()