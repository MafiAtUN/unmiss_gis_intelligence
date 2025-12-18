"""DuckDB storage layer for geocoding data."""
import duckdb
from pathlib import Path
from typing import List, Dict, Optional, Any
import geopandas as gpd
from shapely import wkb
import json
from datetime import datetime
from app.core.config import DUCKDB_PATH, LAYER_NAMES


class DuckDBStore:
    """DuckDB storage manager for geocoding data."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize DuckDB connection.
        
        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = db_path or DUCKDB_PATH
        self.conn = duckdb.connect(str(self.db_path))
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema."""
        # Admin layers
        for layer_name in LAYER_NAMES.values():
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {layer_name} (
                    feature_id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    geometry_wkb BLOB,
                    geometry_geojson TEXT,
                    centroid_lon DOUBLE,
                    centroid_lat DOUBLE,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Name index
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS name_index (
                id INTEGER PRIMARY KEY,
                layer VARCHAR,
                feature_id VARCHAR,
                canonical_name VARCHAR,
                normalized_name VARCHAR,
                alias VARCHAR,
                normalized_alias VARCHAR,
                admin_codes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # DuckDB auto-increments INTEGER PRIMARY KEY
        
        # Geocode cache
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS geocode_cache (
                id INTEGER PRIMARY KEY,
                input_text VARCHAR,
                normalized_text VARCHAR,
                resolved_layer VARCHAR,
                feature_id VARCHAR,
                matched_name VARCHAR,
                score DOUBLE,
                lon DOUBLE,
                lat DOUBLE,
                state VARCHAR,
                county VARCHAR,
                payam VARCHAR,
                boma VARCHAR,
                village VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_name_index_layer ON name_index(layer)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_name_index_normalized ON name_index(normalized_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_normalized ON geocode_cache(normalized_text)")
        
        # DuckDB is autocommit, no need for commit()
    
    def ingest_geojson(
        self,
        layer_name: str,
        gdf: gpd.GeoDataFrame,
        name_field: str = "name"
    ):
        """
        Ingest GeoJSON data into DuckDB.
        
        Args:
            layer_name: Name of the layer (must be in LAYER_NAMES)
            gdf: GeoDataFrame to ingest
            name_field: Field name containing feature names
        """
        if layer_name not in LAYER_NAMES.values():
            raise ValueError(f"Unknown layer name: {layer_name}")
        
        # Ensure WGS84
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        # Clear existing data
        self.conn.execute(f"DELETE FROM {layer_name}")
        
        # Prepare data
        from app.core.centroids import compute_centroid
        
        rows = []
        for idx, row in gdf.iterrows():
            # Try to get feature_id from row, otherwise use index
            if "feature_id" in row:
                feature_id = str(row["feature_id"])
            elif "id" in row:
                feature_id = str(row["id"])
            else:
                feature_id = str(idx)
            name = row.get(name_field, "")
            geometry = row.geometry
            
            # Convert to WKB
            geometry_wkb = wkb.dumps(geometry, hex=True)
            
            # Create GeoJSON feature
            feature_dict = {
                "type": "Feature",
                "geometry": json.loads(gpd.GeoSeries([geometry]).to_json())["features"][0]["geometry"],
                "properties": {k: str(v) for k, v in row.items() if k != "geometry"}
            }
            geometry_geojson = json.dumps(feature_dict)
            
            # Compute centroid for polygons
            centroid_lon, centroid_lat = None, None
            if geometry.geom_type in ["Polygon", "MultiPolygon"]:
                try:
                    centroid_lon, centroid_lat = compute_centroid(geometry)
                except Exception:
                    pass
            
            properties = json.dumps({k: str(v) for k, v in row.items() if k != "geometry"})
            
            rows.append((
                feature_id,
                name,
                geometry_wkb,
                geometry_geojson,
                centroid_lon,
                centroid_lat,
                properties,
                datetime.now()
            ))
        
        # Insert
        self.conn.executemany(
            f"""
            INSERT INTO {layer_name} 
            (feature_id, name, geometry_wkb, geometry_geojson, centroid_lon, centroid_lat, properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        
        # DuckDB is autocommit
    
    def ingest_settlements_csv(
        self,
        csv_path: Path,
        lon_field: str = "lon",
        lat_field: str = "lat",
        name_field: str = "name"
    ):
        """
        Ingest settlements from CSV file.
        
        Args:
            csv_path: Path to CSV file
            lon_field: Longitude field name
            lat_field: Latitude field name
            name_field: Name field name
        """
        import pandas as pd
        
        df = pd.read_csv(csv_path)
        
        # Clear existing settlements
        self.conn.execute("DELETE FROM settlements")
        
        rows = []
        for idx, row in df.iterrows():
            feature_id = str(idx)
            name = row.get(name_field, "")
            lon = float(row[lon_field])
            lat = float(row[lat_field])
            
            # Create point geometry
            from shapely.geometry import Point
            point = Point(lon, lat)
            geometry_wkb = wkb.dumps(point, hex=True)
            geometry_geojson = json.dumps({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {k: v for k, v in row.items()}
            })
            
            properties = json.dumps({k: v for k, v in row.items()})
            
            rows.append((
                feature_id,
                name,
                geometry_wkb,
                geometry_geojson,
                lon,  # centroid_lon
                lat,  # centroid_lat
                properties,
                datetime.now()
            ))
        
        self.conn.executemany(
            """
            INSERT INTO settlements 
            (feature_id, name, geometry_wkb, geometry_geojson, centroid_lon, centroid_lat, properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        
        # DuckDB is autocommit
    
    def build_name_index(self):
        """Build name index from all layers."""
        # Clear existing index
        self.conn.execute("DELETE FROM name_index")
        
        # Index all layers
        for layer_name in LAYER_NAMES.values():
            result = self.conn.execute(f"""
                SELECT feature_id, name, properties
                FROM {layer_name}
            """).fetchall()
            
            rows = []
            for feature_id, name, properties_str in result:
                if not name:
                    continue
                
                props = json.loads(properties_str) if properties_str else {}
                
                # Normalize name
                from app.core.normalization import normalize_text
                normalized_name = normalize_text(name)
                
                # Add canonical entry
                rows.append((
                    layer_name,
                    feature_id,
                    name,
                    normalized_name,
                    None,  # alias
                    None,  # normalized_alias
                    json.dumps({}),  # admin_codes
                    datetime.now()
                ))
                
                # Add alias entries if present
                for alias_field in ["aliases", "alias", "alternate_name", "alt_name"]:
                    if alias_field in props:
                        alias_value = props[alias_field]
                        if isinstance(alias_value, str):
                            alias_list = [a.strip() for a in alias_value.split(",")]
                        elif isinstance(alias_value, list):
                            alias_list = alias_value
                        else:
                            continue
                        
                        for alias in alias_list:
                            if alias:
                                rows.append((
                                    layer_name,
                                    feature_id,
                                    name,
                                    normalized_name,
                                    alias,
                                    normalize_text(alias),
                                    json.dumps({}),
                                    datetime.now()
                                ))
            
            if rows:
                self.conn.executemany(
                    """
                    INSERT INTO name_index 
                    (layer, feature_id, canonical_name, normalized_name, alias, normalized_alias, admin_codes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows
                )
        
        # DuckDB is autocommit
    
    def search_name_index(
        self,
        query: str,
        layer: Optional[str] = None,
        threshold: float = 0.7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search name index with fuzzy matching.
        
        Args:
            query: Query string
            layer: Optional layer filter
            threshold: Minimum similarity score
            limit: Maximum results
            
        Returns:
            List of matching entries
        """
        from app.core.normalization import normalize_text
        from app.core.fuzzy import fuzzy_match
        
        normalized_query = normalize_text(query)
        
        # Get all candidates
        if layer:
            candidates = self.conn.execute("""
                SELECT id, layer, feature_id, canonical_name, normalized_name, 
                       alias, normalized_alias, admin_codes
                FROM name_index
                WHERE layer = ?
            """, [layer]).fetchall()
        else:
            candidates = self.conn.execute("""
                SELECT id, layer, feature_id, canonical_name, normalized_name,
                       alias, normalized_alias, admin_codes
                FROM name_index
            """).fetchall()
        
        # Extract searchable strings
        search_strings = []
        for row in candidates:
            # Try normalized_name first
            search_strings.append(row[4])  # normalized_name
            # Also try normalized_alias if present
            if row[6]:  # normalized_alias
                search_strings.append(row[6])
        
        # Fuzzy match
        matches = fuzzy_match(normalized_query, search_strings, threshold, limit)
        
        # Map back to entries
        results = []
        matched_indices = {match[2] for match in matches}
        
        for idx, row in enumerate(candidates):
            if idx in matched_indices:
                # Find matching score
                score = next((m[1] for m in matches if m[2] == idx), 0.0)
                
                results.append({
                    "id": row[0],
                    "layer": row[1],
                    "feature_id": row[2],
                    "canonical_name": row[3],
                    "normalized_name": row[4],
                    "alias": row[5],
                    "normalized_alias": row[6],
                    "admin_codes": json.loads(row[7]) if row[7] else {},
                    "score": score
                })
        
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
    
    def get_cache(self, normalized_text: str) -> Optional[Dict[str, Any]]:
        """Get cached geocode result."""
        result = self.conn.execute("""
            SELECT resolved_layer, feature_id, matched_name, score, lon, lat,
                   state, county, payam, boma, village
            FROM geocode_cache
            WHERE normalized_text = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, [normalized_text]).fetchone()
        
        if result:
            return {
                "resolved_layer": result[0],
                "feature_id": result[1],
                "matched_name": result[2],
                "score": result[3],
                "lon": result[4],
                "lat": result[5],
                "state": result[6],
                "county": result[7],
                "payam": result[8],
                "boma": result[9],
                "village": result[10],
            }
        return None
    
    def set_cache(self, result: Dict[str, Any]):
        """Cache geocode result."""
        self.conn.execute("""
            INSERT INTO geocode_cache
            (input_text, normalized_text, resolved_layer, feature_id, matched_name,
             score, lon, lat, state, county, payam, boma, village, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            result.get("input_text"),
            result.get("normalized_text"),
            result.get("resolved_layer"),
            result.get("feature_id"),
            result.get("matched_name"),
            result.get("score"),
            result.get("lon"),
            result.get("lat"),
            result.get("state"),
            result.get("county"),
            result.get("payam"),
            result.get("boma"),
            result.get("village"),
            datetime.now()
        ])
        # DuckDB is autocommit
    
    def get_geometry(self, layer: str, feature_id: str) -> Optional[Any]:
        """Get geometry for a feature."""
        result = self.conn.execute(f"""
            SELECT geometry_wkb
            FROM {layer}
            WHERE feature_id = ?
        """, [feature_id]).fetchone()
        
        if result:
            return wkb.loads(result[0], hex=True)
        return None
    
    def get_feature(self, layer: str, feature_id: str) -> Optional[Dict[str, Any]]:
        """Get full feature data."""
        result = self.conn.execute(f"""
            SELECT feature_id, name, centroid_lon, centroid_lat, properties
            FROM {layer}
            WHERE feature_id = ?
        """, [feature_id]).fetchone()
        
        if result:
            return {
                "feature_id": result[0],
                "name": result[1],
                "centroid_lon": result[2],
                "centroid_lat": result[3],
                "properties": json.loads(result[4]) if result[4] else {}
            }
        return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM geocode_cache").fetchone()[0]
        hits = self.conn.execute("""
            SELECT COUNT(DISTINCT normalized_text) FROM geocode_cache
        """).fetchone()[0]
        
        return {
            "total_entries": total,
            "unique_queries": hits,
        }
    
    def close(self):
        """Close database connection."""
        self.conn.close()

