"""Data Manager page for uploading and ingesting geospatial data."""
import streamlit as st
import geopandas as gpd
import pandas as pd
from pathlib import Path
from app.core.duckdb_store import DuckDBStore
from app.core.config import LAYER_NAMES, INGESTED_DIR


st.title("📊 Data Manager")

db_store: DuckDBStore = st.session_state.db_store

st.markdown("Upload GeoJSON or CSV files to ingest into the geocoding database.")

# File upload section
st.subheader("Upload Data")

upload_type = st.radio(
    "Data type:",
    ["GeoJSON (Admin layers)", "CSV (Settlements)"],
    horizontal=True
)

uploaded_file = st.file_uploader(
    "Choose a file",
    type=["geojson", "json", "csv"]
)

if uploaded_file:
    st.info(f"Uploaded: {uploaded_file.name} ({uploaded_file.size} bytes)")

# GeoJSON upload
if upload_type == "GeoJSON (Admin layers)" and uploaded_file:
    st.subheader("GeoJSON Configuration")
    
    layer_name = st.selectbox(
        "Select layer:",
        options=list(LAYER_NAMES.values())
    )
    
    name_field = st.text_input(
        "Name field:",
        value="name",
        help="Field name containing feature names"
    )
    
    if st.button("Ingest GeoJSON", type="primary"):
        try:
            # Read GeoJSON
            gdf = gpd.read_file(uploaded_file)
            
            # Validate
            if gdf.empty:
                st.error("GeoJSON file is empty")
            elif name_field not in gdf.columns:
                st.error(f"Name field '{name_field}' not found in GeoJSON")
            else:
                with st.spinner("Ingesting data..."):
                    db_store.ingest_geojson(layer_name, gdf, name_field)
                
                st.success(f"✅ Ingested {len(gdf)} features into {layer_name}")
                
                # Show preview
                st.dataframe(gdf.head(10))
        
        except Exception as e:
            st.error(f"Error ingesting GeoJSON: {e}")

# CSV upload
if upload_type == "CSV (Settlements)" and uploaded_file:
    st.subheader("CSV Configuration")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        lon_field = st.text_input("Longitude field:", value="lon")
    with col2:
        lat_field = st.text_input("Latitude field:", value="lat")
    with col3:
        name_field = st.text_input("Name field:", value="name")
    
    if st.button("Ingest CSV", type="primary"):
        try:
            # Save uploaded file temporarily
            temp_path = INGESTED_DIR / uploaded_file.name
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            with st.spinner("Ingesting data..."):
                db_store.ingest_settlements_csv(temp_path, lon_field, lat_field, name_field)
            
            st.success("✅ CSV ingested successfully")
            
            # Show preview
            df = pd.read_csv(temp_path)
            st.dataframe(df.head(10))
        
        except Exception as e:
            st.error(f"Error ingesting CSV: {e}")

# Build index section
st.subheader("Build Name Index")
st.markdown("After ingesting data, build the name index for fast fuzzy matching.")

if st.button("Build Index", type="primary"):
    with st.spinner("Building name index..."):
        db_store.build_name_index()
    st.success("✅ Name index built successfully")

# Data status
st.subheader("Data Status")
status_cols = st.columns(len(LAYER_NAMES))

for idx, (key, layer_name) in enumerate(LAYER_NAMES.items()):
    with status_cols[idx]:
        count = db_store.conn.execute(
            f"SELECT COUNT(*) FROM {layer_name}"
        ).fetchone()[0]
        st.metric(layer_name, count)

