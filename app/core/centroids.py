"""Centroid computation utilities for polygons."""
import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer
from typing import Tuple, Optional
from app.core.config import CENTROID_CRS


def compute_centroid(
    geometry,
    source_crs: str = "EPSG:4326",
    target_crs: Optional[str] = None
) -> Tuple[float, float]:
    """
    Compute centroid of a geometry in a projected CRS, then convert back to WGS84.
    
    Args:
        geometry: Shapely geometry object
        source_crs: Source CRS (default EPSG:4326)
        target_crs: Target CRS for centroid computation (default from config)
        
    Returns:
        Tuple of (longitude, latitude) in EPSG:4326
    """
    if geometry is None or geometry.is_empty:
        raise ValueError("Geometry is None or empty")
    
    if target_crs is None:
        target_crs = CENTROID_CRS
    
    # If already a point, return its coordinates
    if geometry.geom_type == "Point":
        return (geometry.x, geometry.y)
    
    # For polygons, compute centroid in projected CRS
    if geometry.geom_type in ["Polygon", "MultiPolygon"]:
        # Create transformer
        transformer_to_proj = Transformer.from_crs(
            source_crs, target_crs, always_xy=True
        )
        transformer_to_wgs = Transformer.from_crs(
            target_crs, source_crs, always_xy=True
        )
        
        # Transform geometry to projected CRS
        geom_proj = gpd.GeoSeries([geometry], crs=source_crs).to_crs(target_crs).iloc[0]
        
        # Compute centroid
        centroid_proj = geom_proj.centroid
        
        # Transform back to WGS84
        lon, lat = transformer_to_wgs.transform(centroid_proj.x, centroid_proj.y)
        
        return (lon, lat)
    
    # For other geometry types, use default centroid
    return (geometry.centroid.x, geometry.centroid.y)


def auto_select_utm(geometry) -> str:
    """
    Automatically select appropriate UTM zone based on geometry centroid.
    
    Args:
        geometry: Shapely geometry object
        
    Returns:
        UTM CRS string (e.g., "EPSG:32736")
    """
    if geometry is None or geometry.is_empty:
        return CENTROID_CRS
    
    centroid = geometry.centroid
    lon = centroid.x
    
    # UTM zones are 6 degrees wide, starting at -180
    # Zone number = floor((lon + 180) / 6) + 1
    zone = int((lon + 180) / 6) + 1
    
    # South Sudan is in northern hemisphere, so use 326XX series
    # But we'll use 327XX for consistency with config
    epsg_code = 32700 + zone
    
    return f"EPSG:{epsg_code}"

