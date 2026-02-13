#!/usr/bin/env python3
"""Robust OSM data extraction with better error handling and incremental processing."""
import sys
from pathlib import Path
import time

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.scrapers.osm_data_extractor import OSMDataExtractor
from app.core.duckdb_store import DuckDBStore
from app.core.config import DUCKDB_PATH
import argparse


def extract_category_batch(extractor, db_store, categories, bbox, include_roads=False, retries=3):
    """Extract categories one at a time to avoid timeouts."""
    all_results = {}
    
    # Extract roads separately if requested
    if include_roads:
        print("\n" + "="*60)
        print("Extracting ROADS...")
        print("="*60)
        for attempt in range(retries):
            try:
                roads_result = extractor.extract_features(
                    feature_types=[],
                    bbox=bbox,
                    include_roads=True
                )
                if "roads" in roads_result and not roads_result["roads"].empty:
                    print(f"✓ Extracted {len(roads_result['roads'])} roads")
                    db_store.ingest_osm_roads(roads_result["roads"])
                    print("✓ Roads stored in database")
                    all_results["roads"] = roads_result["roads"]
                break
            except Exception as e:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 30
                    print(f"✗ Error (attempt {attempt + 1}/{retries}): {e}")
                    print(f"  Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"✗ Failed after {retries} attempts: {e}")
        time.sleep(5)  # Rate limiting
    
    # Extract POI categories one at a time
    for category in categories:
        print("\n" + "="*60)
        print(f"Extracting {category.upper()}...")
        print("="*60)
        
        for attempt in range(retries):
            try:
                result = extractor.extract_features(
                    feature_types=[category],
                    bbox=bbox,
                    include_roads=False
                )
                
                if category in result and not result[category].empty:
                    print(f"✓ Extracted {len(result[category])} {category} features")
                    db_store.ingest_osm_pois(result[category])
                    print(f"✓ {category.capitalize()} stored in database")
                    all_results[category] = result[category]
                else:
                    print(f"⚠ No {category} features found in this area")
                break
                
            except Exception as e:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 30
                    print(f"✗ Error (attempt {attempt + 1}/{retries}): {e}")
                    print(f"  Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"✗ Failed after {retries} attempts: {e}")
        
        # Rate limiting between categories
        time.sleep(10)
    
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Robust OSM data extraction for South Sudan")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        help="POI categories to extract (default: all)"
    )
    parser.add_argument(
        "--no-roads",
        action="store_true",
        help="Skip road extraction"
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        default=None,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="Bounding box (default: entire South Sudan)"
    )
    
    args = parser.parse_args()
    
    # Initialize
    extractor = OSMDataExtractor()
    
    # Determine feature types
    if args.categories is None:
        feature_types = list(extractor.POI_CATEGORIES.keys())
    else:
        feature_types = args.categories
        invalid = [c for c in feature_types if c not in extractor.POI_CATEGORIES]
        if invalid:
            print(f"Error: Invalid categories: {', '.join(invalid)}")
            return 1
    
    # Determine bounding box
    if args.bbox:
        bbox = tuple(args.bbox)
    else:
        bbox = extractor.SOUTH_SUDAN_BBOX
    
    print("="*60)
    print("OSM DATA EXTRACTION (Robust Mode)")
    print("="*60)
    print(f"Categories: {', '.join(feature_types)}")
    print(f"Bounding box: {bbox}")
    print(f"Include roads: {not args.no_roads}")
    print("\n⚠️  NOTE: This will extract categories ONE AT A TIME")
    print("   to avoid API timeouts. This may take a while.\n")
    
    # Initialize database
    try:
        db_store = DuckDBStore(DUCKDB_PATH)
        print("✓ Database connection established")
    except Exception as e:
        print(f"✗ Error connecting to database: {e}")
        print("\nMake sure no other process (like Streamlit) is using the database.")
        return 1
    
    # Extract in batches
    try:
        results = extract_category_batch(
            extractor,
            db_store,
            feature_types,
            bbox,
            include_roads=not args.no_roads,
            retries=3
        )
        
        # Summary
        print("\n" + "="*60)
        print("EXTRACTION COMPLETE")
        print("="*60)
        for key, gdf in results.items():
            print(f"{key:20s}: {len(gdf):6d} features")
        
        db_store.close()
        print(f"\n✓ Database location: {DUCKDB_PATH}")
        return 0
        
    except KeyboardInterrupt:
        print("\n\nExtraction interrupted by user.")
        db_store.close()
        return 1
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        db_store.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())

