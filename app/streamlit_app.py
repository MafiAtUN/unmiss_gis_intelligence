"""Main Streamlit application entry point."""
import streamlit as st
from app.core.config import DUCKDB_PATH
from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder
from app.utils.logging import setup_logging

# Setup logging
setup_logging()

# Initialize session state
if "db_store" not in st.session_state:
    st.session_state.db_store = DuckDBStore(DUCKDB_PATH)

if "geocoder" not in st.session_state:
    st.session_state.geocoder = Geocoder(st.session_state.db_store)

# Page configuration
st.set_page_config(
    page_title="South Sudan Geocoder",
    page_icon="📍",
    layout="wide"
)

# Main title
st.title("📍 South Sudan Administrative Geocoder")
st.markdown("Geocode free text locations using hierarchical administrative boundaries")

