# Virtual Industrial IoT System for a Smart Manufacturing Cell

**Course:** Industrial Data Analytics (ME 217)  
**Assignment:** Assignment 1 — Virtual Industrial IoT System for a Smart Manufacturing Cell  
**Group:** 1A

---

## 1. Overview

This project implements a virtual Industrial Internet of Things (IIoT) system for a manufacturing cell containing five CNC machines. It simulates sensor measurements, processes machine data, calculates production metrics, detects abnormal conditions, and presents the results through an interactive dashboard.

The system uses Python to demonstrate the complete workflow without physical machines or sensors.

### Project Pipeline

```text
Virtual CNC Machines and Sensors
              |
              v
       Data Acquisition
              |
              v
        Edge Processing
              |
              v
       CSV Data Storage
              |
              v
    KPI Analysis and Anomaly Detection
              |
              v
    Visualization / Dashboard
              |
              v
     Manufacturing Decisions
```

### Project Tasks

| Task | Component | Description |
| --- | --- | --- |
| Task 1 | Virtual Data Generation | Physics-inspired simulation of five CNC machines |
| Task 2 | IIoT Architecture | Layered architecture for the virtual manufacturing system |
| Task 3 | Edge Processing | Filtering, rolling statistics, outlier detection, and status segmentation |
| Task 4 | Industrial Data Analysis | Machine KPIs, utilization, production performance, and downtime analysis |
| Task 5 | Anomaly Detection | Comparison of threshold, robust Z-score, and Isolation Forest detectors |
| Task 6 | Dashboard | Interactive Streamlit dashboard for visualization and decision support |

---

## 2. Repository Structure

```text
Industrial-Data-Analytics-ME-217-Project----Group-1A/
|
├── README.md
├── .gitignore
├── run_pipeline.py
|
├── Task 1/
│   ├── config.py
│   ├── generator.py
│   ├── generate_data.py
│   └── cnc_cell_data.zip
|
├── Task 3/
│   └── edge_processing (1).py
|
├── Task 4/
│   └── task4_analysis.py
|
├── Task 5/
│   └── anomaly_detection.py
|
├── Task 6/
│   └── assignmentapp.py
|
└── csv_files/                     # Created during execution; ignored by Git
    ├── cnc_cell_data.csv
    ├── processed_data.csv
    ├── task4_machine_metrics.csv
    └── data_with_flags.csv
```

All generated CSV files are stored in the project's `csv_files/` folder. Task 1 creates this folder automatically if it does not exist.

Paths are resolved relative to the scripts, so the data location does not depend on the terminal's working directory. Task 3 and Task 4 resolve supplied relative file paths within `csv_files/` and reject paths outside that folder.

---

## 3. Task Descriptions

### Task 1 — Virtual Manufacturing Data Generation

**Objective:** Generate sensor and production data for five CNC machines.

#### Dataset Specifications

| Parameter | Value |
| --- | --- |
| Number of CNC machines | 5 |
| Sampling frequency | 10 Hz per machine |
| Simulation duration | 2 hours |
| Samples per machine | 72,000 |
| Total observations | 360,000 |
| Dataset format | CSV |

#### Dataset Columns

| Column | Description |
| --- | --- |
| `Timestamp` | Observation timestamp |
| `Machine_ID` | CNC machine identifier |
| `Machine_Status` | Current operating state |
| `Temperature` | Machine temperature |
| `Vibration` | Measured vibration level |
| `Motor_Current` | Motor current |
| `Spindle_RPM` | Spindle rotational speed |
| `Pressure` | Operating pressure |
| `Cycle_Time` | Most recently completed part's cycle time; may be missing before a completion |
| `Production_Count` | Cumulative number of produced parts |
| `Rejected_Parts` | Cumulative number of rejected parts |
| `Abnormal_Flag` | Ground-truth indicator for injected abnormal conditions |

#### Simulation Model

The simulation includes:

- Transitions between `Running`, `Idle`, `Stopped`, `Fault`, and `Maintenance`.
- First-order sensor response models representing thermal inertia and other response delays.
- Measurement noise, physical limits, and sensor quantization.
- Machine-specific sensor characteristics, production cycle times, and rejection rates.
- Cyclic cutting loads that influence vibration and motor current.
- Injected bearing-wear windows for `CNC_03` and `CNC_05`.

During the injected bearing-wear windows, severity gradually increases. At severity approaching one, the configured effects include approximately:

- Temperature: +15 °C.
- Vibration: +4 mm/s.
- Motor current: +6 A.
- Nominal production cycle time: +35%.
- Increased spindle-speed noise and rejection probability.

These effects modify simulation targets; measured values also depend on sensor response and noise. The affected machine enters `Maintenance` when its injected anomaly window ends.

The random seed in `Task 1/config.py` makes the simulation reproducible. Repeated runs with the same seed and configuration generate the same dataset.

**Implementation:** `Task 1/config.py`, `Task 1/generator.py`, and `Task 1/generate_data.py`.

**Output:** `csv_files/cnc_cell_data.csv`

---

### Task 2 — IIoT System Architecture

**Objective:** Describe the layered architecture of the virtual manufacturing system.

The architecture consists of:

1. **Physical and Sensing Layer:** Five simulated CNC machines and their virtual sensors.
2. **Data Acquisition Layer:** Timestamped collection of sensor readings, operating states, and production counters.
3. **Edge Processing Layer:** Filtering, feature extraction, rolling statistics, and preliminary outlier detection.
4. **Data Storage Layer:** CSV storage for raw data, processed features, metrics, and detection results.
5. **Analytics Layer:** Machine-performance analysis and abnormal-condition detection.
6. **Visualization and Decision-Support Layer:** Interactive presentation of sensor trends, production metrics, machine states, and alarms.

The implementation exchanges saved datasets between scripts rather than operating as a continuously streaming system.

---

### Task 3 — Edge Processing

**Objective:** Process raw machine readings into features suitable for downstream analytics.

| Method | Implementation | Purpose |
| --- | --- | --- |
| Moving-average filtering | Causal 5-second rolling mean for five sensor measurements | Reduces measurement noise |
| Rolling statistics | Up to 30 seconds of spindle-RPM history, with a minimum of 5 seconds of samples | Measures spindle-speed variability |
| Feature extraction | Segment runtime, active-state flag, smoothed sensor measurements, and RPM standard deviation | Supplies analytical features |
| Rolling Z-score outlier detection | Compares raw vibration with the preceding 5-second reference window | Detects unusual vibration readings |
| Status segmentation | Resets rolling calculations at each machine-status change | Separates operating states |
| Startup grace period | Marks Running readings as active after 60 seconds in the segment | Suppresses detection during startup |

Rolling features are still calculated during the startup grace period. The active-state flag controls whether readings are eligible for the relevant detections.

The output retains the original columns and adds features such as:

- `Seg`
- `Run_Time_s`
- `Active`
- Sensor columns ending in `_MA`
- `RPM_Std`
- `Vibration_Zscore`
- `Vibration_Outlier`

**Implementation:** `Task 3/edge_processing (1).py`

**Input:** `csv_files/cnc_cell_data.csv`

**Output:** `csv_files/processed_data.csv`

---

### Task 4 — Industrial Data Analysis

**Objective:** Calculate performance indicators for each CNC machine.

This task uses Python's standard library.

#### Calculated KPIs

| KPI | Description |
| --- | --- |
| Average Temperature | Mean recorded temperature |
| Average Vibration | Mean recorded vibration |
| Maximum Motor Current | Highest recorded motor current |
| Average Cycle Time | Mean cycle time from qualifying production-counter advances during Running |
| Machine Utilization | Percentage of observations in the Running state |
| Total Production | Total produced parts |
| Production Rate | Parts produced per running hour |
| Total Rejected Parts | Total rejected parts |
| Rejection Rate | Rejected parts as a percentage of production |
| Total Downtime | Time in Stopped, Fault, and Maintenance states |
| Abnormal Events | Count of contiguous abnormal periods identified by the selected indicator |
| Cycle-Time CV | Sample standard deviation of cycle time divided by its mean, expressed as a percentage |

#### Key Formulas

**Machine Utilization**

$$
\text{Utilization (\%)} =
\frac{\text{Running Observations}}
{\text{Total Observations}} \times 100
$$

**Rejection Rate**

$$
\text{Rejection Rate (\%)} =
\frac{\text{Rejected Parts}}
{\text{Total Produced Parts}} \times 100
$$

**Production Rate**

$$
\text{Production Rate} =
\frac{\text{Total Parts Produced}}
{\text{Running Time in Hours}}
$$

**Cycle-Time Coefficient of Variation**

$$
CV(\%) =
\frac{s_{\text{cycle time}}}
{\bar{x}_{\text{cycle time}}} \times 100
$$

For the Task 1 dataset, use cumulative-counter mode and an observation interval of 0.1 seconds, equivalent to approximately `0.0016666666666666668` minutes.

**Implementation:** `Task 4/task4_analysis.py`

**Default input:** `csv_files/cnc_cell_data.csv`

**Output:** `csv_files/task4_machine_metrics.csv`

---

### Task 5 — Abnormal Condition Detection

**Objective:** Compare three detection methods against the simulated ground-truth labels.

Task 5 uses the smoothed features and RPM standard deviation generated by Task 3.

The healthy reference consists of active Running observations before `2026-01-05 07:00:00`, corresponding to the first simulated hour. Baseline statistics are calculated separately for each machine.

#### 1. Fixed-Threshold Detector

Uses machine-specific limits derived from healthy-data quantiles with a configurable margin. These are statistical limits estimated from the simulation data.

Temperature, vibration, motor current, and RPM variability are checked for unusually high values. Spindle speed and pressure are checked for unusually high or low values.

#### 2. Robust Z-Score Detector

Uses each machine's healthy median and median absolute deviation:

$$
Z_{\text{robust}} =
\frac{x-\operatorname{median}(X)}
{1.4826 \times MAD(X)}
$$

The current configuration uses:

- Z-score cutoff: **2.4**.
- At least **one** variable-level detection.
- A **25-second persistence** requirement.

Temperature, vibration, motor current, and RPM variability use upper-tail detection. Spindle speed and pressure use two-sided detection.

The robust Z-score output is copied to `Flag_final` and is the detector displayed by the dashboard.

#### 3. Isolation Forest

Fits an Isolation Forest to healthy features standardized using each machine's median and MAD-based scale.

The model uses:

- Temperature.
- Vibration.
- Motor current.
- RPM standard deviation.

The current configuration includes 200 trees and 10-second score smoothing. An alarm-score threshold is estimated from healthy training scores using a target tail fraction of `0.0075`; this is separate from the model's `contamination` parameter and does not guarantee the same false-alarm rate on later data.

#### Persistence and Operating-State Filtering

All three detectors apply the configured 25-second persistence filter. Detections are restricted to active Running readings and persistence is evaluated within each machine-status segment.

#### Evaluation

The implementation calculates precision, recall, accuracy, F1 score, false-alarm rate, and confusion counts. The printed comparison shows TP, FP, FN, precision, recall, and false-alarm rate, followed by alarm delays.

Evaluation is restricted to Running observations. Both full-period scores and additional scores excluding the first 600 seconds of each machine's injected anomaly are reported.

| Metric | Description |
| --- | --- |
| Precision | Fraction of positive detections that match injected anomalies |
| Recall | Fraction of injected-anomaly readings detected |
| False-Alarm Rate | Fraction of normal readings incorrectly flagged |
| True Positives | Injected-anomaly readings correctly detected |
| False Positives | Normal readings incorrectly flagged |
| False Negatives | Injected-anomaly readings missed |
| True Negatives | Normal readings correctly classified |
| Alarm Delay | Time from injected anomaly onset to the first qualifying alarm at or after onset |

A detector can generate false alarms even when no bearing-wear anomaly was injected into a machine.

**Implementation:** `Task 5/anomaly_detection.py`

**Input:** `csv_files/processed_data.csv`

**Output:** `csv_files/data_with_flags.csv`

---

### Task 6 — Visualization and Decision Support

**Objective:** Display machine conditions, production performance, and detected abnormalities through an interactive dashboard.

The dashboard uses Streamlit and Plotly.

#### Dashboard Features

- **Cell-Level KPIs:** Total production and rejected-part counts.
- **Sensor Trends:** Temperature and vibration charts for the selected machine.
- **Reference Lines:** Fixed temperature and vibration reference lines; these are separate from Task 5's detector thresholds.
- **Machine-Status Timeline:** Operating-state history for the selected machine.
- **Machine Comparisons:** Utilization and rejection-rate comparisons based on Task 4 outputs.
- **Alarm Timeline:** Z-score detections across all machines, grouped by minute.
- **Anomaly Log:** Expandable table summarizing flagged readings by minute and machine.

The alarm timeline shows detector predictions, which may include false alarms. A marker indicates that at least one flagged reading occurred in that minute; it does not imply that the entire minute was abnormal.

The dashboard reads saved CSV files. Restarting it does not generate new data or create a live sensor stream.

**Implementation:** `Task 6/assignmentapp.py`

**Inputs:**

- `csv_files/data_with_flags.csv`
- `csv_files/task4_machine_metrics.csv`

---

## 4. Technology Stack

| Technology | Purpose |
| --- | --- |
| Python 3.10+ | Implementation language |
| NumPy | Numerical calculations and simulation |
| pandas | Dataset processing |
| scikit-learn | Isolation Forest and related utilities |
| Streamlit | Interactive dashboard |
| Plotly | Charts and visualizations |
| Git and GitHub | Version control and collaboration |

---

## 5. Installation and Setup

### Prerequisites

- Python 3.10 or later.
- Git, if cloning the repository.
- pip.

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Abhinav-7070/Industrial-Data-Analytics-ME-217-Project----Group-1A.git
cd Industrial-Data-Analytics-ME-217-Project----Group-1A
```

Alternatively, download and extract the repository, then open a terminal in its root folder.

### Step 2 — Create and Activate a Virtual Environment

**Windows PowerShell:**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows, use `python` instead of `py` if the Python launcher is unavailable.

### Step 3 — Install Dependencies

With the virtual environment activated:

```bash
python -m pip install numpy pandas scikit-learn streamlit plotly
```

The following run commands use `python` from the activated virtual environment and work on Windows, macOS, and Linux. Keep the quotes around script paths because folder names contain spaces.

Without an activated virtual environment, Linux/macOS users can use `python3`, and Windows users can use `py` or `python`. Install dependencies with the same interpreter used to run the project.

---

## 6. Running the Full Pipeline with One Command

From the repository root, with the virtual environment activated:

```bash
python run_pipeline.py
```

The runner executes:

1. Task 1 — Generate the raw dataset.
2. Task 3 — Perform edge processing.
3. Task 4 — Calculate metrics using the correct sampling interval and cumulative-counter mode.
4. Task 5 — Detect abnormal conditions.
5. Task 6 — Launch the dashboard.

The runner uses the same Python interpreter for every task and stops if a task fails.

Open the address printed by Streamlit, normally:

```text
http://localhost:8501
```

Press **Ctrl+C** in the terminal to stop the dashboard.

Each full run regenerates the CSV files. With the same random seed and configuration, repeated generation produces the same dataset.

Task 2 describes the architecture and has no executable step in the runner.

---

## 7. Running Individual Tasks

Run these commands from the repository root with the virtual environment activated.

### Step 1 — Generate the Manufacturing Dataset

```bash
python "Task 1/generate_data.py"
```

Creates `csv_files/` if necessary and writes:

```text
csv_files/cnc_cell_data.csv
```

### Step 2 — Run Edge Processing

```bash
python "Task 3/edge_processing (1).py"
```

Reads the raw dataset and writes:

```text
csv_files/processed_data.csv
```

### Step 3 — Calculate Machine KPIs

```bash
python "Task 4/task4_analysis.py" --interval-minutes 0.0016666666666666668 --count-mode cumulative --abnormal-column Abnormal_Flag
```

The arguments specify:

- An observation interval of 0.1 seconds at 10 Hz.
- Cumulative production and rejection counters.
- Ground-truth labels for abnormal-event counts.

Writes:

```text
csv_files/task4_machine_metrics.csv
```

### Step 4 — Run Anomaly Detection

```bash
python "Task 5/anomaly_detection.py"
```

Reads the processed dataset, prints detector evaluation results, and writes:

```text
csv_files/data_with_flags.csv
```

### Step 5 — Launch the Dashboard

```bash
python -m streamlit run "Task 6/assignmentapp.py" --server.fileWatcherType none
```

Open `http://localhost:8501`, or the address printed in the terminal.

The dashboard requires the Task 4 and Task 5 output files. Starting it before these files exist will produce a file-not-found error.

Press **Ctrl+C** to stop.

### Reopening the Dashboard Without Regenerating Data

If all CSV outputs already exist, run only the dashboard command:

```bash
python -m streamlit run "Task 6/assignmentapp.py" --server.fileWatcherType none
```

It will display the previously generated results.

### Using the Archived Raw Dataset

An archived dataset is included at:

```text
Task 1/cnc_cell_data.zip
```

To use it instead of running Task 1, extract `cnc_cell_data.csv` into the project's `csv_files/` folder, creating the folder if necessary. Then run Tasks 3, 4, 5, and 6.

The archived dataset may differ from a dataset generated using modified simulation settings.

### Calculating KPIs from Detected Alarms

By default, Task 4 counts abnormal events using the simulation's ground-truth labels.

To count events using Task 5's final detector output instead, run this after Task 5:

```bash
python "Task 4/task4_analysis.py" data_with_flags.csv --interval-minutes 0.0016666666666666668 --count-mode cumulative --abnormal-column Flag_final
```

This overwrites `csv_files/task4_machine_metrics.csv` with metrics using detected alarms for the abnormal-event count.

---

## 8. Generated Files and Git

The `.gitignore` excludes:

```gitignore
/csv_files/
```

Generated datasets therefore do not need to be committed. After cloning, the evaluator can install the dependencies and run:

```bash
python run_pipeline.py
```

Task 1 creates the data folder, and subsequent tasks produce the intermediate files required by the dashboard.

---

## 9. Key Design Decisions

### Physics-Inspired Simulation

Sensor values respond to operating states through first-order lag models instead of being generated as unrelated random observations.

### Status-Aware Processing

Rolling features reset at status changes, and detection excludes the initial startup period of Running segments.

### Machine-Specific Baselines

Healthy reference statistics are calculated separately for each machine to account for differences in normal operation.

### Ground-Truth Evaluation

Injected bearing-wear labels allow detector predictions to be compared quantitatively with known simulated anomaly windows.

### Reproducibility

A fixed simulation seed supports repeatable results. Changing the seed and rerunning the pipeline generates a different simulated operating history.

### Separate Pipeline Components

Generation, edge processing, KPI analysis, anomaly detection, and visualization remain separate scripts, with a single runner coordinating their execution.

---

## 10. Acknowledgements

This project was developed as part of **Industrial Data Analytics (ME 217), Assignment 1**, to demonstrate how simulated industrial sensor data can be processed, analyzed, and visualized for machine-condition monitoring and production decision support.
