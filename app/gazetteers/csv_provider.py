"""CSV-based gazetteer provider for UNMISS or mission data."""
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.gazetteers.base import GazetteerProvider
from app.utils.logging import log_structured, log_error


class CSVProvider(GazetteerProvider):
    """CSV-based gazetteer provider."""
    
    def __init__(
        self,
        csv_path: Optional[Path] = None,
        lon_field: str = "lon",
        lat_field: str = "lat",
        name_field: str = "name"
    ):
        """
        Initialize CSV provider.
        
        Args:
            csv_path: Path to CSV file
            lon_field: Longitude field name
            lat_field: Latitude field name
            name_field: Name field name
        """
        self.csv_path = csv_path
        self.lon_field = lon_field
        self.lat_field = lat_field
        self.name_field = name_field
        self.gdf: Optional[gpd.GeoDataFrame] = None
        self._load_data()
    
    def _load_data(self):
        """Load data from CSV file."""
        if not self.csv_path or not self.csv_path.exists():
            return
        
        try:
            df = pd.read_csv(self.csv_path)
            
            # Validate required fields
            if self.lon_field not in df.columns or self.lat_field not in df.columns:
                log_structured("warning", "CSV missing required fields", 
                             module="csv_provider", function="_load_data",
                             lon_field=self.lon_field, lat_field=self.lat_field,
                             csv_path=str(self.csv_path))
                return
            
            # Create geometry
            geometry = [
                Point(lon, lat)
                for lon, lat in zip(df[self.lon_field], df[self.lat_field])
            ]
            
            self.gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
            log_structured("info", "CSV data loaded successfully",
                         module="csv_provider", function="_load_data",
                         row_count=len(self.gdf), csv_path=str(self.csv_path))
            
        except Exception as e:
            log_error(e, {"module": "csv_provider", "function": "_load_data", 
                         "csv_path": str(self.csv_path)})
            self.gdf = gpd.GeoDataFrame()
    
    def fetch_features(self, query: str, bbox: tuple = None) -> gpd.GeoDataFrame:
        """Fetch features matching query."""
        if self.gdf is None or self.gdf.empty:
            return gpd.GeoDataFrame()
        
        # Filter by query
        query_lower = query.lower()
        if self.name_field in self.gdf.columns:
            mask = self.gdf[self.name_field].str.lower().str.contains(query_lower, na=False)
            result = self.gdf[mask].copy()
        else:
            result = self.gdf.copy()
        
        # Filter by bbox if provided
        if bbox and not result.empty:
            minx, miny, maxx, maxy = bbox
            result = result.cx[minx:maxx, miny:maxy]
        
        return result
    
    def get_name(self) -> str:
        """Get provider name."""
        return "CSV Gazetteer"

