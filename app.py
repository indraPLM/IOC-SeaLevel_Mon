import streamlit as st
import regional_map
#import tide_gauge
import earthquake_events

st.set_page_config(page_title="Tsunami & Tide Gauge Dashboard", layout="wide")

st.title("🌊 Tsunami Event & IOC Tide Gauge Dashboard")
st.markdown("Modularized Streamlit app with tabs.")

tab1, tab2, tab3 = st.tabs(["🌍 Regional Map", "📈 Tide Gauge Data", "📊 Earthquake Events"])

with tab1:
    regional_map.show()

with tab2:
    earthquake_events.show()

with tab3:
    
    tide_gauge.show()

