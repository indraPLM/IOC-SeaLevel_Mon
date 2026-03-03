import streamlit as st
import regional_map
import earthquake_events
import tsunami_wave_cat

# Wide layout ensures tabs stretch across the page
st.set_page_config(page_title="Tsunami & Tide Gauge Dashboard", layout="wide")

# Custom CSS to enlarge tab labels
st.markdown(
    """
    <style>
    /* Enlarge tab labels */
    .stTabs [role="tab"] {
        font-size: 1.2rem;
        font-weight: bold;
        padding: 12px 24px;
    }
    /* Highlight active tab */
    .stTabs [role="tab"][aria-selected="true"] {
        background-color: #f0f2f6;
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌊 Tsunami Event & IOC Tide Gauge Dashboard")
#st.markdown("Modularized Streamlit app with tabs.")

# --- API Key Input ---
api_key = st.text_input("Enter IOC API Key:", type="password")

if api_key:
    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "🌍 Regional Map",
        "📊 Earthquake Events",
        "📈 Tide Tsunami Cat"
    ])

    #with tab1:
    #    regional_map.show(api_key)

    #with tab2:
    #    earthquake_events.show(api_key)

    with tab3:
        tsunami_wave_cat.show(api_key)
else:
    st.warning("Please enter your IOC API Key to continue.")
















