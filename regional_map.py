# regional_map.py

import os
import requests
import pandas as pd
import folium
import streamlit as st
import plotly.subplots as sp
import plotly.graph_objs as go
from streamlit_folium import st_folium

API_KEY = os.getenv("IOC_API_KEY", "354a1bc9fc147727d6eaf353d03b8aab9ec085ef87b823299ea65ab117a201ffc6c79ca7a8b87a76ba7452408fe20a2d48d4fb4481a9eb47c30f5cf5eb35472b")

# --- Fetch IOC Stations ---
def get_stations():
    url = "https://api.ioc-sealevelmonitoring.org/v2/stations"
    params = {"showall": "all", "order": "code", "dir": "asc", "limit": 2000}
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    return pd.DataFrame(response.json())

stations_df = get_stations()

# --- Regional Filters ---
def filter_region(df, lon_min, lon_max, lat_min, lat_max):
    return df[
        (df["country"] == "IDN") &
        (df["Lon"].between(lon_min, lon_max)) &
        (df["Lat"].between(lat_min, lat_max))
    ]

sumatra_df = filter_region(stations_df, 90, 104, -5, 6)
java_df    = filter_region(stations_df, 104, 118, -12, -5)
sulawesi_df= filter_region(stations_df, 118, 128, -5, 5)
papua_df   = filter_region(stations_df, 128, 145, -8, 2)

# --- Build Folium Map ---
def build_map(df):
    tiles = "https://services.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}"
    m = folium.Map(location=[-12, 115], tiles=tiles, attr="ESRI", zoom_start=4.5)
    for _, row in df.iterrows():
        if pd.notnull(row["Lat"]) and pd.notnull(row["Lon"]):
            popup_text = f""" 
            <b>Code:</b> {row['Code']}<br> 
            <b>Location:</b> {row['Location']}<br> 
            <b>Country:</b> {row['country']}<br> 
            <b>Status:</b> {row['status']} """
            marker_color = "red" if row["status"] == 5 else "green" if row["status"] == 1 else "blue"
            folium.Marker(
                location=[row["Lat"], row["Lon"]],
                popup=popup_text,
                tooltip=row["Code"],
                icon=folium.Icon(color=marker_color, icon="info-sign")
            ).add_to(m)
    return m

# --- Fetch Tide Gauge Data ---
def fetch_data(station_id, sensor="one-sensor",
               start_date="2026-02-20", end_date="2026-02-23"):
    station_id = station_id.lower()
    url = f"https://api.ioc-sealevelmonitoring.org/v2/research/stations/{station_id}/sensors/{sensor}/data"
    params = {"days_per_page": 7, "page": 1,
              "timestart": start_date, "timestop": end_date, "flag_qc": "true"}
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    r = requests.get(url, params=params, headers=headers)

    if r.status_code == 200:
        js = r.json()
        if "data" in js and len(js["data"]) > 0:
            df = pd.DataFrame(js["data"])
            if "stime" in df.columns:
                df["stime"] = pd.to_datetime(df["stime"])
            return df
    return pd.DataFrame(columns=["stime", "slevel"])

# --- Helper to build subplot figure ---
def build_subplot(stations_df, title, cols, rows):
    stations = stations_df["Code"].tolist()
    fig = sp.make_subplots(rows=rows, cols=cols,
                           subplot_titles=[code.upper() for code in stations])
    for i, code in enumerate(stations):
        df = fetch_data(code)
        row = i // cols + 1
        col = i % cols + 1
        if not df.empty and "stime" in df.columns:
            fig.add_trace(
                go.Scatter(x=df["stime"], y=df["slevel"],
                           mode="lines", name=code.upper()),
                row=row, col=col
            )
    fig.update_layout(title_text=title, height=300*rows)
    return fig

# --- Streamlit Tab Content ---
def show():
    st.subheader("IOC Indonesia Tide Gauge Dashboard")

    # Folium map
    st.markdown("### Tide Gauge Map")
    m = build_map(stations_df)
    st_folium(m, width=None, height=500)

    # Regional plots
    st.markdown("### Sumatra Tide Gauges")
    if not sumatra_df.empty:
        st.plotly_chart(build_subplot(sumatra_df, "Sumatra Sea Level", cols=3, rows=7))
    else:
        st.info("No Sumatra stations available.")

    st.markdown("### Java Tide Gauges")
    if not java_df.empty:
        st.plotly_chart(build_subplot(java_df, "Java Sea Level", cols=3, rows=9))
    else:
        st.info("No Java stations available.")

    st.markdown("### Sulawesi Tide Gauges")
    if not sulawesi_df.empty:
        st.plotly_chart(build_subplot(sulawesi_df, "Sulawesi Sea Level", cols=3, rows=2))
    else:
        st.info("No Sulawesi stations available.")

    st.markdown("### Papua Tide Gauges")
    if not papua_df.empty:
        st.plotly_chart(build_subplot(papua_df, "Papua Sea Level", cols=3, rows=2))
    else:
        st.info("No Papua stations available.")

