#!/usr/bin/env python3
"""CLI script to ingest GeoJSON files into DuckDB."""
import argparse
import sys
from pathlib import Path
import geopandas as gpd
from app.core.duckdb_store import DuckDBStore
from app.core.config import DUCKDB_PATH, LAYER_NAMES


def main():
    parser = argparse.ArgumentParser(description="Ingest GeoJSON into DuckDB")
    parser.add_argument("file", type=Path, help="GeoJSON file path")
    parser.add_argument("--layer", required=True, choices=list(LAYER_NAMES.values()),
                       help="Layer name")
    parser.add_argument("--name-field", default="name", help="Name field (default: name)")
    parser.add_argument("--db-path", type=Path, default=DUCKDB_PATH,
                       help="DuckDB database path")
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    
    # Load GeoJSON
    print(f"Loading {args.file}...")
    gdf = gpd.read_file(args.file)
    print(f"Loaded {len(gdf)} features")
    
    # Ingest
    print(f"Ingesting into {args.layer}...")
    db_store = DuckDBStore(args.db_path)
    db_store.ingest_geojson(args.layer, gdf, args.name_field)
    print("✅ Ingested successfully")
    
    # Build index
    print("Building name index...")
    db_store.build_name_index()
    print("✅ Index built")
    
    db_store.close()


if __name__ == "__main__":
    main()

