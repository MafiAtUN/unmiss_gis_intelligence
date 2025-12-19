"""Data Manager page for uploading and ingesting geospatial data."""
import streamlit as st
import geopandas as gpd
import pandas as pd
from pathlib import Path
import io
from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder
from app.core.config import DUCKDB_PATH, LAYER_NAMES, INGESTED_DIR


# Initialize session state if not already initialized
if "db_store" not in st.session_state:
    st.session_state.db_store = DuckDBStore(DUCKDB_PATH)

st.title("📊 Data Manager")

db_store: DuckDBStore = st.session_state.db_store

# Initialize geocoder if not in session state
if "geocoder" not in st.session_state:
    st.session_state.geocoder = Geocoder(db_store)

geocoder: Geocoder = st.session_state.geocoder

# Tabs for different operations
tab1, tab2, tab3 = st.tabs(["Batch Geocode Locations", "Upload Data", "Build Index"])

# Tab 1: Batch Geocode Locations
with tab1:
    st.subheader("📍 Batch Geocode Location Data")
    st.markdown("""
    Upload an Excel or CSV file with location names, and we'll automatically:
    - Detect the location column
    - Find GPS coordinates for each location
    - Add administrative boundaries (State, County, Payam, Boma)
    - Include Payam ID and other admin IDs
    """)
    
    geocode_file = st.file_uploader(
        "Upload Excel or CSV file with location data",
        type=["csv", "xlsx", "xls"],
        key="geocode_upload"
    )
    
    if geocode_file:
        try:
            # Read file
            if geocode_file.name.endswith('.csv'):
                df = pd.read_csv(geocode_file)
            else:
                df = pd.read_excel(geocode_file)
            
            st.info(f"✅ Loaded {len(df)} rows with {len(df.columns)} columns")
            st.dataframe(df.head(10))
            
            # Auto-detect location column
            location_column = None
            location_candidates = []
            
            # Common location column names
            common_names = ["location", "place", "village", "settlement", "name", "loc", "address", "site"]
            
            for col in df.columns:
                col_lower = col.lower()
                if any(cn in col_lower for cn in common_names):
                    location_candidates.append(col)
            
            if location_candidates:
                location_column = st.selectbox(
                    "Select location column:",
                    options=location_candidates,
                    index=0,
                    help="Column containing location names to geocode"
                )
            else:
                location_column = st.selectbox(
                    "Select location column:",
                    options=list(df.columns),
                    help="Column containing location names to geocode"
                )
            
            # Show preview of location data
            if location_column:
                st.markdown(f"**Preview of location data from '{location_column}' column:**")
                st.dataframe(df[[location_column]].head(10), use_container_width=True)
                
                # Geocoding options
                st.markdown("### Geocoding Options")
                col1, col2 = st.columns(2)
                with col1:
                    use_cache = st.checkbox("Use cache", value=True, help="Use cached geocoding results for faster processing")
                with col2:
                    show_alternatives = st.checkbox("Show alternative matches", value=False, help="Include alternative location matches in results")
                
                if st.button("🚀 Start Geocoding", type="primary"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.container()
                    
                    # Initialize result columns
                    result_df = df.copy()
                    result_df["geocoded_lon"] = None
                    result_df["geocoded_lat"] = None
                    result_df["geocoded_state"] = None
                    result_df["geocoded_county"] = None
                    result_df["geocoded_payam"] = None
                    result_df["geocoded_boma"] = None
                    result_df["geocoded_village"] = None
                    result_df["geocoded_state_id"] = None
                    result_df["geocoded_county_id"] = None
                    result_df["geocoded_payam_id"] = None
                    result_df["geocoded_boma_id"] = None
                    result_df["geocoded_score"] = None
                    result_df["geocoded_match_type"] = None
                    
                    success_count = 0
                    failed_count = 0
                    
                    for idx, row in df.iterrows():
                        location_text = str(row[location_column]).strip() if pd.notna(row[location_column]) else ""
                        
                        if not location_text or location_text.lower() in ["nan", "none", ""]:
                            failed_count += 1
                            continue
                        
                        try:
                            # Geocode the location
                            result = geocoder.geocode(location_text, use_cache=use_cache)
                            
                            if result and result.lon and result.lat:
                                # Add coordinates
                                result_df.at[idx, "geocoded_lon"] = result.lon
                                result_df.at[idx, "geocoded_lat"] = result.lat
                                result_df.at[idx, "geocoded_state"] = result.state
                                result_df.at[idx, "geocoded_county"] = result.county
                                result_df.at[idx, "geocoded_payam"] = result.payam
                                result_df.at[idx, "geocoded_boma"] = result.boma
                                result_df.at[idx, "geocoded_village"] = result.village
                                result_df.at[idx, "geocoded_score"] = result.score
                                result_df.at[idx, "geocoded_match_type"] = result.resolved_layer
                                
                                # Get admin IDs using spatial query
                                if result.lon and result.lat:
                                    hierarchy_with_ids = db_store.get_admin_hierarchy_with_ids(result.lon, result.lat)
                                    result_df.at[idx, "geocoded_state_id"] = hierarchy_with_ids.get("state_id")
                                    result_df.at[idx, "geocoded_county_id"] = hierarchy_with_ids.get("county_id")
                                    result_df.at[idx, "geocoded_payam_id"] = hierarchy_with_ids.get("payam_id")
                                    result_df.at[idx, "geocoded_boma_id"] = hierarchy_with_ids.get("boma_id")
                                
                                success_count += 1
                            else:
                                failed_count += 1
                        except Exception as e:
                            failed_count += 1
                        
                        # Update progress
                        progress = (idx + 1) / len(df)
                        progress_bar.progress(progress)
                        status_text.text(f"Processed {idx + 1}/{len(df)} locations... (✅ {success_count} successful, ❌ {failed_count} failed)")
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Show results
                    with results_container:
                        st.success(f"✅ Geocoding complete! {success_count} locations geocoded successfully, {failed_count} failed.")
                        
                        # Show results preview
                        st.subheader("Geocoded Results Preview")
                        st.dataframe(result_df.head(20), use_container_width=True)
                        
                        # Statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Locations", len(df))
                        with col2:
                            st.metric("Successfully Geocoded", success_count)
                        with col3:
                            st.metric("Failed", failed_count)
                        
                        # Download options
                        st.subheader("Download Enhanced Data")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # CSV download
                            csv_buffer = io.StringIO()
                            result_df.to_csv(csv_buffer, index=False)
                            st.download_button(
                                label="📥 Download as CSV",
                                data=csv_buffer.getvalue(),
                                file_name=f"geocoded_{geocode_file.name}",
                                mime="text/csv"
                            )
                        
                        with col2:
                            # Excel download
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                result_df.to_excel(writer, index=False, sheet_name='Geocoded Data')
                            st.download_button(
                                label="📥 Download as Excel",
                                data=excel_buffer.getvalue(),
                                file_name=f"geocoded_{geocode_file.name.replace('.csv', '.xlsx')}",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
        
        except Exception as e:
            st.error(f"Error processing file: {e}")
            import traceback
            st.code(traceback.format_exc())

# Tab 2: Upload Data (original functionality)
with tab2:
    st.subheader("Upload Data")
    st.markdown("Upload GeoJSON or CSV files to ingest into the geocoding database.")

    upload_type = st.radio(
        "Data type:",
        ["GeoJSON (Admin layers)", "CSV (Settlements)"],
        horizontal=True
    )

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["geojson", "json", "csv"],
        key="upload_data_file"
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

# Tab 3: Build Index
with tab3:
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

