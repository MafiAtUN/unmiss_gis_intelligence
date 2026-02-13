"""Proximity analysis functions for spatial queries."""
from typing import List, Dict, Any, Optional
from shapely.geometry import Point
import math


def calculate_distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    
    Args:
        lon1: Longitude of first point
        lat1: Latitude of first point
        lon2: Longitude of second point
        lat2: Latitude of second point
        
    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth radius in kilometers
    R = 6371.0
    
    return R * c


def find_nearest_features(
    lon: float,
    lat: float,
    features: List[Dict[str, Any]],
    max_distance_km: Optional[float] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Find nearest features to a point.
    
    Args:
        lon: Longitude of query point
        lat: Latitude of query point
        features: List of feature dictionaries with 'lon' and 'lat' keys
        max_distance_km: Maximum distance in km (None = no limit)
        limit: Maximum number of results
        
    Returns:
        List of features sorted by distance, with 'distance_km' added
    """
    results = []
    
    for feature in features:
        feature_lon = feature.get("lon")
        feature_lat = feature.get("lat")
        
        if feature_lon is None or feature_lat is None:
            continue
        
        distance_km = calculate_distance_km(lon, lat, feature_lon, feature_lat)
        
        if max_distance_km is None or distance_km <= max_distance_km:
            feature_copy = feature.copy()
            feature_copy["distance_km"] = round(distance_km, 2)
            results.append(feature_copy)
    
    # Sort by distance
    results.sort(key=lambda x: x["distance_km"])
    
    return results[:limit]


def analyze_location_proximity(
    db_store,
    lon: float,
    lat: float,
    radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Analyze proximity of a location to nearby POIs and infrastructure.
    
    Args:
        db_store: DuckDBStore instance
        lon: Longitude of location
        lat: Latitude of location
        radius_km: Search radius in kilometers
        
    Returns:
        Dictionary with proximity analysis results
    """
    analysis = {
        "location": {"lon": lon, "lat": lat},
        "radius_km": radius_km,
        "hospitals": [],
        "schools": [],
        "healthcare": [],
        "unmiss_bases": [],
        "military": [],
        "airports": [],
        "idp_camps": [],
        "roads": [],
        "summary": {}
    }
    
    # Get nearby POIs by category
    categories = ["hospital", "school", "healthcare", "unmiss", "military", "airport", "idp_camp"]
    key_map = {
        "hospital": "hospitals",
        "school": "schools",
        "healthcare": "healthcare",
        "unmiss": "unmiss_bases",
        "military": "military",
        "airport": "airports",
        "idp_camp": "idp_camps",
    }
    for category in categories:
        pois = db_store.get_nearby_osm_pois(lon, lat, radius_km, [category])
        analysis[key_map.get(category, category + "s")] = pois
    
    # Get nearby roads
    roads = db_store.get_nearby_osm_roads(lon, lat, radius_km)
    analysis["roads"] = roads
    
    # Create summary
    summary = {}
    for category in categories:
        key = key_map.get(category, category + "s")
        pois_list = analysis.get(key, [])
        if pois_list:
            nearest = pois_list[0]
            summary[f"nearest_{category}"] = {
                "name": nearest.get("name", "Unknown"),
                "distance_km": nearest.get("distance_km", 0),
                "distance_miles": round(nearest.get("distance_km", 0) * 0.621371, 2)
            }
            summary[f"count_{category}"] = len(pois_list)
        else:
            summary[f"nearest_{category}"] = None
            summary[f"count_{category}"] = 0
    
    # Nearest road
    if roads:
        nearest_road = roads[0]
        summary["nearest_road"] = {
            "name": nearest_road.get("name", "Unnamed road"),
            "highway": nearest_road.get("highway", "Unknown"),
            "distance_km": nearest_road.get("distance_km", 0),
            "distance_miles": round(nearest_road.get("distance_km", 0) * 0.621371, 2)
        }
        summary["count_roads"] = len(roads)
    else:
        summary["nearest_road"] = None
        summary["count_roads"] = 0
    
    analysis["summary"] = summary
    
    return analysis

