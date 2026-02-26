# earthquake_events.py  (tab2)

import os
import requests
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from obspy.geodetics import locations2degrees, degrees2kilometers
import folium
import plotly.subplots as sp
import plotly.graph_objs as go
import streamlit as st
from streamlit_folium import st_folium

API_KEY = os.getenv("IOC_API_KEY", "354a1bc9fc147727d6eaf353d03b8aab9ec085ef87b823299ea65ab117a201ffc6c79ca7a8b87a76ba7452408fe20a2d48d4fb4481a9eb47c30f5cf5eb35472b")

# --- Utility Functions ---
def fetch_text_data(url, delimiter='|'):
    response = requests.get(url)
    lines = response.text.strip().split('\n')
    return [line.split(delimiter) for line in lines if delimiter in line]

def extract_xml_tag(soup, tag):
    return [float(x.text) if tag == 'mag' else x.text for x in soup.find_all(tag)]

def to_float(lst): return [float(x) for x in lst]

def match_event(df, t_ref, time_column='date_time', tol_sec=60):
    matched = df[df[time_column].apply(lambda t: abs((t_ref - t).total_seconds()) < tol_sec)]
    return matched.iloc[0] if not matched.empty else None

def geo_distance(x0, y0, x1, y1):
    return round(degrees2kilometers(locations2degrees(x0, y0, x1, y1)), 2)

# --- GFZ Data ---
today = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
gfz_raw = fetch_text_data(f'https://geofon.gfz.de/fdsnws/event/1/query?end={today}&limit=40&format=text')
gfz_df = pd.DataFrame(gfz_raw[1:], columns=gfz_raw[0])
gfz_df['mag'] = to_float(gfz_df['Magnitude'])
gfz_df['lat'] = to_float(gfz_df['Latitude'])
gfz_df['lon'] = to_float(gfz_df['Longitude'])
gfz_df['depth'] = to_float(gfz_df['Depth/km'])
gfz_df['date_time'] = pd.to_datetime(gfz_df['Time'])

# --- USGS Data ---
usgs = gpd.read_file("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson")
usgs['time_usgs'] = pd.to_datetime(usgs['time'], unit='ms')
usgs['lon'] = usgs.geometry.x
usgs['lat'] = usgs.geometry.y
usgs['depth'] = usgs.geometry.z
usgs['mag'] = usgs['mag']

# --- BMKG Data ---
soup = BeautifulSoup(requests.get("https://bmkg-content-inatews.storage.googleapis.com/live30event.xml").text, 'xml')
bmkg_df = pd.DataFrame({
    'eventid': extract_xml_tag(soup, 'eventid'),
    'waktu': extract_xml_tag(soup, 'waktu'),
    'lat': extract_xml_tag(soup, 'lintang'),
    'lon': extract_xml_tag(soup, 'bujur'),
    'mag': to_float(extract_xml_tag(soup, 'mag')),
    'depth': extract_xml_tag(soup, 'dalam'),
    'area': [x.split('\n')[9] for x in extract_xml_tag(soup, 'gempa')]
})
bmkg_df['waktu'] = pd.to_datetime(bmkg_df['waktu'])
bmkg_df = bmkg_df[bmkg_df['mag'] >= 5]
bmkg_df.columns = ['eventid', 'waktu', 'lat', 'lon', 'mag', 'depth', 'area']

# --- Reference Event ---
x0, y0, m0, d0 = map(float, bmkg_df.loc[bmkg_df.index[0], ['lon', 'lat', 'mag', 'depth']])
t_ref = bmkg_df['waktu'].iloc[0]
gfz_match = match_event(gfz_df, t_ref)
usgs_match = match_event(usgs, t_ref, time_column='time_usgs')

# --- IOC Stations ---
def get_stations():
    url = "https://api.ioc-sealevelmonitoring.org/v2/stations"
    params = {"showall": "all", "order": "code", "dir": "asc", "limit": 2000}
    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    return pd.DataFrame(response.json())

stations_df = get_stations()

# --- Build Folium Map ---
def build_map_with_eq(df, eq_lat, eq_lon):
    tiles = "https://services.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}"
    m = folium.Map(location=[eq_lat, eq_lon], tiles=tiles, attr="ESRI", zoom_start=5)
    for _, row in df.iterrows():
        if pd.notnull(row["Lat"]) and pd.notnull(row["Lon"]):
            popup_text = f"<b>Code:</b> {row['Code']}<br><b>Location:</b> {row['Location']}<br><b>Country:</b> {row['country']}<br><b>Status:</b> {row['status']}"
            marker_color = "red" if row["status"] == 5 else "green" if row["status"] == 1 else "blue"
            folium.Marker(location=[row["Lat"], row["Lon"]],
                          popup=popup_text,
                          tooltip=row["Code"],
                          icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)
    folium.Marker(location=[eq_lat, eq_lon],
                  popup="Earthquake Epicenter",
                  tooltip="EQ Epicenter",
                  icon=folium.DivIcon(html="""<div style="font-size:50px; color:red;">★</div>""")).add_to(m)
    return m

# --- Find Closest Stations ---
stations_df["distance_km"] = stations_df.apply(
    lambda row: geo_distance(y0, x0, row["Lat"], row["Lon"]) if pd.notnull(row["Lat"]) else None, axis=1
)
closest_stations = stations_df.nsmallest(5, "distance_km")

def build_closest_graphs(df):
    fig = sp.make_subplots(rows=5, cols=1, subplot_titles=[code for code in df["Code"]])
    for i, row in enumerate(df.itertuples(), start=1):
        # placeholder tide data
        fig.add_trace(go.Scatter(x=[0], y=[0], mode="lines", name=row.Code), row=i, col=1)
    fig.update_layout(height=1500, title="Sea Level at 5 Closest Stations")
    return fig

# --- Streamlit Tab Content ---
def show():
    st.subheader("Earthquake & IOC Sea Level Dashboard 🌏")

    # Map
    st.markdown("### Earthquake Epicenter & Tide Stations")
    m = build_map_with_eq(stations_df, y0, x0)
    st_folium(m, width=800, height=500)

    # Comparison
    st.markdown("### Earthquake Magnitude Comparison")
    col1, col2, col3 = st.columns(3)
    col1.metric("BMKG", f"{m0:.2f}")
    col2.metric("GFZ", f"{gfz_match['mag']:.2f}" if gfz_match is not None else "N/A")
    col3.metric("USGS", f"{usgs_match['mag']:.2f}" if usgs_match is not None else "N/A")

    # BMKG Table
    st.markdown("### BMKG Events (M ≥ 5)")
    st.dataframe(bmkg_df, use_container_width=True)

    # Closest Stations Graphs
    st.markdown("### Closest Tide Gauge Stations")
    st.plotly_chart(build_closest_graphs(closest_stations), use_container_width=True)
