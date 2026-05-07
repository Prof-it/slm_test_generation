import os
import subprocess
import sys

# The directory where the benchmark data will be stored.
DATA_DIR = "./TestEval/"
# The Git repository URL for the TestEval benchmark.
TESTEVAL_REPO = "https://github.com/LLM4SoftwareTesting/TestEval.git"


def download_benchmark():
    """
    Downloads the TestEval benchmark by cloning its Git repository.
    Skips the download if the target directory already exists.
    """
    print("Starting Benchmark Download")

    # Check if the target directory already exists (equivalent to `if [ -d "$DATA_DIR" ]`)
    if os.path.isdir(DATA_DIR):
        # A more informative check might be for a .git folder: os.path.isdir(os.path.join(DATA_DIR, '.git'))
        print(f"Directory '{DATA_DIR}' already exists, skipping download.")
    else:
        print(f"Directory '{DATA_DIR}' does not exist, cloning repository...")
        try:
            # Execute the git clone command (equivalent to `git clone $TESTEVAL_REPO $DATA_DIR`)
            subprocess.run(
                ["git", "clone", TESTEVAL_REPO, DATA_DIR],
                check=True,  # This will raise an exception if the command fails
                capture_output=True, # Suppresses git's output unless there's an error
                text=True
            )
            print(f"Successfully cloned repository into '{DATA_DIR}'.")
        except FileNotFoundError:
            print("Error: 'git' command not found. Please ensure Git is installed and in your system's PATH.", file=sys.stderr)
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to clone repository.", file=sys.stderr)
            print(f"Git stderr: {e.stderr}", file=sys.stderr)
            sys.exit(1)

    print("Benchmark Download is complete.")


if __name__ == "__main__":
    download_benchmark()