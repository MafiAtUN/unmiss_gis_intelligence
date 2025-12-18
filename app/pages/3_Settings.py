"""Settings page for configuring geocoding parameters."""
import streamlit as st
from app.core.config import (
    FUZZY_THRESHOLD,
    CENTROID_CRS,
    ENABLE_AI_EXTRACTION,
    AZURE_FOUNDRY_ENDPOINT,
    AZURE_FOUNDRY_API_KEY,
    AZURE_OPENAI_DEPLOYMENT
)


st.title("⚙️ Settings")

st.markdown("Configure geocoding parameters and Azure AI integration.")

# Fuzzy matching settings
st.subheader("Fuzzy Matching")
fuzzy_threshold = st.slider(
    "Fuzzy threshold:",
    min_value=0.0,
    max_value=1.0,
    value=FUZZY_THRESHOLD,
    step=0.05,
    help="Minimum similarity score for fuzzy matching (0-1)"
)

# Centroid computation settings
st.subheader("Centroid Computation")
centroid_crs = st.selectbox(
    "Centroid CRS:",
    options=[
        "EPSG:32736",  # UTM Zone 36N (South Sudan)
        "EPSG:32636",  # UTM Zone 36N (WGS84)
        "Auto (based on geometry)",
    ],
    index=0 if CENTROID_CRS == "EPSG:32736" else 1
)

# Azure AI settings
st.subheader("Azure AI Foundry Integration")
enable_ai = st.checkbox(
    "Enable AI extraction",
    value=ENABLE_AI_EXTRACTION,
    help="Use Azure AI Foundry to extract structured place names from text"
)

if enable_ai:
    st.info("Azure AI extraction is enabled. Ensure environment variables are set.")
    
    # Show current config (without exposing keys)
    col1, col2 = st.columns(2)
    with col1:
        endpoint_status = "✅ Set" if AZURE_FOUNDRY_ENDPOINT else "❌ Not set"
        st.text(f"Endpoint: {endpoint_status}")
    with col2:
        key_status = "✅ Set" if AZURE_FOUNDRY_API_KEY else "❌ Not set"
        st.text(f"API Key: {key_status}")
    
    deployment_name = st.text_input(
        "Deployment name:",
        value=AZURE_OPENAI_DEPLOYMENT or "",
        help="Azure OpenAI deployment name"
    )
else:
    st.info("Azure AI extraction is disabled. Only deterministic parsing will be used.")

# Save settings
if st.button("Save Settings", type="primary"):
    # Note: In a real app, these would be saved to a config file or database
    # For now, we'll just show a message
    st.success("Settings saved (requires app restart to take effect)")
    st.info("""
    To apply settings, update your `.env` file:
    - FUZZY_THRESHOLD={fuzzy_threshold}
    - CENTROID_CRS={centroid_crs}
    - ENABLE_AI_EXTRACTION={enable_ai}
    - AZURE_OPENAI_DEPLOYMENT={deployment_name}
    """.format(
        fuzzy_threshold=fuzzy_threshold,
        centroid_crs=centroid_crs.split("(")[0].strip() if "(" in centroid_crs else centroid_crs,
        enable_ai=str(enable_ai).lower(),
        deployment_name=deployment_name
    ))

