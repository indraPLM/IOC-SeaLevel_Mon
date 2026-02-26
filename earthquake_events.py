# earthquake_events.py (tab2)

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

def get_stations(api_key):
    url = "https://api.ioc-sealevelmonitoring.org/v2/stations"
    params = {"showall": "all", "order": "code", "dir": "asc", "limit": 2000}
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    return pd.DataFrame(response.json())

def build_map_with_eq(df, eq_lat, eq_lon):
    tiles = "https://services.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}"
    m = folium.Map(location=[eq_lat, eq_lon], tiles=tiles, attr="ESRI", zoom_start=5)

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

    # Add earthquake epicenter marker
    folium.Marker(
        location=[eq_lat, eq_lon],
        popup="Earthquake Epicenter",
        tooltip="EQ Epicenter",
        icon=folium.DivIcon(html="""<div style="font-size:50px; color:red;">★</div>""")
    ).add_to(m)

    return m

# --- Fetch Tide Gauge Data ---
def fetch_data(api_key, station_id, sensor="one-sensor"):
    # Compute dynamic date range: end = now, start = 1 day before
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)

    # Format as YYYY-MM-DD for IOC API
    end_str = end_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")

    station_id = station_id.lower()
    url = f"https://api.ioc-sealevelmonitoring.org/v2/research/stations/{station_id}/sensors/{sensor}/data"
    params = {
        "days_per_page": 7, "page": 1,
        "timestart": start_str, "timestop": end_str,
        "flag_qc": "true"
    }
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

# --- Helper to build subplot figure for closest stations ---
def build_closest_graphs(api_key, stations_df):
    stations = stations_df["Code"].tolist()
    fig = sp.make_subplots(rows=len(stations), cols=1,
                           subplot_titles=[code.upper() for code in stations])

    for i, code in enumerate(stations, start=1):
        df = fetch_data(api_key, code)
        if not df.empty and "stime" in df.columns:
            fig.add_trace(
                go.Scatter(x=df["stime"], y=df["slevel"],
                           mode="lines", name=code.upper()),
                row=i, col=1
            )
        else:
            # Add a placeholder trace if no data
            fig.add_trace(
                go.Scatter(x=[0], y=[0], mode="lines", name=f"{code.upper()} (no data)"),
                row=i, col=1
            )

    fig.update_layout(height=300*len(stations),
                      title="Sea Level at Closest Stations")
    return fig


# --- Streamlit Tab Content ---
def show(api_key):
    st.subheader("Earthquake & IOC Sea Level Dashboard 🌏")

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
    stations_df = get_stations(api_key)
    stations_df["distance_km"] = stations_df.apply(
        lambda row: geo_distance(y0, x0, row["Lat"], row["Lon"]) if pd.notnull(row["Lat"]) else None, axis=1
    )
    closest_stations = stations_df.nsmallest(5, "distance_km")
    
    # --- Layout ---
    col_top1, col_top2 = st.columns([2, 1])

    with col_top1:
        st.markdown("### Earthquake Epicenter & Tide Stations")
        m = build_map_with_eq(stations_df, y0, x0)
        st_folium(m, width="100%", height=500)

    with col_top2:
        st.markdown("### Earthquake Parameters")

        # --- Metrics Display ---
        col1, col2 = st.columns(2)
        col1.markdown("## Magnitude")
        col2.markdown("## Depth")

        cols = st.columns(6)
        # BMKG reference
        cols[0].metric("1. BMKG", f"{m0:.2f}")
        cols[3].metric("1. BMKG", f"{d0:.1f} km")

        # GFZ comparison
        if gfz_match is not None:
            delta_mag = round(gfz_match['mag'] - m0, 2)
            delta_depth = round(gfz_match['depth'] - d0, 2)
            dist_km = geo_distance(x0, y0, gfz_match['lon'], gfz_match['lat'])
            cols[1].metric("2. GFZ", f"{gfz_match['mag']:.2f}", f"{delta_mag:+.2f}")
            cols[4].metric("2. GFZ", f"{gfz_match['depth']:.1f} km", f"{delta_depth:+.1f}")
        else:
            cols[1].metric("2. GFZ", "N/A")
            cols[4].metric("2. GFZ", "N/A")

        # USGS comparison
        if usgs_match is not None:
            delta_mag = round(usgs_match['mag'] - m0, 2)
            delta_depth = round(usgs_match['depth'] - d0, 2)
            dist_km = geo_distance(x0, y0, usgs_match['lon'], usgs_match['lat'])
            cols[2].metric("3. USGS", f"{usgs_match['mag']:.2f}", f"{delta_mag:+.2f}")
            cols[5].metric("3. USGS", f"{usgs_match['depth']:.1f} km", f"{delta_depth:+.1f}")
        else:
            cols[2].metric("3. USGS", "N/A")
            cols[5].metric("3. USGS", "N/A")

        # --- Location Display ---
        st.markdown("## Longitude / Latitude")
        loc_cols = st.columns(3)
        loc_cols[0].metric("1. BMKG", f"{x0:.2f} ; {y0:.2f}")
        if gfz_match is not None:
            dist_km = geo_distance(x0, y0, gfz_match['lon'], gfz_match['lat'])
            loc_cols[1].metric("2. GFZ", f"{gfz_match['lon']:.2f} ; {gfz_match['lat']:.2f}", f"{dist_km:.1f} km")
        else:
            loc_cols[1].metric("2. GFZ", "N/A")

        if usgs_match is not None:
            dist_km = geo_distance(x0, y0, usgs_match['lon'], usgs_match['lat'])
            loc_cols[2].metric("3. USGS", f"{usgs_match['lon']:.2f} ; {usgs_match['lat']:.2f}", f"{dist_km:.1f} km")
        else:
            loc_cols[2].metric("3. USGS", "N/A")

    # --- Bottom Panel ---
    st.markdown("### Closest Tide Gauge Stations")
                    
    st.plotly_chart(build_closest_graphs(api_key, closest_stations), use_container_width=True)
    st.dataframe(stations_df)









