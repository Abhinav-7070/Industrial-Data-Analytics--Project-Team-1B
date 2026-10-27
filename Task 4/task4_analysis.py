"""ME217 Assignment 1, Task 4: per-CNC industrial data analysis.

Run: python task4_analysis.py path/to/manufacturing_data.csv
Optional: --interval-minutes 1 --count-mode cumulative --abnormal-column Abnormal_Event
Uses Python standard library only. Dataset and measurement conventions must be checked.
"""
import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

REQUIRED = ['Timestamp','Machine_ID','Machine_Status','Temperature','Vibration','Motor_Current','Cycle_Time','Production_Count','Rejected_Parts']
RUN = {'running','run','operating'}
DOWN = {'stopped','stop','fault','maintenance','down','breakdown'}
BAD = {'fault','abnormal','alarm','failure'}


def number(row, column):
    val = (row.get(column) or '').strip()
    if not val:
        return None
    try:
        v = float(val)
    except ValueError:
        raise ValueError(f"Invalid numeric {column}: {val!r}")
    if not math.isfinite(v):
        raise ValueError(f"Non-finite numeric {column}: {val!r}")
    return v


def timestamp(s):
    s = s.strip().replace('Z','+00:00')
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(f'Invalid ISO timestamp: {s!r}')


def average(vals):
    good = [v for v in vals if v is not None]
    return mean(good) if good else None


def total_counts(records, field, mode):
    vals = [number(row,field) for row in records]
    if mode == 'interval':
        return sum(v for v in vals if v is not None)
    # Cumulative counters can reset, e.g. at new shift. Preserve positive increments.
    total = 0.0
    previous = None
    for v in vals:
        if v is None:
            continue
        if previous is None:
            total += v  # assumes counter started at zero at start of monitored dataset
        elif v >= previous:
            total += v-previous
        else:
            total += v  # counter reset to zero before this observation
        previous = v
    return total


def event_true(row, col):
    if col:
        raw = (row.get(col) or '').strip().lower()
        return raw in {'1','true','yes','y','alarm','abnormal','fault'}
    return (row.get('Machine_Status') or '').strip().lower() in BAD


def fmt(v):
    return '' if v is None else round(v,4)


def analyze(path, interval_minutes, count_mode, abnormal_column):
    with open(path,newline='',encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        missing = [c for c in REQUIRED if c not in columns]
        if missing:
            raise ValueError('Missing required columns: '+', '.join(missing))
        if abnormal_column and abnormal_column not in columns:
            raise ValueError(f'Abnormal indicator column {abnormal_column!r} not found')
        groups = defaultdict(list)
        for row in reader:
            if not (row.get('Machine_ID') or '').strip():
                raise ValueError('Machine_ID cannot be empty')
            groups[row['Machine_ID'].strip()].append(row)
    if not groups:
        raise ValueError('Dataset is empty')
    output=[]
    for machine, rows in sorted(groups.items()):
        rows.sort(key=lambda x: timestamp(x['Timestamp']))
        n = len(rows)
        statuses = [(r['Machine_Status'] or '').strip().lower() for r in rows]
        running = sum(s in RUN for s in statuses)
        downtime = sum(s in DOWN for s in statuses)
        temps = [number(r,'Temperature') for r in rows]
        vibrations = [number(r,'Vibration') for r in rows]
        currents = [number(r,'Motor_Current') for r in rows]
        # Cycle_Time repeats the last completed part's cycle until the next part.
        # Only count readings where the cumulative production counter increases.
        cycles = []
        previous_production = 0.0
        for r in rows:
            current_production = number(r, 'Production_Count')
            if current_production is None:
                continue
            delta = current_production - previous_production
            if delta < 0:  # cumulative counter reset; current value is new production
                delta = current_production
            if delta > 0 and (r['Machine_Status'] or '').strip().lower() in RUN:
                cycle = number(r, 'Cycle_Time')
                if cycle is not None and cycle > 0:
                    cycles.extend([cycle] * int(round(delta)))
            previous_production = current_production
        production=total_counts(rows,'Production_Count',count_mode)
        rejected=total_counts(rows,'Rejected_Parts',count_mode)
        flagged=[event_true(r,abnormal_column) for r in rows]
        events=sum(flag and (i==0 or not flagged[i-1]) for i,flag in enumerate(flagged))
        cycle_cv=(stdev(cycles)/mean(cycles)*100) if len(cycles)>1 and mean(cycles)>0 else None
        running_hours=running*interval_minutes/60
        output.append({
            'Machine_ID':machine,
            'Observations':n,
            'Average_Temperature':fmt(average(temps)),
            'Average_Vibration':fmt(average(vibrations)),
            'Maximum_Motor_Current':fmt(max((v for v in currents if v is not None),default=None)),
            'Average_Cycle_Time_Running':fmt(average(cycles)),
            'Machine_Utilization_Percent':fmt(100*running/n),
            'Total_Production_Parts':fmt(production),
            'Production_Rate_Parts_Per_Running_Hour':fmt(production/running_hours if running_hours else None),
            'Total_Rejected_Parts':fmt(rejected),
            'Rejection_Rate_Percent':fmt(100*rejected/production if production>0 else None),
            'Total_Downtime_Minutes':fmt(downtime*interval_minutes),
            'Number_Of_Abnormal_Events':events,
            'Cycle_Time_CV_Percent':fmt(cycle_cv),
        })
    return output


def main():
    p=argparse.ArgumentParser(description='Analyse CNC manufacturing data for Task 4')
    p.add_argument('csv_file',type=Path)
    p.add_argument('--interval-minutes',type=float,default=1.0,help='Time represented by each observation; default 1 min')
    p.add_argument('--count-mode',choices=['interval','cumulative'],default='interval')
    p.add_argument('--abnormal-column',default=None,help='Task 5 detection flag column, e.g. Abnormal_Event')
    p.add_argument('--output',type=Path,default=Path('task4_machine_metrics.csv'))
    args=p.parse_args()
    if args.interval_minutes <= 0:
        p.error('--interval-minutes must be positive')
    metrics=analyze(args.csv_file,args.interval_minutes,args.count_mode,args.abnormal_column)
    with open(args.output,'w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(metrics[0]))
        writer.writeheader();writer.writerows(metrics)
    valid=[r for r in metrics if r['Cycle_Time_CV_Percent']!='']
    highest=max(valid,key=lambda r:float(r['Cycle_Time_CV_Percent'])) if valid else None
    print(f'Created {args.output} with {len(metrics)} machine(s).')
    if highest:
        print('Highest cycle-time variability:',highest['Machine_ID'],f"(CV {highest['Cycle_Time_CV_Percent']}%)")
    else:
        print('Insufficient positive running cycle-time values to rank variability.')

if __name__=='__main__':
    main()
