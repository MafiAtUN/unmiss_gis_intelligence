"""OpenStreetMap data extractor for roads, POIs, and infrastructure."""
import requests
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import transform
import geopandas as gpd
from app.utils.logging import log_error, log_structured


class OSMDataExtractor:
    """Extract roads, POIs, and infrastructure from OpenStreetMap using Overpass API."""
    
    # South Sudan bounding box (min_lon, min_lat, max_lon, max_lat)
    SOUTH_SUDAN_BBOX = (23.886979, 3.48898, 35.298, 12.248008)
    
    # Overpass API endpoint (public instance)
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    
    # POI categories with their OSM tags
    POI_CATEGORIES = {
        "hospital": {
            "tags": [
                {"amenity": "hospital"},
                {"healthcare": "hospital"},
                {"amenity": "clinic"},
                {"healthcare": "clinic"},
                {"amenity": "health_centre"},
                {"healthcare": "centre"},
            ],
            "color": [255, 0, 0, 200]  # Red
        },
        "school": {
            "tags": [
                {"amenity": "school"},
                {"amenity": "university"},
                {"amenity": "college"},
                {"amenity": "kindergarten"},
            ],
            "color": [0, 0, 255, 200]  # Blue
        },
        "healthcare": {
            "tags": [
                {"healthcare": "doctor"},
                {"healthcare": "pharmacy"},
                {"amenity": "pharmacy"},
                {"healthcare": "dentist"},
                {"healthcare": "optometrist"},
            ],
            "color": [255, 128, 0, 200]  # Orange
        },
        "unmiss": {
            "tags": [
                {"office": "government", "name": "~UNMISS"},
                {"military": "barracks", "name": "~UNMISS"},
                {"office": "ngo", "name": "~UNMISS"},
                {"amenity": "*", "name": "~UNMISS"},
            ],
            "color": [0, 255, 0, 200]  # Green
        },
        "military": {
            "tags": [
                {"military": "barracks"},
                {"military": "airfield"},
                {"military": "base"},
                {"military": "checkpoint"},
                {"military": "range"},
                {"landuse": "military"},
                {"barrier": "checkpoint"},
            ],
            "color": [139, 69, 19, 200]  # Brown
        },
        "airport": {
            "tags": [
                {"aeroway": "aerodrome"},
                {"aeroway": "airport"},
                {"aeroway": "helipad"},
                {"aeroway": "airfield"},
                {"military": "airfield"},
            ],
            "color": [255, 192, 203, 200]  # Pink
        },
        "government": {
            "tags": [
                {"office": "government"},
                {"amenity": "townhall"},
                {"building": "government"},
            ],
            "color": [128, 128, 128, 200]  # Gray
        },
        "police": {
            "tags": [
                {"amenity": "police"},
                {"office": "administrative", "name": "~police"},
            ],
            "color": [0, 0, 139, 200]  # Dark Blue
        },
        "prison": {
            "tags": [
                {"amenity": "prison"},
                {"amenity": "jail"},
            ],
            "color": [75, 0, 130, 200]  # Indigo
        },
        "court": {
            "tags": [
                {"amenity": "courthouse"},
                {"office": "administrative", "name": "~court"},
            ],
            "color": [160, 82, 45, 200]  # Sienna
        },
        "idp_camp": {
            "tags": [
                {"amenity": "refugee_site"},
                {"place": "locality", "name": "~camp"},
                {"place": "locality", "name": "~IDP"},
                {"landuse": "residential", "name": "~camp"},
            ],
            "color": [255, 165, 0, 200]  # Orange
        },
        "border": {
            "tags": [
                {"barrier": "border_control"},
                {"amenity": "customs"},
            ],
            "color": [255, 20, 147, 200]  # Deep Pink
        },
        "checkpoint": {
            "tags": [
                {"barrier": "checkpoint"},
                {"highway": "checkpoint"},
                {"military": "checkpoint"},
            ],
            "color": [220, 20, 60, 200]  # Crimson
        },
        "water": {
            "tags": [
                {"amenity": "water_point"},
                {"amenity": "drinking_water"},
                {"man_made": "water_well"},
            ],
            "color": [0, 128, 255, 200]  # Light Blue
        },
        "market": {
            "tags": [
                {"amenity": "marketplace"},
                {"shop": "*"},
            ],
            "color": [255, 255, 0, 200]  # Yellow
        },
        "religious": {
            "tags": [
                {"amenity": "place_of_worship"},
                {"building": "church"},
                {"building": "mosque"},
            ],
            "color": [128, 0, 128, 200]  # Purple
        },
        "bank": {
            "tags": [
                {"amenity": "bank"},
                {"amenity": "atm"},
            ],
            "color": [34, 139, 34, 200]  # Forest Green
        },
        "communication": {
            "tags": [
                {"man_made": "tower", "tower:type": "*"},
                {"man_made": "mast"},
                {"communication": "*"},
            ],
            "color": [192, 192, 192, 200]  # Silver
        },
        "power": {
            "tags": [
                {"power": "station"},
                {"power": "substation"},
                {"power": "generator"},
            ],
            "color": [255, 215, 0, 200]  # Gold
        },
        "fuel": {
            "tags": [
                {"amenity": "fuel"},
                {"amenity": "gas_station"},
            ],
            "color": [255, 69, 0, 200]  # Red Orange
        },
        "ngo": {
            "tags": [
                {"office": "ngo"},
                {"office": "charity"},
                {"amenity": "*", "operator": "~NGO"},
                {"amenity": "*", "operator": "~UN"},
            ],
            "color": [0, 191, 255, 200]  # Deep Sky Blue
        },
    }
    
    def __init__(self, overpass_url: Optional[str] = None):
        """
        Initialize OSM data extractor.
        
        Args:
            overpass_url: Overpass API URL (defaults to public instance)
        """
        self.overpass_url = overpass_url or self.OVERPASS_URL
    
    def build_overpass_query(
        self,
        feature_types: List[str],
        bbox: Optional[Tuple[float, float, float, float]] = None,
        include_roads: bool = True
    ) -> str:
        """
        Build Overpass QL query for extracting features.
        
        Args:
            feature_types: List of POI categories to extract (e.g., ["hospital", "school"])
            bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
            include_roads: Whether to include roads
            
        Returns:
            Overpass QL query string
        """
        if bbox is None:
            bbox = self.SOUTH_SUDAN_BBOX
        
        min_lon, min_lat, max_lon, max_lat = bbox
        
        query_parts = ["[out:json][timeout:300];", "("]
        
        # Add roads if requested
        if include_roads:
            query_parts.append(
                f'way["highway"]["highway"!~"^(footway|path|cycleway|steps)$"]({min_lat},{min_lon},{max_lat},{max_lon});'
            )
        
        # Add POI categories
        for category in feature_types:
            if category in self.POI_CATEGORIES:
                for tag_filter in self.POI_CATEGORIES[category]["tags"]:
                    tag_key = list(tag_filter.keys())[0]
                    tag_value = tag_filter[tag_key]
                    
                    if tag_value == "*":
                        # Match any value for this key
                        query_parts.append(
                            f'node["{tag_key}"]({min_lat},{min_lon},{max_lat},{max_lon});'
                        )
                        query_parts.append(
                            f'way["{tag_key}"]({min_lat},{min_lon},{max_lat},{max_lon});'
                        )
                    elif tag_value.startswith("~"):
                        # Regex match (case-insensitive)
                        pattern = tag_value[1:]
                        query_parts.append(
                            f'node["{tag_key}"~"{pattern}",i]({min_lat},{min_lon},{max_lat},{max_lon});'
                        )
                        query_parts.append(
                            f'way["{tag_key}"~"{pattern}",i]({min_lat},{min_lon},{max_lat},{max_lon});'
                        )
                    else:
                        # Exact match
                        query_parts.append(
                            f'node["{tag_key}"="{tag_value}"]({min_lat},{min_lon},{max_lat},{max_lon});'
                        )
                        query_parts.append(
                            f'way["{tag_key}"="{tag_value}"]({min_lat},{min_lon},{max_lat},{max_lon});'
                        )
        
        query_parts.append(");")
        query_parts.append("out body geom;")
        
        return "\n".join(query_parts)
    
    def extract_features(
        self,
        feature_types: Optional[List[str]] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        include_roads: bool = True
    ) -> Dict[str, gpd.GeoDataFrame]:
        """
        Extract features from OSM.
        
        Args:
            feature_types: List of POI categories (None = all)
            bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
            include_roads: Whether to include roads
            
        Returns:
            Dictionary mapping category names to GeoDataFrames
        """
        if feature_types is None:
            feature_types = list(self.POI_CATEGORIES.keys())
        
        # Build query
        query = self.build_overpass_query(feature_types, bbox, include_roads)
        
        log_structured("info", "Starting OSM data extraction",
            feature_types=feature_types,
            include_roads=include_roads,
            bbox=bbox
        )
        
        try:
            # Execute query
            response = requests.post(
                self.overpass_url,
                data=query,
                headers={"Content-Type": "text/plain"},
                timeout=600  # 10 minutes timeout for large queries
            )
            response.raise_for_status()
            
            data = response.json()
            elements = data.get("elements", [])
            
            log_structured("info", "OSM query completed",
                element_count=len(elements)
            )
            
            # Process elements
            results = {
                "roads": [],
            }
            for category in feature_types:
                results[category] = []
            
            # Process each element
            for element in elements:
                element_type = element.get("type")
                tags = element.get("tags", {})
                
                # Determine category
                category = None
                if element_type == "way" and "highway" in tags:
                    category = "roads"
                else:
                    # Check POI categories
                    for cat_name, cat_config in self.POI_CATEGORIES.items():
                        if cat_name in feature_types:
                            for tag_filter in cat_config["tags"]:
                                # Check if all tag conditions in this filter match
                                all_match = True
                                for tag_key, tag_value in tag_filter.items():
                                    if tag_key not in tags:
                                        all_match = False
                                        break
                                    
                                    if tag_value == "*":
                                        # Match any value
                                        continue
                                    elif tag_value.startswith("~"):
                                        # Regex match
                                        pattern = tag_value[1:]
                                        import re
                                        if not re.search(pattern, tags[tag_key], re.IGNORECASE):
                                            all_match = False
                                            break
                                    else:
                                        # Exact match
                                        if tags[tag_key] != tag_value:
                                            all_match = False
                                            break
                                
                                if all_match:
                                    category = cat_name
                                    break
                            
                            if category:
                                break
                
                if category is None:
                    continue
                
                # Extract geometry
                geometry = None
                lon = None
                lat = None
                
                if element_type == "node":
                    lon = element.get("lon")
                    lat = element.get("lat")
                    if lon is not None and lat is not None:
                        geometry = Point(lon, lat)
                elif element_type == "way":
                    nodes = element.get("geometry", [])
                    if nodes:
                        coords = [(node.get("lon"), node.get("lat")) for node in nodes]
                        coords = [(lon, lat) for lon, lat in coords if lon is not None and lat is not None]
                        if len(coords) >= 2:
                            geometry = LineString(coords)
                        elif len(coords) == 1:
                            geometry = Point(coords[0])
                
                if geometry is None:
                    continue
                
                # Create feature record
                feature = {
                    "osm_id": element.get("id"),
                    "osm_type": element_type,
                    "name": tags.get("name", ""),
                    "category": category,
                    "geometry": geometry,
                    "tags": json.dumps(tags),
                    "properties": tags.copy(),
                }
                
                # Add specific fields based on category
                if category == "roads":
                    feature["highway"] = tags.get("highway", "")
                    feature["surface"] = tags.get("surface", "")
                    feature["name"] = tags.get("name", "")
                elif category in ["hospital", "healthcare"]:
                    feature["amenity"] = tags.get("amenity", "")
                    feature["healthcare"] = tags.get("healthcare", "")
                
                # Add coordinates for points
                if isinstance(geometry, Point):
                    feature["lon"] = geometry.x
                    feature["lat"] = geometry.y
                else:
                    # Use centroid for lines/polygons
                    centroid = geometry.centroid
                    feature["lon"] = centroid.x
                    feature["lat"] = centroid.y
                
                results[category].append(feature)
            
            # Convert to GeoDataFrames
            gdfs = {}
            for category, features in results.items():
                if features:
                    try:
                        gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
                        gdfs[category] = gdf
                        log_structured("info", f"Extracted {category} features",
                            category=category,
                            count=len(gdf)
                        )
                    except Exception as e:
                        log_error(e, {
                            "module": "osm_data_extractor",
                            "function": "extract_features",
                            "category": category
                        })
            
            # Rate limiting
            time.sleep(2)
            
            return gdfs
            
        except requests.exceptions.RequestException as e:
            log_error(e, {
                "module": "osm_data_extractor",
                "function": "extract_features",
                "feature_types": feature_types
            })
            return {}
        except Exception as e:
            log_error(e, {
                "module": "osm_data_extractor",
                "function": "extract_features",
                "feature_types": feature_types
            })
            return {}
    
    def get_category_color(self, category: str) -> List[int]:
        """Get color for a category."""
        if category == "roads":
            return [100, 100, 100, 200]  # Gray for roads
        elif category in self.POI_CATEGORIES:
            return self.POI_CATEGORIES[category]["color"]
        return [128, 128, 128, 200]  # Default gray

