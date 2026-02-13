"""Village Manager page for managing village GPS coordinates and admin boundaries."""
import streamlit as st
import sys
from pathlib import Path

# Add project root to Python path to ensure imports work
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
import json
from shapely.geometry import Point
from app.core.duckdb_store import DuckDBStore
from app.core.spatial import detect_admin_boundaries_from_point
from app.core.config import DUCKDB_PATH, PROJECT_ROOT
from app.core.admin_hierarchy import (
    load_hierarchy_from_csv,
    get_all_states,
    get_all_counties,
    get_all_payams,
    get_all_bomas
)
from app.core.scrapers import OSMScraper
# Import scraping function
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
try:
    from scrape_all_villages import scrape_all_locations, SOUTH_SUDAN_BBOX
    SCRAPE_MODULE_AVAILABLE = True
except ImportError:
    SCRAPE_MODULE_AVAILABLE = False


# Initialize session state if not already initialized
if "db_store" not in st.session_state:
    st.session_state.db_store = DuckDBStore(DUCKDB_PATH)

st.title("🏘️ Village Manager")

db_store: DuckDBStore = st.session_state.db_store

st.markdown("Manage village GPS coordinates with automatic admin boundary detection.")

# Tabs for different operations
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Add Village", "Batch Import", "Search/Edit", "Scrape", "Statistics"])

# Tab 1: Add Village
with tab1:
    st.subheader("Add New Village")
    
    entry_mode = st.radio(
        "Entry Mode:",
        ["Manual Entry", "Auto-detect Admin Boundaries"],
        horizontal=True
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pre-fill from scrape if available
        village_name_default = st.session_state.get("scrape_name", "")
        lon_default = st.session_state.get("scrape_lon", 0.0)
        lat_default = st.session_state.get("scrape_lat", 0.0)
        scrape_source_default = st.session_state.get("scrape_source", "manual")
        
        village_name = st.text_input("Village Name *", value=village_name_default, help="Primary name of the village")
        lon = st.number_input("Longitude *", value=lon_default, format="%.6f", step=0.000001)
        lat = st.number_input("Latitude *", value=lat_default, format="%.6f", step=0.000001)
        
        # Set default data source based on scrape source
        if scrape_source_default != "manual":
            data_source_options = ["manual", "compiled_dataset", "osm", "google_maps", "geonames", "other"]
            default_idx = data_source_options.index(scrape_source_default) if scrape_source_default in data_source_options else 0
        else:
            default_idx = 0
        
        data_source = st.selectbox(
            "Data Source",
            ["manual", "compiled_dataset", "osm", "google_maps", "geonames", "other"],
            index=default_idx
        )
        
        # Clear scrape state after using
        if village_name_default:
            if st.button("Clear Scraped Data"):
                for key in ["scrape_name", "scrape_lon", "scrape_lat", "scrape_source"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    with col2:
        # Cascading dropdowns for admin boundaries (only in Manual Entry mode)
        if entry_mode == "Manual Entry":
            # Load hierarchy from CSV (primary source) or database (fallback)
            hierarchy = load_hierarchy_from_csv()
            csv_states = get_all_states()
            
            # Try to get states from database as fallback
            db_state_names = []
            try:
                states_result = db_store.conn.execute("""
                    SELECT DISTINCT name 
                    FROM admin1_state 
                    WHERE name IS NOT NULL 
                    ORDER BY name
                """).fetchall()
                db_state_names = [row[0] for row in states_result] if states_result else []
            except Exception:
                pass
            
            # Use CSV states if available, otherwise use database states
            state_names = csv_states if csv_states else db_state_names
            
            if not state_names:
                st.warning("⚠️ No states found. Please ensure the compiled dataset CSV is available or upload state data in the Data Manager page.")
            
            # State dropdown
            selected_state_idx = st.selectbox(
                "State",
                options=[""] + state_names if state_names else [""],
                index=0,
                key="manual_state_select",
                disabled=not state_names
            )
            selected_state = selected_state_idx if selected_state_idx else None
            
            # County dropdown - filtered by selected state
            county_names = []
            if selected_state:
                # First try to get from CSV hierarchy (most reliable)
                if hierarchy.get("state_to_counties") and selected_state in hierarchy["state_to_counties"]:
                    county_names = hierarchy["state_to_counties"][selected_state]
                else:
                    # Fallback: try database
                    try:
                        all_counties_result = db_store.conn.execute("""
                            SELECT DISTINCT name, properties
                            FROM admin2_county
                            WHERE name IS NOT NULL
                            ORDER BY name
                        """).fetchall()
                        
                        if all_counties_result:
                            # Try to filter by parent state from properties
                            for county_name, properties_str in all_counties_result:
                                if properties_str:
                                    try:
                                        props = json.loads(properties_str)
                                        parent_state = (props.get("admin1Name") or 
                                                       props.get("admin1") or 
                                                       props.get("state") or 
                                                       props.get("STATE") or
                                                       props.get("State"))
                                        if parent_state and parent_state.strip().lower() == selected_state.strip().lower():
                                            county_names.append(county_name)
                                    except (json.JSONDecodeError, TypeError, AttributeError):
                                        continue
                            
                            # If no matches, show all counties
                            if not county_names:
                                county_names = [row[0] for row in all_counties_result]
                    except Exception as e:
                        st.error(f"Error loading counties: {e}")
                        # Final fallback: get all counties from CSV
                        county_names = get_all_counties()
            
            # Show county dropdown
            if selected_state:
                if not county_names:
                    st.info("No counties available for this state.")
                selected_county_idx = st.selectbox(
                    "County",
                    options=[""] + county_names if county_names else [""],
                    index=0,
                    key="manual_county_select"
                )
            else:
                selected_county_idx = st.selectbox(
                    "County",
                    options=[""],
                    index=0,
                    key="manual_county_select",
                    disabled=True
                )
            selected_county = selected_county_idx if selected_county_idx else None
            
            # Payam dropdown - filtered by selected county
            payam_names = []
            if selected_county:
                # First try to get from CSV hierarchy (most reliable)
                if hierarchy.get("county_to_payams") and selected_county in hierarchy["county_to_payams"]:
                    payam_names = hierarchy["county_to_payams"][selected_county]
                else:
                    # Fallback: try database
                    try:
                        all_payams_result = db_store.conn.execute("""
                            SELECT DISTINCT name, properties
                            FROM admin3_payam
                            WHERE name IS NOT NULL
                            ORDER BY name
                        """).fetchall()
                        
                        if all_payams_result:
                            for payam_name, properties_str in all_payams_result:
                                if properties_str:
                                    try:
                                        props = json.loads(properties_str)
                                        parent_county = (props.get("admin2Name") or 
                                                        props.get("admin2") or 
                                                        props.get("county") or 
                                                        props.get("COUNTY") or
                                                        props.get("County"))
                                        if parent_county and parent_county.strip().lower() == selected_county.strip().lower():
                                            payam_names.append(payam_name)
                                    except (json.JSONDecodeError, TypeError, AttributeError):
                                        continue
                            
                            # If no matches, show all payams
                            if not payam_names:
                                payam_names = [row[0] for row in all_payams_result]
                    except Exception as e:
                        st.error(f"Error loading payams: {e}")
                        # Final fallback: get all payams from CSV
                        payam_names = get_all_payams()
            
            if selected_county:
                if not payam_names:
                    st.info("No payams available for this county.")
                selected_payam_idx = st.selectbox(
                    "Payam",
                    options=[""] + payam_names if payam_names else [""],
                    index=0,
                    key="manual_payam_select"
                )
            else:
                selected_payam_idx = st.selectbox(
                    "Payam",
                    options=[""],
                    index=0,
                    key="manual_payam_select",
                    disabled=True
                )
            selected_payam = selected_payam_idx if selected_payam_idx else None
            
            # Boma dropdown - filtered by selected payam
            boma_names = []
            if selected_payam:
                # First try to get from CSV hierarchy (most reliable)
                if hierarchy.get("payam_to_bomas") and selected_payam in hierarchy["payam_to_bomas"]:
                    boma_names = hierarchy["payam_to_bomas"][selected_payam]
                else:
                    # Fallback: try database
                    try:
                        all_bomas_result = db_store.conn.execute("""
                            SELECT DISTINCT name, properties
                            FROM admin4_boma
                            WHERE name IS NOT NULL
                            ORDER BY name
                        """).fetchall()
                        
                        if all_bomas_result:
                            for boma_name, properties_str in all_bomas_result:
                                if properties_str:
                                    try:
                                        props = json.loads(properties_str)
                                        parent_payam = (props.get("admin3Name") or 
                                                       props.get("admin3") or 
                                                       props.get("payam") or 
                                                       props.get("PAYAM") or
                                                       props.get("Payam"))
                                        if parent_payam and parent_payam.strip().lower() == selected_payam.strip().lower():
                                            boma_names.append(boma_name)
                                    except (json.JSONDecodeError, TypeError, AttributeError):
                                        continue
                            
                            # If no matches, show all bomas
                            if not boma_names:
                                boma_names = [row[0] for row in all_bomas_result]
                    except Exception as e:
                        st.error(f"Error loading bomas: {e}")
                        # Final fallback: get all bomas from CSV
                        boma_names = get_all_bomas()
            
            if selected_payam:
                if not boma_names:
                    st.info("No bomas available for this payam.")
                selected_boma_idx = st.selectbox(
                    "Boma",
                    options=[""] + boma_names if boma_names else [""],
                    index=0,
                    key="manual_boma_select"
                )
            else:
                selected_boma_idx = st.selectbox(
                    "Boma",
                    options=[""],
                    index=0,
                    key="manual_boma_select",
                    disabled=True
                )
            selected_boma = selected_boma_idx if selected_boma_idx else None
            
            # Store selected values for use in save
            state = selected_state
            county = selected_county
            payam = selected_payam
            boma = selected_boma
        else:
            # Auto-detect mode: use text inputs (will be filled by auto-detect)
            state = st.text_input("State", key="state_manual", value=st.session_state.get("detected_state", ""))
            county = st.text_input("County", key="county_manual", value=st.session_state.get("detected_county", ""))
            payam = st.text_input("Payam", key="payam_manual", value=st.session_state.get("detected_payam", ""))
            boma = st.text_input("Boma", key="boma_manual", value=st.session_state.get("detected_boma", ""))
    
    # Auto-detect functionality
    if entry_mode == "Auto-detect Admin Boundaries":
        if st.button("🔍 Auto-detect Admin Boundaries", type="primary"):
            if lon and lat and abs(lon) > 0.1 and abs(lat) > 0.1:  # Basic validation
                try:
                    with st.spinner("Detecting admin boundaries..."):
                        point = Point(lon, lat)
                        hierarchy = detect_admin_boundaries_from_point(point)
                        
                        if hierarchy.get("state"):
                            st.session_state.detected_state = hierarchy["state"]
                            st.session_state.detected_county = hierarchy["county"]
                            st.session_state.detected_payam = hierarchy["payam"]
                            st.session_state.detected_boma = hierarchy["boma"]
                            st.success("✅ Admin boundaries detected!")
                        else:
                            st.warning("⚠️ Could not detect admin boundaries for these coordinates. They may be outside South Sudan.")
                            st.session_state.detected_state = None
                except Exception as e:
                    st.error(f"Error detecting admin boundaries: {e}")
            else:
                st.warning("Please enter valid coordinates first")
    
    # Show detected values if available
    if entry_mode == "Auto-detect Admin Boundaries":
        if hasattr(st.session_state, "detected_state") and st.session_state.detected_state:
            st.info(f"Detected: {st.session_state.detected_state} → {st.session_state.detected_county} → {st.session_state.detected_payam} → {st.session_state.detected_boma}")
            # Pre-fill the fields
            state = st.session_state.detected_state or state
            county = st.session_state.detected_county or county
            payam = st.session_state.detected_payam or payam
            boma = st.session_state.detected_boma or boma
    
    # Alternate names section
    with st.expander("Add Alternate Names (Optional)"):
        alt_names_input = st.text_area(
            "Alternate names (one per line)",
            help="Enter alternate spellings or names for this village, one per line"
        )
    
    # Save button
    if st.button("💾 Save Village", type="primary"):
        if not village_name or not village_name.strip():
            st.error("Village name is required")
        elif abs(lon) < 0.1 or abs(lat) < 0.1:
            st.error("Valid coordinates are required")
        else:
            try:
                # Add village
                village_id = db_store.add_village(
                    name=village_name.strip(),
                    lon=lon,
                    lat=lat,
                    state=state.strip() if state else None,
                    county=county.strip() if county else None,
                    payam=payam.strip() if payam else None,
                    boma=boma.strip() if boma else None,
                    data_source=data_source,
                    verified=False
                )
                
                # Add alternate names if provided
                if alt_names_input:
                    alt_names = [name.strip() for name in alt_names_input.split("\n") if name.strip()]
                    for alt_name in alt_names:
                        try:
                            db_store.add_alternate_name(
                                village_id=village_id,
                                alternate_name=alt_name,
                                name_type="alias",
                                source=data_source
                            )
                        except Exception:
                            pass  # Skip duplicates
                
                st.success(f"✅ Village '{village_name}' saved successfully!")
                st.balloons()
                
                # Clear form
                st.session_state.detected_state = None
                st.rerun()
                
            except Exception as e:
                st.error(f"Error saving village: {e}")

# Tab 2: Batch Import
with tab2:
    st.subheader("Batch Import Villages")
    
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        help="File should have columns: name, lon, lat (or longitude, latitude)"
    )
    
    if uploaded_file:
        try:
            # Read file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.info(f"Loaded {len(df)} rows")
            st.dataframe(df.head(10))
            
            # Column mapping
            st.subheader("Column Mapping")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                name_col = st.selectbox("Name Column", df.columns, index=0 if "name" in df.columns.str.lower() else 0)
            with col2:
                lon_col = st.selectbox(
                    "Longitude Column",
                    df.columns,
                    index=0 if any(c.lower() in ["lon", "longitude", "lng"] for c in df.columns) else 0
                )
            with col3:
                lat_col = st.selectbox(
                    "Latitude Column",
                    df.columns,
                    index=0 if any(c.lower() in ["lat", "latitude"] for c in df.columns) else 0
                )
            
            auto_detect = st.checkbox("Auto-detect admin boundaries for all rows", value=True)
            data_source = st.selectbox(
                "Data Source",
                ["compiled_dataset", "osm", "google_maps", "geonames", "manual", "other"],
                key="batch_source"
            )
            
            if st.button("🚀 Import Villages", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                imported = 0
                skipped = 0
                errors = []
                
                for idx, row in df.iterrows():
                    try:
                        # Get values
                        name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None
                        lon = float(row[lon_col]) if pd.notna(row[lon_col]) else None
                        lat = float(row[lat_col]) if pd.notna(row[lat_col]) else None
                        
                        if not name or lon is None or lat is None:
                            skipped += 1
                            continue
                        
                        # Auto-detect admin boundaries if requested
                        state = county = payam = boma = None
                        if auto_detect:
                            try:
                                point = Point(lon, lat)
                                hierarchy = detect_admin_boundaries_from_point(point)
                                state = hierarchy.get("state")
                                county = hierarchy.get("county")
                                payam = hierarchy.get("payam")
                                boma = hierarchy.get("boma")
                            except Exception:
                                pass
                        
                        # Add village
                        db_store.add_village(
                            name=name,
                            lon=lon,
                            lat=lat,
                            state=state,
                            county=county,
                            payam=payam,
                            boma=boma,
                            data_source=data_source,
                            source_id=str(idx)
                        )
                        
                        imported += 1
                        
                    except Exception as e:
                        errors.append((idx, str(e)))
                        skipped += 1
                    
                    # Update progress
                    progress = (idx + 1) / len(df)
                    progress_bar.progress(progress)
                    status_text.text(f"Processed {idx + 1}/{len(df)} rows...")
                
                progress_bar.empty()
                status_text.empty()
                
                st.success(f"✅ Imported {imported} villages!")
                if skipped > 0:
                    st.warning(f"⚠️ Skipped {skipped} rows")
                if errors:
                    st.error(f"❌ {len(errors)} errors occurred")
                    with st.expander("Error Details"):
                        for idx, error in errors[:20]:
                            st.text(f"Row {idx}: {error}")
        
        except Exception as e:
            st.error(f"Error reading file: {e}")

# Tab 3: Search/Edit
with tab3:
    st.subheader("Search and Edit Villages")
    
    search_query = st.text_input("Search village by name", placeholder="Enter village name...")
    
    if search_query:
        try:
            with st.spinner("Searching..."):
                results = db_store.search_villages(search_query, threshold=0.6, limit=20)
            
            if results:
                st.info(f"Found {len(results)} matching villages")
                
                # Display results
                for result in results:
                    with st.expander(f"📍 {result['name']} (Score: {result['score']:.2f})"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Coordinates:** {result['lon']:.6f}, {result['lat']:.6f}")
                            st.write(f"**State:** {result.get('state', 'N/A')}")
                            st.write(f"**County:** {result.get('county', 'N/A')}")
                            st.write(f"**Payam:** {result.get('payam', 'N/A')}")
                            st.write(f"**Boma:** {result.get('boma', 'N/A')}")
                        
                        with col2:
                            st.write(f"**Data Source:** {result.get('data_source', 'N/A')}")
                            st.write(f"**Verified:** {'Yes' if result.get('verified') else 'No'}")
                            if result.get('matched_alternate_name'):
                                st.write(f"**Matched via:** {result['matched_alternate_name']}")
                        
                        # Edit button
                        if st.button(f"Edit", key=f"edit_{result['village_id']}"):
                            st.session_state.edit_village_id = result['village_id']
                            st.rerun()
                        
                        # Re-detect admin boundaries
                        if st.button(f"Re-detect Admin Boundaries", key=f"redetect_{result['village_id']}"):
                            try:
                                point = Point(result['lon'], result['lat'])
                                hierarchy = detect_admin_boundaries_from_point(point)
                                
                                db_store.update_village_admin_boundaries(
                                    village_id=result['village_id'],
                                    state=hierarchy.get("state"),
                                    county=hierarchy.get("county"),
                                    payam=hierarchy.get("payam"),
                                    boma=hierarchy.get("boma"),
                                    state_id=hierarchy.get("state_id"),
                                    county_id=hierarchy.get("county_id"),
                                    payam_id=hierarchy.get("payam_id"),
                                    boma_id=hierarchy.get("boma_id")
                                )
                                
                                st.success("✅ Admin boundaries updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
            else:
                st.info("No villages found matching your search")
        
        except Exception as e:
            st.error(f"Error searching: {e}")
    
    # Edit form (if village selected)
    if "edit_village_id" in st.session_state:
        st.subheader("Edit Village")
        village = db_store.get_village(st.session_state.edit_village_id)
        
        if village:
            with st.form("edit_village_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    edit_name = st.text_input("Name", value=village["name"])
                    edit_lon = st.number_input("Longitude", value=village["lon"], format="%.6f")
                    edit_lat = st.number_input("Latitude", value=village["lat"], format="%.6f")
                
                with col2:
                    # Cascading dropdowns for admin boundaries in edit form
                    # Load hierarchy from CSV (primary source) or database (fallback)
                    edit_hierarchy = load_hierarchy_from_csv()
                    edit_csv_states = get_all_states()
                    
                    # Try to get states from database as fallback
                    edit_db_state_names = []
                    try:
                        states_result = db_store.conn.execute("""
                            SELECT DISTINCT name 
                            FROM admin1_state 
                            WHERE name IS NOT NULL 
                            ORDER BY name
                        """).fetchall()
                        edit_db_state_names = [row[0] for row in states_result] if states_result else []
                    except Exception:
                        pass
                    
                    # Use CSV states if available, otherwise use database states
                    edit_state_names = edit_csv_states if edit_csv_states else edit_db_state_names
                    
                    # Find current state index
                    current_state = village.get("state") or ""
                    state_index = 0
                    if current_state and current_state in edit_state_names:
                        state_index = edit_state_names.index(current_state) + 1  # +1 for empty option
                    
                    selected_edit_state_idx = st.selectbox(
                        "State",
                        options=[""] + edit_state_names if edit_state_names else [""],
                        index=state_index,
                        key="edit_state_select"
                    )
                    selected_edit_state = selected_edit_state_idx if selected_edit_state_idx else None
                    
                    # County dropdown - filtered by selected state
                    county_names = []
                    if selected_edit_state:
                        # First try to get from CSV hierarchy (most reliable)
                        if edit_hierarchy.get("state_to_counties") and selected_edit_state in edit_hierarchy["state_to_counties"]:
                            county_names = edit_hierarchy["state_to_counties"][selected_edit_state]
                        else:
                            # Fallback: try database
                            try:
                                counties_result = db_store.conn.execute("""
                                    SELECT DISTINCT name, properties
                                    FROM admin2_county
                                    WHERE name IS NOT NULL
                                    ORDER BY name
                                """).fetchall()
                                
                                if counties_result:
                                    for county_name, properties_str in counties_result:
                                        if properties_str:
                                            try:
                                                props = json.loads(properties_str)
                                                parent_state = (props.get("admin1Name") or 
                                                               props.get("admin1") or 
                                                               props.get("state") or 
                                                               props.get("STATE") or
                                                               props.get("State"))
                                                if parent_state and parent_state.strip().lower() == selected_edit_state.strip().lower():
                                                    county_names.append(county_name)
                                            except (json.JSONDecodeError, TypeError, AttributeError):
                                                continue
                                    
                                    # If no matches, show all counties
                                    if not county_names:
                                        county_names = [row[0] for row in counties_result]
                            except Exception as e:
                                # Final fallback: get all counties from CSV
                                county_names = get_all_counties()
                    
                    # Find current county index
                    current_county = village.get("county") or ""
                    county_index = 0
                    if current_county and current_county in county_names:
                        county_index = county_names.index(current_county) + 1
                    
                    selected_edit_county_idx = st.selectbox(
                        "County",
                        options=[""] + county_names,
                        index=county_index,
                        key="edit_county_select",
                        disabled=not selected_edit_state
                    )
                    selected_edit_county = selected_edit_county_idx if selected_edit_county_idx else None
                    
                    # Payam dropdown - filtered by selected county
                    payam_names = []
                    if selected_edit_county:
                        # First try to get from CSV hierarchy (most reliable)
                        if edit_hierarchy.get("county_to_payams") and selected_edit_county in edit_hierarchy["county_to_payams"]:
                            payam_names = edit_hierarchy["county_to_payams"][selected_edit_county]
                        else:
                            # Fallback: try database
                            try:
                                payams_result = db_store.conn.execute("""
                                    SELECT DISTINCT name, properties
                                    FROM admin3_payam
                                    WHERE name IS NOT NULL
                                    ORDER BY name
                                """).fetchall()
                                
                                if payams_result:
                                    for payam_name, properties_str in payams_result:
                                        if properties_str:
                                            try:
                                                props = json.loads(properties_str)
                                                parent_county = (props.get("admin2Name") or 
                                                               props.get("admin2") or 
                                                               props.get("county") or 
                                                               props.get("COUNTY") or
                                                               props.get("County"))
                                                if parent_county and parent_county.strip().lower() == selected_edit_county.strip().lower():
                                                    payam_names.append(payam_name)
                                            except (json.JSONDecodeError, TypeError, AttributeError):
                                                continue
                                    
                                    # If no matches, show all payams
                                    if not payam_names:
                                        payam_names = [row[0] for row in payams_result]
                            except Exception as e:
                                # Final fallback: get all payams from CSV
                                payam_names = get_all_payams()
                    
                    # Find current payam index
                    current_payam = village.get("payam") or ""
                    payam_index = 0
                    if current_payam and current_payam in payam_names:
                        payam_index = payam_names.index(current_payam) + 1
                    
                    selected_edit_payam_idx = st.selectbox(
                        "Payam",
                        options=[""] + payam_names,
                        index=payam_index,
                        key="edit_payam_select",
                        disabled=not selected_edit_county
                    )
                    selected_edit_payam = selected_edit_payam_idx if selected_edit_payam_idx else None
                    
                    # Boma dropdown - filtered by selected payam
                    boma_names = []
                    if selected_edit_payam:
                        # First try to get from CSV hierarchy (most reliable)
                        if edit_hierarchy.get("payam_to_bomas") and selected_edit_payam in edit_hierarchy["payam_to_bomas"]:
                            boma_names = edit_hierarchy["payam_to_bomas"][selected_edit_payam]
                        else:
                            # Fallback: try database
                            try:
                                bomas_result = db_store.conn.execute("""
                                    SELECT DISTINCT name, properties
                                    FROM admin4_boma
                                    WHERE name IS NOT NULL
                                    ORDER BY name
                                """).fetchall()
                                
                                if bomas_result:
                                    for boma_name, properties_str in bomas_result:
                                        if properties_str:
                                            try:
                                                props = json.loads(properties_str)
                                                parent_payam = (props.get("admin3Name") or 
                                                               props.get("admin3") or 
                                                               props.get("payam") or 
                                                               props.get("PAYAM") or
                                                               props.get("Payam"))
                                                if parent_payam and parent_payam.strip().lower() == selected_edit_payam.strip().lower():
                                                    boma_names.append(boma_name)
                                            except (json.JSONDecodeError, TypeError, AttributeError):
                                                continue
                                    
                                    # If no matches, show all bomas
                                    if not boma_names:
                                        boma_names = [row[0] for row in bomas_result]
                            except Exception as e:
                                # Final fallback: get all bomas from CSV
                                boma_names = get_all_bomas()
                    
                    # Find current boma index
                    current_boma = village.get("boma") or ""
                    boma_index = 0
                    if current_boma and current_boma in boma_names:
                        boma_index = boma_names.index(current_boma) + 1
                    
                    selected_edit_boma_idx = st.selectbox(
                        "Boma",
                        options=[""] + boma_names,
                        index=boma_index,
                        key="edit_boma_select",
                        disabled=not selected_edit_payam
                    )
                    selected_edit_boma = selected_edit_boma_idx if selected_edit_boma_idx else None
                    
                    # Use selected values
                    edit_state = selected_edit_state
                    edit_county = selected_edit_county
                    edit_payam = selected_edit_payam
                    edit_boma = selected_edit_boma
                
                col_submit, col_cancel = st.columns(2)
                with col_submit:
                    submitted = st.form_submit_button("💾 Save Changes", type="primary")
                with col_cancel:
                    cancelled = st.form_submit_button("❌ Cancel")
                
                if submitted:
                    try:
                        # Update using add_village with same ID (will replace)
                        db_store.add_village(
                            name=edit_name,
                            lon=edit_lon,
                            lat=edit_lat,
                            state=edit_state.strip() if edit_state else None,
                            county=edit_county.strip() if edit_county else None,
                            payam=edit_payam.strip() if edit_payam else None,
                            boma=edit_boma.strip() if edit_boma else None,
                            village_id=village["village_id"],
                            data_source=village.get("data_source", "manual")
                        )
                        st.success("✅ Village updated!")
                        del st.session_state.edit_village_id
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating village: {e}")
                
                if cancelled:
                    del st.session_state.edit_village_id
                    st.rerun()
            
            # Alternate names section
            st.subheader("Alternate Names")
            alt_names = db_store.get_village_alternate_names(village["village_id"])
            
            if alt_names:
                for alt in alt_names:
                    st.write(f"- {alt['alternate_name']} ({alt['name_type']})")
            else:
                st.info("No alternate names")
            
            # Add alternate name
            with st.form("add_alt_name_form"):
                new_alt_name = st.text_input("New Alternate Name")
                alt_name_type = st.selectbox("Type", ["alias", "variant", "misspelling", "translation"])
                
                if st.form_submit_button("Add Alternate Name"):
                    if new_alt_name:
                        try:
                            db_store.add_alternate_name(
                                village_id=village["village_id"],
                                alternate_name=new_alt_name.strip(),
                                name_type=alt_name_type
                            )
                            st.success("✅ Alternate name added!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

# Tab 4: Scrape
with tab4:
    st.subheader("Scrape Village Data from Web Sources")
    
    # Two modes: individual search and batch scrape all
    scrape_mode = st.radio(
        "Mode:",
        ["Search Individual Village", "Scrape All Locations (Batch)"],
        horizontal=True
    )
    
    if scrape_mode == "Search Individual Village":
        scrape_source = st.selectbox(
            "Data Source",
            ["OpenStreetMap"],
            help="Select a web source to scrape village data from"
        )
        
        scrape_query = st.text_input("Search for village name", placeholder="Enter village name to search...")
        
        if scrape_query and st.button("🔍 Search", type="primary"):
            try:
                results = []
                with st.spinner(f"Searching {scrape_source}..."):
                    if scrape_source == "OpenStreetMap":
                        scraper = OSMScraper()
                        results = scraper.search_village(scrape_query)
                
                if results:
                    st.success(f"Found {len(results)} results")
                    
                    for idx, result in enumerate(results):
                        with st.expander(f"📍 {result['name']} (Confidence: {result['confidence']:.2f})"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Coordinates:** {result['lon']:.6f}, {result['lat']:.6f}")
                                st.write(f"**Source:** {result['source']}")
                                st.write(f"**Source ID:** {result.get('source_id', 'N/A')}")
                            
                            with col2:
                                if result.get('properties'):
                                    props = result['properties']
                                    if props.get('place_type'):
                                        st.write(f"**Place Type:** {props['place_type']}")
                                    if props.get('wikipedia'):
                                        st.write(f"**Wikipedia:** {props['wikipedia']}")
                                
                                # Auto-fill form button
                                if st.button(f"Use This Result", key=f"use_result_{idx}"):
                                    st.session_state.scrape_name = result['name']
                                    st.session_state.scrape_lon = result['lon']
                                    st.session_state.scrape_lat = result['lat']
                                    st.session_state.scrape_source = result['source']
                                    st.success("✅ Result selected! Go to 'Add Village' tab to review and save.")
                                    st.rerun()
                    else:
                        st.info("No results found")
            
            except Exception as e:
                st.error(f"Error scraping: {e}")
        
        # Show selected result if available
        if hasattr(st.session_state, "scrape_name"):
            st.info(f"Selected: {st.session_state.scrape_name} at {st.session_state.scrape_lon:.6f}, {st.session_state.scrape_lat:.6f}")
    
    else:  # Batch scrape mode
        st.markdown("""
        ### Batch Scrape All Locations
        
        This will scrape **all villages and locations** in South Sudan from OpenStreetMap.
        
        **What it does:**
        - Queries OSM for all places (villages, hamlets, towns, cities) in South Sudan
        - Auto-detects admin boundaries (state, county, payam, boma) for each location
        - Stores all locations in the database with source attribution
        - Skips duplicates (locations already in database)
        
        **Note:** This process may take 10-30 minutes depending on the number of locations found.
        """)
        
        # Get current stats
        current_count = db_store.conn.execute("SELECT COUNT(*) FROM villages").fetchone()[0]
        osm_count = db_store.conn.execute("SELECT COUNT(*) FROM villages WHERE data_source = 'osm'").fetchone()[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Villages", current_count)
        with col2:
            st.metric("From OSM", osm_count)
        
        if not SCRAPE_MODULE_AVAILABLE:
            st.warning("⚠️ Scraping module not available. Please run from command line:")
            st.code("python scripts/scrape_all_villages.py")
        else:
            if st.button("🚀 Start Batch Scrape from OpenStreetMap", type="primary"):
                try:
                    st.warning("⚠️ This may take 10-30 minutes. Please do not close this page.")
                    
                    # Create a placeholder for progress
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    output_placeholder = st.empty()
                    
                    # Redirect stdout to capture output
                    import io
                    from contextlib import redirect_stdout, redirect_stderr
                    
                    output_buffer = io.StringIO()
                    
                    with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
                        try:
                            # Run the scraping function
                            with st.spinner("Scraping in progress... This may take 10-30 minutes."):
                                scrape_all_locations(db_store, SOUTH_SUDAN_BBOX)
                            
                            output_text = output_buffer.getvalue()
                            
                            st.success("✅ Batch scrape completed!")
                            output_placeholder.text_area("Scraping Output", output_text, height=300)
                            
                            # Refresh stats
                            st.rerun()
                        
                        except Exception as e:
                            output_text = output_buffer.getvalue()
                            st.error(f"❌ Scraping failed: {e}")
                            if output_text:
                                output_placeholder.text_area("Error Output", output_text, height=300)
                
                except Exception as e:
                    st.error(f"Error running scrape: {e}")
                    import traceback
                    st.code(traceback.format_exc())

# Tab 5: Statistics
with tab5:
    st.subheader("Village Database Statistics")
    
    try:
        # Total villages
        total_villages = db_store.conn.execute("SELECT COUNT(*) FROM villages").fetchone()[0]
        st.metric("Total Villages", total_villages)
        
        # By data source
        st.subheader("By Data Source")
        source_counts = db_store.conn.execute("""
            SELECT data_source, COUNT(*) as count
            FROM villages
            GROUP BY data_source
            ORDER BY count DESC
        """).fetchall()
        
        source_df = pd.DataFrame(source_counts, columns=["Data Source", "Count"])
        st.dataframe(source_df, use_container_width=True)
        
        # By state
        st.subheader("By State")
        state_counts = db_store.conn.execute("""
            SELECT state, COUNT(*) as count
            FROM villages
            WHERE state IS NOT NULL
            GROUP BY state
            ORDER BY count DESC
            LIMIT 20
        """).fetchall()
        
        if state_counts:
            state_df = pd.DataFrame(state_counts, columns=["State", "Count"])
            st.dataframe(state_df, use_container_width=True)
        
        # Alternate names count
        alt_count = db_store.conn.execute("SELECT COUNT(*) FROM village_alternate_names").fetchone()[0]
        st.metric("Total Alternate Names", alt_count)
        
    except Exception as e:
        st.error(f"Error loading statistics: {e}")

