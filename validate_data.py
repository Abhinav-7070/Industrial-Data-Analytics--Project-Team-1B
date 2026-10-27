import math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import config as cfg

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / cfg.OUTPUT_FILENAME
FIG_DIR = ROOT / "figures"
SENSORS = ["Temperature", "Vibration", "Motor_Current", "Spindle_RPM", "Pressure"]

def sampling_checks(df):
    print("=== 1. Sampling and Nyquist check ===")
    one = df[df["Machine_ID"] == "CNC_01"]
    dt = one["Timestamp"].diff().dropna().dt.total_seconds()
    print(f"Sampling interval: min {dt.min():.3f} s, max {dt.max():.3f} s "
          f"-> fs = {1 / dt.mean():.1f} Hz, Nyquist = {0.5 / dt.mean():.1f} Hz")
    assert dt.nunique() == 1, "Irregular sampling!"
    print("Signal bandwidth ~ 1/(2*pi*tau) for each channel:")
    for k, tau in cfg.TAU_S.items():
        bw = 1 / (2 * math.pi * tau)
        print(f"  {k:9s} tau={tau:6.1f} s -> bandwidth {bw:.4f} Hz "
              f"({cfg.SAMPLING_HZ / 2 / bw:,.0f}x below Nyquist)")
    fastest = 1 / min(m["cycle_s"] for m in cfg.MACHINES.values())
    print(f"  part cycle: shortest period {1 / fastest:.0f} s -> {fastest:.3f} Hz\n")

def basic_checks(df):
    print("=== 2. Shape, missing values, counters ===")
    print(f"Rows: {len(df):,} | Columns: {list(df.columns)}")
    print("Missing values:\n", df.isna().sum()[lambda s: s > 0].to_string())
    print("(Cycle_Time is NaN until a part completes / when not Running)\n")
    assert len(df) >= 10_000
    g = df.groupby("Machine_ID")
    assert g["Production_Count"].apply(lambda s: s.is_monotonic_increasing).all()
    assert g["Rejected_Parts"].apply(lambda s: s.is_monotonic_increasing).all()
    assert (df["Rejected_Parts"] <= df["Production_Count"]).all()
    print("Counters monotonic and Rejected <= Produced: OK\n")

def status_checks(df):
    print("=== 3. Mean sensor value per status ===")
    print(df.groupby("Machine_Status")[SENSORS].mean().round(2), "\n")
    print("=== 4. Share of time in each status (%) ===")
    share = (df.groupby("Machine_ID")["Machine_Status"]
               .value_counts(normalize=True).unstack().fillna(0) * 100)
    print(share.round(1), "\n")

def machine_checks(df):
    run = df[df["Machine_Status"] == "Running"]
    normal = run[run["Abnormal_Flag"] == 0]
    print("=== 5. Running-state comparison (normal rows only) ===")
    print(normal.groupby("Machine_ID").agg(
        temp=("Temperature", "mean"), vib=("Vibration", "mean"),
        current=("Motor_Current", "mean"), rpm=("Spindle_RPM", "mean"),
        rpm_std=("Spindle_RPM", "std")).round(2), "\n")

    print("=== 6. Production summary per machine ===")
    g = df.groupby("Machine_ID")
    prod = g["Production_Count"].max()
    rej = g["Rejected_Parts"].max()
    # cycle time averaged per completed part (rows where the counter increases)
    done = df[df.groupby("Machine_ID")["Production_Count"].diff() > 0]
    out = pd.DataFrame({"parts": prod, "rejected": rej,
                        "reject_%": (rej / prod * 100).round(2),
                        "avg_cycle_s": done.groupby("Machine_ID")["Cycle_Time"].mean().round(2)})
    print(out, "\n")

    print("=== 7. Abnormal vs normal (Running rows) ===")
    print(run.groupby("Abnormal_Flag")[SENSORS + ["Cycle_Time"]].mean().round(2), "\n")


def make_plots(df):
    FIG_DIR.mkdir(exist_ok=True)

    # Plot 1: bearing wear on CNC_03 (full run, rolling mean over 10 s for clarity)
    m = df[df["Machine_ID"] == "CNC_03"].set_index("Timestamp")
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    for ax, col in zip(axes, ["Temperature", "Vibration", "Motor_Current"]):
        ax.plot(m.index, m[col], lw=0.3, alpha=0.5)
        ax.plot(m.index, m[col].rolling(100, min_periods=1).mean(), lw=1.2, color="k")
        ab = m["Abnormal_Flag"] == 1
        ax.fill_between(m.index, m[col].min(), m[col].max(), where=ab,
                        color="red", alpha=0.12)
        ax.set_ylabel(col)
    fig.suptitle("CNC_03 - gradual bearing wear (red = injected window, black = 10 s mean)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "validation_cnc03_anomaly.png", dpi=120)
    plt.close(fig)

    # Plot 2: CNC_01 first 20 minutes - warm-up and status blocks
    m = df[df["Machine_ID"] == "CNC_01"].head(12_000).reset_index(drop=True)
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(m["Timestamp"], m["Temperature"], lw=0.6); axes[0].set_ylabel("Temperature")
    axes[1].plot(m["Timestamp"], m["Spindle_RPM"], lw=0.6); axes[1].set_ylabel("Spindle_RPM")
    codes = m["Machine_Status"].astype("category")
    axes[2].step(m["Timestamp"], codes.cat.codes, lw=1)
    axes[2].set_yticks(range(len(codes.cat.categories)))
    axes[2].set_yticklabels(codes.cat.categories); axes[2].set_ylabel("Status")
    fig.suptitle("CNC_01 - first 20 minutes: warm-up and status blocks")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "validation_cnc01_warmup.png", dpi=120)
    plt.close(fig)

    # Plot 3: sudden fault on CNC_05
    m = df[df["Machine_ID"] == "CNC_05"].reset_index(drop=True)
    idx = m.index[m["Abnormal_Flag"] == 1]
    seg = m.iloc[max(idx.min() - 3000, 0): idx.max() + 3000]
    fig, axes = plt.subplots(2, 1, figsize=(11, 5), sharex=True)
    for ax, col in zip(axes, ["Vibration", "Motor_Current"]):
        ax.plot(seg["Timestamp"], seg[col], lw=0.5); ax.set_ylabel(col)
        ax.axvspan(m["Timestamp"][idx.min()], m["Timestamp"][idx.max()], color="red", alpha=0.12)
    fig.suptitle("CNC_05 - sudden fault window")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "validation_cnc05_fault.png", dpi=120)
    plt.close(fig)

    # Plot 4: 60 s zoom on a normal Running stretch - what 10 Hz samples look like
    m = df[df["Machine_ID"] == "CNC_02"].reset_index(drop=True)
    run = (m["Machine_Status"] == "Running").astype(int)
    full = run.rolling(900).min() == 1                      # 90 s all Running
    i0 = full[full].index[0] - 899 + 300
    seg = m.iloc[i0: i0 + 600]
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    for ax, col in zip(axes, ["Spindle_RPM", "Motor_Current", "Vibration"]):
        ax.plot(seg["Timestamp"], seg[col], ".-", ms=2, lw=0.4); ax.set_ylabel(col)
    fig.suptitle("CNC_02 - 60 s of raw 10 Hz samples while Running (load follows the part cycle)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "validation_cnc02_zoom_60s.png", dpi=120)
    plt.close(fig)
    print(f"Plots saved in {FIG_DIR}")


if __name__ == "__main__":
    data = pd.read_csv(DATA, parse_dates=["Timestamp"])
    sampling_checks(data)
    basic_checks(data)
    status_checks(data)
    machine_checks(data)
    make_plots(data)
