"""GeoNames gazetteer provider using local export files."""
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.gazetteers.base import GazetteerProvider
from app.utils.logging import log_error


class GeoNamesProvider(GazetteerProvider):
    """GeoNames provider using local TSV export files."""
    
    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize GeoNames provider.
        
        Args:
            data_path: Path to GeoNames TSV file (allCountries.txt or SS.txt)
        """
        self.data_path = data_path
        self.gdf: Optional[gpd.GeoDataFrame] = None
        self._load_data()
    
    def _load_data(self):
        """Load GeoNames data from TSV file."""
        if not self.data_path or not self.data_path.exists():
            return
        
        # GeoNames TSV format:
        # geonameid, name, asciiname, alternatenames, latitude, longitude,
        # feature class, feature code, country code, cc2, admin1, admin2, admin3, admin4,
        # population, elevation, dem, timezone, modification date
        try:
            df = pd.read_csv(
                self.data_path,
                sep="\t",
                header=None,
                names=[
                    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
                    "feature_class", "feature_code", "country_code", "cc2", "admin1", "admin2",
                    "admin3", "admin4", "population", "elevation", "dem", "timezone", "modification_date"
                ],
                low_memory=False
            )
            
            # Filter for South Sudan (SS)
            df = df[df["country_code"] == "SS"]
            
            # Create geometry
            geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
            
            self.gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
            
        except Exception as e:
            log_error(e, {
                "module": "geonames",
                "function": "_load_data",
                "data_path": str(self.data_path) if self.data_path else None
            })
            self.gdf = gpd.GeoDataFrame()
    
    def fetch_features(self, query: str, bbox: tuple = None) -> gpd.GeoDataFrame:
        """Fetch features matching query."""
        if self.gdf is None or self.gdf.empty:
            return gpd.GeoDataFrame()
        
        # Filter by query (simple name matching)
        query_lower = query.lower()
        mask = (
            self.gdf["name"].str.lower().str.contains(query_lower, na=False) |
            self.gdf["asciiname"].str.lower().str.contains(query_lower, na=False) |
            self.gdf["alternatenames"].str.lower().str.contains(query_lower, na=False)
        )
        
        result = self.gdf[mask].copy()
        
        # Filter by bbox if provided
        if bbox and not result.empty:
            minx, miny, maxx, maxy = bbox
            result = result.cx[minx:maxx, miny:maxy]
        
        return result
    
    def get_name(self) -> str:
        """Get provider name."""
        return "GeoNames"

