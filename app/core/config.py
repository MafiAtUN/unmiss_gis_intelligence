"""Configuration management for the geocoding application."""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
# Gracefully handle permission errors (e.g., macOS security restrictions)
PROJECT_ROOT = Path(__file__).parent.parent.parent
env_path = PROJECT_ROOT / ".env"
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

# Base paths
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
ENABLE_AI_EXTRACTION: bool = os.getenv("ENABLE_AI_EXTRACTION", "true").lower() == "true"  # Enabled by default for better accuracy

# Cache settings
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "86400"))  # 24 hours

# Ollama settings (for local LLM pattern learning)
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Recommended models for M4 MacBook Pro with 24GB RAM (in order of preference):
# - llama3.2:3b (best balance: fast, efficient, ~2GB) - RECOMMENDED
# - llama3.2:1b (fastest, ~1.3GB, good for simple tasks)
# - gemma2:2b (lightweight alternative, ~1.6GB)
# - llama3:8b (you have this, works but slower, ~4.7GB)
# - mistral:7b (you have this, good quality but larger, ~4.4GB)
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")  # Default to llama3.2:3b for optimal speed/quality balance
ENABLE_OLLAMA: bool = os.getenv("ENABLE_OLLAMA", "true").lower() == "true"

# Admin layer names
LAYER_NAMES = {
    "admin1": "admin1_state",
    "admin2": "admin2_county",
    "admin3": "admin3_payam",
    "admin4": "admin4_boma",
    "settlements": "settlements",
}

# Logging settings
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR: Path = DATA_DIR / "logs"
LOG_FILE: Optional[Path] = Path(os.getenv("LOG_FILE", str(LOG_DIR / "app.log"))) if os.getenv("LOG_FILE") else LOG_DIR / "app.log"
LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10MB
LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Error tracking settings
SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
RELEASE: Optional[str] = os.getenv("RELEASE")