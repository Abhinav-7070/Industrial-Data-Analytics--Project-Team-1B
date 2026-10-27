from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from sklearn.metrics import confusion_matrix

# --- 1. LOAD TASK 5 DATA ---
CSV_DIR = Path(__file__).resolve().parent.parent / "csv_files"
df = pd.read_csv(CSV_DIR / "data_with_flags.csv")

# Convert Timestamp column to actual date-time format for the charts
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# Task 4 mentioned Task 1 provided an 'Abnormal_Flag' column. 
# We rename it to 'Is_Abnormal' so the rest of your dashboard code doesn't break.
if "Abnormal_Flag" in df.columns:
    df.rename(columns={"Abnormal_Flag": "Is_Abnormal"}, inplace=True)

# --- 2. DASHBOARD LAYOUT & CONFIG ---
st.set_page_config(page_title="IIoT Smart Manufacturing Cell", layout="wide")
st.title("⚙️ Smart Manufacturing Cell Dashboard")
st.markdown("Monitoring machine condition, production performance, and abnormal conditions.")

# Sidebar Filters
st.sidebar.header("Dashboard Controls")
selected_machine = st.sidebar.selectbox("Select Machine for Detailed View", df["Machine_ID"].unique())

# Filter data based on selection
machine_data = df[df["Machine_ID"] == selected_machine]

# --- 3. TOP LEVEL KPIs (Alarm Summary & Production Counts) ---
# --- 4. TOP LEVEL KPIs ---
st.subheader("Live Cell Metrics")
col1, col2 = st.columns(2) # Changed to 2 columns 

# Calculate only the production and rejections
total_production = int(df.groupby("Machine_ID")["Production_Count"].max().sum())
total_rejections = int(df.groupby("Machine_ID")["Rejected_Parts"].max().sum())

# Display only the two remaining metrics
col1.metric("Total Production Count", f"{total_production:,}")
col2.metric("Total Rejected Parts", f"{total_rejections:,}")

st.divider()

# --- 4. TREND VISUALISATIONS ---
st.subheader(f"Sensor Trends: {selected_machine}")
col_trend1, col_trend2 = st.columns(2)

with col_trend1:
    fig_temp = px.line(machine_data, x="Timestamp", y="Temperature", 
                       title="Temperature Trend (°C)", color_discrete_sequence=["#FF5733"])
    fig_temp.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="Threshold")
    st.plotly_chart(fig_temp, use_container_width=True)

with col_trend2:
    fig_vib = px.line(machine_data, x="Timestamp", y="Vibration", 
                      title="Vibration Trend (mm/s)", color_discrete_sequence=["#33C1FF"])
    fig_vib.add_hline(y=7, line_dash="dash", line_color="red", annotation_text="Threshold")
    st.plotly_chart(fig_vib, use_container_width=True)
#this is the part where we display machine status 
st.markdown("### Machine Status History")
# A stepped line chart perfectly visualizes state changes over time
fig_status = px.line(
    machine_data, 
    x="Timestamp", 
    y="Machine_Status", 
    title=f"Full Status Timeline: {selected_machine}",
    line_shape="hv", # 'hv' makes the line step horizontally then vertically (perfect for digital states)
    color_discrete_sequence=["#FFC300"]
)
st.plotly_chart(fig_status, use_container_width=True)

st.divider()

#displaying machine status of every machine
# st.subheader("Live Machine Status")

# # Get the very last recorded status for every single machine
# latest_statuses = df.groupby("Machine_ID")["Machine_Status"].last()

# # Create dynamic columns based on the number of machines (5)
# status_cols = st.columns(len(latest_statuses))

# # Loop through and create a metric box for each one
# for col, (machine, status) in zip(status_cols, latest_statuses.items()):
#     col.metric(label=machine, value=status)
# --- 5. MACHINE COMPARISONS ---

st.subheader("Machine Comparisons (Cell Overview)")

# Load the Task 4 CSV directly
task4_df = pd.read_csv(CSV_DIR / "task4_machine_metrics.csv")

col_comp1, col_comp2 = st.columns(2)

with col_comp1:
    # Update "Utilization" below to match the exact column name in their CSV
    fig_util = px.bar(task4_df, x="Machine_ID", y="Machine_Utilization_Percent", 
                      title="Machine Utilization Comparison", color="Machine_ID")
    st.plotly_chart(fig_util, use_container_width=True)

with col_comp2:
    # Update "Rejection_Rate" below to match the exact column name in their CSV
    fig_rej = px.bar(task4_df, x="Machine_ID", y="Rejection_Rate_Percent", 
                     title="Rejection Rate Comparison", color="Machine_ID")
    st.plotly_chart(fig_rej, use_container_width=True)

# --- 6. ALARM SUMMARY & ABNORMAL PERIODS ---
# --- 7. ALARM SUMMARY & ABNORMAL PERIODS ---
st.subheader("🚨 Detected Abnormal Periods")

# Filter for Z-score anomalies
abnormal_raw = df[df["Flag_zscore"] == True].copy()

if not abnormal_raw.empty:
    # Group the alarms by the minute
    abnormal_raw["Minute"] = abnormal_raw["Timestamp"].dt.floor("min")
    
    abnormal_summary = abnormal_raw.groupby(["Minute", "Machine_ID"]).agg({
        "Temperature": "max",
        "Vibration": "max",
        "Machine_Status": "last"
    }).reset_index()

    # 1. SIMPLER VISUAL: A clean Bar Chart (No complex bubble sizes)
    # 1. THE SWIMLANE VISUAL: Shows exactly when alarms triggered for each machine
    fig_alarms = px.scatter(
        abnormal_summary, 
        x="Minute", 
        y="Machine_ID", 
        color="Machine_ID",
        title="Alarm Timeline: When Did Machines Enter Abnormal States?",
        labels={"Minute": "Timestamp (Grouped by Minute)", "Machine_ID": "Machine"},
        color_discrete_sequence=["#FF0000", "#FF8C00"] # Red and Orange alert colors
    )
    
    # Make the markers large "X" symbols so they look like actual system errors
    fig_alarms.update_traces(marker=dict(size=14, symbol="x"))
    
    st.plotly_chart(fig_alarms, use_container_width=True)

    # 2. CLEAN TABLE: Hide the long list inside a dropdown expander
    with st.expander("📄 View Full Minute-by-Minute Anomaly Log"):
        st.dataframe(
            abnormal_summary.sort_values(by="Minute", ascending=False), 
            use_container_width=True,
            hide_index=True
        )
else:
    st.success("No abnormal conditions detected currently.")
st.divider()
