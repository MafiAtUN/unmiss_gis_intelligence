#!/usr/bin/env python3
"""CLI script to build name index from DuckDB data."""
import argparse
import sys
from pathlib import Path
from app.core.duckdb_store import DuckDBStore
from app.core.config import DUCKDB_PATH


def main():
    parser = argparse.ArgumentParser(description="Build name index")
    parser.add_argument("--db-path", type=Path, default=DUCKDB_PATH,
                       help="DuckDB database path")
    
    args = parser.parse_args()
    
    print("Building name index...")
    db_store = DuckDBStore(args.db_path)
    db_store.build_name_index()
    print("✅ Index built successfully")
    
    db_store.close()


if __name__ == "__main__":
    main()

