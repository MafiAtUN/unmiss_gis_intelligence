"""Base class for gazetteer providers."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import geopandas as gpd


class GazetteerProvider(ABC):
    """Base class for gazetteer data providers."""
    
    @abstractmethod
    def fetch_features(self, query: str, bbox: tuple = None) -> gpd.GeoDataFrame:
        """
        Fetch features from the gazetteer.
        
        Args:
            query: Search query
            bbox: Optional bounding box (minx, miny, maxx, maxy)
            
        Returns:
            GeoDataFrame with features
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get provider name."""
        pass

