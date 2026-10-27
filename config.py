SEED = 42                          
START_TIME = "2026-01-05 06:00:00"
SAMPLING_HZ = 10                   # acquisition rate (OPC UA / MTConnect style polling)
DT = 1.0 / SAMPLING_HZ             # 0.1 s between samples
DURATION_S = 7200                  # 2 hours of operation per machine
N_STEPS = int(DURATION_S * SAMPLING_HZ)   # 72,000 samples/machine, 360,000 rows total
AMBIENT_TEMP = 25.0                # shop-floor temperature, deg C

# Per-sample probability of leaving = DT / MEAN_DWELL_S (rate independent).
MEAN_DWELL_S = {"Running": 600, "Idle": 120, "Stopped": 180,
                "Fault": 90, "Maintenance": 240}
NEXT_STATE = {
    "Running":     {"Idle": 0.55, "Stopped": 0.28, "Fault": 0.10, "Maintenance": 0.07},
    "Idle":        {"Running": 0.80, "Stopped": 0.12, "Maintenance": 0.08},
    "Stopped":     {"Idle": 0.85, "Maintenance": 0.15},
    "Fault":       {"Maintenance": 0.80, "Stopped": 0.20},
    "Maintenance": {"Idle": 0.85, "Stopped": 0.15},
}
STATUSES = list(MEAN_DWELL_S.keys())
INITIAL_STATUS = "Idle"
AFTER_ANOMALY_STATUS = "Maintenance"   # machine is taken down when an anomaly ends

BASELINES = {
    "Running":     dict(temp=62.0, vib=2.0, current=18.0, rpm=3000, pressure=6.0),
    "Idle":        dict(temp=38.0, vib=0.4, current=3.0,  rpm=50,   pressure=4.0),
    "Stopped":     dict(temp=25.0, vib=0.05, current=0.2, rpm=0,    pressure=0.5),
    "Maintenance": dict(temp=25.0, vib=0.05, current=0.1, rpm=0,    pressure=0.0),
    "Fault":       dict(temp=70.0, vib=5.0, current=24.0, rpm=800,  pressure=4.0),
}

# Time constant tau: after tau seconds a sensor has covered 63 % of the gap to
# its target. Bandwidth ~ 1/(2*pi*tau) -> used for the Nyquist check.
TAU_S = dict(temp=300.0,     # thermal mass of spindle housing (minutes scale)
             vib=1.0,        # = 1 s RMS window computed by the sensor/edge unit
             current=0.5,    
             rpm=1.0,        # spindle accelerates / stops in a few seconds
             pressure=2.0)   # hydraulic/pneumatic line
.
NOISE_BASE = dict(temp=0.15,     # PT100-class sensor
                  vib=0.10,      
                  current=0.30,  
                  rpm=15.0,      # ~0.5 % of 3000 rpm speed ripple
                  pressure=0.05) # bar
NOISE_SCALE = {"Running": 1.0, "Idle": 0.5, "Stopped": 0.1,
               "Maintenance": 0.1, "Fault": 3.0}

# Sensor resolution (decimals kept) = ADC quantisation of the real device.
DECIMALS = dict(temp=1, vib=2, current=2, rpm=0, pressure=2)

# Cutting-load pattern inside one part cycle (fraction of target, sinusoidal).
CYCLE_LOAD_AMP = dict(current=0.10, vib=0.08)

MACHINES = {
    "CNC_01": dict(temp_mult=1.00, vib_mult=0.80, cur_mult=0.95, rpm_mult=1.00,
                   noise_mult=0.8, cycle_s=38, base_reject=0.010),  # newest
    "CNC_02": dict(temp_mult=1.00, vib_mult=1.00, cur_mult=1.00, rpm_mult=1.00,
                   noise_mult=1.0, cycle_s=40, base_reject=0.015),  # reference
    "CNC_03": dict(temp_mult=1.10, vib_mult=1.30, cur_mult=1.05, rpm_mult=0.97,
                   noise_mult=1.3, cycle_s=42, base_reject=0.020),  # older
    "CNC_04": dict(temp_mult=1.05, vib_mult=1.00, cur_mult=1.20, rpm_mult=0.85,
                   noise_mult=1.0, cycle_s=55, base_reject=0.012),  # heavy duty
    "CNC_05": dict(temp_mult=1.03, vib_mult=1.10, cur_mult=1.00, rpm_mult=1.15,
                   noise_mult=1.5, cycle_s=30, base_reject=0.018),  # fast, noisy
}
CYCLE_TIME_NOISE_FRAC = 0.03       # part-to-part cycle jitter = 3 %

ANOMALIES = [
    dict(machine="CNC_03", type="bearing_wear", start_s=3600, end_s=6300),
    dict(machine="CNC_05", type="sudden_fault", start_s=5000, end_s=6800),
]
WEAR_EFFECTS = dict(
    temp_add=15.0,        # deg C at severity 1
    vib_add=4.0,          # mm/s
    current_add=6.0,      
    rpm_noise_extra=3.0,  # rpm noise becomes (1 + 3 x severity) times larger
    cycle_increase=0.35,  # cycle time +35 %
    reject_add=0.30,      # reject probability +30 percentage points at severity 1
)

OUTPUT_FILENAME = "cnc_cell_data.csv"
