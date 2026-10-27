# Industrial-Data-Analytics-ME-217-Project----Group-1B
Virtual Industrial IoT System for a Smart Manufacturing Cell.

All task inputs and generated CSV files live in the project's `csv_files/`
folder. Paths are based on the script location, so they also work when a task
is launched from another working directory. Task 3 and Task 4 accept filenames
or paths inside this folder; paths outside it are rejected.

The scripts support Windows, macOS, and Linux with Python 3.10 or newer.
Run commands in a terminal from the project root. The examples below use
`python3` (Linux/macOS). On Windows, replace `python3` with `py` or `python`
in every command, including dependency installation and individual task commands.
Keep the quotes around script paths because the folder names contain spaces.

Install dependencies once (Linux/macOS):

```bash
python3 -m pip install numpy pandas scikit-learn streamlit plotly
```

On Windows:

```powershell
py -m pip install numpy pandas scikit-learn streamlit plotly
```

Run the full pipeline from the project root with one command:

```bash
python3 run_pipeline.py
```

On Windows:

```powershell
py run_pipeline.py
```

This regenerates the CSV files, runs Tasks 1, 3, 4, and 5 in order, and starts
the Task 6 dashboard. Open http://localhost:8501 and press Ctrl+C in the
terminal to stop. If a task fails, the pipeline stops before the next task.

To run the tasks individually:

```bash
python3 "Task 1/generate_data.py"
python3 "Task 3/edge_processing (1).py"
python3 "Task 4/task4_analysis.py" --interval-minutes 0.0016666666666666668 --count-mode cumulative --abnormal-column Abnormal_Flag
python3 "Task 5/anomaly_detection.py"
python3 -m streamlit run "Task 6/assignmentapp.py"
```

Task 4's arguments above match Task 1's 10 Hz sampling and cumulative counters.
For metrics based on detected alarms instead, run Task 4 after Task 5 with
`data_with_flags.csv --abnormal-column Flag_final` and the same interval/count options.

Files in `csv_files/`:

- `cnc_cell_data.csv`: Task 1's generated data.
- `processed_data.csv`: Task 3's edge processing output.
- `task4_machine_metrics.csv`: Task 4's machine metrics.
- `data_with_flags.csv`: Task 5's anomaly detection output.

Task 6 reads the metrics and flagged data. Python dependencies: `numpy`,
`pandas`, `scikit-learn`, `streamlit`, and `plotly`.
