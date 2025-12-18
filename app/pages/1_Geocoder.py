"""Geocoder page for resolving location strings."""
import streamlit as st
import pydeck as pdk
from app.core.geocoder import Geocoder
from app.core.duckdb_store import DuckDBStore
from app.core.config import FUZZY_THRESHOLD
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
        
        # Coordinates
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Longitude", f"{result.lon:.6f}")
        with col2:
            st.metric("Latitude", f"{result.lat:.6f}")
        
        # Admin hierarchy
        st.markdown("### Administrative Hierarchy")
        hierarchy_data = {
            "State": result.state or "N/A",
            "County": result.county or "N/A",
            "Payam": result.payam or "N/A",
            "Boma": result.boma or "N/A",
        }
        if result.village:
            hierarchy_data["Village"] = result.village
        
        for level, name in hierarchy_data.items():
            st.text(f"{level}: {name}")
        
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
    
    # Alternatives
    if result.alternatives:
        st.markdown("### Alternative Matches")
        for i, alt in enumerate(result.alternatives[:5], 1):
            with st.expander(f"{i}. {alt['name']} ({alt['layer']}) - Score: {alt['score']:.2f}"):
                st.text(f"Feature ID: {alt['feature_id']}")
                if alt.get('lon') and alt.get('lat'):
                    st.text(f"Coordinates: {alt['lon']:.6f}, {alt['lat']:.6f}")

elif resolve_button and not input_text:
    st.warning("Please enter a location string to geocode.")

