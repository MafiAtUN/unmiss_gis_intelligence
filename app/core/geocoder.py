"""Core geocoding engine with hierarchical resolution."""
from typing import Optional, List, Dict, Any
from shapely.geometry import Point
import geopandas as gpd
from app.core.models import GeocodeResult
from app.core.duckdb_store import DuckDBStore
from app.core.normalization import normalize_text, extract_candidates, parse_hierarchical_constraints
from app.core.fuzzy import fuzzy_match, progressive_fuzzy_match, apply_context_boost
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
        
        # Check cache - BUT skip cache if constraints are specified (to avoid stale wrong results)
        constraints = parse_hierarchical_constraints(text)
        has_constraints = any(constraints.values())
        
        if use_cache and not has_constraints:
            cached = self.db_store.get_cache(normalized)
            if cached:
                return GeocodeResult(
                    input_text=text,
                    normalized_text=normalized,
                    **cached
                )
        
        # Load admin layers if needed
        self._load_admin_layers()
        
        # Parse hierarchical constraints from input (state, county, payam, boma, village)
        # (Already parsed above if skipping cache, but parse again for consistency)
        if not has_constraints:
            constraints = parse_hierarchical_constraints(text)
        
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
            # Also use AI-extracted hierarchical info if available
            if ai_candidates.get("state_candidates"):
                constraints["state"] = constraints["state"] or normalize_text(ai_candidates["state_candidates"][0])
            if ai_candidates.get("county_candidates"):
                constraints["county"] = constraints["county"] or normalize_text(ai_candidates["county_candidates"][0])
            if ai_candidates.get("payam_candidates"):
                constraints["payam"] = constraints["payam"] or normalize_text(ai_candidates["payam_candidates"][0])
            if ai_candidates.get("boma_candidates"):
                constraints["boma"] = constraints["boma"] or normalize_text(ai_candidates["boma_candidates"][0])
            if ai_candidates.get("village_candidates"):
                constraints["village"] = constraints["village"] or normalize_text(ai_candidates["village_candidates"][0])
        
        # Try resolution in order: village -> boma -> payam (with constraints)
        result = self._resolve_hierarchical(candidates, text, normalized, constraints)
        
        # Cache result
        if use_cache:
            self.db_store.set_cache(result.to_dict())
        
        return result
    
    def _resolve_hierarchical(
        self,
        candidates: set,
        original_text: str,
        normalized_text: str,
        constraints: Dict[str, Optional[str]] = None
    ) -> GeocodeResult:
        """
        Resolve location using hierarchical matching.
        
        Args:
            candidates: Set of candidate place name strings
            original_text: Original input text
            normalized_text: Normalized input text
            constraints: Dictionary with state, county, payam, boma, village constraints
            
        Returns:
            GeocodeResult
        """
        if constraints is None:
            constraints = {}
        
        # 1. Try village/settlement point match (with constraints)
        village_result = self._try_settlement_match(candidates, constraints)
        if village_result:
            village_result.input_text = original_text
            village_result.normalized_text = normalized_text
            return village_result
        
        # 2. Try Boma polygon match (with constraints)
        boma_result = self._try_polygon_match("admin4_boma", candidates, constraints=constraints)
        if boma_result:
            boma_result.input_text = original_text
            boma_result.normalized_text = normalized_text
            return boma_result
        
        # 3. Try Payam polygon match (with constraints)
        payam_result = self._try_polygon_match("admin3_payam", candidates, constraints=constraints)
        if payam_result:
            payam_result.input_text = original_text
            payam_result.normalized_text = normalized_text
            return payam_result
        
        # 4. Check for County or State only (do not return coordinates, with constraints)
        county_result = self._try_polygon_match("admin2_county", candidates, return_coords=False, constraints=constraints)
        state_result = self._try_polygon_match("admin1_state", candidates, return_coords=False, constraints=constraints)
        
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
    
    def _try_settlement_match(self, candidates: set, constraints: Dict[str, Optional[str]] = None) -> Optional[GeocodeResult]:
        """Try to match against village points (from villages table)."""
        # First try villages table (new approach)
        best_match = None
        best_score = 0.0
        
        # Prioritize village name from constraints if available
        prioritized_candidates = []
        if constraints.get("village"):
            prioritized_candidates.append(constraints["village"])
            # Also try with "town" suffix if not already there
            village_name = constraints["village"]
            if "town" not in village_name.lower():
                prioritized_candidates.append(f"{village_name} town")
        # Add other candidates
        for candidate in candidates:
            if candidate not in prioritized_candidates:
                prioritized_candidates.append(candidate)
        
        for candidate in prioritized_candidates:
            # Search villages table (includes alternate names, with STRICT constraints)
            village_matches = self.db_store.search_villages(
                candidate,
                threshold=0.5,  # Lower threshold to get more candidates, then filter
                limit=20,  # Get more candidates for better selection
                include_alternates=True,
                state_constraint=constraints.get("state") if constraints else None,
                county_constraint=constraints.get("county") if constraints else None,
                payam_constraint=constraints.get("payam") if constraints else None,
                boma_constraint=constraints.get("boma") if constraints else None
            )
            
            # Filter out matches that violate constraints (double-check)
            for match in village_matches:
                # Skip if score is too low
                if match["score"] < FUZZY_THRESHOLD:
                    continue
                
                # Verify constraints are satisfied
                passes_constraints = True
                
                if constraints:
                    if constraints.get("state"):
                        match_state = (match.get("state") or "").lower().replace(" state", "").strip()
                        constraint_state = constraints["state"].lower().replace(" state", "").strip()
                        if match_state and constraint_state not in match_state and match_state not in constraint_state and constraint_state != match_state:
                            passes_constraints = False
                    
                    if passes_constraints and constraints.get("county"):
                        match_county = (match.get("county") or "").lower().replace(" county", "").strip()
                        constraint_county = constraints["county"].lower().replace(" county", "").strip()
                        if match_county and constraint_county not in match_county and match_county not in constraint_county and constraint_county != match_county:
                            passes_constraints = False
                
                if passes_constraints and match["score"] > best_score:
                    best_score = match["score"]
                    best_match = match
        
        # If found in villages table, validate constraints before returning
        if best_match:
            # Get full village details
            village = self.db_store.get_village(best_match["village_id"])
            if village:
                # FINAL VALIDATION: Reject if constraints are violated
                if constraints:
                    # Check state constraint
                    if constraints.get("state"):
                        constraint_state = constraints["state"].lower().replace(" state", "").strip()
                        village_state = (village.get("state") or "").lower().replace(" state", "").strip()
                        if village_state and constraint_state not in village_state and village_state not in constraint_state and constraint_state != village_state:
                            # Wrong state - reject this match
                            return None
                    
                    # Check county constraint
                    if constraints.get("county"):
                        constraint_county = constraints["county"].lower().replace(" county", "").strip()
                        village_county = (village.get("county") or "").lower().replace(" county", "").strip()
                        if village_county and constraint_county not in village_county and village_county not in constraint_county and constraint_county != village_county:
                            # Wrong county - reject this match
                            return None
                
                return GeocodeResult(
                    input_text="",  # Set by caller
                    normalized_text="",  # Set by caller
                    resolved_layer="villages",
                    feature_id=village["village_id"],
                    matched_name=best_match["name"],
                    score=best_score,
                    lon=village["lon"],
                    lat=village["lat"],
                    state=village.get("state"),
                    county=village.get("county"),
                    payam=village.get("payam"),
                    boma=village.get("boma"),
                    village=village["name"],
                    alternatives=[]
                )
        
        # Fallback to old settlements table if villages table not populated
        if "settlements" not in self.admin_layers:
            return None
        
        settlements_gdf = self.admin_layers["settlements"]
        if settlements_gdf.empty:
            return None
        
        # Search name index for settlements (legacy)
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            matches = self.db_store.search_name_index(
                candidate,
                layer="settlements",
                threshold=FUZZY_THRESHOLD,
                limit=5,
                state_constraint=constraints.get("state") if constraints else None,
                county_constraint=constraints.get("county") if constraints else None
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
        return_coords: bool = True,
        constraints: Dict[str, Optional[str]] = None
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
                limit=5,
                state_constraint=constraints.get("state") if constraints else None,
                county_constraint=constraints.get("county") if constraints else None,
                payam_constraint=constraints.get("payam") if constraints else None,
                boma_constraint=constraints.get("boma") if constraints else None
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
        
        # FINAL VALIDATION: Check constraints against spatial hierarchy
        if constraints:
            # Check state constraint
            if constraints.get("state"):
                constraint_state = constraints["state"].lower().replace(" state", "").strip()
                hierarchy_state = (hierarchy.get("state") or "").lower().replace(" state", "").strip()
                # Also check if this is the state layer itself
                if layer_name == "admin1_state":
                    feature_state = (best_match["canonical_name"] or "").lower().replace(" state", "").strip()
                    if feature_state and constraint_state not in feature_state and feature_state not in constraint_state and constraint_state != feature_state:
                        return None
                elif hierarchy_state and constraint_state not in hierarchy_state and hierarchy_state not in constraint_state and constraint_state != hierarchy_state:
                    # Wrong state - reject this match
                    return None
            
            # Check county constraint
            if constraints.get("county"):
                constraint_county = constraints["county"].lower().replace(" county", "").strip()
                hierarchy_county = (hierarchy.get("county") or "").lower().replace(" county", "").strip()
                # Also check if this is the county layer itself
                if layer_name == "admin2_county":
                    feature_county = (best_match["canonical_name"] or "").lower().replace(" county", "").strip()
                    if feature_county and constraint_county not in feature_county and feature_county not in constraint_county and constraint_county != feature_county:
                        return None
                elif hierarchy_county and constraint_county not in hierarchy_county and hierarchy_county not in constraint_county and constraint_county != hierarchy_county:
                    # Wrong county - reject this match
                    return None
        
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

