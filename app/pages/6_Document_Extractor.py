"""Document Location Extractor page for extracting locations from unstructured text."""
import streamlit as st
import sys
from pathlib import Path

# Add project root to Python path to ensure imports work
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pydeck as pdk
import pandas as pd
import json
from typing import Dict, Any
from app.core.geocoder import Geocoder
from app.core.duckdb_store import DuckDBStore
from app.core.config import DUCKDB_PATH
from app.core.location_extractor import DocumentLocationExtractor
from app.utils.timing import Timer


# Example UNMISS report text
EXAMPLE_TEXT = """UNITED NATIONS          ألأمم المتحدة
United Nations Mission in South Sudan (UNMISS)

Human Rights Division (HRD)
Daily Situation Report 
19 December 2025
Highlights

Attacks by community-based militias and violations by government security forces continue to pose protection risks to civilians:

•	Suspected Bul Nuer armed elements shot and killed two civilians and injured another in Abiemnom Town, Abiemnom County, Ruweng Administrative Area (Unity); 
•	South Sudan People's Defence Forces (SSPDF) killed one civilian in Wau Town, Wau County (Western Bahr el Ghazal).

Unity

1.	On 18 December, multiple sources reported that on 17 December, suspected Bul Nuer armed elements shot and killed two male civilians (24 and 27 years old) and injured another (22-year-old) from the Dunka Alor community in Abiemnom Town, Abiemnom County, Ruweng Administrative Area. According to the sources, the suspected Bul Nuer armed elements Bul Nuer armed elements attacked when the victims as they were travelling on a motorcycle from Nyinjuai to Abiemnom Town. The motives for the attack remain unknown. Government security forces were reportedly deployed to the scene; however, they arrived when the assailants had fled. The injured victim was reportedly evacuated to a health care facility in Abiemnom for medical treatment.

Comments: Such armed attacks persist along the Warrap-Abiemnom-Mayom axis, in the context of unresolved communal grievances, exacerbated by the proliferation of small arms and light weapons and impunity. HRD continues to monitor and advocate for perpetrators to be held accountable.

Western Bahr el Ghazal

2.	On 18 December, multiple sources reported that on 15 December, the SSPDF killed one 43-year-old male civilian (UNMISS local staff) in the Hai Masana area, Wau Town, Wau County. According to the sources, SSPDF personnel extracted the victim from a vehicle belonging to UNMISS during a routine patrol in the Hai Masana area and forcibly took him in SSPDF vehicle. On 18 December, the SSPDF Division 5 Commander confirmed that the victim was killed by SSPDF personnel, and the victim's body was subsequently retrieved. The motive for the killing remains unclear. The main suspect is reportedly under military detention at the SSPDF Division 5 barracks in Grinti in Wau Town, while three others remain at charge. The victim's family has reportedly filed a case at the Wau Town Police Station.

Comments: HRD will continue to gather more information on the motive of the incident as well as follow up on the investigation and prosecution process for accountability of the suspect. 


-	End    -
"""


# Initialize session state if not already initialized
if "db_store" not in st.session_state:
    st.session_state.db_store = DuckDBStore(DUCKDB_PATH)

if "geocoder" not in st.session_state:
    st.session_state.geocoder = Geocoder(st.session_state.db_store)

if "document_extractor" not in st.session_state:
    st.session_state.document_extractor = DocumentLocationExtractor(st.session_state.geocoder)

if "extraction_result" not in st.session_state:
    st.session_state.extraction_result = None

if "document_hash" not in st.session_state:
    st.session_state.document_hash = None

st.title("📄 Document Location Extractor")

geocoder: Geocoder = st.session_state.geocoder
db_store: DuckDBStore = st.session_state.db_store
extractor: DocumentLocationExtractor = st.session_state.document_extractor

# Input section
st.subheader("Document Input")
col1, col2 = st.columns([4, 1])
with col1:
    document_text = st.text_area(
        "Paste document text here:",
        height=300,
        placeholder="Paste your document text here...",
        key="document_input"
    )
with col2:
    if st.button("Load Example", use_container_width=True):
        st.session_state.document_input = EXAMPLE_TEXT
        st.rerun()

extract_button = st.button("Extract Locations", type="primary", use_container_width=True)

# Process extraction
if extract_button and document_text:
    with st.spinner("Extracting locations and geocoding..."):
        try:
            with Timer("extract_locations"):
                result = extractor.extract_locations(document_text, geocode=True)
                document_hash = extractor.get_document_hash(document_text)
                st.session_state.extraction_result = result
                st.session_state.document_hash = document_hash
        except Exception as e:
            st.error(f"❌ Error during extraction: {str(e)}")
            import traceback
            with st.expander("🔍 Error Details", expanded=False):
                st.code(traceback.format_exc(), language="python")
            st.session_state.extraction_result = None

# Display results
if st.session_state.extraction_result:
    result = st.session_state.extraction_result
    document_hash = st.session_state.document_hash
    
    st.subheader("Extraction Results")
    
    # Statistics
    regex_count = len(result.regex_locations)
    ollama_count = len(result.ollama_locations) if result.ollama_locations else 0
    ai_count = len(result.ai_locations)  # Azure AI
    regex_geocoded = sum(1 for loc in result.regex_locations if loc.geocode_result and loc.geocode_result.lon)
    ollama_geocoded = sum(1 for loc in (result.ollama_locations or []) if loc.geocode_result and loc.geocode_result.lon)
    ai_geocoded = sum(1 for loc in result.ai_locations if loc.geocode_result and loc.geocode_result.lon)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Regex", regex_count)
    with col2:
        st.metric("Ollama", ollama_count)
    with col3:
        st.metric("Azure AI", ai_count)
    with col4:
        st.metric("Regex ✅", regex_geocoded)
    with col5:
        st.metric("Ollama ✅", ollama_geocoded)
    with col6:
        st.metric("Azure ✅", ai_geocoded)
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["Comparison", "Detailed Table", "Map View", "Feedback Statistics"])
    
    with tab1:
        st.markdown("### Extraction Method Comparison")
        
        # Three-column comparison
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### Regex Extractions")
            if result.regex_locations:
                regex_data = []
                for i, loc in enumerate(result.regex_locations, 1):
                    geocode_status = "✅" if loc.geocode_result and loc.geocode_result.lon else "❌"
                    regex_data.append({
                        "#": i,
                        "Location": loc.original_text[:40] + "..." if len(loc.original_text) > 40 else loc.original_text,
                        "Status": geocode_status,
                        "Score": f"{loc.geocode_result.score:.2f}" if loc.geocode_result else "N/A"
                    })
                st.dataframe(pd.DataFrame(regex_data), use_container_width=True, hide_index=True)
            else:
                st.info("No locations extracted using regex.")
        
        with col2:
            st.markdown("#### Ollama Extractions")
            ollama_locs = result.ollama_locations if result.ollama_locations else []
            if ollama_locs:
                ollama_data = []
                for i, loc in enumerate(ollama_locs, 1):
                    geocode_status = "✅" if loc.geocode_result and loc.geocode_result.lon else "❌"
                    ollama_data.append({
                        "#": i,
                        "Location": loc.original_text[:40] + "..." if len(loc.original_text) > 40 else loc.original_text,
                        "Status": geocode_status,
                        "Score": f"{loc.geocode_result.score:.2f}" if loc.geocode_result else "N/A"
                    })
                st.dataframe(pd.DataFrame(ollama_data), use_container_width=True, hide_index=True)
            else:
                st.info("No locations extracted using Ollama.")
        
        with col3:
            st.markdown("#### Azure AI Extractions")
            if result.ai_locations:
                ai_data = []
                for i, loc in enumerate(result.ai_locations, 1):
                    geocode_status = "✅" if loc.geocode_result and loc.geocode_result.lon else "❌"
                    ai_data.append({
                        "#": i,
                        "Location": loc.original_text[:40] + "..." if len(loc.original_text) > 40 else loc.original_text,
                        "Status": geocode_status,
                        "Score": f"{loc.geocode_result.score:.2f}" if loc.geocode_result else "N/A"
                    })
                st.dataframe(pd.DataFrame(ai_data), use_container_width=True, hide_index=True)
            else:
                st.info("No locations extracted using Azure AI.")
    
    with tab2:
        st.markdown("### Detailed Extraction Results")
        
        # Combine all locations for display
        all_locations = result.get_all_locations()
        
        if all_locations:
            for idx, loc in enumerate(all_locations):
                with st.expander(f"[{loc.extraction_method.upper()}] {loc.original_text}", expanded=False):
                    # Context
                    st.markdown("**Context:**")
                    st.text(loc.context)
                    
                    # Geocoding result
                    if loc.geocode_result:
                        gr = loc.geocode_result
                        
                        # Color coding based on confidence
                        if gr.score >= 0.8:
                            status_color = "🟢"
                            status_text = "High Confidence"
                        elif gr.score >= 0.5:
                            status_color = "🟡"
                            status_text = "Medium Confidence"
                        else:
                            status_color = "🔴"
                            status_text = "Low Confidence"
                        
                        st.markdown(f"**Geocoding Status:** {status_color} {status_text} (Score: {gr.score:.3f})")
                        
                        if gr.lon and gr.lat:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Longitude", f"{gr.lon:.6f}")
                            with col2:
                                st.metric("Latitude", f"{gr.lat:.6f}")
                            
                            # Admin hierarchy
                            st.markdown("**Administrative Hierarchy:**")
                            hierarchy = {
                                "State": gr.state or "N/A",
                                "County": gr.county or "N/A",
                                "Payam": gr.payam or "N/A",
                                "Boma": gr.boma or "N/A",
                            }
                            if gr.village:
                                hierarchy["Village"] = gr.village
                            
                            hierarchy_df = pd.DataFrame([
                                {"Level": level, "Name": name}
                                for level, name in hierarchy.items()
                            ])
                            st.dataframe(hierarchy_df, use_container_width=True, hide_index=True)
                            
                            if gr.matched_name:
                                st.info(f"**Matched:** {gr.matched_name} ({gr.resolved_layer})")
                        else:
                            st.warning("Coordinates not available (resolution too coarse or no match found)")
                    else:
                        st.warning("No geocoding result available")
                    
                    # Feedback controls
                    st.markdown("---")
                    st.markdown("**Provide Feedback:**")
                    
                    feedback_key = f"feedback_{idx}_{document_hash}"
                    feedback_col1, feedback_col2, feedback_col3 = st.columns(3)
                    
                    with feedback_col1:
                        if st.button("✅ Correct", key=f"correct_{idx}", use_container_width=True):
                            geocode_json = json.dumps(loc.geocode_result.to_dict()) if loc.geocode_result else None
                            db_store.save_extraction_feedback(
                                document_hash=document_hash,
                                original_text=loc.original_text,
                                extracted_text=loc.original_text,
                                method=loc.extraction_method,
                                is_correct=True,
                                context_text=loc.context,
                                geocode_result_json=geocode_json
                            )
                            st.success("Feedback saved!")
                            st.rerun()
                    
                    with feedback_col2:
                        if st.button("❌ Incorrect", key=f"incorrect_{idx}", use_container_width=True):
                            geocode_json = json.dumps(loc.geocode_result.to_dict()) if loc.geocode_result else None
                            db_store.save_extraction_feedback(
                                document_hash=document_hash,
                                original_text=loc.original_text,
                                extracted_text=loc.original_text,
                                method=loc.extraction_method,
                                is_correct=False,
                                context_text=loc.context,
                                geocode_result_json=geocode_json
                            )
                            st.success("Feedback saved!")
                            st.rerun()
                    
                    with feedback_col3:
                        corrected_text = st.text_input(
                            "Corrected text:",
                            key=f"corrected_{idx}",
                            placeholder="Enter corrected location text"
                        )
                        if corrected_text and st.button("💾 Save Correction", key=f"save_corrected_{idx}", use_container_width=True):
                            geocode_json = json.dumps(loc.geocode_result.to_dict()) if loc.geocode_result else None
                            db_store.save_extraction_feedback(
                                document_hash=document_hash,
                                original_text=loc.original_text,
                                extracted_text=loc.original_text,
                                method=loc.extraction_method,
                                user_corrected_text=corrected_text,
                                context_text=loc.context,
                                geocode_result_json=geocode_json
                            )
                            st.success("Correction saved!")
                            st.rerun()
        else:
            st.info("No locations were extracted from the document.")
    
    with tab3:
        st.markdown("### Map Visualization")
        
        # Prepare map data
        map_data = []
        for loc in all_locations:
            if loc.geocode_result and loc.geocode_result.lon and loc.geocode_result.lat:
                # Different colors for each method
                if loc.extraction_method == "regex":
                    color = [255, 0, 0, 160]  # Red
                    method_name = "Regex"
                elif loc.extraction_method == "ollama":
                    color = [0, 255, 0, 160]  # Green
                    method_name = "Ollama"
                else:  # ai/azure
                    color = [0, 0, 255, 160]  # Blue
                    method_name = "Azure AI"
                
                map_data.append({
                    "lon": loc.geocode_result.lon,
                    "lat": loc.geocode_result.lat,
                    "location": loc.original_text,
                    "method": method_name,
                    "score": loc.geocode_result.score if loc.geocode_result else 0.0,
                    "matched_name": loc.geocode_result.matched_name if loc.geocode_result else "N/A",
                    "state": loc.geocode_result.state if loc.geocode_result else "N/A",
                    "county": loc.geocode_result.county if loc.geocode_result else "N/A",
                    "color": color,
                })
        
        if map_data:
            df = pd.DataFrame(map_data)
            
            # Colors already set in map_data preparation
            
            # Create map
            view_state = pdk.ViewState(
                latitude=df["lat"].mean() if not df.empty else 7.5,
                longitude=df["lon"].mean() if not df.empty else 30.0,
                zoom=6,
                pitch=0
            )
            
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=df,
                get_position=["lon", "lat"],
                get_color="color",
                get_radius=500,
                radius_min_pixels=10,
                radius_max_pixels=50,
                pickable=True,
                auto_highlight=True,
            )
            
            tooltip = {
                "html": """
                    <b>{location}</b><br/>
                    Method: {method}<br/>
                    Matched: {matched_name}<br/>
                    Score: {score:.2f}<br/>
                    State: {state}<br/>
                    County: {county}
                """,
                "style": {
                    "backgroundColor": "steelblue",
                    "color": "white"
                }
            }
            
            # Use default OpenStreetMap style (no API token required)
            # If you have a Mapbox token, you can use: map_style="mapbox://styles/mapbox/light-v9"
            r = pdk.Deck(
                map_style=None,  # Uses default OpenStreetMap style
                initial_view_state=view_state,
                layers=[layer],
                tooltip=tooltip
            )
            
            st.pydeck_chart(r)
            
            # Legend
            st.markdown("**Legend:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("🔴 Red markers = Regex extraction")
            with col2:
                st.markdown("🟢 Green markers = Ollama extraction")
            with col3:
                st.markdown("🔵 Blue markers = Azure AI extraction")
        else:
            st.info("No geocoded locations to display on map.")
    
    with tab4:
        st.markdown("### Feedback Statistics")
        
        # Get feedback for this document
        feedback_list = db_store.get_extraction_feedback(document_hash=document_hash)
        
        if feedback_list:
            st.metric("Total Feedback Entries", len(feedback_list))
            
            # Statistics
            correct_count = sum(1 for f in feedback_list if f.get("is_correct") is True)
            incorrect_count = sum(1 for f in feedback_list if f.get("is_correct") is False)
            corrected_text_count = sum(1 for f in feedback_list if f.get("user_corrected_text"))
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Marked Correct", correct_count)
            with col2:
                st.metric("Marked Incorrect", incorrect_count)
            with col3:
                st.metric("Corrections Provided", corrected_text_count)
            
            # Feedback table
            st.markdown("**Recent Feedback:**")
            feedback_data = []
            for f in feedback_list[:20]:  # Show last 20
                feedback_data.append({
                    "Original": f["original_text"][:50] + "..." if len(f["original_text"]) > 50 else f["original_text"],
                    "Method": f["method"],
                    "Correct": "✅" if f.get("is_correct") is True else "❌" if f.get("is_correct") is False else "—",
                    "Corrected": f["user_corrected_text"][:30] + "..." if f.get("user_corrected_text") and len(f["user_corrected_text"]) > 30 else (f.get("user_corrected_text") or "—"),
                    "Timestamp": str(f["feedback_timestamp"])[:19] if f.get("feedback_timestamp") else "—"
                })
            
            if feedback_data:
                st.dataframe(pd.DataFrame(feedback_data), use_container_width=True, hide_index=True)
        else:
            st.info("No feedback has been provided for this document yet.")
            
            # Show overall pattern performance if available
            st.markdown("### Pattern Performance Statistics")
            pattern_perf = db_store.get_pattern_performance()
            if pattern_perf:
                perf_data = []
                for p in pattern_perf[:10]:  # Show top 10
                    perf_data.append({
                        "Pattern": p["pattern_string"][:60] + "..." if len(p["pattern_string"]) > 60 else p["pattern_string"],
                        "Success": p["success_count"],
                        "Failure": p["failure_count"],
                        "Success Rate": f"{p['success_rate']:.1%}"
                    })
                st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)
            else:
                st.info("No pattern performance data available yet.")

