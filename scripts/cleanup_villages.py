"""Script to clean up villages: ensure all are within South Sudan and have admin boundaries."""
import sys
from pathlib import Path
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.duckdb_store import DuckDBStore
from app.core.spatial import detect_admin_boundaries_from_point
from app.core.config import PROJECT_ROOT, DUCKDB_PATH
from shapely.geometry import Point
import geopandas as gpd

# South Sudan bounding box (min_lon, min_lat, max_lon, max_lat)
SOUTH_SUDAN_BBOX = (23.886979, 3.48898, 35.298, 12.248008)


def is_within_south_sudan_bbox(lon: float, lat: float) -> bool:
    """Check if coordinates are within South Sudan bounding box."""
    min_lon, min_lat, max_lon, max_lat = SOUTH_SUDAN_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def cleanup_villages(db_store: DuckDBStore):
    """
    Clean up villages:
    1. Re-detect admin boundaries for all villages
    2. Delete villages outside South Sudan
    3. Ensure all remaining villages have admin boundaries
    """
    print("=" * 80)
    print("Cleaning up villages database")
    print("=" * 80)
    
    # Load Boma GeoJSON to get all polygons for spatial join
    boma_geojson_path = PROJECT_ROOT / "resources" / "GeoJSON" / "SS_Boma_GeoJSON.geojson"
    
    if not boma_geojson_path.exists():
        print(f"Error: Boma GeoJSON not found at {boma_geojson_path}")
        return
    
    print(f"\nLoading Boma GeoJSON from {boma_geojson_path}")
    boma_gdf = gpd.read_file(boma_geojson_path)
    
    if boma_gdf.crs != "EPSG:4326":
        boma_gdf = boma_gdf.to_crs("EPSG:4326")
    
    print(f"Loaded {len(boma_gdf)} boma polygons")
    
    # Get all villages
    villages = db_store.conn.execute("""
        SELECT village_id, name, lon, lat, state, county, payam, boma
        FROM villages
    """).fetchall()
    
    print(f"\nTotal villages to check: {len(villages)}")
    
    # Process each village
    updated = 0
    deleted = 0
    errors = []
    
    for village_id, name, lon, lat, state, county, payam, boma in tqdm(villages, desc="Processing villages"):
        try:
            # Check if within South Sudan bounding box
            if not is_within_south_sudan_bbox(lon, lat):
                # Delete village outside South Sudan
                db_store.delete_village(village_id)
                deleted += 1
                continue
            
            # Check if already has admin boundaries
            if state and county and payam and boma:
                # Already has complete admin boundaries, skip
                continue
            
            # Re-detect admin boundaries
            point = Point(lon, lat)
            hierarchy = detect_admin_boundaries_from_point(point, boma_geojson_path)
            
            # If still no boma found, try spatial join directly with GeoDataFrame
            if not hierarchy.get("boma"):
                # Perform spatial join directly
                point_gdf = gpd.GeoDataFrame([{"geometry": point}], crs="EPSG:4326")
                joined = gpd.sjoin(point_gdf, boma_gdf, how="inner", predicate="within")
                
                if not joined.empty:
                    match = joined.iloc[0]
                    hierarchy["state"] = match.get("STATE") or match.get("state")
                    hierarchy["county"] = match.get("COUNTY") or match.get("county")
                    hierarchy["payam"] = match.get("PAYAM") or match.get("payam")
                    hierarchy["boma"] = match.get("BOMA") or match.get("boma")
                    hierarchy["state_id"] = str(match.get("STA_CODE", "")) if match.get("STA_CODE") else None
                    hierarchy["county_id"] = str(match.get("CTY_CODE", "")) if match.get("CTY_CODE") else None
                    hierarchy["payam_id"] = str(match.get("PAY_CODE", "")) if match.get("PAY_CODE") else None
                    hierarchy["boma_id"] = str(match.get("BOM_CODE", "")) or str(match.get("OBJECTID", "")) if match.get("BOM_CODE") or match.get("OBJECTID") else None
            
            # If still no boma found, try "touches" predicate (for border cases)
            if not hierarchy.get("boma"):
                point_gdf = gpd.GeoDataFrame([{"geometry": point}], crs="EPSG:4326")
                joined = gpd.sjoin(point_gdf, boma_gdf, how="inner", predicate="touches")
                
                if not joined.empty:
                    # Use the first match (for border cases, pick one)
                    match = joined.iloc[0]
                    hierarchy["state"] = match.get("STATE") or match.get("state")
                    hierarchy["county"] = match.get("COUNTY") or match.get("county")
                    hierarchy["payam"] = match.get("PAYAM") or match.get("payam")
                    hierarchy["boma"] = match.get("BOMA") or match.get("boma")
                    hierarchy["state_id"] = str(match.get("STA_CODE", "")) if match.get("STA_CODE") else None
                    hierarchy["county_id"] = str(match.get("CTY_CODE", "")) if match.get("CTY_CODE") else None
                    hierarchy["payam_id"] = str(match.get("PAY_CODE", "")) if match.get("PAY_CODE") else None
                    hierarchy["boma_id"] = str(match.get("BOM_CODE", "")) or str(match.get("OBJECTID", "")) if match.get("BOM_CODE") or match.get("OBJECTID") else None
            
            # If we found admin boundaries, update the village
            if hierarchy.get("boma"):
                db_store.update_village_admin_boundaries(
                    village_id=village_id,
                    state=hierarchy.get("state"),
                    county=hierarchy.get("county"),
                    payam=hierarchy.get("payam"),
                    boma=hierarchy.get("boma"),
                    state_id=hierarchy.get("state_id"),
                    county_id=hierarchy.get("county_id"),
                    payam_id=hierarchy.get("payam_id"),
                    boma_id=hierarchy.get("boma_id")
                )
                updated += 1
            else:
                # Still no boma found - this point is likely outside all boma boundaries
                # Check if it's very close to border (within ~1km tolerance)
                # For now, delete it as it's not properly within any boma
                db_store.delete_village(village_id)
                deleted += 1
                
        except Exception as e:
            errors.append((village_id, name, str(e)))
            continue
    
    print("\n" + "=" * 80)
    print("Cleanup complete!")
    print("=" * 80)
    print(f"  Updated with admin boundaries: {updated}")
    print(f"  Deleted (outside South Sudan or no boma): {deleted}")
    print(f"  Errors: {len(errors)}")
    
    if errors:
        print("\nFirst 10 errors:")
        for village_id, name, error in errors[:10]:
            print(f"  {name} ({village_id}): {error}")
    
    # Final statistics
    final_count = db_store.conn.execute("SELECT COUNT(*) FROM villages").fetchone()[0]
    with_boundaries = db_store.conn.execute("""
        SELECT COUNT(*) FROM villages WHERE boma IS NOT NULL
    """).fetchone()[0]
    
    print(f"\nFinal Statistics:")
    print(f"  Total villages: {final_count}")
    print(f"  Villages with admin boundaries: {with_boundaries} ({with_boundaries/final_count*100:.1f}%)")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up villages database")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to DuckDB database (defaults to config default)"
    )
    
    args = parser.parse_args()
    
    db_store = DuckDBStore(db_path=args.db_path) if args.db_path else DuckDBStore()
    
    try:
        cleanup_villages(db_store)
    finally:
        db_store.close()


if __name__ == "__main__":
    main()


