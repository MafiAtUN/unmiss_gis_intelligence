"""Location Extractor page for extracting location data from tabular files using AI."""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import io
import json
import os
from typing import Dict, List, Optional, Any
import pydeck as pdk
from shapely import wkb
from shapely.geometry import mapping
from dotenv import load_dotenv
from openai import OpenAI

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder
from app.core.config import DUCKDB_PATH
from app.core.admin_hierarchy import (
    load_hierarchy_from_csv,
    get_all_states,
    get_all_counties,
    get_all_payams,
    get_all_bomas,
)

# Gracefully handle permission errors (e.g., macOS security restrictions)
env_path = project_root / ".env"
try:
    # Try loading with explicit path first
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        # Fallback to default behavior (searches for .env in current directory)
        load_dotenv()
except (PermissionError, OSError) as e:
    # If .env file can't be accessed due to permissions, continue without it
    # Environment variables can still be set via system environment
    # Note: On macOS, you may need to grant Full Disk Access to Terminal/Python
    # in System Settings > Privacy & Security > Full Disk Access
    import warnings
    warnings.warn(
        f"Could not load .env file: {e}. "
        "Continuing with system environment variables. "
        "If you need .env file access, check macOS Full Disk Access settings.",
        UserWarning
    )

# Initialize session state if not already initialized
if "db_store" not in st.session_state:
    st.session_state.db_store = DuckDBStore(DUCKDB_PATH)

if "geocoder" not in st.session_state:
    st.session_state.geocoder = Geocoder(st.session_state.db_store)

db_store: DuckDBStore = st.session_state.db_store
geocoder: Geocoder = st.session_state.geocoder

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
is_azure = False

if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    from app.core.config import AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_API_KEY, AZURE_OPENAI_DEPLOYMENT
    if AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY:
        from openai import AzureOpenAI
        openai_client = AzureOpenAI(
            api_key=AZURE_FOUNDRY_API_KEY,
            api_version="2024-02-15-preview",
            azure_endpoint=AZURE_FOUNDRY_ENDPOINT
        )
        is_azure = True


def _clean_text(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text.lower() in ["", "nan", "none"]:
        return None
    return text


def build_location_query(location_text: str, state_value: Optional[str]) -> str:
    if not state_value:
        return location_text
    if state_value.lower() in location_text.lower():
        return location_text
    return f"{location_text}, {state_value}"


def extract_location_with_ai(
    row_data: Dict[str, Any],
    column_names: List[str],
    state_hint: Optional[str]
) -> Optional[str]:
    if not openai_client:
        return None

    row_context = "\n".join([f"{col}: {row_data.get(col, 'N/A')}" for col in column_names])
    state_context = f"State provided: {state_hint}" if state_hint else "State provided: Unknown"

    system_prompt = """You are a location extraction assistant for South Sudan.
Your task is to extract location information from tabular data rows.
The state is always provided in the row and must be honored.

Given a row of data with various columns, identify the location information.
The location could be in:
- A dedicated location/place/village/address column
- Multiple columns (e.g., village + county + state)
- Text descriptions that mention locations

Return ONLY a location string in the most specific format possible, such as:
- "Village Name, Payam Name, County Name, State Name"
- "Village Name, County Name, State Name"
- "Village Name, State Name"
- Or just "Village Name" if that's all available

If no clear location can be identified, return "NONE".
Return only the location string, nothing else."""

    user_prompt = f"""Extract the location from this data row:
{state_context}

{row_context}

Location:"""

    try:
        if is_azure:
            from app.core.config import AZURE_OPENAI_DEPLOYMENT
            deployment = AZURE_OPENAI_DEPLOYMENT or "gpt-4o-mini"
            response = openai_client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
        else:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )

        location = response.choices[0].message.content.strip()
        location = location.replace('"', "").replace("'", "").strip()

        if location.lower().startswith("location:"):
            location = location[9:].strip()
        if location.lower().startswith("the location is"):
            location = location[15:].strip()
        if location.upper() == "NONE" or not location:
            return None
        return location
    except Exception as e:
        st.warning(f"AI extraction error: {e}")
        return None


def geocode_location(location_text: str, state_value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not location_text:
        return None
    try:
        query = build_location_query(location_text, state_value)
        result = geocoder.geocode(query, use_cache=True)
        if result and result.lon and result.lat:
            hierarchy = db_store.get_admin_hierarchy_with_ids(result.lon, result.lat)
            return {
                "lat": result.lat,
                "lon": result.lon,
                "payam": result.payam or hierarchy.get("payam"),
                "county": result.county or hierarchy.get("county"),
                "state": result.state or hierarchy.get("state"),
                "boma": result.boma or hierarchy.get("boma"),
                "village": result.village,
                "payam_id": hierarchy.get("payam_id"),
                "county_id": hierarchy.get("county_id"),
                "state_id": hierarchy.get("state_id"),
                "score": result.score,
                "match_type": result.resolved_layer
            }
    except Exception as e:
        st.warning(f"Geocoding error for '{location_text}': {e}")
        return None
    return None


def search_candidates(
    query: str,
    state_value: Optional[str],
    threshold: float,
    limit: int
) -> List[Dict[str, Any]]:
    return db_store.search_villages(
        query=query,
        threshold=threshold,
        limit=limit,
        include_alternates=True,
        state_constraint=state_value
    )


def candidate_to_result(candidate: Dict[str, Any]) -> Dict[str, Any]:
    hierarchy = db_store.get_admin_hierarchy_with_ids(candidate["lon"], candidate["lat"])
    return {
        "lat": candidate["lat"],
        "lon": candidate["lon"],
        "payam": candidate.get("payam"),
        "county": candidate.get("county"),
        "state": candidate.get("state"),
        "boma": candidate.get("boma"),
        "village": candidate.get("name"),
        "payam_id": hierarchy.get("payam_id"),
        "county_id": hierarchy.get("county_id"),
        "state_id": hierarchy.get("state_id"),
        "score": candidate.get("score"),
        "match_type": "village_search"
    }


@st.cache_data(show_spinner=False)
def get_admin_geojson(layer_name: str, name_value: str) -> Optional[Dict[str, Any]]:
    if not name_value:
        return None
    try:
        results = db_store.conn.execute(
            f"SELECT geometry_wkb, name FROM {layer_name} WHERE name = ?",
            [name_value]
        ).fetchall()
        if not results:
            return None
        features = []
        for geometry_wkb, name in results:
            if geometry_wkb:
                geom = wkb.loads(geometry_wkb, hex=True)
                features.append({
                    "type": "Feature",
                    "properties": {"name": name},
                    "geometry": mapping(geom)
                })
        return {"type": "FeatureCollection", "features": features}
    except Exception:
        return None


def render_candidate_map(candidate: Dict[str, Any]):
    if not candidate or not candidate.get("lon") or not candidate.get("lat"):
        return

    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=[{
                "lon": candidate["lon"],
                "lat": candidate["lat"],
                "name": candidate.get("name") or candidate.get("village") or "Location"
            }],
            get_position=["lon", "lat"],
            get_color=[255, 0, 0, 255],
            get_radius=500,
            radius_min_pixels=10,
            radius_max_pixels=50,
            pickable=True
        )
    ]

    boma_geojson = get_admin_geojson("admin4_boma", candidate.get("boma"))
    if boma_geojson:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=boma_geojson,
                get_fill_color=[0, 100, 200, 80],
                get_line_color=[0, 100, 200, 255],
                line_width_min_pixels=2,
                pickable=True
            )
        )

    view_state = pdk.ViewState(
        longitude=candidate["lon"],
        latitude=candidate["lat"],
        zoom=10,
        pitch=0
    )

    deck = pdk.Deck(
        map_style=None,
        initial_view_state=view_state,
        layers=layers,
        tooltip={"text": "{name}"}
    )

    st.pydeck_chart(deck)


@st.cache_data(show_spinner=False)
def get_admin_hierarchy():
    return load_hierarchy_from_csv()


def render_manual_entry_panel():
    st.subheader("Manual Coordinates Entry")
    st.markdown("Enter coordinates and select admin hierarchy manually.")

    hierarchy = get_admin_hierarchy()
    state_names = get_all_states()
    county_names = get_all_counties()
    payam_names = get_all_payams()
    boma_names = get_all_bomas()

    col1, col2 = st.columns(2)
    with col1:
        lon = st.number_input("Longitude", value=0.0, format="%.6f", step=0.000001, key="manual_lon")
        lat = st.number_input("Latitude", value=0.0, format="%.6f", step=0.000001, key="manual_lat")
    with col2:
        selected_state = st.selectbox("State", options=[""] + state_names, key="manual_state_select")
        selected_county = st.selectbox(
            "County",
            options=[""] + (hierarchy.get("state_to_counties", {}).get(selected_state, county_names)),
            key="manual_county_select"
        )
        selected_payam = st.selectbox(
            "Payam",
            options=[""] + (hierarchy.get("county_to_payams", {}).get(selected_county, payam_names)),
            key="manual_payam_select"
        )
        selected_boma = st.selectbox(
            "Boma",
            options=[""] + (hierarchy.get("payam_to_bomas", {}).get(selected_payam, boma_names)),
            key="manual_boma_select"
        )

    if st.button("Add Manual Entry", type="secondary"):
        if "manual_entries" not in st.session_state:
            st.session_state.manual_entries = []
        st.session_state.manual_entries.append({
            "lon": lon,
            "lat": lat,
            "state": selected_state or None,
            "county": selected_county or None,
            "payam": selected_payam or None,
            "boma": selected_boma or None
        })

    if st.session_state.get("manual_entries"):
        manual_df = pd.DataFrame(st.session_state.manual_entries)
        st.dataframe(manual_df, use_container_width=True)
        csv_buffer = io.StringIO()
        manual_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download Manual Entries (CSV)",
            data=csv_buffer.getvalue(),
            file_name="manual_entries.csv",
            mime="text/csv"
        )

        if len(st.session_state.manual_entries) > 0:
            last_entry = st.session_state.manual_entries[-1]
            render_candidate_map({
                "lon": last_entry["lon"],
                "lat": last_entry["lat"],
                "name": "Manual Entry",
                "boma": last_entry.get("boma")
            })


st.title("📍 Location Extractor")
st.markdown("""
Upload tabular data (CSV or Excel) to extract location names, match similar spellings,
constrain matches by the provided state, and review duplicates on a map with boma overlay.
""")

if not openai_client:
    st.error("OpenAI API not configured. Set OPENAI_API_KEY or Azure OpenAI settings in .env.")
    st.stop()

uploaded_file = st.file_uploader(
    "Upload CSV or Excel file with location data",
    type=["csv", "xlsx", "xls"],
    key="location_extractor_upload"
)

with st.expander("Manual Coordinates Entry", expanded=False):
    render_manual_entry_panel()

if uploaded_file:
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success(f"Loaded {len(df)} rows with {len(df.columns)} columns")
        st.subheader("Data Preview")
        st.dataframe(df.head(10), use_container_width=True)

        st.subheader("Configuration")
        col1, col2, col3 = st.columns(3)
        with col1:
            use_ai_extraction = st.checkbox(
                "Use AI for location extraction",
                value=True,
                help="Extract location from multiple columns or descriptions."
            )
        with col2:
            fuzzy_threshold = st.slider(
                "Fuzzy match threshold",
                min_value=0.60,
                max_value=0.95,
                value=0.75,
                step=0.05
            )
        with col3:
            max_candidates = st.number_input(
                "Max candidates per row",
                min_value=1,
                max_value=20,
                value=8
            )

        state_column = st.selectbox(
            "Select the State column (required):",
            options=list(df.columns),
            help="State column is mandatory to constrain matches."
        )

        location_column = None
        if not use_ai_extraction:
            location_column = st.selectbox(
                "Select location column:",
                options=list(df.columns),
                help="Column containing location names to geocode"
            )

        if st.button("Extract and Match Locations", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            result_df = df.copy()
            result_df["provided_state"] = None
            result_df["extracted_location"] = None
            result_df["geocoded_lat"] = None
            result_df["geocoded_lon"] = None
            result_df["geocoded_payam"] = None
            result_df["geocoded_county"] = None
            result_df["geocoded_state"] = None
            result_df["geocoded_boma"] = None
            result_df["geocoded_village"] = None
            result_df["geocoded_payam_id"] = None
            result_df["geocoded_county_id"] = None
            result_df["geocoded_state_id"] = None
            result_df["geocoded_score"] = None
            result_df["geocoded_match_type"] = None
            result_df["review_status"] = None

            success_count = 0
            failed_count = 0
            ai_extraction_count = 0
            ambiguous_rows = []

            column_names = list(df.columns)

            for idx, row in df.iterrows():
                state_value = _clean_text(row.get(state_column))
                location_text = None
                result_df.at[idx, "provided_state"] = state_value

                if use_ai_extraction:
                    row_dict = {col: row[col] for col in column_names}
                    location_text = extract_location_with_ai(row_dict, column_names, state_value)
                    if location_text:
                        ai_extraction_count += 1
                        result_df.at[idx, "extracted_location"] = location_text
                else:
                    if location_column:
                        location_text = _clean_text(row.get(location_column))
                        if location_text:
                            result_df.at[idx, "extracted_location"] = location_text

                if location_text and state_value:
                    candidates = search_candidates(
                        query=location_text,
                        state_value=state_value,
                        threshold=fuzzy_threshold,
                        limit=int(max_candidates)
                    )
                    if candidates:
                        selected = candidates[0]
                        resolved = candidate_to_result(selected)
                        for k, v in resolved.items():
                            result_df.at[idx, f"geocoded_{k}"] = v
                        result_df.at[idx, "review_status"] = "auto"
                        success_count += 1

                        if len(candidates) > 1:
                            label = f"Row {idx + 1}: {location_text} ({state_value})"
                            ambiguous_rows.append({
                                "row_index": idx,
                                "label": label,
                                "candidates": candidates,
                                "location_text": location_text,
                                "state_value": state_value
                            })
                    else:
                        fallback = geocode_location(location_text, state_value)
                        if fallback:
                            for k, v in fallback.items():
                                result_df.at[idx, f"geocoded_{k}"] = v
                            result_df.at[idx, "review_status"] = "auto"
                            success_count += 1
                        else:
                            failed_count += 1
                else:
                    failed_count += 1

                progress = (idx + 1) / len(df)
                progress_bar.progress(progress)
                status_text.text(
                    f"Processed {idx + 1}/{len(df)} rows... "
                    f"(OK {success_count}, AI {ai_extraction_count}, Failed {failed_count})"
                )

            progress_bar.empty()
            status_text.empty()

            st.session_state.location_extractor_result_df = result_df
            st.session_state.location_extractor_ambiguous = ambiguous_rows
            st.session_state.location_extractor_review_index = 0

            st.success(
                f"Processing complete. {success_count} matched, {failed_count} failed."
            )
            if use_ai_extraction:
                st.info(f"AI extracted {ai_extraction_count} locations from the data.")

        if st.session_state.get("location_extractor_result_df") is not None:
            result_df = st.session_state.location_extractor_result_df
            st.subheader("Results Preview")
            st.dataframe(result_df.head(20), use_container_width=True)

            ambiguous_rows = st.session_state.get("location_extractor_ambiguous", [])
            if ambiguous_rows:
                st.subheader("Review Duplicate Matches")
                st.markdown("Review ambiguous locations one by one and pick the correct match.")

                idx = st.session_state.get("location_extractor_review_index", 0)
                idx = max(0, min(idx, len(ambiguous_rows) - 1))

                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if st.button("Previous", disabled=(idx == 0)):
                        st.session_state.location_extractor_review_index = idx - 1
                        st.rerun()
                with col3:
                    if st.button("Next", disabled=(idx >= len(ambiguous_rows) - 1)):
                        st.session_state.location_extractor_review_index = idx + 1
                        st.rerun()

                current = ambiguous_rows[idx]
                st.markdown(f"**{current['label']}**")

                candidate_labels = []
                for cand in current["candidates"]:
                    candidate_labels.append(
                        f"{cand.get('name')} | {cand.get('payam')}, {cand.get('county')}, {cand.get('state')} | score {cand.get('score', 0):.2f}"
                    )

                selected_idx = st.radio(
                    "Select the correct location:",
                    options=list(range(len(candidate_labels))),
                    format_func=lambda i: candidate_labels[i],
                    key=f"candidate_select_{current['row_index']}"
                )

                selected_candidate = current["candidates"][selected_idx]
                render_candidate_map(selected_candidate)

                if st.button("Apply Selection"):
                    resolved = candidate_to_result(selected_candidate)
                    row_index = current["row_index"]
                    for k, v in resolved.items():
                        result_df.at[row_index, f"geocoded_{k}"] = v
                    result_df.at[row_index, "review_status"] = "manual"
                    st.session_state.location_extractor_result_df = result_df
                    st.success("Selection applied.")

            st.subheader("Download Enhanced Data")
            col1, col2 = st.columns(2)
            with col1:
                csv_buffer = io.StringIO()
                result_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="Download as CSV",
                    data=csv_buffer.getvalue(),
                    file_name=f"geocoded_{uploaded_file.name}",
                    mime="text/csv"
                )
            with col2:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    result_df.to_excel(writer, index=False, sheet_name="Geocoded Data")
                st.download_button(
                    label="Download as Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"geocoded_{uploaded_file.name.replace('.csv', '.xlsx')}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"Error processing file: {e}")
        import traceback
        with st.expander("Error Details"):
            st.code(traceback.format_exc(), language="python")
