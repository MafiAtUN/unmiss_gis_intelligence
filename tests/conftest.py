"""Pytest configuration and fixtures."""
import pytest
import tempfile
import shutil
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder


@pytest.fixture
def temp_db():
    """Create temporary DuckDB database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.duckdb"
    db_store = DuckDBStore(db_path)
    yield db_store
    db_store.close()
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_admin_data():
    """Create sample administrative boundary data."""
    # Sample state polygon
    state_poly = Polygon([
        (30.0, 4.0), (32.0, 4.0), (32.0, 6.0), (30.0, 6.0), (30.0, 4.0)
    ])
    
    # Sample county polygon
    county_poly = Polygon([
        (30.5, 4.5), (31.5, 4.5), (31.5, 5.5), (30.5, 5.5), (30.5, 4.5)
    ])
    
    # Sample payam polygon
    payam_poly = Polygon([
        (30.7, 4.7), (31.3, 4.7), (31.3, 5.3), (30.7, 5.3), (30.7, 4.7)
    ])
    
    # Sample boma polygon
    boma_poly = Polygon([
        (30.8, 4.8), (31.2, 4.8), (31.2, 5.2), (30.8, 5.2), (30.8, 4.8)
    ])
    
    return {
        "state": gpd.GeoDataFrame(
            [{"name": "Test State", "geometry": state_poly}],
            crs="EPSG:4326"
        ),
        "county": gpd.GeoDataFrame(
            [{"name": "Test County", "geometry": county_poly}],
            crs="EPSG:4326"
        ),
        "payam": gpd.GeoDataFrame(
            [{"name": "Test Payam", "geometry": payam_poly}],
            crs="EPSG:4326"
        ),
        "boma": gpd.GeoDataFrame(
            [{"name": "Test Boma", "geometry": boma_poly}],
            crs="EPSG:4326"
        ),
    }


@pytest.fixture
def sample_settlements():
    """Create sample settlement points."""
    settlements = [
        {"name": "Test Village", "lon": 31.0, "lat": 5.0},
        {"name": "Another Village", "lon": 30.9, "lat": 4.9},
    ]
    return pd.DataFrame(settlements)


@pytest.fixture
def populated_db(temp_db, sample_admin_data, sample_settlements):
    """Create database with sample data."""
    # Ingest admin layers
    temp_db.ingest_geojson("admin1_state", sample_admin_data["state"])
    temp_db.ingest_geojson("admin2_county", sample_admin_data["county"])
    temp_db.ingest_geojson("admin3_payam", sample_admin_data["payam"])
    temp_db.ingest_geojson("admin4_boma", sample_admin_data["boma"])
    
    # Ingest settlements
    import tempfile
    import os
    temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    sample_settlements.to_csv(temp_csv.name, index=False)
    temp_db.ingest_settlements_csv(Path(temp_csv.name))
    os.unlink(temp_csv.name)  # Clean up temp file
    
    # Build index
    temp_db.build_name_index()
    
    return temp_db


@pytest.fixture
def geocoder(populated_db):
    """Create geocoder with populated database."""
    return Geocoder(populated_db)

