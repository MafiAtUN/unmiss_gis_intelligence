"""DuckDB storage layer for geocoding data."""
import duckdb
from pathlib import Path
from typing import List, Dict, Optional, Any
import geopandas as gpd
from shapely import wkb
from shapely.geometry import Point
import json
from datetime import datetime
from app.core.config import DUCKDB_PATH, LAYER_NAMES
from app.core.normalization import normalize_text
from app.core.security import sanitize_layer_name, validate_feature_id


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
        # Note: DuckDB does NOT auto-increment INTEGER PRIMARY KEY - IDs must be generated manually
        
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
        
        # Initialize villages schema
        self._init_villages_schema()
        
        # Initialize feedback schema
        self._init_feedback_schema()
        
        # Initialize OSM features schema
        self._init_osm_features_schema()
        
        # DuckDB is autocommit, no need for commit()
    
    def _get_next_id(self, table_name: str, id_column: str = "id") -> int:
        """
        Get the next available ID for a table.
        
        DuckDB does not auto-increment INTEGER PRIMARY KEY columns, so we need
        to manually generate IDs by finding the maximum existing ID and adding 1.
        
        Args:
            table_name: Name of the table
            id_column: Name of the ID column (default: "id")
            
        Returns:
            Next available ID (starts at 1 if table is empty)
        """
        try:
            result = self.conn.execute(f"""
                SELECT COALESCE(MAX({id_column}), 0) + 1 FROM {table_name}
            """).fetchone()
            if result and result[0] is not None:
                return result[0]
            return 1
        except Exception:
            # If table doesn't exist or query fails, start at 1
            return 1
    
    def _init_villages_schema(self):
        """Initialize villages and alternate names tables."""
        # Villages table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS villages (
                village_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                normalized_name VARCHAR,
                lon DOUBLE NOT NULL,
                lat DOUBLE NOT NULL,
                geometry_wkb BLOB,
                state VARCHAR,
                county VARCHAR,
                payam VARCHAR,
                boma VARCHAR,
                state_id VARCHAR,
                county_id VARCHAR,
                payam_id VARCHAR,
                boma_id VARCHAR,
                data_source VARCHAR,
                source_id VARCHAR,
                confidence_score DOUBLE,
                verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR,
                properties TEXT
            )
        """)
        
        # Village alternate names table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS village_alternate_names (
                id INTEGER PRIMARY KEY,
                village_id VARCHAR NOT NULL,
                alternate_name VARCHAR NOT NULL,
                normalized_alternate_name VARCHAR,
                name_type VARCHAR,
                source VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for villages
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_villages_bbox ON villages(lon, lat)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_villages_name ON villages(normalized_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_villages_state ON villages(state)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_villages_county ON villages(county)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_villages_payam ON villages(payam)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_villages_boma ON villages(boma)")
        
        # Create indexes for alternate names
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_alternate_names_normalized ON village_alternate_names(normalized_alternate_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_alternate_names_village ON village_alternate_names(village_id)")
    
    def _init_feedback_schema(self):
        """Initialize feedback and pattern performance tables."""
        # Extraction feedback table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_feedback (
                id INTEGER PRIMARY KEY,
                document_hash VARCHAR,
                original_text TEXT,
                extracted_text TEXT,
                method VARCHAR,
                user_corrected_text TEXT,
                is_correct BOOLEAN,
                context_text TEXT,
                geocode_result_json TEXT,
                feedback_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Regex pattern performance table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS regex_pattern_performance (
                id INTEGER PRIMARY KEY,
                pattern_string TEXT,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                examples TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for feedback
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_document_hash ON extraction_feedback(document_hash)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_method ON extraction_feedback(method)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_pattern_performance_pattern ON regex_pattern_performance(pattern_string)")
    
    def _init_osm_features_schema(self):
        """Initialize OSM features tables (roads and POIs)."""
        # Roads table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS osm_roads (
                feature_id VARCHAR PRIMARY KEY,
                osm_id BIGINT NOT NULL,
                osm_type VARCHAR NOT NULL,
                name VARCHAR,
                highway VARCHAR,
                surface VARCHAR,
                geometry_wkb BLOB NOT NULL,
                geometry_geojson TEXT,
                centroid_lon DOUBLE,
                centroid_lat DOUBLE,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(osm_id, osm_type)
            )
        """)
        
        # POIs table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS osm_pois (
                feature_id VARCHAR PRIMARY KEY,
                osm_id BIGINT NOT NULL,
                osm_type VARCHAR NOT NULL,
                name VARCHAR,
                category VARCHAR NOT NULL,
                lon DOUBLE NOT NULL,
                lat DOUBLE NOT NULL,
                geometry_wkb BLOB NOT NULL,
                geometry_geojson TEXT,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(osm_id, osm_type)
            )
        """)
        
        # Create indexes for OSM features
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_osm_roads_bbox ON osm_roads(centroid_lon, centroid_lat)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_osm_roads_highway ON osm_roads(highway)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_osm_pois_bbox ON osm_pois(lon, lat)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_osm_pois_category ON osm_pois(category)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_osm_pois_name ON osm_pois(name)")
    
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
            
        Raises:
            ValueError: If layer_name is not in the allowed whitelist
        """
        # Validate layer name to prevent SQL injection
        sanitized_layer = sanitize_layer_name(layer_name)
        if not sanitized_layer:
            raise ValueError(f"Invalid layer name: {layer_name}. Must be one of {list(LAYER_NAMES.values())}")
        
        layer_name = sanitized_layer
        
        # Ensure WGS84
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        # Clear existing data (layer_name is now validated)
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
        """Build name index from all layers and villages."""
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
                # Get the next ID to start from
                next_id = self._get_next_id("name_index")
                
                # Prepend ID to each row
                rows_with_ids = [(next_id + i,) + row for i, row in enumerate(rows)]
                
                self.conn.executemany(
                    """
                    INSERT INTO name_index 
                    (id, layer, feature_id, canonical_name, normalized_name, alias, normalized_alias, admin_codes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows_with_ids
                )
        
        # Index villages and their alternate names
        from app.core.normalization import normalize_text
        
        villages_result = self.conn.execute("""
            SELECT village_id, name, normalized_name
            FROM villages
        """).fetchall()
        
        village_rows = []
        for village_id, name, normalized_name in villages_result:
            if not name:
                continue
            
            # Add primary name entry
            village_rows.append((
                "villages",
                village_id,
                name,
                normalized_name if normalized_name else normalize_text(name),
                None,  # alias
                None,  # normalized_alias
                json.dumps({}),  # admin_codes
                datetime.now()
            ))
        
        # Add alternate names
        alternate_names_result = self.conn.execute("""
            SELECT van.village_id, van.alternate_name, van.normalized_alternate_name, v.name
            FROM village_alternate_names van
            JOIN villages v ON van.village_id = v.village_id
        """).fetchall()
        
        for village_id, alt_name, norm_alt_name, primary_name in alternate_names_result:
            if alt_name:
                village_rows.append((
                    "villages",
                    village_id,
                    primary_name,  # canonical name
                    normalize_text(primary_name) if primary_name else "",
                    alt_name,  # alias
                    norm_alt_name if norm_alt_name else normalize_text(alt_name),
                    json.dumps({}),
                    datetime.now()
                ))
        
        if village_rows:
            # Get the next ID to start from
            next_id = self._get_next_id("name_index")
            
            # Prepend ID to each row
            village_rows_with_ids = [(next_id + i,) + row for i, row in enumerate(village_rows)]
            
            self.conn.executemany(
                """
                INSERT INTO name_index 
                (id, layer, feature_id, canonical_name, normalized_name, alias, normalized_alias, admin_codes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                village_rows_with_ids
            )
        
        # DuckDB is autocommit
    
    def search_name_index(
        self,
        query: str,
        layer: Optional[str] = None,
        threshold: float = 0.7,
        limit: int = 10,
        state_constraint: Optional[str] = None,
        county_constraint: Optional[str] = None,
        payam_constraint: Optional[str] = None,
        boma_constraint: Optional[str] = None
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
        from app.core.fuzzy import progressive_fuzzy_match, apply_context_boost
        
        normalized_query = normalize_text(query)
        
        # Get all candidates (constraints will be applied after fuzzy matching)
        # This is because name_index doesn't directly store hierarchical info
        # We'll filter results by checking actual feature properties
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
        
        # Use progressive fuzzy matching
        matches = progressive_fuzzy_match(normalized_query, search_strings, threshold, limit)
        
        # Prepare match data for context boosting
        match_data = []
        for idx, row in enumerate(candidates):
            # Extract match info from row
            match_info = {
                "layer": row[1],
                "feature_id": row[2],
                "canonical_name": row[3],
            }
            # Try to get admin hierarchy info from feature
            try:
                feature = self.get_feature(row[1], row[2])
                if feature:
                    props = feature.get("properties", {})
                    if isinstance(props, dict):
                        match_info["state"] = props.get("admin1Name") or props.get("state") or props.get("STATE")
                        match_info["county"] = props.get("admin2Name") or props.get("county") or props.get("COUNTY")
                        match_info["payam"] = props.get("admin3Name") or props.get("payam") or props.get("PAYAM")
                        match_info["boma"] = props.get("admin4Name") or props.get("boma") or props.get("BOMA")
            except:
                pass
            match_data.append(match_info)
        
        # Apply context-aware scoring boost
        constraints = {
            "state": state_constraint,
            "county": county_constraint,
            "payam": payam_constraint,
            "boma": boma_constraint,
        }
        boosted_matches = apply_context_boost(matches, match_data, constraints)
        
        # Map back to entries
        results = []
        matched_indices = {match[2] for match in boosted_matches}
        
        for idx, row in enumerate(candidates):
            if idx in matched_indices:
                # Find matching score from boosted matches
                score = next((m[1] for m in boosted_matches if m[2] == idx), 0.0)
                
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
        try:
            # Get the next ID using helper method
            next_id = self._get_next_id("geocode_cache")
            
            self.conn.execute("""
                INSERT INTO geocode_cache
                    (id, input_text, normalized_text, resolved_layer, feature_id, matched_name,
                 score, lon, lat, state, county, payam, boma, village, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                    next_id,
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
        except Exception as e:
            # Log error but don't fail the geocoding operation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to cache geocode result: {e}")
        # DuckDB is autocommit
    
    def get_geometry(self, layer: str, feature_id: str) -> Optional[Any]:
        """
        Get geometry for a feature.
        
        Args:
            layer: Layer name (validated against whitelist)
            feature_id: Feature ID (validated)
            
        Returns:
            Geometry object or None if not found
        """
        # Validate inputs to prevent SQL injection
        sanitized_layer = sanitize_layer_name(layer)
        if not sanitized_layer:
            raise ValueError(f"Invalid layer name: {layer}")
        
        if not validate_feature_id(feature_id):
            raise ValueError(f"Invalid feature_id: {feature_id}")
        
        result = self.conn.execute(f"""
            SELECT geometry_wkb
            FROM {sanitized_layer}
            WHERE feature_id = ?
        """, [feature_id]).fetchone()
        
        if result:
            return wkb.loads(result[0], hex=True)
        return None
    
    def get_feature(self, layer: str, feature_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full feature data.
        
        Args:
            layer: Layer name (validated against whitelist)
            feature_id: Feature ID (validated)
            
        Returns:
            Feature dictionary or None if not found
        """
        # Validate inputs to prevent SQL injection
        sanitized_layer = sanitize_layer_name(layer)
        if not sanitized_layer:
            raise ValueError(f"Invalid layer name: {layer}")
        
        if not validate_feature_id(feature_id):
            raise ValueError(f"Invalid feature_id: {feature_id}")
        
        result = self.conn.execute(f"""
            SELECT feature_id, name, centroid_lon, centroid_lat, properties
            FROM {sanitized_layer}
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
    
    def get_admin_hierarchy_with_ids(self, lon: float, lat: float) -> Dict[str, Optional[str]]:
        """
        Get administrative hierarchy with feature IDs for a point using spatial queries.
        
        Args:
            lon: Longitude
            lat: Latitude
            
        Returns:
            Dictionary with state, county, payam, boma, state_id, county_id, payam_id, boma_id
        """
        from shapely.geometry import Point
        from shapely import wkb
        
        hierarchy = {
            "state": None,
            "county": None,
            "payam": None,
            "boma": None,
            "state_id": None,
            "county_id": None,
            "payam_id": None,
            "boma_id": None,
        }
        
        point = Point(lon, lat)
        
        # Query each admin layer to find which polygon contains the point
        # Order: boma -> payam -> county -> state
        layer_order = [
            ("admin4_boma", "boma", "boma_id"),
            ("admin3_payam", "payam", "payam_id"),
            ("admin2_county", "county", "county_id"),
            ("admin1_state", "state", "state_id"),
        ]
        
        for layer_name, name_key, id_key in layer_order:
            try:
                # Get all features from this layer
                # Use centroid as a quick filter first (if point is far from centroid, skip detailed check)
                results = self.conn.execute(f"""
                    SELECT feature_id, name, geometry_wkb, centroid_lon, centroid_lat
                    FROM {layer_name}
                    WHERE centroid_lon IS NOT NULL AND centroid_lat IS NOT NULL
                """).fetchall()
                
                # Check each polygon to see if it contains the point
                for feature_id, name, geometry_wkb, centroid_lon, centroid_lat in results:
                    if geometry_wkb:
                        try:
                            # Quick distance check first (rough approximation)
                            if centroid_lon and centroid_lat:
                                # Skip if point is very far from centroid (rough check)
                                # This is approximate but helps performance
                                dist_approx = ((lon - centroid_lon)**2 + (lat - centroid_lat)**2)**0.5
                                if dist_approx > 1.0:  # Skip if more than ~1 degree away (rough)
                                    continue
                            
                            geometry = wkb.loads(geometry_wkb, hex=True)
                            if geometry.contains(point) or geometry.touches(point):
                                hierarchy[name_key] = name
                                hierarchy[id_key] = str(feature_id)
                                break  # Found match, move to next layer
                        except Exception:
                            continue
            except Exception:
                continue
        
        return hierarchy
    
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
    
    # Village management methods
    
    def add_village(
        self,
        name: str,
        lon: float,
        lat: float,
        state: Optional[str] = None,
        county: Optional[str] = None,
        payam: Optional[str] = None,
        boma: Optional[str] = None,
        state_id: Optional[str] = None,
        county_id: Optional[str] = None,
        payam_id: Optional[str] = None,
        boma_id: Optional[str] = None,
        data_source: str = "manual",
        source_id: Optional[str] = None,
        confidence_score: Optional[float] = None,
        verified: bool = False,
        created_by: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        village_id: Optional[str] = None
    ) -> str:
        """
        Add a village to the database.
        
        Args:
            name: Village name
            lon: Longitude
            lat: Latitude
            state: State name
            county: County name
            payam: Payam name
            boma: Boma name
            state_id: State ID
            county_id: County ID
            payam_id: Payam ID
            boma_id: Boma ID
            data_source: Source of the data
            source_id: Original ID from source
            confidence_score: Confidence score (0.0-1.0)
            verified: Whether human-verified
            created_by: User/system identifier
            properties: Additional properties as dict
            village_id: Optional village ID (if not provided, will be generated)
            
        Returns:
            village_id
        """
        import hashlib
        from shapely.geometry import Point
        from app.core.normalization import normalize_text
        
        # Generate village_id if not provided
        if not village_id:
            # Use hash of name + coordinates for consistent IDs
            id_string = f"{name}_{lon}_{lat}"
            village_id = hashlib.md5(id_string.encode()).hexdigest()
        
        # Normalize name
        normalized_name = normalize_text(name)
        
        # Create point geometry
        point = Point(lon, lat)
        geometry_wkb = wkb.dumps(point, hex=True)
        
        # Serialize properties
        properties_json = json.dumps(properties) if properties else None
        
        # Insert village
        self.conn.execute("""
            INSERT OR REPLACE INTO villages
            (village_id, name, normalized_name, lon, lat, geometry_wkb,
             state, county, payam, boma, state_id, county_id, payam_id, boma_id,
             data_source, source_id, confidence_score, verified, created_by, properties, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            village_id, name, normalized_name, lon, lat, geometry_wkb,
            state, county, payam, boma, state_id, county_id, payam_id, boma_id,
            data_source, source_id, confidence_score, verified, created_by, properties_json
        ])
        
        return village_id
    
    def add_alternate_name(
        self,
        village_id: str,
        alternate_name: str,
        name_type: str = "alias",
        source: Optional[str] = None
    ) -> int:
        """
        Add an alternate name for a village.
        
        Args:
            village_id: Village ID
            alternate_name: Alternate name/spelling
            name_type: Type of name ('alias', 'variant', 'misspelling', 'translation')
            source: Source of the alternate name
            
        Returns:
            Alternate name ID
        """
        from app.core.normalization import normalize_text
        
        normalized_alternate_name = normalize_text(alternate_name)
        
        # Get the next ID manually (DuckDB doesn't auto-increment INTEGER PRIMARY KEY)
        next_id = self._get_next_id("village_alternate_names")
        
        self.conn.execute("""
            INSERT INTO village_alternate_names
            (id, village_id, alternate_name, normalized_alternate_name, name_type, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [next_id, village_id, alternate_name, normalized_alternate_name, name_type, source])
        
        return next_id
    
    def search_villages(
        self,
        query: str,
        threshold: float = 0.7,
        limit: int = 10,
        include_alternates: bool = True,
        state_constraint: Optional[str] = None,
        county_constraint: Optional[str] = None,
        payam_constraint: Optional[str] = None,
        boma_constraint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search villages by name (including alternate names) with fuzzy matching.
        
        Args:
            query: Search query
            threshold: Minimum similarity score
            limit: Maximum results
            include_alternates: Whether to search alternate names too
            
        Returns:
            List of matching villages
        """
        from app.core.normalization import normalize_text
        from app.core.fuzzy import progressive_fuzzy_match, apply_context_boost
        
        normalized_query = normalize_text(query)
        
        # Build WHERE clause for hierarchical constraints
        where_clauses = []
        params = []
        
        # STRICT constraint filtering - CRITICAL: Only search villages within specified boundaries
        # If constraints are specified, we MUST only return villages that match them
        # This prevents wrong matches across states/counties
        if state_constraint:
            # STRICT: Only match villages where state field matches (case-insensitive)
            # Use LIKE with % for partial matching (handles "Unity" vs "Unity State")
            where_clauses.append("LOWER(state) LIKE LOWER(?)")
            # Try with and without "state" suffix
            state_param = state_constraint.replace(" state", "").strip()
            params.append(f"%{state_param}%")
        
        if county_constraint:
            # STRICT: Only match villages where county field matches
            # Try both exact match and LIKE match
            county_param = county_constraint.replace(" county", "").strip()
            # Use OR to match both exact and partial
            where_clauses.append("(LOWER(county) = LOWER(?) OR LOWER(county) LIKE LOWER(?))")
            params.append(county_param)  # Exact match
            params.append(f"%{county_param}%")  # Partial match
        
        if payam_constraint:
            # STRICT: Only match villages where payam field matches
            where_clauses.append("LOWER(payam) LIKE LOWER(?)")
            payam_param = payam_constraint.replace(" payam", "").strip()
            params.append(f"%{payam_param}%")
        
        if boma_constraint:
            # STRICT: Only match villages where boma field matches
            where_clauses.append("LOWER(boma) LIKE LOWER(?)")
            boma_param = boma_constraint.replace(" boma", "").strip()
            params.append(f"%{boma_param}%")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get all village names and normalized names (filtered by constraints)
        villages = self.conn.execute(f"""
            SELECT village_id, name, normalized_name, lon, lat,
                   state, county, payam, boma, data_source, verified
            FROM villages
            WHERE {where_sql}
        """, params).fetchall()
        
        # If no villages found with constraints, try fallback strategies
        if len(villages) == 0:
            # Strategy 1: If we have county constraint, try exact match on county (ignore state)
            if county_constraint:
                county_param = county_constraint.replace(" county", "").strip()
                villages = self.conn.execute("""
                    SELECT village_id, name, normalized_name, lon, lat,
                           state, county, payam, boma, data_source, verified
                    FROM villages
                    WHERE LOWER(county) = LOWER(?)
                """, [county_param]).fetchall()
            
            # Strategy 2: If still no results and we have state constraint, try state only (ignore county)
            if len(villages) == 0 and state_constraint:
                state_param = state_constraint.replace(" state", "").strip()
                villages = self.conn.execute("""
                    SELECT village_id, name, normalized_name, lon, lat,
                           state, county, payam, boma, data_source, verified
                    FROM villages
                    WHERE LOWER(state) LIKE LOWER(?)
                """, [f"%{state_param}%"]).fetchall()
            
            # Strategy 3: If still no results, search all villages (no constraints)
            # This is a last resort - we'll filter by constraints later in the matching logic
            if len(villages) == 0:
                villages = self.conn.execute("""
                    SELECT village_id, name, normalized_name, lon, lat,
                           state, county, payam, boma, data_source, verified
                    FROM villages
                """).fetchall()
        
        # Build search strings list
        search_strings = []
        village_map = {}  # Map index to village data
        
        for idx, (v_id, name, norm_name, lon, lat, state, county, payam, boma, source, verified) in enumerate(villages):
            search_strings.append(norm_name)
            village_map[idx] = {
                "village_id": v_id,
                "name": name,
                "normalized_name": norm_name,
                "lon": lon,
                "lat": lat,
                "state": state,
                "county": county,
                "payam": payam,
                "boma": boma,
                "data_source": source,
                "verified": verified
            }
        
        # Search alternate names if requested (with constraints)
        if include_alternates:
            alt_where_clauses = []
            alt_params = []
            
            # STRICT constraint filtering for alternate names too
            if state_constraint:
                alt_where_clauses.append("LOWER(v.state) LIKE LOWER(?)")
                state_param = state_constraint.replace(" state", "").strip()
                alt_params.append(f"%{state_param}%")
            if county_constraint:
                alt_where_clauses.append("LOWER(v.county) LIKE LOWER(?)")
                county_param = county_constraint.replace(" county", "").strip()
                alt_params.append(f"%{county_param}%")
            if payam_constraint:
                alt_where_clauses.append("LOWER(v.payam) LIKE LOWER(?)")
                payam_param = payam_constraint.replace(" payam", "").strip()
                alt_params.append(f"%{payam_param}%")
            if boma_constraint:
                alt_where_clauses.append("LOWER(v.boma) LIKE LOWER(?)")
                boma_param = boma_constraint.replace(" boma", "").strip()
                alt_params.append(f"%{boma_param}%")
            
            alt_where_sql = " AND ".join(alt_where_clauses) if alt_where_clauses else "1=1"
            
            alternates = self.conn.execute(f"""
                SELECT van.village_id, van.alternate_name, van.normalized_alternate_name,
                       v.village_id, v.name, v.normalized_name, v.lon, v.lat,
                       v.state, v.county, v.payam, v.boma, v.data_source, v.verified
                FROM village_alternate_names van
                JOIN villages v ON van.village_id = v.village_id
                WHERE {alt_where_sql}
            """, alt_params).fetchall()
            
            alt_start_idx = len(search_strings)
            for idx, (v_id, alt_name, norm_alt_name, v_id2, name, norm_name, lon, lat, state, county, payam, boma, source, verified) in enumerate(alternates):
                search_idx = alt_start_idx + idx
                search_strings.append(norm_alt_name)
                village_map[search_idx] = {
                    "village_id": v_id,
                    "name": name,
                    "normalized_name": norm_name,
                    "lon": lon,
                    "lat": lat,
                    "state": state,
                    "county": county,
                    "payam": payam,
                    "boma": boma,
                    "data_source": source,
                    "verified": verified,
                    "matched_alternate_name": alt_name
                }
        
        # FIRST: Try exact match (case-insensitive, normalized)
        # This is critical - if the village name exactly matches, use it immediately
        exact_match_idx = None
        for idx, search_str in enumerate(search_strings):
            # search_str is already normalized_name from DB, but normalize again to be safe
            norm_search = normalize_text(search_str)
            if norm_search == normalized_query:
                exact_match_idx = idx
                break
        
        if exact_match_idx is not None and exact_match_idx in village_map:
            # Found exact match - return it immediately with high score
            village_data = village_map[exact_match_idx].copy()
            village_data["score"] = 1.0  # Perfect match
            return [village_data]
        
        # SECOND: Try substring exact match (e.g., "abiemnom" in "abiemnom town")
        # Prioritize matches where query is contained in name (query is the core name)
        substring_match_idx = None
        best_substring_score = 0.0
        
        for idx, search_str in enumerate(search_strings):
            norm_search = normalize_text(search_str)
            
            # Case 1: Query is contained in name (e.g., "abiemnom" in "abiemnom town")
            # This is the GOOD case - query is the core name, name has suffix
            if normalized_query in norm_search:
                # Calculate how much of the name is the query
                query_ratio = len(normalized_query) / len(norm_search)
                # If query is at least 70% of the name, it's a good match
                # Also check if query starts the name (most common case)
                if norm_search.startswith(normalized_query) and query_ratio >= 0.5:
                    score = query_ratio  # Higher score for longer query relative to name
                    if score > best_substring_score:
                        best_substring_score = score
                        substring_match_idx = idx
            
            # Case 2: Name is contained in query (e.g., "abiemnom town" in "abiemnom town center")
            # This is also acceptable if the name is a significant portion
            elif norm_search in normalized_query:
                name_ratio = len(norm_search) / len(normalized_query)
                if name_ratio >= 0.7:  # Name is at least 70% of query
                    score = name_ratio
                    if score > best_substring_score:
                        best_substring_score = score
                        substring_match_idx = idx
        
        # Only use substring match if it's a good quality match
        if substring_match_idx is not None and best_substring_score >= 0.5 and substring_match_idx in village_map:
            # Found good substring match - return it with high score
            village_data = village_map[substring_match_idx].copy()
            # Score based on how much of the name matches (0.85 to 0.95 range)
            village_data["score"] = 0.85 + (best_substring_score * 0.1)  # Scale to 0.85-0.95
            return [village_data]
        
        # THIRD: Use progressive fuzzy matching for better accuracy
        matches = progressive_fuzzy_match(normalized_query, search_strings, threshold, limit * 2)
        
        # Prepare match data for context boosting
        match_data = []
        for match_idx in range(len(search_strings)):
            if match_idx in village_map:
                match_data.append(village_map[match_idx])
            else:
                match_data.append({})
        
        # Apply context-aware scoring boost
        constraints = {
            "state": state_constraint,
            "county": county_constraint,
            "payam": payam_constraint,
            "boma": boma_constraint,
        }
        boosted_matches = apply_context_boost(matches, match_data, constraints)
        
        # Map back to villages and deduplicate
        results = []
        seen_village_ids = set()
        
        for match in boosted_matches:
            match_idx = match[2]
            score = match[1]
            
            if match_idx in village_map:
                village_data = village_map[match_idx].copy()
                village_data["score"] = score
                
                # Deduplicate by village_id, keeping highest score
                v_id = village_data["village_id"]
                if v_id not in seen_village_ids:
                    seen_village_ids.add(v_id)
                    results.append(village_data)
                else:
                    # Update if this match has higher score
                    for i, r in enumerate(results):
                        if r["village_id"] == v_id and score > r["score"]:
                            results[i] = village_data
                            break
        
        # Sort by score and limit
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
        return results
    
    def get_village_by_coordinates(
        self,
        lon: float,
        lat: float,
        tolerance: float = 0.001  # ~100 meters
    ) -> Optional[Dict[str, Any]]:
        """
        Find village near given coordinates.
        
        Args:
            lon: Longitude
            lat: Latitude
            tolerance: Distance tolerance in degrees
            
        Returns:
            Village dictionary or None
        """
        result = self.conn.execute("""
            SELECT village_id, name, normalized_name, lon, lat,
                   state, county, payam, boma, state_id, county_id, payam_id, boma_id,
                   data_source, source_id, confidence_score, verified, properties
            FROM villages
            WHERE lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?
            ORDER BY ABS(lon - ?) + ABS(lat - ?)
            LIMIT 1
        """, [lon - tolerance, lon + tolerance, lat - tolerance, lat + tolerance, lon, lat]).fetchone()
        
        if result:
            return {
                "village_id": result[0],
                "name": result[1],
                "normalized_name": result[2],
                "lon": result[3],
                "lat": result[4],
                "state": result[5],
                "county": result[6],
                "payam": result[7],
                "boma": result[8],
                "state_id": result[9],
                "county_id": result[10],
                "payam_id": result[11],
                "boma_id": result[12],
                "data_source": result[13],
                "source_id": result[14],
                "confidence_score": result[15],
                "verified": result[16],
                "properties": json.loads(result[17]) if result[17] else {}
            }
        return None
    
    def update_village_admin_boundaries(
        self,
        village_id: str,
        state: Optional[str] = None,
        county: Optional[str] = None,
        payam: Optional[str] = None,
        boma: Optional[str] = None,
        state_id: Optional[str] = None,
        county_id: Optional[str] = None,
        payam_id: Optional[str] = None,
        boma_id: Optional[str] = None
    ) -> bool:
        """
        Update admin boundaries for a village.
        
        Args:
            village_id: Village ID
            state: State name
            county: County name
            payam: Payam name
            boma: Boma name
            state_id: State ID
            county_id: County ID
            payam_id: Payam ID
            boma_id: Boma ID
            
        Returns:
            True if updated, False if village not found
        """
        result = self.conn.execute("""
            UPDATE villages
            SET state = COALESCE(?, state),
                county = COALESCE(?, county),
                payam = COALESCE(?, payam),
                boma = COALESCE(?, boma),
                state_id = COALESCE(?, state_id),
                county_id = COALESCE(?, county_id),
                payam_id = COALESCE(?, payam_id),
                boma_id = COALESCE(?, boma_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE village_id = ?
        """, [state, county, payam, boma, state_id, county_id, payam_id, boma_id, village_id])
        
        return result.rowcount > 0
    
    def get_village(self, village_id: str) -> Optional[Dict[str, Any]]:
        """Get village by ID."""
        result = self.conn.execute("""
            SELECT village_id, name, normalized_name, lon, lat,
                   state, county, payam, boma, state_id, county_id, payam_id, boma_id,
                   data_source, source_id, confidence_score, verified, properties,
                   created_at, updated_at, created_by
            FROM villages
            WHERE village_id = ?
        """, [village_id]).fetchone()
        
        if result:
            return {
                "village_id": result[0],
                "name": result[1],
                "normalized_name": result[2],
                "lon": result[3],
                "lat": result[4],
                "state": result[5],
                "county": result[6],
                "payam": result[7],
                "boma": result[8],
                "state_id": result[9],
                "county_id": result[10],
                "payam_id": result[11],
                "boma_id": result[12],
                "data_source": result[13],
                "source_id": result[14],
                "confidence_score": result[15],
                "verified": result[16],
                "properties": json.loads(result[17]) if result[17] else {},
                "created_at": result[18],
                "updated_at": result[19],
                "created_by": result[20]
            }
        return None
    
    def get_village_alternate_names(self, village_id: str) -> List[Dict[str, Any]]:
        """Get all alternate names for a village."""
        results = self.conn.execute("""
            SELECT id, alternate_name, normalized_alternate_name, name_type, source, created_at
            FROM village_alternate_names
            WHERE village_id = ?
            ORDER BY created_at DESC
        """, [village_id]).fetchall()
        
        return [
            {
                "id": r[0],
                "alternate_name": r[1],
                "normalized_alternate_name": r[2],
                "name_type": r[3],
                "source": r[4],
                "created_at": r[5]
            }
            for r in results
        ]
    
    def delete_village(self, village_id: str) -> bool:
        """Delete a village and its alternate names."""
        # Delete alternate names first (CASCADE if supported)
        self.conn.execute("DELETE FROM village_alternate_names WHERE village_id = ?", [village_id])
        
        # Delete village
        result = self.conn.execute("DELETE FROM villages WHERE village_id = ?", [village_id])
        
        return result.rowcount > 0
    
    def save_extraction_feedback(
        self,
        document_hash: str,
        original_text: str,
        extracted_text: str,
        method: str,
        user_corrected_text: Optional[str] = None,
        is_correct: Optional[bool] = None,
        context_text: Optional[str] = None,
        geocode_result_json: Optional[str] = None
    ) -> int:
        """Save user feedback on an extraction."""
        feedback_id = self._get_next_id("extraction_feedback")
        
        self.conn.execute("""
            INSERT INTO extraction_feedback (
                id, document_hash, original_text, extracted_text, method,
                user_corrected_text, is_correct, context_text, geocode_result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            feedback_id, document_hash, original_text, extracted_text, method,
            user_corrected_text, is_correct, context_text, geocode_result_json
        ])
        
        return feedback_id
    
    def get_extraction_feedback(self, document_hash: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get extraction feedback, optionally filtered by document hash."""
        if document_hash:
            results = self.conn.execute("""
                SELECT id, document_hash, original_text, extracted_text, method,
                       user_corrected_text, is_correct, context_text, geocode_result_json,
                       feedback_timestamp
                FROM extraction_feedback
                WHERE document_hash = ?
                ORDER BY feedback_timestamp DESC
            """, [document_hash]).fetchall()
        else:
            results = self.conn.execute("""
                SELECT id, document_hash, original_text, extracted_text, method,
                       user_corrected_text, is_correct, context_text, geocode_result_json,
                       feedback_timestamp
                FROM extraction_feedback
                ORDER BY feedback_timestamp DESC
                LIMIT 1000
            """).fetchall()
        
        return [
            {
                "id": r[0],
                "document_hash": r[1],
                "original_text": r[2],
                "extracted_text": r[3],
                "method": r[4],
                "user_corrected_text": r[5],
                "is_correct": r[6],
                "context_text": r[7],
                "geocode_result_json": r[8],
                "feedback_timestamp": r[9]
            }
            for r in results
        ]
    
    def update_pattern_performance(
        self,
        pattern_string: str,
        success: bool = True,
        example: Optional[str] = None
    ):
        """Update pattern performance tracking."""
        # Check if pattern exists
        existing = self.conn.execute("""
            SELECT id, success_count, failure_count, examples
            FROM regex_pattern_performance
            WHERE pattern_string = ?
        """, [pattern_string]).fetchone()
        
        if existing:
            # Update existing
            pattern_id, success_count, failure_count, examples = existing
            if success:
                success_count += 1
            else:
                failure_count += 1
            
            # Update examples (keep last 10)
            examples_list = json.loads(examples) if examples else []
            if example:
                examples_list.append(example)
                examples_list = examples_list[-10:]  # Keep last 10
            
            self.conn.execute("""
                UPDATE regex_pattern_performance
                SET success_count = ?, failure_count = ?, examples = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, [success_count, failure_count, json.dumps(examples_list), pattern_id])
        else:
            # Insert new
            pattern_id = self._get_next_id("regex_pattern_performance")
            examples_list = [example] if example else []
            
            self.conn.execute("""
                INSERT INTO regex_pattern_performance (
                    id, pattern_string, success_count, failure_count, examples
                ) VALUES (?, ?, ?, ?, ?)
            """, [
                pattern_id, pattern_string,
                1 if success else 0,
                0 if success else 1,
                json.dumps(examples_list)
            ])
    
    def get_pattern_performance(self) -> List[Dict[str, Any]]:
        """Get all pattern performance statistics."""
        results = self.conn.execute("""
            SELECT id, pattern_string, success_count, failure_count, examples,
                   created_at, updated_at
            FROM regex_pattern_performance
            ORDER BY (success_count + failure_count) DESC
        """).fetchall()
        
        return [
            {
                "id": r[0],
                "pattern_string": r[1],
                "success_count": r[2],
                "failure_count": r[3],
                "examples": json.loads(r[4]) if r[4] else [],
                "created_at": r[5],
                "updated_at": r[6],
                "success_rate": r[2] / (r[2] + r[3]) if (r[2] + r[3]) > 0 else 0.0
            }
            for r in results
        ]
    
    def ingest_osm_roads(self, gdf: gpd.GeoDataFrame):
        """
        Ingest OSM roads into database.
        
        Args:
            gdf: GeoDataFrame with roads (must have 'osm_id', 'osm_type', 'geometry' columns)
        """
        import hashlib
        
        # Ensure WGS84
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        rows = []
        for idx, row in gdf.iterrows():
            osm_id = row.get("osm_id", idx)
            osm_type = row.get("osm_type", "way")
            feature_id = f"{osm_type}_{osm_id}"
            
            geometry = row.geometry
            geometry_wkb = wkb.dumps(geometry, hex=True)
            
            # Create GeoJSON
            feature_dict = {
                "type": "Feature",
                "geometry": json.loads(gpd.GeoSeries([geometry]).to_json())["features"][0]["geometry"],
                "properties": {k: str(v) for k, v in row.items() if k != "geometry"}
            }
            geometry_geojson = json.dumps(feature_dict)
            
            # Compute centroid
            centroid_lon, centroid_lat = None, None
            if hasattr(geometry, 'centroid'):
                centroid = geometry.centroid
                centroid_lon = centroid.x
                centroid_lat = centroid.y
            
            properties = json.dumps({k: str(v) for k, v in row.items() if k != "geometry"})
            
            rows.append((
                feature_id,
                int(osm_id),
                osm_type,
                row.get("name"),
                row.get("highway"),
                row.get("surface"),
                geometry_wkb,
                geometry_geojson,
                centroid_lon,
                centroid_lat,
                properties,
                datetime.now()
            ))
        
        if rows:
            # Use INSERT OR REPLACE to handle duplicates
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO osm_roads 
                (feature_id, osm_id, osm_type, name, highway, surface, geometry_wkb, 
                 geometry_geojson, centroid_lon, centroid_lat, properties, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
    
    def ingest_osm_pois(self, gdf: gpd.GeoDataFrame):
        """
        Ingest OSM POIs into database.
        
        Args:
            gdf: GeoDataFrame with POIs (must have 'osm_id', 'osm_type', 'category', 'geometry' columns)
        """
        import hashlib
        
        # Ensure WGS84
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        rows = []
        for idx, row in gdf.iterrows():
            osm_id = row.get("osm_id", idx)
            osm_type = row.get("osm_type", "node")
            feature_id = f"{osm_type}_{osm_id}"
            
            geometry = row.geometry
            geometry_wkb = wkb.dumps(geometry, hex=True)
            
            # Create GeoJSON
            feature_dict = {
                "type": "Feature",
                "geometry": json.loads(gpd.GeoSeries([geometry]).to_json())["features"][0]["geometry"],
                "properties": {k: str(v) for k, v in row.items() if k != "geometry"}
            }
            geometry_geojson = json.dumps(feature_dict)
            
            # Get coordinates (for points, use directly; for others, use centroid)
            if isinstance(geometry, Point):
                lon = geometry.x
                lat = geometry.y
            else:
                centroid = geometry.centroid
                lon = centroid.x
                lat = centroid.y
            
            properties = json.dumps({k: str(v) for k, v in row.items() if k != "geometry"})
            
            rows.append((
                feature_id,
                int(osm_id),
                osm_type,
                row.get("name"),
                row.get("category"),
                lon,
                lat,
                geometry_wkb,
                geometry_geojson,
                properties,
                datetime.now()
            ))
        
        if rows:
            # Use INSERT OR REPLACE to handle duplicates
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO osm_pois 
                (feature_id, osm_id, osm_type, name, category, lon, lat, geometry_wkb, 
                 geometry_geojson, properties, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
    
    def get_nearby_osm_pois(
        self,
        lon: float,
        lat: float,
        distance_km: float = 5.0,
        categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get nearby OSM POIs within a distance.
        
        Args:
            lon: Longitude
            lat: Latitude
            distance_km: Distance in kilometers
            categories: Optional list of categories to filter by
            
        Returns:
            List of POI dictionaries
        """
        from shapely.geometry import Point
        import math
        
        # Rough bounding box calculation (1 degree ≈ 111 km)
        degree_buffer = distance_km / 111.0
        
        where_clauses = [
            "lon BETWEEN ? AND ?",
            "lat BETWEEN ? AND ?"
        ]
        params = [
            lon - degree_buffer,
            lon + degree_buffer,
            lat - degree_buffer,
            lat + degree_buffer
        ]
        
        if categories:
            placeholders = ",".join(["?"] * len(categories))
            where_clauses.append(f"category IN ({placeholders})")
            params.extend(categories)
        
        where_sql = " AND ".join(where_clauses)
        
        results = self.conn.execute(f"""
            SELECT feature_id, osm_id, osm_type, name, category, lon, lat, 
                   geometry_geojson, properties
            FROM osm_pois
            WHERE {where_sql}
        """, params).fetchall()
        
        # Calculate actual distances and filter
        poi_list = []
        for row in results:
            poi_lon = row[5]
            poi_lat = row[6]
            
            # Haversine distance calculation
            dlat = math.radians(poi_lat - lat)
            dlon = math.radians(poi_lon - lon)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(poi_lat)) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            distance = 6371 * c  # Earth radius in km
            
            if distance <= distance_km:
                properties = json.loads(row[8]) if row[8] else {}
                poi_list.append({
                    "feature_id": row[0],
                    "osm_id": row[1],
                    "osm_type": row[2],
                    "name": row[3],
                    "category": row[4],
                    "lon": poi_lon,
                    "lat": poi_lat,
                    "distance_km": round(distance, 2),
                    "geometry_geojson": row[7],
                    "properties": properties
                })
        
        # Sort by distance
        poi_list.sort(key=lambda x: x["distance_km"])
        
        return poi_list
    
    def get_nearby_osm_roads(
        self,
        lon: float,
        lat: float,
        distance_km: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Get nearby OSM roads within a distance.
        
        Args:
            lon: Longitude
            lat: Latitude
            distance_km: Distance in kilometers
            
        Returns:
            List of road dictionaries
        """
        from shapely.geometry import Point
        from shapely import wkb
        import math
        
        # Rough bounding box calculation
        degree_buffer = distance_km / 111.0
        
        results = self.conn.execute("""
            SELECT feature_id, osm_id, osm_type, name, highway, surface,
                   geometry_wkb, geometry_geojson, centroid_lon, centroid_lat, properties
            FROM osm_roads
            WHERE centroid_lon BETWEEN ? AND ? AND centroid_lat BETWEEN ? AND ?
        """, [
            lon - degree_buffer,
            lon + degree_buffer,
            lat - degree_buffer,
            lat + degree_buffer
        ]).fetchall()
        
        # Calculate actual distances and filter
        road_list = []
        point = Point(lon, lat)
        
        for row in results:
            geometry_wkb = row[6]
            try:
                geometry = wkb.loads(geometry_wkb, hex=True)
                # Calculate distance to line
                distance_m = geometry.distance(point) * 111000  # Convert to meters
                calculated_distance_km = distance_m / 1000
                
                if calculated_distance_km <= distance_km:
                    properties = json.loads(row[10]) if row[10] else {}
                    road_list.append({
                        "feature_id": row[0],
                        "osm_id": row[1],
                        "osm_type": row[2],
                        "name": row[3],
                        "highway": row[4],
                        "surface": row[5],
                        "distance_km": round(calculated_distance_km, 2),
                        "geometry_geojson": row[7],
                        "properties": properties
                    })
            except Exception:
                continue
        
        # Sort by distance
        road_list.sort(key=lambda x: x["distance_km"])
        
        return road_list
    
    def get_osm_pois_in_bbox(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        categories: Optional[List[str]] = None
    ) -> gpd.GeoDataFrame:
        """
        Get OSM POIs in a bounding box.
        
        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude
            categories: Optional list of categories to filter by
            
        Returns:
            GeoDataFrame with POIs
        """
        where_clauses = [
            "lon BETWEEN ? AND ?",
            "lat BETWEEN ? AND ?"
        ]
        params = [min_lon, max_lon, min_lat, max_lat]
        
        if categories:
            placeholders = ",".join(["?"] * len(categories))
            where_clauses.append(f"category IN ({placeholders})")
            params.extend(categories)
        
        where_sql = " AND ".join(where_clauses)
        
        results = self.conn.execute(f"""
            SELECT feature_id, name, category, lon, lat, geometry_wkb, properties
            FROM osm_pois
            WHERE {where_sql}
        """, params).fetchall()
        
        if not results:
            return gpd.GeoDataFrame(crs="EPSG:4326")
        
        features = []
        for row in results:
            geometry = wkb.loads(row[5], hex=True)
            properties = json.loads(row[6]) if row[6] else {}
            features.append({
                "feature_id": row[0],
                "name": row[1],
                "category": row[2],
                "lon": row[3],
                "lat": row[4],
                "geometry": geometry,
                "properties": properties
            })
        
        return gpd.GeoDataFrame(features, crs="EPSG:4326")
    
    def get_osm_roads_in_bbox(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float
    ) -> gpd.GeoDataFrame:
        """
        Get OSM roads in a bounding box.
        
        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude
            
        Returns:
            GeoDataFrame with roads
        """
        results = self.conn.execute("""
            SELECT feature_id, name, highway, surface, geometry_wkb, properties
            FROM osm_roads
            WHERE centroid_lon BETWEEN ? AND ? AND centroid_lat BETWEEN ? AND ?
        """, [min_lon, max_lon, min_lat, max_lat]).fetchall()
        
        if not results:
            return gpd.GeoDataFrame(crs="EPSG:4326")
        
        features = []
        for row in results:
            geometry = wkb.loads(row[4], hex=True)
            properties = json.loads(row[5]) if row[5] else {}
            features.append({
                "feature_id": row[0],
                "name": row[1],
                "highway": row[2],
                "surface": row[3],
                "geometry": geometry,
                "properties": properties
            })
        
        return gpd.GeoDataFrame(features, crs="EPSG:4326")
    
    def close(self):
        """Close database connection."""
        self.conn.close()

