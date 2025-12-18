"""Tests for spatial operations."""
import pytest
from shapely.geometry import Point
import geopandas as gpd
from app.core.spatial import spatial_join_point_to_polygons, get_admin_hierarchy
from app.core.centroids import compute_centroid


def test_spatial_join_point_to_polygons(sample_admin_data):
    """Test spatial join of point to polygons."""
    point = Point(31.0, 5.0)  # Inside boma polygon
    
    result = spatial_join_point_to_polygons(point, sample_admin_data["boma"])
    assert result is not None
    assert not result.empty
    
    point_outside = Point(35.0, 10.0)
    result = spatial_join_point_to_polygons(point_outside, sample_admin_data["boma"])
    assert result is None or result.empty


def test_get_admin_hierarchy(sample_admin_data):
    """Test getting admin hierarchy for a point."""
    point = Point(31.0, 5.0)  # Inside all polygons
    
    hierarchy = get_admin_hierarchy(point, {
        "admin1_state": sample_admin_data["state"],
        "admin2_county": sample_admin_data["county"],
        "admin3_payam": sample_admin_data["payam"],
        "admin4_boma": sample_admin_data["boma"],
    })
    
    assert hierarchy["state"] == "Test State"
    assert hierarchy["county"] == "Test County"
    assert hierarchy["payam"] == "Test Payam"
    assert hierarchy["boma"] == "Test Boma"


def test_compute_centroid(sample_admin_data):
    """Test centroid computation."""
    polygon = sample_admin_data["boma"].geometry.iloc[0]
    lon, lat = compute_centroid(polygon)
    
    assert isinstance(lon, float)
    assert isinstance(lat, float)
    assert 30.0 <= lon <= 32.0
    assert 4.0 <= lat <= 6.0

