"""Script to scrape all villages and locations in South Sudan from open sources."""
import sys
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import tqdm, but don't fail if not available
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Simple progress function if tqdm not available
    def tqdm(iterable, desc=""):
        print(f"{desc}: Starting...")
        return iterable

from app.core.duckdb_store import DuckDBStore
from app.core.spatial import detect_admin_boundaries_from_point
from app.core.config import PROJECT_ROOT
from shapely.geometry import Point
import requests


# South Sudan bounding box (min_lon, min_lat, max_lon, max_lat)
SOUTH_SUDAN_BBOX = (23.886979, 3.48898, 35.298, 12.248008)

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Place types to scrape from OSM
PLACE_TYPES = ["village", "hamlet", "town", "city", "isolated_dwelling", "suburb", "neighbourhood"]


def scrape_osm_places(bbox: tuple, place_types: list, chunk_size: int = 1000):
    """
    Scrape all places from OpenStreetMap within bounding box.
    
    Args:
        bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
        place_types: List of place types to scrape
        chunk_size: Number of results per query (to avoid timeout)
        
    Yields:
        Dict with place information
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # Build place type filter
    place_filter = "|".join(place_types)
    
    # Query to get all places with names in South Sudan
    # We'll query in chunks to avoid timeout
    query = f"""
    [out:json][timeout:300];
    (
      node["place"~"^({place_filter})$"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["place"~"^({place_filter})$"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["place"~"^({place_filter})$"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    
    try:
        print("Querying Overpass API...")
        response = requests.post(
            OVERPASS_URL,
            data=query,
            headers={"Content-Type": "text/plain"},
            timeout=600  # 10 minutes timeout
        )
        response.raise_for_status()
        
        data = response.json()
        elements = data.get("elements", [])
        
        print(f"Found {len(elements)} places in OSM")
        
        for element in elements:
            # Get coordinates
            lon = None
            lat = None
            
            if element["type"] == "node":
                lon = element.get("lon")
                lat = element.get("lat")
            elif element["type"] in ["way", "relation"]:
                center = element.get("center", {})
                lon = center.get("lon")
                lat = center.get("lat")
            
            if lon is None or lat is None:
                continue
            
            # Get properties
            tags = element.get("tags", {})
            name = tags.get("name", "").strip()
            
            if not name:
                continue
            
            place_type = tags.get("place", "")
            
            yield {
                "name": name,
                "lon": lon,
                "lat": lat,
                "place_type": place_type,
                "osm_id": element["id"],
                "osm_type": element["type"],
                "properties": {
                    "osm_id": element["id"],
                    "osm_type": element["type"],
                    "place_type": place_type,
                    "admin_level": tags.get("admin_level"),
                    "wikidata": tags.get("wikidata"),
                    "wikipedia": tags.get("wikipedia"),
                    "population": tags.get("population"),
                    **{k: v for k, v in tags.items() if k not in ["name", "place"] and v}
                }
            }
        
        # Rate limiting
        time.sleep(2)
    
    except requests.exceptions.RequestException as e:
        print(f"Error querying Overpass API: {e}")
        return
    except Exception as e:
        print(f"Error processing OSM results: {e}")
        import traceback
        traceback.print_exc()
        return


def scrape_all_locations(db_store: DuckDBStore, bbox: tuple = SOUTH_SUDAN_BBOX):
    """
    Scrape all locations from OSM and store in database.
    
    Args:
        db_store: DuckDBStore instance
        bbox: Bounding box for South Sudan
    """
    print("=" * 80)
    print("Scraping all villages and locations in South Sudan from OpenStreetMap")
    print("=" * 80)
    
    # Get existing village count
    existing_count = db_store.conn.execute("SELECT COUNT(*) FROM villages").fetchone()[0]
    print(f"Existing villages in database: {existing_count}")
    
    # Scrape from OSM
    print("\nScraping from OpenStreetMap...")
    places = list(scrape_osm_places(bbox, PLACE_TYPES))
    
    if not places:
        print("No places found to scrape")
        return
    
    print(f"\nProcessing {len(places)} places...")
    
    # Process each place
    added = 0
    skipped = 0
    updated = 0
    errors = []
    
    # Use tqdm if available, otherwise simple iteration
    if HAS_TQDM:
        places_iter = tqdm(places, desc="Processing places")
    else:
        places_iter = places
        print(f"Processing {len(places)} places...")
    
    for place in places_iter:
        try:
            name = place["name"]
            lon = place["lon"]
            lat = place["lat"]
            
            # Check if village already exists (by coordinates with small tolerance)
            existing = db_store.get_village_by_coordinates(lon, lat, tolerance=0.0001)
            
            if existing:
                # If exists but from different source, we could add as alternate source
                # For now, skip if already exists to avoid duplicates
                # Could enhance later to merge data sources
                if existing.get("data_source") == "osm" and existing.get("source_id") == f"osm_{place['osm_type']}_{place['osm_id']}":
                    # Same source, definitely skip
                    skipped += 1
                    continue
                # Different source or no source_id match - could add, but skip for now to avoid duplicates
                skipped += 1
                continue
            
            # Auto-detect admin boundaries
            point = Point(lon, lat)
            hierarchy = detect_admin_boundaries_from_point(point)
            
            # Prepare properties
            properties = place.get("properties", {})
            properties["scraped_from"] = "osm"
            properties["scrape_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Add village to database
            village_id = db_store.add_village(
                name=name,
                lon=lon,
                lat=lat,
                state=hierarchy.get("state"),
                county=hierarchy.get("county"),
                payam=hierarchy.get("payam"),
                boma=hierarchy.get("boma"),
                state_id=hierarchy.get("state_id"),
                county_id=hierarchy.get("county_id"),
                payam_id=hierarchy.get("payam_id"),
                boma_id=hierarchy.get("boma_id"),
                data_source="osm",
                source_id=f"osm_{place['osm_type']}_{place['osm_id']}",
                confidence_score=0.8,  # Medium confidence for scraped data
                verified=False,
                properties=properties
            )
            
            # Add alternate names if available
            # OSM might have name:en, name:ar, etc.
            for key, value in place.get("properties", {}).items():
                if key.startswith("name:") and value and value != name:
                    try:
                        db_store.add_alternate_name(
                            village_id=village_id,
                            alternate_name=str(value).strip(),
                            name_type="translation",
                            source="osm"
                        )
                    except Exception:
                        pass  # Skip duplicates
            
            added += 1
            
            # Small delay to avoid overwhelming the database
            if added % 100 == 0:
                time.sleep(0.1)
        
        except Exception as e:
            errors.append((place.get("name", "unknown"), str(e)))
            continue
    
    print("\n" + "=" * 80)
    print("Scraping complete!")
    print("=" * 80)
    print(f"  Added: {added}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Errors: {len(errors)}")
    
    if errors:
        print("\nFirst 10 errors:")
        for name, error in errors[:10]:
            print(f"  {name}: {error}")
    
    # Show final count
    final_count = db_store.conn.execute("SELECT COUNT(*) FROM villages").fetchone()[0]
    print(f"\nTotal villages in database: {final_count}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape all villages from open sources")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to DuckDB database (defaults to config default)"
    )
    parser.add_argument(
        "--min-lon",
        type=float,
        default=SOUTH_SUDAN_BBOX[0],
        help="Minimum longitude"
    )
    parser.add_argument(
        "--min-lat",
        type=float,
        default=SOUTH_SUDAN_BBOX[1],
        help="Minimum latitude"
    )
    parser.add_argument(
        "--max-lon",
        type=float,
        default=SOUTH_SUDAN_BBOX[2],
        help="Maximum longitude"
    )
    parser.add_argument(
        "--max-lat",
        type=float,
        default=SOUTH_SUDAN_BBOX[3],
        help="Maximum latitude"
    )
    
    args = parser.parse_args()
    
    bbox = (args.min_lon, args.min_lat, args.max_lon, args.max_lat)
    
    db_store = DuckDBStore(db_path=args.db_path) if args.db_path else DuckDBStore()
    
    try:
        scrape_all_locations(db_store, bbox)
    finally:
        db_store.close()


if __name__ == "__main__":
    main()

