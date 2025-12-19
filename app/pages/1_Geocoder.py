"""Geocoder page for resolving location strings."""
import streamlit as st
import pydeck as pdk
import pandas as pd
from app.core.geocoder import Geocoder
from app.core.duckdb_store import DuckDBStore
from app.core.config import DUCKDB_PATH, FUZZY_THRESHOLD
from app.utils.timing import Timer


def load_admin_boundaries(layer_name: str, db_store: DuckDBStore):
    """Load admin boundary polygons for visualization."""
    from shapely import wkb
    import json
    import geopandas as gpd
    
    result = db_store.conn.execute(f"""
        SELECT feature_id, geometry_wkb, name, properties
        FROM {layer_name}
    """).fetchall()
    
    if not result:
        return gpd.GeoDataFrame()
    
    features = []
    for feature_id, geometry_wkb, name, properties_str in result:
        geometry = wkb.loads(geometry_wkb, hex=True)
        features.append({
            "feature_id": feature_id,
            "name": name,
            "geometry": geometry
        })
    
    return gpd.GeoDataFrame(features, crs="EPSG:4326")


# Initialize session state if not already initialized
if "db_store" not in st.session_state:
    st.session_state.db_store = DuckDBStore(DUCKDB_PATH)

if "geocoder" not in st.session_state:
    st.session_state.geocoder = Geocoder(st.session_state.db_store)

st.title("🔍 Geocoder")

geocoder: Geocoder = st.session_state.geocoder
db_store: DuckDBStore = st.session_state.db_store

# Input section
st.subheader("Location Input")
input_text = st.text_area(
    "Enter location string:",
    height=100,
    placeholder="e.g., 'Juba, Central Equatoria' or 'Bentiu, Unity State'"
)

col1, col2 = st.columns([1, 4])
with col1:
    resolve_button = st.button("Resolve", type="primary", use_container_width=True)

# Process geocoding
result = None
if resolve_button and input_text:
    with Timer("geocode"):
        result = geocoder.geocode(input_text.strip())

# Display results
if result:
    st.subheader("Results")
    
    # Main result card
    if result.resolution_too_coarse:
        st.warning("⚠️ Resolution too coarse - only County or State level match found. Coordinates not provided.")
        st.info(f"**Best match:** {result.matched_name} ({result.resolved_layer})")
    elif result.lon and result.lat:
        st.success(f"✅ Resolved to: **{result.matched_name}** ({result.resolved_layer})")
        
        # Detailed Information Section
        st.markdown("### 📍 Location Details")
        
        # Create tabs for different views
        detail_tab1, detail_tab2, detail_tab3 = st.tabs(["Coordinates", "Administrative Hierarchy", "Full Details"])
        
        with detail_tab1:
            st.markdown("#### GPS Coordinates (Easy Copy Format)")
            
            # Tab-separated format for Excel
            coords_tsv = f"{result.lon}\t{result.lat}"
            coords_csv = f"{result.lon},{result.lat}"
            coords_formatted = f"Longitude: {result.lon:.6f}\nLatitude: {result.lat:.6f}"
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Tab-Separated (for Excel):**")
                st.code(coords_tsv, language=None)
                st.caption("💡 Select and copy (Ctrl+C / Cmd+C) to paste into Excel")
            with col2:
                st.markdown("**Comma-Separated (CSV):**")
                st.code(coords_csv, language=None)
                st.caption("💡 Select and copy to paste into CSV files")
            with col3:
                st.markdown("**Formatted:**")
                st.code(coords_formatted, language=None)
                st.caption("💡 Select and copy for formatted text")
            
            # Also show as metrics
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Longitude", f"{result.lon:.6f}")
            with col2:
                st.metric("Latitude", f"{result.lat:.6f}")
        
        with detail_tab2:
            st.markdown("#### Administrative Hierarchy")
            hierarchy_data = {
                "State": result.state or "N/A",
                "County": result.county or "N/A",
                "Payam": result.payam or "N/A",
                "Boma": result.boma or "N/A",
            }
            if result.village:
                hierarchy_data["Village"] = result.village
            
            # Display as a nice table
            hierarchy_df = pd.DataFrame([
                {"Level": level, "Name": name}
                for level, name in hierarchy_data.items()
            ])
            st.dataframe(hierarchy_df, use_container_width=True, hide_index=True)
            
            # Also show as text for easy copy
            st.markdown("**Copy-friendly format:**")
            hierarchy_text = "\n".join([f"{level}: {name}" for level, name in hierarchy_data.items()])
            st.code(hierarchy_text, language=None)
        
        with detail_tab3:
            st.markdown("#### Full Location Information")
            
            # Get additional details from database if available
            if result.feature_id and result.resolved_layer:
                try:
                    feature = db_store.get_feature(result.resolved_layer, result.feature_id)
                    if feature:
                        st.markdown("**Feature Information:**")
                        feature_data = {
                            "Feature ID": result.feature_id,
                            "Layer": result.resolved_layer,
                            "Matched Name": result.matched_name,
                            "Match Score": f"{result.score:.3f}",
                            "Longitude": f"{result.lon:.6f}",
                            "Latitude": f"{result.lat:.6f}",
                        }
                        
                        # Add properties if available
                        if feature.get("properties"):
                            props = feature["properties"]
                            if isinstance(props, dict):
                                for key, value in list(props.items())[:10]:  # Show first 10 properties
                                    if key not in ["name", "feature_id"]:
                                        feature_data[f"Property: {key}"] = str(value)[:100]  # Truncate long values
                        
                        feature_df = pd.DataFrame([
                            {"Field": k, "Value": v}
                            for k, v in feature_data.items()
                        ])
                        st.dataframe(feature_df, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.info(f"Additional details not available: {e}")
            
            # Show input and normalized text
            st.markdown("**Query Information:**")
            query_data = {
                "Input Text": result.input_text,
                "Normalized Text": result.normalized_text,
                "Match Score": f"{result.score:.3f}",
            }
            query_df = pd.DataFrame([
                {"Field": k, "Value": v}
                for k, v in query_data.items()
            ])
            st.dataframe(query_df, use_container_width=True, hide_index=True)
        
        # Map visualization
        st.markdown("### Map")
        
        # Create map layers
        layers = []
        
        # Point layer
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=[{
                    "lon": result.lon,
                    "lat": result.lat,
                    "name": result.matched_name
                }],
                get_position=["lon", "lat"],
                get_color=[255, 0, 0, 200],
                get_radius=500,
                radius_min_pixels=10,
                radius_max_pixels=50,
                pickable=True
            )
        )
        
        # Load and display admin boundaries
        if result.boma and result.resolved_layer != "admin4_boma":
            boma_gdf = load_admin_boundaries("admin4_boma", db_store)
            if not boma_gdf.empty:
                # Filter to matching boma
                boma_match = boma_gdf[boma_gdf["name"] == result.boma]
                if not boma_match.empty:
                    # Convert to GeoJSON for pydeck
                    import json
                    geojson = json.loads(boma_match.to_json())
                    layers.append(
                        pdk.Layer(
                            "GeoJsonLayer",
                            data=geojson,
                            get_fill_color=[0, 100, 200, 100],
                            get_line_color=[0, 100, 200, 255],
                            line_width_min_pixels=2,
                            pickable=True
                        )
                    )
        
        # Create map
        view_state = pdk.ViewState(
            longitude=result.lon,
            latitude=result.lat,
            zoom=10,
            pitch=0
        )
        
        deck = pdk.Deck(
            map_style=None,  # Use default OpenStreetMap style
            initial_view_state=view_state,
            layers=layers,
            tooltip={"text": "{name}"}
        )
        
        st.pydeck_chart(deck)
        
    else:
        st.error("❌ No match found")
    
    # Alternatives / Similar Locations
    if result.alternatives:
        st.markdown("### 🔍 Similar Locations Found")
        st.info(f"Found {len(result.alternatives)} similar location(s) that might match your query.")
        
        # Create a table of alternatives
        alt_data = []
        for i, alt in enumerate(result.alternatives, 1):
            alt_row = {
                "#": i,
                "Name": alt.get('name', 'N/A'),
                "Layer": alt.get('layer', 'N/A'),
                "Score": f"{alt.get('score', 0):.3f}",
                "Longitude": f"{alt.get('lon', 0):.6f}" if alt.get('lon') else "N/A",
                "Latitude": f"{alt.get('lat', 0):.6f}" if alt.get('lat') else "N/A",
                "Feature ID": alt.get('feature_id', 'N/A'),
            }
            
            # Try to get admin hierarchy for alternatives
            if alt.get('lon') and alt.get('lat'):
                try:
                    from shapely.geometry import Point
                    from app.core.spatial import get_admin_hierarchy
                    # Ensure admin layers are loaded
                    geocoder._load_admin_layers()
                    point = Point(alt['lon'], alt['lat'])
                    hierarchy = get_admin_hierarchy(point, geocoder.admin_layers)
                    alt_row["State"] = hierarchy.get('state') or 'N/A'
                    alt_row["County"] = hierarchy.get('county') or 'N/A'
                    alt_row["Payam"] = hierarchy.get('payam') or 'N/A'
                    alt_row["Boma"] = hierarchy.get('boma') or 'N/A'
                except Exception as e:
                    alt_row["State"] = "N/A"
                    alt_row["County"] = "N/A"
                    alt_row["Payam"] = "N/A"
                    alt_row["Boma"] = "N/A"
            else:
                alt_row["State"] = "N/A"
                alt_row["County"] = "N/A"
                alt_row["Payam"] = "N/A"
                alt_row["Boma"] = "N/A"
            
            alt_data.append(alt_row)
        
        if alt_data:
            alt_df = pd.DataFrame(alt_data)
            
            # Display as interactive table
            st.dataframe(
                alt_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Score": st.column_config.NumberColumn("Score", format="%.3f"),
                    "Longitude": st.column_config.TextColumn("Longitude"),
                    "Latitude": st.column_config.TextColumn("Latitude"),
                }
            )
            
            # Export options
            st.markdown("#### 📥 Export Similar Locations")
            col1, col2 = st.columns(2)
            
            with col1:
                # CSV export
                csv_data = alt_df.to_csv(index=False)
                st.download_button(
                    label="📊 Download as CSV",
                    data=csv_data,
                    file_name="similar_locations.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Excel-friendly TSV export
                tsv_data = alt_df.to_csv(index=False, sep='\t')
                st.download_button(
                    label="📋 Download as TSV (Excel)",
                    data=tsv_data,
                    file_name="similar_locations.tsv",
                    mime="text/tab-separated-values"
                )
            
            # Detailed view for each alternative
            st.markdown("#### 📋 Detailed View")
            for i, alt in enumerate(result.alternatives, 1):
                with st.expander(f"{i}. {alt['name']} ({alt['layer']}) - Score: {alt['score']:.3f}", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Basic Information:**")
                        st.text(f"Name: {alt.get('name', 'N/A')}")
                        st.text(f"Layer: {alt.get('layer', 'N/A')}")
                        st.text(f"Feature ID: {alt.get('feature_id', 'N/A')}")
                        st.text(f"Match Score: {alt.get('score', 0):.3f}")
                    
                    with col2:
                        st.markdown("**Coordinates:**")
                        if alt.get('lon') and alt.get('lat'):
                            st.text(f"Longitude: {alt['lon']:.6f}")
                            st.text(f"Latitude: {alt['lat']:.6f}")
                            
                            # Copy-friendly format
                            st.markdown("**Copy format (Tab-separated for Excel):**")
                            alt_coords = f"{alt['lon']:.6f}\t{alt['lat']:.6f}"
                            st.code(alt_coords, language=None)
                            st.caption("💡 Select and copy to paste into Excel")
                        else:
                            st.text("Coordinates: N/A")
                    
                    # Try to get full feature details
                    if alt.get('feature_id') and alt.get('layer'):
                        try:
                            feature = db_store.get_feature(alt['layer'], alt['feature_id'])
                            if feature and feature.get('properties'):
                                st.markdown("**Additional Properties:**")
                                props = feature['properties']
                                if isinstance(props, dict):
                                    for key, value in list(props.items())[:5]:
                                        if key not in ['name', 'feature_id']:
                                            st.text(f"{key}: {str(value)[:200]}")
                        except:
                            pass
    else:
        if result.score > 0:
            st.info("No similar locations found. This was the only match.")

elif resolve_button and not input_text:
    st.warning("Please enter a location string to geocode.")

