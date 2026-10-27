import math
import numpy as np
import pandas as pd
import config as cfg

SENSORS = ["temp", "vib", "current", "rpm", "pressure"]
# per-sample inertia from the physical time constant: alpha = 1 - exp(-dt/tau)
ALPHA = {k: 1.0 - math.exp(-cfg.DT / tau) for k, tau in cfg.TAU_S.items()}


def to_step(seconds):
    """Convert seconds to a sample index."""
    return int(round(seconds * cfg.SAMPLING_HZ))

def build_forced_windows(machine_id):
    """Return ({step: forced_status}, {step: severity}, set_of_abnormal_steps)."""
    forced, severity, abnormal = {}, {}, set()
    for a in cfg.ANOMALIES:
        if a["machine"] != machine_id:
            continue
        start, end = to_step(a["start_s"]), to_step(a["end_s"])
        for t in range(start, end):
            abnormal.add(t)
            if a["type"] == "bearing_wear":
                forced[t] = "Running"
                severity[t] = (t - start) / (end - start)   # ramps 0 -> 1
            elif a["type"] == "sudden_fault":
                forced[t] = "Fault"
    return forced, severity, abnormal


def generate_status_sequence(rng, n_steps, forced):
    """Status per sample: random dwell times + next-state odds; forced steps override."""
    leave_draw = rng.random(n_steps)       # one 'do I leave now?' draw per sample
    statuses = []
    prev = cfg.INITIAL_STATUS
    for t in range(n_steps):
        if t in forced:
            current = forced[t]
        elif (t - 1) in forced:                       # anomaly just ended
            current = cfg.AFTER_ANOMALY_STATUS
        elif leave_draw[t] < cfg.DT / cfg.MEAN_DWELL_S[prev]:
            options = cfg.NEXT_STATE[prev]
            current = rng.choice(list(options), p=list(options.values()))
        else:
            current = prev
        statuses.append(current)
        prev = current
    return statuses

def generate_machine(machine_id, params, rng, timestamps):
    """Generate the full table for one machine."""
    n = len(timestamps)
    forced, severity, abnormal = build_forced_windows(machine_id)
    statuses = generate_status_sequence(rng, n, forced)
    z = rng.standard_normal((n, len(SENSORS)))     # all white noise drawn at once
    w = cfg.WEAR_EFFECTS

    state = dict(temp=cfg.AMBIENT_TEMP, vib=0.0, current=0.0, rpm=0.0, pressure=0.0)
    prod_count = rejected_total = 0
    cycle_target = None            # duration of the part being machined (s)
    cycle_elapsed = 0.0
    last_cycle = np.nan            # last completed cycle time (PLC-style register)

    cols = {c: [] for c in ["Machine_Status", "Temperature", "Vibration",
                            "Motor_Current", "Spindle_RPM", "Pressure",
                            "Cycle_Time", "Production_Count", "Rejected_Parts",
                            "Abnormal_Flag"]}

    for t in range(n):
        status = statuses[t]
        base = cfg.BASELINES[status]
        running = status == "Running"
        sev = severity.get(t, 0.0) if running else 0.0

        # ---- part-cycle timer (only while Running) ----------------------
        if running:
            if cycle_target is None:                       # start a new part
                nominal = params["cycle_s"] * (1.0 + w["cycle_increase"] * sev)
                cycle_target = max(rng.normal(
                    nominal, cfg.CYCLE_TIME_NOISE_FRAC * nominal), 1.0)
                cycle_elapsed = 0.0
            load = math.sin(2 * math.pi * cycle_elapsed / cycle_target)
        else:
            cycle_target, load, last_cycle = None, 0.0, np.nan   # part in progress lost

        # ---- 1. targets: status baseline x machine personality ----------
        target = dict(
            temp=cfg.AMBIENT_TEMP + (base["temp"] - cfg.AMBIENT_TEMP) * params["temp_mult"],
            vib=base["vib"] * params["vib_mult"] * (1 + cfg.CYCLE_LOAD_AMP["vib"] * load),
            current=base["current"] * params["cur_mult"] * (1 + cfg.CYCLE_LOAD_AMP["current"] * load),
            rpm=base["rpm"] * params["rpm_mult"],
            pressure=base["pressure"],
        )
        # ---- 2. abnormal condition pushes targets up --------------------
        target["temp"] += w["temp_add"] * sev
        target["vib"] += w["vib_add"] * sev
        target["current"] += w["current_add"] * sev

        # ---- 3. inertia: first-order lag towards the target -------------
        for k in SENSORS:
            state[k] += ALPHA[k] * (target[k] - state[k])

        # ---- 4. measurement noise, limits, quantisation -----------------
        scale = cfg.NOISE_SCALE[status] * params["noise_mult"]
        meas = {}
        for i, k in enumerate(SENSORS):
            std = cfg.NOISE_BASE[k] * scale
            if k == "rpm":
                std *= 1.0 + w["rpm_noise_extra"] * sev     # unstable speed
            val = state[k] + z[t, i] * std
            val = max(val, 15.0 if k == "temp" else 0.0)    # physical limits
            meas[k] = round(val, cfg.DECIMALS[k])
        meas["rpm"] = int(meas["rpm"])

        # ---- 5. part completion -----------------------------------------
        if running:
            cycle_elapsed += cfg.DT
            if cycle_elapsed >= cycle_target:
                prod_count += 1
                if rng.random() < min(params["base_reject"] + w["reject_add"] * sev, 1.0):
                    rejected_total += 1
                last_cycle = round(cycle_target, 2)
                cycle_target = None

        cols["Machine_Status"].append(status)
        cols["Temperature"].append(meas["temp"])
        cols["Vibration"].append(meas["vib"])
        cols["Motor_Current"].append(meas["current"])
        cols["Spindle_RPM"].append(meas["rpm"])
        cols["Pressure"].append(meas["pressure"])
        cols["Cycle_Time"].append(last_cycle)
        cols["Production_Count"].append(prod_count)
        cols["Rejected_Parts"].append(rejected_total)
        cols["Abnormal_Flag"].append(1 if t in abnormal else 0)

    df = pd.DataFrame(cols)
    df.insert(0, "Machine_ID", machine_id)
    df.insert(0, "Timestamp", timestamps)
    return df

def generate_all():
    """Generate every machine and stack them into one DataFrame."""
    timestamps = pd.date_range(cfg.START_TIME, periods=cfg.N_STEPS,
                               freq=f"{round(1000 * cfg.DT)}ms")
    frames = []
    for i, (machine_id, params) in enumerate(cfg.MACHINES.items()):
        rng = np.random.default_rng([cfg.SEED, i])   # independent stream per machine
        frames.append(generate_machine(machine_id, params, rng, timestamps))
    df = pd.concat(frames, ignore_index=True)
    return df.sort_values(["Timestamp", "Machine_ID"]).reset_index(drop=True)
