#!/usr/bin/env python3
"""Extract OSM data (roads, POIs) for South Sudan and store in database."""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.scrapers.osm_data_extractor import OSMDataExtractor
from app.core.duckdb_store import DuckDBStore
from app.core.config import DUCKDB_PATH
from tqdm import tqdm
import argparse


def main():
    parser = argparse.ArgumentParser(description="Extract OSM data for South Sudan")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        help="POI categories to extract (default: all). Options: hospital, school, healthcare, unmiss, military, airport, government, police, prison, court, idp_camp, border, checkpoint, water, market, religious, bank, communication, power, fuel, ngo"
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be extracted, don't store in database"
    )
    
    args = parser.parse_args()
    
    # Initialize extractor
    extractor = OSMDataExtractor()
    
    # Determine feature types
    if args.categories is None:
        feature_types = list(extractor.POI_CATEGORIES.keys())
        print(f"Extracting all POI categories: {', '.join(feature_types)}")
    else:
        feature_types = args.categories
        invalid = [c for c in feature_types if c not in extractor.POI_CATEGORIES]
        if invalid:
            print(f"Error: Invalid categories: {', '.join(invalid)}")
            print(f"Valid categories: {', '.join(extractor.POI_CATEGORIES.keys())}")
            return 1
        print(f"Extracting POI categories: {', '.join(feature_types)}")
    
    # Determine bounding box
    bbox = None
    if args.bbox:
        bbox = tuple(args.bbox)
        print(f"Using bounding box: {bbox}")
    else:
        bbox = extractor.SOUTH_SUDAN_BBOX
        print(f"Using South Sudan bounding box: {bbox}")
    
    # Extract features
    print("\nStarting OSM data extraction...")
    print("This may take a while depending on the amount of data...")
    print("\n⚠️  NOTE: OSM data coverage in South Sudan is LIMITED.")
    print("   Many POI categories may have zero or very few results.")
    print("   Consider testing with a small bounding box first.")
    print("   See OSM_DATA_LIMITATIONS.md for more information.\n")
    
    try:
        gdfs = extractor.extract_features(
            feature_types=feature_types,
            bbox=bbox,
            include_roads=not args.no_roads
        )
        
        if not gdfs:
            print("No data extracted.")
            return 1
        
        # Display summary
        print("\n" + "="*60)
        print("EXTRACTION SUMMARY")
        print("="*60)
        for category, gdf in gdfs.items():
            print(f"{category:20s}: {len(gdf):6d} features")
        
        if args.dry_run:
            print("\nDry run mode - data not stored in database.")
            return 0
        
        # Store in database
        print("\n" + "="*60)
        print("STORING IN DATABASE")
        print("="*60)
        
        db_store = DuckDBStore(DUCKDB_PATH)
        
        # Store roads
        if "roads" in gdfs:
            print(f"\nStoring {len(gdfs['roads'])} roads...")
            db_store.ingest_osm_roads(gdfs["roads"])
            print("✓ Roads stored successfully")
        
        # Store POIs
        poi_categories = [cat for cat in gdfs.keys() if cat != "roads"]
        for category in poi_categories:
            if category in gdfs:
                print(f"\nStoring {len(gdfs[category])} {category} POIs...")
                db_store.ingest_osm_pois(gdfs[category])
                print(f"✓ {category.capitalize()} POIs stored successfully")
        
        db_store.close()
        
        print("\n" + "="*60)
        print("EXTRACTION COMPLETE")
        print("="*60)
        print(f"Database location: {DUCKDB_PATH}")
        print("\nYou can now view this data in the Geocoder map interface.")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nExtraction interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n\nError during extraction: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

