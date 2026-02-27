import requests
import pandas as pd
import plotly.subplots as sp
import plotly.graph_objs as go
import folium
from streamlit_folium import st_folium
import streamlit as st
from obspy.geodetics import locations2degrees, degrees2kilometers
from datetime import datetime, timedelta

API_KEY = "YOUR_API_KEY"

# --- IOC Stations ---
def get_stations(api_key):
    url = "https://api.ioc-sealevelmonitoring.org/v2/stations"
    params = {"showall": "all", "order": "code", "dir": "asc", "limit": 2000}
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    return pd.DataFrame(response.json())

stations_df = get_stations()

# --- Distance helper ---
def geo_distance(lat0, lon0, lat1, lon1):
    return round(degrees2kilometers(locations2degrees(lat0, lon0, lat1, lon1)), 2)

# --- Find Closest Stations given tsunami lat/lon ---
def get_closest_stations(tsu_lat, tsu_lon, n=5):
    stations_df["distance_km"] = stations_df.apply(
        lambda row: geo_distance(tsu_lat, tsu_lon, row["Lat"], row["Lon"]) 
        if pd.notnull(row["Lat"]) else None, axis=1
    )
    return stations_df.nsmallest(n, "distance_km")

# --- Fetch IOC Tide Gauge Data ---
def fetch_data(api_key, station_id, sensor="one-sensor", days_back=1):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    end_str = end_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")

    station_id = station_id.lower()
    url = f"https://api.ioc-sealevelmonitoring.org/v2/research/stations/{station_id}/sensors/{sensor}/data"
    params = {"days_per_page": 7, "page": 1,
              "timestart": start_str, "timestop": end_str, "flag_qc": "true"}
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

# --- Build graph from IOC sea level data ---
def build_closest_graphs(api_key, df):
    fig = sp.make_subplots(rows=len(df), cols=1, subplot_titles=[code for code in df["Code"]])
    for i, row in enumerate(df.itertuples(), start=1):
        tide_df = fetch_data(api_key, row.Code)
        if not tide_df.empty:
            fig.add_trace(go.Scatter(x=tide_df["stime"], y=tide_df["slevel"],
                                     mode="lines", name=row.Code), row=i, col=1)
        else:
            fig.add_trace(go.Scatter(x=[0], y=[0], mode="lines", name=f"{row.Code} (no data)"), row=i, col=1)
    fig.update_layout(height=300*len(df), title="Sea Level at Closest Stations")
    return fig

# --- Streamlit Integration ---
def show_closest_stations():
    st.subheader("Click Tsunami Location on Map 🌊")

    # Base map to click
    m = folium.Map(location=[0, 120], zoom_start=3)
    st.markdown("Click anywhere on the map to select a tsunami location.")
    map_data = st_folium(m, width="100%", height=500)

    if map_data and map_data["last_clicked"]:
        tsu_lat = map_data["last_clicked"]["lat"]
        tsu_lon = map_data["last_clicked"]["lng"]

        st.success(f"Selected location: Lat {tsu_lat:.2f}, Lon {tsu_lon:.2f}")

        closest = get_closest_stations(tsu_lat, tsu_lon)
        st.dataframe(closest[["Code", "Location", "country", "distance_km"]])

        # Plot tide gauge data
        st.plotly_chart(build_closest_graphs(api_key, closest), use_container_width=True)

        # Map visualization with tsunami + closest stations
        m2 = folium.Map(location=[tsu_lat, tsu_lon], zoom_start=5)
        folium.Marker([tsu_lat, tsu_lon], popup="Tsunami Location", icon=folium.Icon(color="red")).add_to(m2)
        for _, row in closest.iterrows():
            folium.Marker([row["Lat"], row["Lon"]],
                          popup=f"{row['Code']} ({row['distance_km']} km)",
                          icon=folium.Icon(color="blue")).add_to(m2)
        st_folium(m2, width="100%", height=500)
