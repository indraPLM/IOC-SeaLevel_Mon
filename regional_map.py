# regional_map.py

import requests
import pandas as pd
import folium
import streamlit as st
import plotly.subplots as sp
import plotly.graph_objs as go
from streamlit_folium import st_folium

# --- Fetch IOC Stations ---
def get_stations(api_key):
    url = "https://api.ioc-sealevelmonitoring.org/v2/stations"
    params = {"showall": "all", "order": "code", "dir": "asc", "limit": 2000}
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    return pd.DataFrame(response.json())

# --- Regional Filters ---
def filter_region(df, lon_min, lon_max, lat_min, lat_max):
    return df[
        (df["country"] == "IDN") &
        (df["Lon"].between(lon_min, lon_max)) &
        (df["Lat"].between(lat_min, lat_max))
    ]

# --- Build Folium Map ---
def build_map(df):
    tiles = "https://services.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}"
    m = folium.Map(location=[0, 118], tiles=tiles, attr="ESRI", zoom_start=5)

    for _, row in df.iterrows():
        if pd.notnull(row["Lat"]) and pd.notnull(row["Lon"]):
            popup_text = (
                f"<b>Code:</b> {row['Code']}<br>"
                f"<b>Location:</b> {row['Location']}<br>"
                f"<b>Country:</b> {row['country']}<br>"
                f"<b>Status:</b> {row['status']}"
            )

            # Choose marker color based on status
            if row["status"] == 5:
                marker_color = "red"
            elif row["status"] == 1:
                marker_color = "green"
            else:
                marker_color = "blue"

            folium.Marker(
                location=[row["Lat"], row["Lon"]],
                popup=popup_text,
                tooltip=row["Code"],
                icon=folium.Icon(color=marker_color, icon="info-sign")
            ).add_to(m)
    return m


# --- Fetch Tide Gauge Data ---
def fetch_data(api_key, station_id, sensor="one-sensor"):
    # Compute dynamic date range: end = now, start = 1 day before
    end_date = datetime.now()
    start_date = end_date - timedelta(days=2)

    # Format as YYYY-MM-DD for IOC API
    end_str = end_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")
                   
    station_id = station_id.lower()
    url = f"https://api.ioc-sealevelmonitoring.org/v2/research/stations/{station_id}/sensors/{sensor}/data"
    params = {"days_per_page": 7, "page": 1,
              "timestart": start_date, "timestop": end_date, "flag_qc": "true"}
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
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
def build_subplot(api_key, stations_df, title, cols, rows):
    stations = stations_df["Code"].tolist()
    fig = sp.make_subplots(rows=rows, cols=cols,
                           subplot_titles=[code.upper() for code in stations])
    for i, code in enumerate(stations):
        df = fetch_data(api_key, code)
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
def show(api_key):
    stations_df = get_stations(api_key)

    # Regional subsets
    sumatra_df = filter_region(stations_df, 90, 104, -5, 6)
    java_df    = filter_region(stations_df, 104, 118, -12, -5)
    sulawesi_df= filter_region(stations_df, 118, 128, -5, 5)
    papua_df   = filter_region(stations_df, 128, 145, -8, 2)

    # Folium map
    m = build_map(stations_df)
    st_folium(m, width="100%", height=600)

    # Regional plots
    if not sumatra_df.empty:
        st.plotly_chart(build_subplot(api_key, sumatra_df, "Sumatra Sea Level", cols=3, rows=7))
    if not java_df.empty:
        st.plotly_chart(build_subplot(api_key, java_df, "Java Sea Level", cols=3, rows=9))
    if not sulawesi_df.empty:
        st.plotly_chart(build_subplot(api_key, sulawesi_df, "Sulawesi Sea Level", cols=3, rows=2))
    if not papua_df.empty:
        st.plotly_chart(build_subplot(api_key, papua_df, "Papua Sea Level", cols=3, rows=2))




