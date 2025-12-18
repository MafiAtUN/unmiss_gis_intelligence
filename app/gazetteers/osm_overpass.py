"""OpenStreetMap Overpass API provider (optional, off by default)."""
import geopandas as gpd
from typing import List, Dict, Any, Optional
from app.gazetteers.base import GazetteerProvider


class OSMOverpassProvider(GazetteerProvider):
    """OSM Overpass API provider - disabled by default."""
    
    def __init__(self, enabled: bool = False):
        """
        Initialize OSM provider.
        
        Args:
            enabled: Whether provider is enabled (default False)
        """
        self.enabled = enabled
    
    def fetch_features(self, query: str, bbox: tuple = None) -> gpd.GeoDataFrame:
        """
        Fetch features from OSM Overpass API.
        
        Note: This is a placeholder. Implementation requires Overpass API client.
        """
        if not self.enabled:
            return gpd.GeoDataFrame()
        
        # Placeholder - would require overpy or similar library
        # For now, return empty GeoDataFrame
        return gpd.GeoDataFrame()
    
    def get_name(self) -> str:
        """Get provider name."""
        return "OSM Overpass"

