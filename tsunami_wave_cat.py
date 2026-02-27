import requests
import pandas as pd
import plotly.subplots as sp
import plotly.graph_objs as go
import folium
from streamlit_folium import st_folium
import streamlit as st
from obspy.geodetics import locations2degrees, degrees2kilometers
from datetime import datetime, timedelta

#API_KEY = "YOUR_API_KEY"

# --- Load Tsunami Catalog ---
def load_noaa_tsunami_catalog(csv_path):
    # Load the CSV with flexible parsing
    df=pd.read_csv(csv_path,encoding="latin1")

    # Combine year/month/day/hour/minute/second into a datetime column
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Mo"] = pd.to_numeric(df["Mo"], errors="coerce").fillna(1)
    df["Dy"] = pd.to_numeric(df["Dy"], errors="coerce").fillna(1)
    df["Hr"] = pd.to_numeric(df["Hr"], errors="coerce").fillna(0)
    df["Mn"] = pd.to_numeric(df["Mn"], errors="coerce").fillna(0)
    df["Sec"] = pd.to_numeric(df["Sec"], errors="coerce").fillna(0)

    df["datetime"] = pd.to_datetime(dict(
        year=df["Year"],
        month=df["Mo"],
        day=df["Dy"],
        hour=df["Hr"],
        minute=df["Mn"],
        second=df["Sec"]
    ), errors="coerce")

    # Clean and rename key columns
    df.rename(columns={
        "Latitude": "lat",
        "Longitude": "lon",
        "Earthquake Magnitude": "mag",
        "Tsunami Event Validity": "validity",
        "Tsunami Cause Code" : "source",
        "Maximum Number": "max_wave_height",
        "Country": "country",
        "Location Name": "location"        
    }, inplace=True)

    # Filter out rows without coordinates
    df = df[pd.notnull(df["lat"]) & pd.notnull(df["lon"])]

    return df

def map_tsunami_catalog_validity_layers(df):
    # Alias for ESRI Ocean basemap
    esri_ocean_map = "https://services.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}"

    # Initialize map
    m = folium.Map(location=[0, 120], tiles=esri_ocean_map, attr="ESRI", zoom_start=5)

    # Validity categories with labels + colors
    validity_colors = {
        -1: ("Erroneous", "black"),
        0: ("Seiche only", "gray"),
        1: ("Very doubtful", "purple"),
        2: ("Questionable", "orange"),
        3: ("Probable", "blue"),
        4: ("Definite", "red")
    }

    # Create FeatureGroups for each validity category
    validity_groups = {k: folium.FeatureGroup(name=v[0]) for k, v in validity_colors.items()}

    # Symbol assignment by cause
    def get_symbol(cause):
        if cause in [1, 2, 3]:
            return "★"   # earthquake
        elif cause in [4, 5, 6, 7]:
            return "▲"   # volcano
        elif cause == 8:
            return "▼"   # landslide
        else:
            return "●"   # other

    # Add markers into their validity group
    for _, row in df.iterrows():
        lat, lon = row["lat"], row["lon"]
        mag = row.get("mag", None)
        vald = row.get("validity", None)
        source = row.get("source", None)
        country = row.get("country", "")
        location = row.get("location", "")
        event_time = row.get("datetime", "")

        popup_text = (
            f"<b>Date/Time:</b> {event_time}<br>"
            f"<b>Magnitude:</b> {mag}<br>"
            f"<b>Validity:</b> {vald}<br>"
            f"<b>Location:</b> {location}, {country}<br>"
            f"<b>Cause:</b> {source}"
        )

        if vald in validity_colors:
            group = validity_groups[vald]
            color = validity_colors[vald][1]
        else:
            group = m
            color = "green"

        symbol = get_symbol(source)

        folium.Marker(
            location=[lat, lon],
            popup=popup_text,
            tooltip=f"Validity {vald}, Cause {source} - {location}",
            icon=folium.DivIcon(html=f"""<div style="font-size:18px; color:{color};">{symbol}</div>""")
        ).add_to(group)

    # Add each validity group to the map
    for group in validity_groups.values():
        group.add_to(m)

    # Add LayerControl (only validity layers)
    folium.LayerControl(collapsed=False).add_to(m)

    return m

# --- Map Tsunami Catalog Events ---
def map_tsunami_catalog(df):
    tiles = "https://services.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}"
    m = folium.Map(location=[0, 120], tiles=tiles, attr="ESRI", zoom_start=5)

    validity_colors = {
        -1: "black", 0: "gray", 1: "purple",
        2: "orange", 3: "blue", 4: "red"
    }

    def get_symbol(cause):
        if cause in [1, 2, 3]:
            return "★"   # earthquake
        elif cause in [4, 5, 6, 7]:
            return "▲"   # volcano
        elif cause == 8:
            return "▼"   # landslide
        else:
            return "●"   # other

    for _, row in df.iterrows():
        lat, lon = row["lat"], row["lon"]
        mag = row.get("mag", None)
        vald = row.get("validity", None)
        source = row.get("source", None)
        country = row.get("country", "")
        location = row.get("location", "")
        event_time = row.get("datetime", "")

        popup_text = (
            f"<b>Date/Time:</b> {event_time}<br>"
            f"<b>Magnitude:</b> {mag}<br>"
            f"<b>Validity:</b> {vald}<br>"
            f"<b>Location:</b> {location}, {country}<br>"
            f"<b>Cause:</b> {source}"
        )

        color = validity_colors.get(vald, "green")
        symbol = get_symbol(source)

        folium.Marker(
            location=[lat, lon],
            popup=popup_text,
            tooltip=f"Validity {vald}, Cause {source} - {location}",
            icon=folium.DivIcon(html=f"""<div style="font-size:18px; color:{color};">{symbol}</div>""")
        ).add_to(m)

    return m

# --- IOC Stations ---
def get_stations(api_key):
    url = "https://api.ioc-sealevelmonitoring.org/v2/stations"
    params = {"showall": "all", "order": "code", "dir": "asc", "limit": 2000}
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    return pd.DataFrame(response.json())

#stations_df = get_stations()

# --- Distance helper ---
def geo_distance(lat0, lon0, lat1, lon1):
    return round(degrees2kilometers(locations2degrees(lat0, lon0, lat1, lon1)), 2)

# --- Find Closest Stations given tsunami lat/lon ---
def get_closest_stations(stations_df, tsu_lat, tsu_lon, n=5):
    stations_df = stations_df.copy()
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

def show(api_key):
    st.subheader("Click Tsunami Location on Map 🌊")

    # Load catalog
    catalog_df = load_noaa_tsunami_catalog("noaa_tsunamis_catalog_to_2026-02-24.csv")

    # Load IOC stations once
    stations_df = get_stations(api_key)

    # Map tsunami catalog
    m = map_tsunami_catalog_validity_layers(catalog_df)
    map_data = st_folium(m, width="100%", height=500)

    if map_data and map_data["last_clicked"]:
        tsu_lat = map_data["last_clicked"]["lat"]
        tsu_lon = map_data["last_clicked"]["lng"]

        st.success(f"Selected location: Lat {tsu_lat:.2f}, Lon {tsu_lon:.2f}")

        # Pass stations_df explicitly
        closest = get_closest_stations(stations_df, tsu_lat, tsu_lon)
        st.dataframe(closest[["Code", "Location", "country", "distance_km"]])

        st.plotly_chart(build_closest_graphs(api_key, closest), use_container_width=True)

        # Map visualization with tsunami + closest stations
        m2 = folium.Map(location=[tsu_lat, tsu_lon], zoom_start=5)
        folium.Marker([tsu_lat, tsu_lon], popup="Tsunami Location", icon=folium.Icon(color="red")).add_to(m2)
        for _, row in closest.iterrows():
            folium.Marker([row["Lat"], row["Lon"]],
                          popup=f"{row['Code']} ({row['distance_km']} km)",
                          icon=folium.Icon(color="blue")).add_to(m2)
        st_folium(m2, width="100%", height=500)

