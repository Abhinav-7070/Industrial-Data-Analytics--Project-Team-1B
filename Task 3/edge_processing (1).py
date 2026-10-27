# ==============================================================
# TASK 3: EDGE PROCESSING METHODS IMPLEMENTED
# ==============================================================
#
# 1. Moving Average Filtering:
#    Smooths temperature, vibration, motor current, spindle RPM,
#    and pressure readings using a 5-second rolling window.
#
# 2. Rolling Statistics:
#    Calculates the rolling standard deviation of spindle RPM
#    over a 30-second window to measure operating instability.
#
# 3. Feature Extraction:
#    Generates features including moving averages, RPM standard
#    deviation, segment runtime, and vibration Z-scores for
#    downstream machine-condition analysis.
#
# 4. Outlier Detection:
#    Uses a causal rolling Z-score to detect unusual vibration
#    readings. Values with |Z| > 3 are flagged as outliers.
#
# Additional Processing:
# - Status-aware segmentation separates operating periods.
# - A 60-second startup grace period excludes startup readings
#   from vibration outlier detection.
# - Processing is performed independently for each CNC machine.
#
# ==============================================================

import argparse
from pathlib import Path

import pandas as pd

SAMPLING_HZ = 10
STARTUP_GRACE_S = 60
SMOOTH_S = 5
RPM_STD_WINDOW_S = 30
OUTLIER_Z_CUTOFF = 3.0
SENSORS = ["Temperature", "Vibration", "Motor_Current", "Spindle_RPM", "Pressure"]
REQUIRED_COLUMNS = {"Timestamp", "Machine_ID", "Machine_Status", *SENSORS}


def load_data(csv_path: Path) -> pd.DataFrame:
    """Read raw CNC data and validate the columns needed for processing."""
    data = pd.read_csv(csv_path)
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    data["Timestamp"] = pd.to_datetime(data["Timestamp"], errors="raise")
    for sensor in SENSORS:
        data[sensor] = pd.to_numeric(data[sensor], errors="raise")
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Required columns contain missing values; clean the input first.")
    if data[SENSORS].isin([float("inf"), float("-inf")]).any().any():
        raise ValueError("Sensor columns contain infinite values.")
    return data


def process_at_edge(data: pd.DataFrame) -> pd.DataFrame:
    """Match Task5 features, keeping raw sensors alongside derived columns."""
    processed = data.sort_values(["Machine_ID", "Timestamp"]).reset_index(drop=True).copy()
    status_changed = processed["Machine_Status"] != processed.groupby("Machine_ID")["Machine_Status"].shift()
    processed["Seg"] = status_changed.groupby(processed["Machine_ID"]).cumsum()
    segments = processed.groupby([processed["Machine_ID"], processed["Seg"]])
    processed["Run_Time_s"] = segments.cumcount() / SAMPLING_HZ
    processed["Active"] = (
        (processed["Machine_Status"] == "Running")
        & (processed["Run_Time_s"] >= STARTUP_GRACE_S)
    )

    # Match Task5's 50-sample smoothing, resetting at every status change.
    window = max(int(SMOOTH_S * SAMPLING_HZ), 1)
    for sensor in SENSORS:
        processed[f"{sensor}_MA"] = segments[sensor].transform(
            lambda readings: readings.rolling(window, min_periods=1).mean()
        )
    processed["RPM_Std"] = segments["Spindle_RPM"].transform(
        lambda readings: readings.rolling(
            int(RPM_STD_WINDOW_S * SAMPLING_HZ), min_periods=window
        ).std()
    )

    # Detect raw vibration spikes using only previous readings in this segment.
    # This local outlier score is separate from Task5's healthy-baseline detectors.
    previous_mean = segments["Vibration"].transform(
        lambda readings: readings.shift(1).rolling(window, min_periods=window).mean()
    )
    previous_std = segments["Vibration"].transform(
        lambda readings: readings.shift(1).rolling(window, min_periods=window).std()
    )
    difference = processed["Vibration"] - previous_mean
    score = difference / previous_std.replace(0, float("nan"))
    # A changed reading after an exactly constant window is an outlier as well.
    constant_changed = previous_std.eq(0) & difference.ne(0)
    score.loc[constant_changed & difference.gt(0)] = float("inf")
    score.loc[constant_changed & difference.lt(0)] = float("-inf")
    score.loc[previous_std.eq(0) & difference.eq(0)] = 0.0
    processed["Vibration_Zscore"] = score.where(processed["Active"])
    processed["Vibration_Outlier"] = processed["Vibration_Zscore"].abs() > OUTLIER_Z_CUTOFF
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run status-aware CNC edge processing")
    parser.add_argument("--input", type=Path, required=True, help="Raw CNC input CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "Output",
        help="Output directory (default: the project's Output folder)",
    )
    args = parser.parse_args()

    processed = process_at_edge(load_data(args.input))
    args.output.mkdir(parents=True, exist_ok=True)
    output_path = args.output / "processed_data.csv"
    processed.to_csv(output_path, index=False)
    print(f"Processed {len(processed)} readings from {processed['Machine_ID'].nunique()} machines.")
    print(f"Active readings: {processed['Active'].sum()} | Vibration outliers: {processed['Vibration_Outlier'].sum()}")
    print(f"File saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
