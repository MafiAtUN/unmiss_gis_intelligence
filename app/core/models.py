"""Data models for geocoding results."""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class GeocodeResult:
    """Result of a geocoding operation."""
    input_text: str
    normalized_text: str
    resolved_layer: Optional[str] = None
    feature_id: Optional[str] = None
    matched_name: Optional[str] = None
    score: float = 0.0
    lon: Optional[float] = None
    lat: Optional[float] = None
    state: Optional[str] = None
    county: Optional[str] = None
    payam: Optional[str] = None
    boma: Optional[str] = None
    village: Optional[str] = None
    resolution_too_coarse: bool = False
    alternatives: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "input_text": self.input_text,
            "normalized_text": self.normalized_text,
            "resolved_layer": self.resolved_layer,
            "feature_id": self.feature_id,
            "matched_name": self.matched_name,
            "score": self.score,
            "lon": self.lon,
            "lat": self.lat,
            "state": self.state,
            "county": self.county,
            "payam": self.payam,
            "boma": self.boma,
            "village": self.village,
            "resolution_too_coarse": self.resolution_too_coarse,
            "alternatives": self.alternatives,
        }


@dataclass
class NameIndexEntry:
    """Entry in the name index for fast lookup."""
    layer: str
    feature_id: str
    canonical_name: str
    normalized_name: str
    alias: Optional[str] = None
    normalized_alias: Optional[str] = None
    admin_codes: Optional[Dict[str, str]] = None


@dataclass
class ExtractedLocation:
    """A location mention extracted from a document."""
    original_text: str
    context: str
    extraction_method: str  # "regex" or "ai"
    start_pos: int
    end_pos: int
    geocode_result: Optional[GeocodeResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "original_text": self.original_text,
            "context": self.context,
            "extraction_method": self.extraction_method,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "geocode_result": self.geocode_result.to_dict() if self.geocode_result else None,
        }


@dataclass
class ExtractionResult:
    """Container for all extracted locations from a document."""
    regex_locations: List[ExtractedLocation]
    ai_locations: List[ExtractedLocation]  # Azure AI locations (for backward compatibility)
    ollama_locations: List[ExtractedLocation] = None  # Ollama locations
    document_text: str = ""
    
    def __post_init__(self):
        if self.ollama_locations is None:
            self.ollama_locations = []
    
    def get_all_locations(self) -> List[ExtractedLocation]:
        """Get all locations from all methods."""
        return self.regex_locations + self.ai_locations + self.ollama_locations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "regex_locations": [loc.to_dict() for loc in self.regex_locations],
            "ai_locations": [loc.to_dict() for loc in self.ai_locations],
            "ollama_locations": [loc.to_dict() for loc in (self.ollama_locations or [])],
            "document_text": self.document_text,
        }


@dataclass
class ExtractionFeedback:
    """User feedback on an extracted location."""
    document_hash: str
    original_text: str
    extracted_text: str
    method: str  # "regex" or "ai"
    user_corrected_text: Optional[str] = None
    is_correct: Optional[bool] = None
    context_text: Optional[str] = None
    geocode_result_json: Optional[str] = None
    feedback_timestamp: Optional[datetime] = None

