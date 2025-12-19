"""Spatial operations for geocoding."""
import geopandas as gpd
from shapely.geometry import Point
from typing import Dict, Optional, List
from pathlib import Path
from app.core.centroids import compute_centroid
from app.core.config import PROJECT_ROOT


def spatial_join_point_to_polygons(
    point: Point,
    polygons_gdf: gpd.GeoDataFrame,
    crs: str = "EPSG:4326"
) -> Optional[gpd.GeoDataFrame]:
    """
    Perform spatial join of a point to polygons.
    
    Args:
        point: Shapely Point geometry
        polygons_gdf: GeoDataFrame with polygon geometries
        crs: CRS string
        
    Returns:
        GeoDataFrame with matching polygons or None
    """
    if polygons_gdf.empty:
        return None
    
    # Create point GeoDataFrame
    point_gdf = gpd.GeoDataFrame(
        [{"geometry": point}],
        crs=crs
    )
    
    # Ensure both are in same CRS
    if polygons_gdf.crs != crs:
        polygons_gdf = polygons_gdf.to_crs(crs)
    
    # Perform spatial join
    joined = gpd.sjoin(point_gdf, polygons_gdf, how="inner", predicate="within")
    
    return joined if not joined.empty else None


def get_admin_hierarchy(
    point: Point,
    admin_layers: Dict[str, gpd.GeoDataFrame],
    crs: str = "EPSG:4326"
) -> Dict[str, Optional[str]]:
    """
    Get administrative hierarchy for a point by spatial join.
    
    Args:
        point: Shapely Point geometry
        admin_layers: Dictionary mapping layer names to GeoDataFrames
        crs: CRS string
        
    Returns:
        Dictionary with state, county, payam, boma keys and matched names
    """
    hierarchy = {
        "state": None,
        "county": None,
        "payam": None,
        "boma": None,
    }
    
    # Join order: boma -> payam -> county -> state
    layer_order = ["admin4_boma", "admin3_payam", "admin2_county", "admin1_state"]
    layer_map = {
        "admin4_boma": "boma",
        "admin3_payam": "payam",
        "admin2_county": "county",
        "admin1_state": "state",
    }
    
    for layer_name in layer_order:
        if layer_name not in admin_layers:
            continue
        
        gdf = admin_layers[layer_name]
        if gdf.empty:
            continue
        
        joined = spatial_join_point_to_polygons(point, gdf, crs)
        if joined is not None and not joined.empty:
            # Get the first match (should be only one for point-in-polygon)
            match = joined.iloc[0]
            # Try to find name field
            name_field = None
            for field in ["name", "NAME", "Name", "admin4Name", "admin3Name", "admin2Name", "admin1Name"]:
                if field in match:
                    name_field = field
                    break
            
            if name_field:
                hierarchy[layer_map[layer_name]] = match[name_field]
            elif "name" in gdf.columns:
                # Fallback: use the name from the original gdf if available
                # Get feature_id from joined result
                if "feature_id" in joined.columns:
                    feature_id = match.get("feature_id")
                    if feature_id and feature_id in gdf.index:
                        hierarchy[layer_map[layer_name]] = gdf.loc[feature_id, "name"]
    
    return hierarchy


def verify_point_containment(
    point: Point,
    polygon_gdf: gpd.GeoDataFrame,
    feature_id: str,
    crs: str = "EPSG:4326"
) -> bool:
    """
    Verify that a point is contained within a specific polygon feature.
    
    Args:
        point: Shapely Point geometry
        polygon_gdf: GeoDataFrame with polygon geometries
        feature_id: ID of the feature to check
        crs: CRS string
        
    Returns:
        True if point is contained, False otherwise
    """
    if polygon_gdf.empty:
        return False
    
    # Filter by feature_id - check if feature_id is in index or in a column
    if "feature_id" in polygon_gdf.columns:
        feature = polygon_gdf[polygon_gdf["feature_id"] == feature_id]
    elif feature_id in polygon_gdf.index:
        feature = polygon_gdf.loc[[feature_id]]
    else:
        return False
    
    if feature.empty:
        return False
    
    # Ensure same CRS
    if polygon_gdf.crs != crs:
        polygon_gdf = polygon_gdf.to_crs(crs)
        feature = feature.to_crs(crs)
    
    # Check containment
    return feature.geometry.iloc[0].contains(point) or feature.geometry.iloc[0].touches(point)


def detect_admin_boundaries_from_point(
    point: Point,
    boma_geojson_path: Optional[Path] = None,
    crs: str = "EPSG:4326"
) -> Dict[str, Optional[str]]:
    """
    Detect administrative boundaries (state, county, payam, boma) for a point
    by performing spatial join with Boma GeoJSON polygons.
    
    Args:
        point: Shapely Point geometry (lon, lat)
        boma_geojson_path: Path to Boma GeoJSON file (defaults to resources/GeoJSON/SS_Boma_GeoJSON.geojson)
        crs: CRS string
        
    Returns:
        Dictionary with keys: state, county, payam, boma, state_id, county_id, payam_id, boma_id
    """
    if boma_geojson_path is None:
        boma_geojson_path = PROJECT_ROOT / "resources" / "GeoJSON" / "SS_Boma_GeoJSON.geojson"
    
    if not boma_geojson_path.exists():
        return {
            "state": None,
            "county": None,
            "payam": None,
            "boma": None,
            "state_id": None,
            "county_id": None,
            "payam_id": None,
            "boma_id": None
        }
    
    # Load Boma GeoJSON
    try:
        boma_gdf = gpd.read_file(boma_geojson_path)
        
        # Ensure CRS is correct
        if boma_gdf.crs != crs:
            boma_gdf = boma_gdf.to_crs(crs)
        
        # Perform spatial join
        joined = spatial_join_point_to_polygons(point, boma_gdf, crs)
        
        if joined is not None and not joined.empty:
            match = joined.iloc[0]
            
            # Extract admin boundaries from properties
            # Based on the GeoJSON structure: STATE, COUNTY, PAYAM, BOMA
            # Also try different field name variations
            state = None
            county = None
            payam = None
            boma = None
            state_id = None
            county_id = None
            payam_id = None
            boma_id = None
            
            # Try to find fields with various naming conventions
            for field in ["STATE", "state", "State", "admin1_state", "admin1Name"]:
                if field in match:
                    state = match[field]
                    break
            
            for field in ["COUNTY", "county", "County", "admin2_county", "admin2Name"]:
                if field in match:
                    county = match[field]
                    break
            
            for field in ["PAYAM", "payam", "Payam", "admin3_payam", "admin3Name"]:
                if field in match:
                    payam = match[field]
                    break
            
            for field in ["BOMA", "boma", "Boma", "admin4_boma", "admin4Name"]:
                if field in match:
                    boma = match[field]
                    break
            
            # Try to find IDs/codes
            for field in ["STA_CODE", "state_code", "state_id", "STATE_ID"]:
                if field in match:
                    state_id = str(match[field])
                    break
            
            for field in ["CTY_CODE", "county_code", "county_id", "COUNTY_ID"]:
                if field in match:
                    county_id = str(match[field])
                    break
            
            for field in ["PAY_CODE", "payam_code", "payam_id", "PAYAM_ID"]:
                if field in match:
                    payam_id = str(match[field])
                    break
            
            for field in ["BOM_CODE", "boma_code", "boma_id", "BOMA_ID", "OBJECTID"]:
                if field in match:
                    boma_id = str(match[field])
                    break
            
            return {
                "state": state,
                "county": county,
                "payam": payam,
                "boma": boma,
                "state_id": state_id,
                "county_id": county_id,
                "payam_id": payam_id,
                "boma_id": boma_id
            }
    
    except Exception as e:
        # Log error but return empty dict
        print(f"Error detecting admin boundaries: {e}")
    
    return {
        "state": None,
        "county": None,
        "payam": None,
        "boma": None,
        "state_id": None,
        "county_id": None,
        "payam_id": None,
        "boma_id": None
    }

