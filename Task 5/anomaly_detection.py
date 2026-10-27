from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

CSV_DIR = Path(__file__).resolve().parent.parent / "csv_files"
DATA_PATH = CSV_DIR / "processed_data.csv"
OUTPUT_PATH = CSV_DIR / "data_with_flags.csv"

TIMESTAMP_COL, MACHINE_COL, STATUS_COL = "Timestamp", "Machine_ID", "Machine_Status"
RUNNING_LABEL = "Running"
TRUTH_COL = "Abnormal_Flag"               
SAMPLING_HZ = 10                          
HEALTHY_END = "2026-01-05 07:00:00"       

STARTUP_GRACE_S = 60      
SMOOTH_S = 5              
RPM_STD_WINDOW_S = 30      
PERSISTENCE_S = 25   
LABEL_RAMP_IGNORE_S = 600  

SENSORS = ["Temperature", "Vibration", "Motor_Current", "Spindle_RPM", "Pressure"]
FEATURES = SENSORS + ["RPM_Std"]
UPPER_ONLY = {"Temperature", "Vibration", "Motor_Current", "RPM_Std"}  
LIMIT_QUANTILE = 0.999    
LIMIT_MARGIN = 0.35       
IFOREST_COLUMNS = ["Temperature", "Vibration", "Motor_Current", "RPM_Std"]
IFOREST_TREES = 200        
IFOREST_SEED = 0
IFOREST_SCORE_SMOOTH_S = 10       
IFOREST_FALSE_ALARM_RATE = 0.0075 
Z_CUTOFF = 2.4

def prepare_features(df):
    """Use the features already calculated by Task 3."""

    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df["Active"] = df["Active"].astype(bool)

    df = df.sort_values(["Machine_ID", "Timestamp"]).reset_index(drop=True)

    feature_columns = [f"{c}_MA" for c in SENSORS] + ["RPM_Std"]

    F = df[feature_columns].copy()
    F.columns = FEATURES

    return df, F

def healthy_mask(df):
    return df["Active"] & (df[TIMESTAMP_COL] < HEALTHY_END)


class BaseDetector:
    name = "base"

    def __init__(self, columns, min_conditions=1, name=None):
        self.columns, self.min_conditions = list(columns), min_conditions
        if name:
            self.name = name

    def _bc(self, df, table):
        return pd.DataFrame(table.reindex(df[MACHINE_COL]).to_numpy(), index=df.index, columns=table.columns)

    def fit(self, F, df):
        m = healthy_mask(df)
        h, d = F.loc[m, self.columns], df.loc[m]
        g = h.groupby(d[MACHINE_COL])
        self.center_ = g.median()
        mad = (h - self._bc(d, self.center_)).abs().groupby(d[MACHINE_COL]).median()
        self.scale_ = (mad * 1.4826).clip(lower=1e-9)            # robust sigma
        hi, lo = g.quantile(LIMIT_QUANTILE), g.quantile(1 - LIMIT_QUANTILE)
        self.hi_ = hi + LIMIT_MARGIN * (hi - self.center_)
        self.lo_ = lo - LIMIT_MARGIN * (self.center_ - lo)
        return self

    def _hits(self, F, df):
        raise NotImplementedError

    def per_variable(self, F, df):
        hits = self._hits(F, df).fillna(False).astype(bool)
        hits.loc[~df["Active"]] = False          # only judge Running rows after the grace period
        return hits

    def detect(self, F, df):
        return self.per_variable(F, df).sum(axis=1) >= self.min_conditions


class ThresholdDetector(BaseDetector):
    def _hits(self, F, df):
        x, hi, lo = F[self.columns], self._bc(df, self.hi_), self._bc(df, self.lo_)
        out = x > hi
        for c in self.columns:
            if c not in UPPER_ONLY:                      # RPM level / pressure: too low is also bad
                out[c] = out[c] | (x[c] < lo[c])
        return out


class ZScoreDetector(BaseDetector):
    name = "zscore"

    def __init__(self, columns, z=Z_CUTOFF, **kw):
        super().__init__(columns, **kw)
        self.z = z

    def _hits(self, F, df):
        z = (F[self.columns] - self._bc(df, self.center_)) / self._bc(df, self.scale_)
        out = z > self.z
        for c in self.columns:
            if c not in UPPER_ONLY:
                out[c] = z[c].abs() > self.z
        return out


class IsolationForestDetector(BaseDetector):
    name = "iforest"

    def __init__(self, columns, false_alarm_rate=IFOREST_FALSE_ALARM_RATE, n_estimators=IFOREST_TREES,
                 seed=IFOREST_SEED, smooth_s=IFOREST_SCORE_SMOOTH_S, **kw):
        super().__init__(columns, **kw)
        self.false_alarm_rate, self.n_estimators, self.seed, self.smooth_s = false_alarm_rate, n_estimators, seed, smooth_s

    def _features(self, F, df):
        return (F[self.columns] - self._bc(df, self.center_)) / self._bc(df, self.scale_)

    def _anomaly_score(self, X, df):
        a = pd.Series(-self.model_.score_samples(X), index=X.index)
        w = int(self.smooth_s * SAMPLING_HZ)
        if w <= 1:
            return a
        keys = [df.loc[X.index, MACHINE_COL], df.loc[X.index, "Seg"]]
        return a.groupby(keys).transform(lambda x: x.rolling(w, min_periods=max(w // 2, 1)).mean())

    def fit(self, F, df):
        super().fit(F, df)                                   # per-machine median / robust sigma
        m = healthy_mask(df)
        X = self._features(F.loc[m], df.loc[m]).dropna()
        self.model_ = IsolationForest(n_estimators=self.n_estimators, random_state=self.seed, n_jobs=-1).fit(X)
        self.threshold_ = np.nanquantile(self._anomaly_score(X, df), 1 - self.false_alarm_rate)
        return self

    def _hits(self, F, df):
        out = pd.Series(False, index=df.index)
        act = df["Active"]
        X = self._features(F[act], df[act]).dropna()
        out.loc[X.index] = self._anomaly_score(X, df) > self.threshold_
        return out.to_frame("IForest")


def require_persistence(flags, df, seconds=PERSISTENCE_S):
    n = max(int(seconds * SAMPLING_HZ), 1)
    if n <= 1:
        return flags
    def f(s):
        ends = s.astype(int).rolling(n, min_periods=n).sum() == n
        return ends
    return flags.groupby([df[MACHINE_COL], df['Seg']]).transform(f).astype(bool)



def evaluate(pred, truth):
    pred, truth = pred.astype(bool), truth.astype(bool)
    tp, fp = int((pred & truth).sum()), int((pred & ~truth).sum())
    fn, tn = int((~pred & truth).sum()), int((~pred & ~truth).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return dict(TP=tp, FP=fp, FN=fn, TN=tn,
                accuracy=round((tp + tn) / len(truth), 5) if len(truth) else 0.0,
                f1=round(2 * prec * rec / (prec + rec), 5) if prec + rec else 0.0,
                precision=round(prec, 3), recall=round(rec, 3),
                false_alarm_rate=round(fp / (fp + tn), 5) if fp + tn else 0.0)


def score(flags, df, ignore_ramp_s=0):
    run = df[STATUS_COL] == RUNNING_LABEL
    truth = df[TRUTH_COL].astype(bool)
    keep = run.copy()
    if ignore_ramp_s:
        t0 = df.loc[truth & run].groupby(MACHINE_COL)[TIMESTAMP_COL].min()
        start = df[MACHINE_COL].map(t0)
        keep &= ~(truth & (df[TIMESTAMP_COL] < start + pd.Timedelta(seconds=ignore_ramp_s)))
    return evaluate(flags[keep], truth[keep])


def alarm_delay_s(flags, df):
    out = {}
    truth, run = df[TRUTH_COL].astype(bool), df[STATUS_COL] == RUNNING_LABEL
    for mid, g in df.groupby(MACHINE_COL):
        tr = g[TIMESTAMP_COL][truth.loc[g.index] & run.loc[g.index]]
        if tr.empty:
            continue
        hit = g[TIMESTAMP_COL][flags.loc[g.index] & (g[TIMESTAMP_COL] >= tr.iloc[0])]
        out[mid] = round((hit.iloc[0] - tr.iloc[0]).total_seconds(), 1) if len(hit) else None
    return out


def sweep(make_detector, values, F, df):
    rows = []
    for v in values:
        flags = require_persistence(make_detector(v).fit(F, df).detect(F, df), df)
        rows.append({"param": v, **score(flags, df)})
    return pd.DataFrame(rows)


def main():
    df = pd.read_csv(DATA_PATH)
    df, F = prepare_features(df)
    detectors = [
        ThresholdDetector(FEATURES, min_conditions=1, name="fixed_any"),
        ZScoreDetector(FEATURES, name="zscore"),
        IsolationForestDetector(IFOREST_COLUMNS),
    ]
    results, delays = {}, {}
    for d in detectors:
        d.fit(F, df)
        flags = require_persistence(d.detect(F, df), df)
        df[f"Flag_{d.name}"] = flags
        if d.name == 'zscore':
            df['Flag_final'] = flags
        if TRUTH_COL and TRUTH_COL in df.columns:
            results[d.name] = score(flags, df)
            results[d.name + " (excl. first ramp)"] = score(flags, df, LABEL_RAMP_IGNORE_S)
            delays[d.name] = alarm_delay_s(flags, df)

    if results:
        columns = [
            "TP", "FP", "FN",
            "precision", "recall", "false_alarm_rate"
        ]
        print(pd.DataFrame(results).T[columns])
        print("alarm delay (s) after fault start:", delays)

    print(
        "\nWhich variable triggers the z-score alarms:\n",
        detectors[1].per_variable(F, df).sum()
    )  
    df.to_csv(OUTPUT_PATH, index=False)  
    return df, F


if __name__ == "__main__":
    main()
