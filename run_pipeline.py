"""Generate the CNC datasets, analyze them, and launch the dashboard."""

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    steps = [
        ("Task 1: Generate data", ["Task 1/generate_data.py"]),
        ("Task 3: Edge processing", ["Task 3/edge_processing (1).py"]),
        (
            "Task 4: Calculate machine metrics",
            [
                "Task 4/task4_analysis.py",
                "--interval-minutes", str(1 / 10 / 60),
                "--count-mode", "cumulative",
                "--abnormal-column", "Abnormal_Flag",
            ],
        ),
        ("Task 5: Detect anomalies", ["Task 5/anomaly_detection.py"]),
        (
            "Task 6: Launch dashboard (press Ctrl+C to stop)",
            [
                "-m", "streamlit", "run", "Task 6/assignmentapp.py",
                "--server.fileWatcherType", "none",
            ],
        ),
    ]

    try:
        for label, arguments in steps:
            print(f"\n{label}", flush=True)
            subprocess.run([sys.executable, *arguments], cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as error:
        print(f"\nPipeline stopped: {label} failed (exit code {error.returncode}).", file=sys.stderr)
        return error.returncode
    except KeyboardInterrupt:
        print("\nPipeline stopped.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
