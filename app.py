import streamlit as st
import regional_map
import earthquake_events
#import tide_gauge

# Wide layout ensures tabs stretch across the page
st.set_page_config(page_title="Tsunami & Tide Gauge Dashboard", layout="wide")

# Larger title and spacing
st.title("🌊 Tsunami Event & IOC Tide Gauge Dashboard")
#st.markdown("### Modularized Streamlit app with expanded tabs")

# Tabs with wide content
tab1, tab2, tab3 = st.tabs([
    "🌍 Regional Map",
    "📊 Earthquake Events",
    "📈 Tide Gauge Data"
])

with tab1:
    st.markdown("## Regional Map View")  # larger section header
    regional_map.show()

with tab2:
    st.markdown("## Earthquake Events Analysis")
    earthquake_events.show()

with tab3:
    st.markdown("## Tide Gauge Monitoring")
    tide_gauge.show()


