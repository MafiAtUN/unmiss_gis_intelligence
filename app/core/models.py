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

