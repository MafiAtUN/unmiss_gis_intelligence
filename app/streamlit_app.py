"""Main Streamlit application entry point with comprehensive error handling."""
import streamlit as st
import sys
import traceback
from pathlib import Path

# Add project root to Python path to ensure imports work
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.config import DUCKDB_PATH, LOG_FILE, LOG_LEVEL
from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder
from app.utils.logging import setup_logging, log_critical, get_logger
from app.utils.error_tracking import setup_error_tracking
from app.utils.static_assets import display_logo, static_file_exists

# Setup error tracking first (before anything else can fail)
setup_error_tracking()

# Setup logging with file rotation
setup_logging(level=LOG_LEVEL, log_file=LOG_FILE)

logger = get_logger()

# Global exception handler for uncaught exceptions
def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions globally."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    log_critical(
        f"Uncaught exception: {exc_type.__name__}: {exc_value}",
        error=exc_value,
        context={
            "exception_type": exc_type.__name__,
            "traceback": ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        }
    )
    
    # Also show in Streamlit if possible
    try:
        st.error(f"❌ Critical Error: {exc_type.__name__}: {exc_value}")
        with st.expander("🔍 Critical Error Details", expanded=True):
            st.code(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)), language="python")
    except:
        pass  # Streamlit not available yet
    
    # Call default handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Set global exception handler
sys.excepthook = handle_uncaught_exception

# Initialize session state with error handling
try:
    if "db_store" not in st.session_state:
        st.session_state.db_store = DuckDBStore(DUCKDB_PATH)
        logger.info("Database store initialized")

    if "geocoder" not in st.session_state:
        st.session_state.geocoder = Geocoder(st.session_state.db_store)
        logger.info("Geocoder initialized")
except Exception as e:
    log_critical("Failed to initialize application components", error=e)
    st.error(f"❌ Failed to initialize application: {e}")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="South Sudan Geocoder",
    page_icon="📍",
    layout="wide"
)

# Display logo if available (optional - won't break if logo doesn't exist)
# Check for common logo file names
logo_files = ["logo.png", "logo.svg", "logo.jpg"]
logo_found = False
for logo_file in logo_files:
    if static_file_exists(logo_file):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            display_logo(logo_file, width=300)
        logo_found = True
        break

# Main title
st.title("📍 South Sudan Administrative Geocoder")
st.markdown("Geocode free text locations using hierarchical administrative boundaries")

