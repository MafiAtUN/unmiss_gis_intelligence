"""Configuration management for the geocoding application."""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
DUCKDB_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "duckdb" / "geocoder.duckdb"))
INGESTED_DIR = DATA_DIR / "ingested"

# Ensure directories exist
DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
INGESTED_DIR.mkdir(parents=True, exist_ok=True)

# Azure AI Foundry settings
AZURE_FOUNDRY_ENDPOINT: Optional[str] = os.getenv("AZURE_FOUNDRY_ENDPOINT")
AZURE_FOUNDRY_API_KEY: Optional[str] = os.getenv("AZURE_FOUNDRY_API_KEY")
AZURE_OPENAI_DEPLOYMENT: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Geocoding settings
FUZZY_THRESHOLD: float = float(os.getenv("FUZZY_THRESHOLD", "0.7"))
CENTROID_CRS: str = os.getenv("CENTROID_CRS", "EPSG:32736")  # UTM Zone 36N for South Sudan
ENABLE_AI_EXTRACTION: bool = os.getenv("ENABLE_AI_EXTRACTION", "false").lower() == "true"

# Cache settings
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "86400"))  # 24 hours

# Admin layer names
LAYER_NAMES = {
    "admin1": "admin1_state",
    "admin2": "admin2_county",
    "admin3": "admin3_payam",
    "admin4": "admin4_boma",
    "settlements": "settlements",
}

