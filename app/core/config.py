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
AZURE_FOUNDRY_PROJECT_ENDPOINT: Optional[str] = os.getenv("AZURE_FOUNDRY_PROJECT_ENDPOINT")
AZURE_FOUNDRY_API_KEY: Optional[str] = os.getenv("AZURE_FOUNDRY_API_KEY")
AZURE_OPENAI_DEPLOYMENT: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION: Optional[str] = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# UNMISS AI Foundry deployment names (all available models)
AZURE_UNMISS_DEPLOYMENT_GPT41_MINI: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_GPT41_MINI", "gpt-4.1-mini")
AZURE_UNMISS_DEPLOYMENT_ROUTER: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_ROUTER", "model-router")
AZURE_UNMISS_DEPLOYMENT_GPT52: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_GPT52", "gpt-5.2-chat")
AZURE_UNMISS_DEPLOYMENT_GPT41: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_GPT41", "gpt-4.1")
AZURE_UNMISS_DEPLOYMENT_CLAUDE_OPUS: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_CLAUDE_OPUS", "claude-opus-4-1")
AZURE_UNMISS_DEPLOYMENT_CLAUDE_SONNET: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_CLAUDE_SONNET", "claude-sonnet-4-5")
AZURE_UNMISS_DEPLOYMENT_GROK: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_GROK", "grok-3-mini")
AZURE_UNMISS_DEPLOYMENT_LLAMA: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_LLAMA", "Llama-4-Maverick-17B-128E-Instruct-FP8")
AZURE_UNMISS_DEPLOYMENT_EMBEDDINGS: Optional[str] = os.getenv("AZURE_UNMISS_DEPLOYMENT_EMBEDDINGS", "text-embedding-3-large")

# All UNMISS deployments as a dictionary for easy access
UNMISS_DEPLOYMENTS = {
    "gpt-4.1-mini": AZURE_UNMISS_DEPLOYMENT_GPT41_MINI,
    "model-router": AZURE_UNMISS_DEPLOYMENT_ROUTER,
    "gpt-5.2-chat": AZURE_UNMISS_DEPLOYMENT_GPT52,
    "gpt-4.1": AZURE_UNMISS_DEPLOYMENT_GPT41,
    "claude-opus-4-1": AZURE_UNMISS_DEPLOYMENT_CLAUDE_OPUS,
    "claude-sonnet-4-5": AZURE_UNMISS_DEPLOYMENT_CLAUDE_SONNET,
    "grok-3-mini": AZURE_UNMISS_DEPLOYMENT_GROK,
    "llama": AZURE_UNMISS_DEPLOYMENT_LLAMA,
    "embeddings": AZURE_UNMISS_DEPLOYMENT_EMBEDDINGS,
}

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

