"""Core geocoding engine with hierarchical resolution."""
from typing import Optional, List, Dict, Any
from shapely.geometry import Point
import geopandas as gpd
from app.core.models import GeocodeResult
from app.core.duckdb_store import DuckDBStore
from app.core.normalization import normalize_text, extract_candidates
from app.core.fuzzy import fuzzy_match
from app.core.spatial import get_admin_hierarchy
from app.core.centroids import compute_centroid
from app.core.azure_ai import AzureAIParser
from app.core.config import FUZZY_THRESHOLD, LAYER_NAMES


class Geocoder:
    """Main geocoding engine."""
    
    def __init__(self, db_store: DuckDBStore):
        """
        Initialize geocoder.
        
        Args:
            db_store: DuckDBStore instance
        """
        self.db_store = db_store
        self.azure_parser = AzureAIParser()
        self.admin_layers = {}  # Cache for loaded admin layers
    
    def _load_admin_layers(self):
        """Load admin layers from DuckDB into memory."""
        if self.admin_layers:
            return
        
        for layer_name in LAYER_NAMES.values():
            # Load geometries from DuckDB
            result = self.db_store.conn.execute(f"""
                SELECT feature_id, geometry_wkb, name, properties
                FROM {layer_name}
            """).fetchall()
            
            if not result:
                continue
            
            from shapely import wkb
            import json
            
            features = []
            for feature_id, geometry_wkb, name, properties_str in result:
                geometry = wkb.loads(geometry_wkb, hex=True)
                props = json.loads(properties_str) if properties_str else {}
                props["name"] = name
                props["feature_id"] = feature_id
                
                features.append({
                    "feature_id": feature_id,
                    "name": name,
                    "geometry": geometry,
                    "properties": props
                })
            
            if features:
                gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
                # Set feature_id as index for easier lookup
                if "feature_id" in gdf.columns:
                    gdf = gdf.set_index("feature_id")
                self.admin_layers[layer_name] = gdf
    
    def geocode(self, text: str, use_cache: bool = True) -> GeocodeResult:
        """
        Geocode a free text location string.
        
        Resolution order:
        1. Village/settlement point match
        2. Boma polygon match
        3. Payam polygon match
        Do not return coordinates for County or State only.
        
        Args:
            text: Free text location string
            use_cache: Whether to use cache
            
        Returns:
            GeocodeResult object
        """
        normalized = normalize_text(text)
        
        # Check cache
        if use_cache:
            cached = self.db_store.get_cache(normalized)
            if cached:
                return GeocodeResult(
                    input_text=text,
                    normalized_text=normalized,
                    **cached
                )
        
        # Load admin layers if needed
        self._load_admin_layers()
        
        # Extract candidates (deterministic + optional AI)
        candidates = extract_candidates(text)
        
        # Optionally use Azure AI for extraction
        if self.azure_parser.enabled:
            ai_candidates = self.azure_parser.extract_candidates(text)
            # Merge AI candidates into deterministic candidates
            for level_candidates in ai_candidates.values():
                if isinstance(level_candidates, list):
                    for candidate in level_candidates:
                        candidates.add(normalize_text(candidate))
        
        # Try resolution in order: village -> boma -> payam
        result = self._resolve_hierarchical(candidates, text, normalized)
        
        # Cache result
        if use_cache:
            self.db_store.set_cache(result.to_dict())
        
        return result
    
    def _resolve_hierarchical(
        self,
        candidates: set,
        original_text: str,
        normalized_text: str
    ) -> GeocodeResult:
        """
        Resolve location using hierarchical matching.
        
        Args:
            candidates: Set of candidate place name strings
            original_text: Original input text
            normalized_text: Normalized input text
            
        Returns:
            GeocodeResult
        """
        # 1. Try village/settlement point match
        village_result = self._try_settlement_match(candidates)
        if village_result:
            village_result.input_text = original_text
            village_result.normalized_text = normalized_text
            return village_result
        
        # 2. Try Boma polygon match
        boma_result = self._try_polygon_match("admin4_boma", candidates)
        if boma_result:
            boma_result.input_text = original_text
            boma_result.normalized_text = normalized_text
            return boma_result
        
        # 3. Try Payam polygon match
        payam_result = self._try_polygon_match("admin3_payam", candidates)
        if payam_result:
            payam_result.input_text = original_text
            payam_result.normalized_text = normalized_text
            return payam_result
        
        # 4. Check for County or State only (do not return coordinates)
        county_result = self._try_polygon_match("admin2_county", candidates, return_coords=False)
        state_result = self._try_polygon_match("admin1_state", candidates, return_coords=False)
        
        if county_result or state_result:
            # Return best match suggestions without coordinates
            best_match = county_result if county_result else state_result
            best_match.input_text = original_text
            best_match.normalized_text = normalized_text
            best_match.resolution_too_coarse = True
            best_match.lon = None
            best_match.lat = None
            return best_match
        
        # No match found
        return GeocodeResult(
            input_text=original_text,
            normalized_text=normalized_text,
            score=0.0
        )
    
    def _try_settlement_match(self, candidates: set) -> Optional[GeocodeResult]:
        """Try to match against settlement points."""
        if "settlements" not in self.admin_layers:
            return None
        
        settlements_gdf = self.admin_layers["settlements"]
        if settlements_gdf.empty:
            return None
        
        # Search name index for settlements
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            matches = self.db_store.search_name_index(
                candidate,
                layer="settlements",
                threshold=FUZZY_THRESHOLD,
                limit=5
            )
            
            for match in matches:
                if match["score"] > best_score:
                    best_score = match["score"]
                    best_match = match
        
        if not best_match:
            return None
        
        # Get settlement point
        feature_id = best_match["feature_id"]
        feature = self.db_store.get_feature("settlements", feature_id)
        
        if not feature:
            return None
        
        lon = feature["centroid_lon"]
        lat = feature["centroid_lat"]
        point = Point(lon, lat)
        
        # Get admin hierarchy
        hierarchy = get_admin_hierarchy(point, self.admin_layers)
        
        # Get alternatives
        alternatives = self._get_alternatives("settlements", candidates, limit=5)
        
        return GeocodeResult(
            input_text="",  # Set by caller
            normalized_text="",  # Set by caller
            resolved_layer="settlements",
            feature_id=feature_id,
            matched_name=best_match["canonical_name"],
            score=best_score,
            lon=lon,
            lat=lat,
            state=hierarchy.get("state"),
            county=hierarchy.get("county"),
            payam=hierarchy.get("payam"),
            boma=hierarchy.get("boma"),
            village=best_match["canonical_name"],
            alternatives=alternatives
        )
    
    def _try_polygon_match(
        self,
        layer_name: str,
        candidates: set,
        return_coords: bool = True
    ) -> Optional[GeocodeResult]:
        """Try to match against polygon layer."""
        if layer_name not in self.admin_layers:
            return None
        
        gdf = self.admin_layers[layer_name]
        if gdf.empty:
            return None
        
        # Search name index
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            matches = self.db_store.search_name_index(
                candidate,
                layer=layer_name,
                threshold=FUZZY_THRESHOLD,
                limit=5
            )
            
            for match in matches:
                if match["score"] > best_score:
                    best_score = match["score"]
                    best_match = match
        
        if not best_match:
            return None
        
        # Get feature
        feature_id = best_match["feature_id"]
        feature = self.db_store.get_feature(layer_name, feature_id)
        
        if not feature:
            return None
        
        # Get geometry
        geometry = self.db_store.get_geometry(layer_name, feature_id)
        if not geometry:
            return None
        
        # Compute centroid if returning coordinates
        lon, lat = None, None
        if return_coords:
            try:
                lon, lat = compute_centroid(geometry)
            except Exception:
                pass
        
        # Get admin hierarchy
        if lon and lat:
            point = Point(lon, lat)
            hierarchy = get_admin_hierarchy(point, self.admin_layers)
        else:
            hierarchy = {}
        
        # Map layer to hierarchy field
        layer_map = {
            "admin4_boma": "boma",
            "admin3_payam": "payam",
            "admin2_county": "county",
            "admin1_state": "state",
        }
        
        hierarchy_field = layer_map.get(layer_name)
        if hierarchy_field:
            hierarchy[hierarchy_field] = best_match["canonical_name"]
        
        # Get alternatives
        alternatives = self._get_alternatives(layer_name, candidates, limit=5)
        
        return GeocodeResult(
            input_text="",  # Set by caller
            normalized_text="",  # Set by caller
            resolved_layer=layer_name,
            feature_id=feature_id,
            matched_name=best_match["canonical_name"],
            score=best_score,
            lon=lon,
            lat=lat,
            state=hierarchy.get("state"),
            county=hierarchy.get("county"),
            payam=hierarchy.get("payam"),
            boma=hierarchy.get("boma"),
            alternatives=alternatives
        )
    
    def _get_alternatives(
        self,
        layer: str,
        candidates: set,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get alternative matches for a layer."""
        alternatives = []
        
        for candidate in candidates:
            matches = self.db_store.search_name_index(
                candidate,
                layer=layer,
                threshold=FUZZY_THRESHOLD * 0.8,  # Lower threshold for alternatives
                limit=limit
            )
            
            for match in matches:
                feature = self.db_store.get_feature(layer, match["feature_id"])
                if feature:
                    alt = {
                        "layer": layer,
                        "feature_id": match["feature_id"],
                        "name": match["canonical_name"],
                        "score": match["score"],
                        "lon": feature.get("centroid_lon"),
                        "lat": feature.get("centroid_lat"),
                    }
                    alternatives.append(alt)
        
        # Deduplicate and sort
        seen = set()
        unique_alts = []
        for alt in sorted(alternatives, key=lambda x: x["score"], reverse=True):
            key = (alt["layer"], alt["feature_id"])
            if key not in seen:
                seen.add(key)
                unique_alts.append(alt)
                if len(unique_alts) >= limit:
                    break
        
        return unique_alts

