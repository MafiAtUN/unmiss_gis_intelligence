"""OpenStreetMap scraper for village locations."""
import requests
import time
from typing import List, Dict, Any, Optional, Tuple
from app.core.scrapers.base import BaseScraper


class OSMScraper(BaseScraper):
    """Scraper for OpenStreetMap using Overpass API."""
    
    # South Sudan bounding box
    DEFAULT_BBOX = (23.886979, 3.48898, 35.298, 12.248008)
    
    # Overpass API endpoint (public instance)
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    
    def __init__(self, overpass_url: Optional[str] = None):
        """
        Initialize OSM scraper.
        
        Args:
            overpass_url: Overpass API URL (defaults to public instance)
        """
        super().__init__("osm")
        self.overpass_url = overpass_url or self.OVERPASS_URL
    
    def search_village(
        self,
        name: str,
        bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for villages in OSM using Overpass API.
        
        Args:
            name: Village name to search
            bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
            
        Returns:
            List of village results
        """
        if bbox is None:
            bbox = self.DEFAULT_BBOX
        
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Overpass QL query to find places with the name
        # Search for nodes and ways tagged as place=village or place=hamlet
        query = f"""
        [out:json][timeout:25];
        (
          node["place"~"^(village|hamlet|town)$"]["name"~"{name}", i]({min_lat},{min_lon},{max_lat},{max_lon});
          way["place"~"^(village|hamlet|town)$"]["name"~"{name}", i]({min_lat},{min_lon},{max_lat},{max_lon});
          relation["place"~"^(village|hamlet|town)$"]["name"~"{name}", i]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out center;
        """
        
        try:
            response = requests.post(
                self.overpass_url,
                data=query,
                headers={"Content-Type": "text/plain"},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for element in data.get("elements", []):
                # Get coordinates
                lon = None
                lat = None
                
                if element["type"] == "node":
                    lon = element.get("lon")
                    lat = element.get("lat")
                elif element["type"] in ["way", "relation"]:
                    # Use center for ways/relations
                    center = element.get("center", {})
                    lon = center.get("lon")
                    lat = center.get("lat")
                
                if lon is None or lat is None:
                    continue
                
                # Get name and properties
                tags = element.get("tags", {})
                place_name = tags.get("name", name)
                
                # Calculate confidence based on name match
                name_lower = name.lower()
                place_name_lower = place_name.lower()
                if name_lower == place_name_lower:
                    confidence = 1.0
                elif name_lower in place_name_lower or place_name_lower in name_lower:
                    confidence = 0.8
                else:
                    confidence = 0.6
                
                result = {
                    "name": place_name,
                    "lon": lon,
                    "lat": lat,
                    "source": self.name,
                    "source_id": str(element["id"]),
                    "confidence": confidence,
                    "properties": {
                        "place_type": tags.get("place"),
                        "osm_id": element["id"],
                        "osm_type": element["type"],
                        "admin_level": tags.get("admin_level"),
                        "wikidata": tags.get("wikidata"),
                        "wikipedia": tags.get("wikipedia"),
                        **{k: v for k, v in tags.items() if k not in ["name", "place"]}
                    }
                }
                
                results.append(self.normalize_result(result))
            
            # Rate limiting
            time.sleep(1)
            
            return results
        
        except requests.exceptions.RequestException as e:
            print(f"Error querying Overpass API: {e}")
            return []
        except Exception as e:
            print(f"Error parsing OSM results: {e}")
            return []
    
    def get_coordinates(self, place_id: str) -> Optional[Tuple[float, float]]:
        """
        Get coordinates for an OSM place by ID.
        
        Args:
            place_id: OSM element ID (format: "node/123" or just "123")
            
        Returns:
            Tuple of (lon, lat) or None
        """
        # Parse place_id
        parts = place_id.split("/")
        if len(parts) == 2:
            element_type = parts[0]
            element_id = parts[1]
        else:
            # Assume node if not specified
            element_type = "node"
            element_id = place_id
        
        query = f"""
        [out:json][timeout:10];
        {element_type}({element_id});
        out center;
        """
        
        try:
            response = requests.post(
                self.overpass_url,
                data=query,
                headers={"Content-Type": "text/plain"},
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            elements = data.get("elements", [])
            
            if elements:
                element = elements[0]
                if element["type"] == "node":
                    return (element.get("lon"), element.get("lat"))
                else:
                    center = element.get("center", {})
                    return (center.get("lon"), center.get("lat"))
        
        except Exception as e:
            print(f"Error getting coordinates from OSM: {e}")
        
        return None

