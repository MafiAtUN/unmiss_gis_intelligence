"""Base scraper class for village location data."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class BaseScraper(ABC):
    """Base class for village location scrapers."""
    
    def __init__(self, name: str):
        """
        Initialize scraper.
        
        Args:
            name: Name of the scraper (e.g., 'osm', 'google_maps')
        """
        self.name = name
    
    @abstractmethod
    def search_village(
        self,
        name: str,
        bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for a village by name.
        
        Args:
            name: Village name to search for
            bbox: Optional bounding box (min_lon, min_lat, max_lon, max_lat)
            
        Returns:
            List of results, each with keys:
            - name: Village name
            - lon: Longitude
            - lat: Latitude
            - source: Source identifier
            - source_id: Source-specific ID
            - confidence: Confidence score (0.0-1.0)
            - properties: Additional properties dict
        """
        pass
    
    @abstractmethod
    def get_coordinates(self, place_id: str) -> Optional[Tuple[float, float]]:
        """
        Get coordinates for a place by its source ID.
        
        Args:
            place_id: Source-specific place ID
            
        Returns:
            Tuple of (lon, lat) or None if not found
        """
        pass
    
    def normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a search result to standard format.
        
        Args:
            result: Raw result from scraper
            
        Returns:
            Normalized result dict
        """
        return {
            "name": result.get("name", ""),
            "lon": result.get("lon"),
            "lat": result.get("lat"),
            "source": self.name,
            "source_id": result.get("source_id"),
            "confidence": result.get("confidence", 0.5),
            "properties": result.get("properties", {})
        }

