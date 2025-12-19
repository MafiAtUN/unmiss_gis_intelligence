"""Script to ingest compiled dataset Excel file into villages table."""
import sys
from pathlib import Path
import pandas as pd
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.duckdb_store import DuckDBStore
from app.core.config import PROJECT_ROOT


def ingest_compiled_dataset(
    excel_path: Path,
    sheet_name: str = "Complete data set - Boma",
    db_store: DuckDBStore = None
):
    """
    Ingest compiled dataset Excel file into villages table.
    
    Args:
        excel_path: Path to Excel file
        sheet_name: Name of sheet to ingest
        db_store: DuckDBStore instance (creates new if None)
    """
    if db_store is None:
        db_store = DuckDBStore()
    
    # Read Excel file
    print(f"Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    
    print(f"Found {len(df)} rows")
    
    # Column mapping
    # featureNam -> name
    # POINT_X -> lon
    # POINT_Y -> lat
    # admin1_state -> state
    # admin2_county -> county
    # admin3_payam -> payam
    # admin4_boma -> boma
    # County_id -> county_id
    # Payam_id -> payam_id
    # Boma_id -> boma_id
    # featureRef -> alternate name (if different from featureNam)
    # featureAlt -> alternate name
    
    rows_processed = 0
    rows_skipped = 0
    errors = []
    
    print("Ingesting villages...")
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing rows"):
        try:
            # Skip rows with missing coordinates
            if pd.isna(row.get("POINT_X")) or pd.isna(row.get("POINT_Y")):
                rows_skipped += 1
                continue
            
            # Skip rows with missing feature name
            feature_name = row.get("featureNam")
            if pd.isna(feature_name) or not str(feature_name).strip():
                rows_skipped += 1
                continue
            
            name = str(feature_name).strip()
            lon = float(row["POINT_X"])
            lat = float(row["POINT_Y"])
            
            # Admin boundaries
            state = str(row.get("admin1_state", "")).strip() if pd.notna(row.get("admin1_state")) else None
            county = str(row.get("admin2_county", "")).strip() if pd.notna(row.get("admin2_county")) else None
            payam = str(row.get("admin3_payam", "")).strip() if pd.notna(row.get("admin3_payam")) else None
            boma = str(row.get("admin4_boma", "")).strip() if pd.notna(row.get("admin4_boma")) else None
            
            # Admin IDs
            county_id = str(int(row["County_id"])) if pd.notna(row.get("County_id")) else None
            payam_id = str(int(row["Payam_id"])) if pd.notna(row.get("Payam_id")) else None
            boma_id = str(int(row["Boma_id"])) if pd.notna(row.get("Boma_id")) else None
            
            # Add village
            village_id = db_store.add_village(
                name=name,
                lon=lon,
                lat=lat,
                state=state if state else None,
                county=county if county else None,
                payam=payam if payam else None,
                boma=boma if boma else None,
                county_id=county_id,
                payam_id=payam_id,
                boma_id=boma_id,
                data_source="compiled_dataset",
                source_id=str(idx),
                verified=False
            )
            
            # Add alternate names if present
            feature_ref = row.get("featureRef")
            if pd.notna(feature_ref) and str(feature_ref).strip() and str(feature_ref).strip() != name:
                try:
                    db_store.add_alternate_name(
                        village_id=village_id,
                        alternate_name=str(feature_ref).strip(),
                        name_type="alias",
                        source="compiled_dataset"
                    )
                except Exception as e:
                    # Skip duplicate alternate names
                    pass
            
            feature_alt = row.get("featureAlt")
            if pd.notna(feature_alt) and str(feature_alt).strip() and str(feature_alt).strip() != name:
                try:
                    db_store.add_alternate_name(
                        village_id=village_id,
                        alternate_name=str(feature_alt).strip(),
                        name_type="variant",
                        source="compiled_dataset"
                    )
                except Exception as e:
                    # Skip duplicate alternate names
                    pass
            
            rows_processed += 1
            
        except Exception as e:
            errors.append((idx, str(e)))
            rows_skipped += 1
            continue
    
    print(f"\nIngestion complete!")
    print(f"  Rows processed: {rows_processed}")
    print(f"  Rows skipped: {rows_skipped}")
    if errors:
        print(f"  Errors: {len(errors)}")
        print("\nFirst 10 errors:")
        for idx, error in errors[:10]:
            print(f"    Row {idx}: {error}")
    
    return rows_processed, rows_skipped, errors


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest compiled dataset Excel file into villages table")
    parser.add_argument(
        "--excel-path",
        type=Path,
        default=PROJECT_ROOT / "resources" / "GPS point data" / "Compiled dataset.xlsx",
        help="Path to Excel file"
    )
    parser.add_argument(
        "--sheet-name",
        type=str,
        default="Complete data set - Boma",
        help="Sheet name to ingest"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to DuckDB database (defaults to config default)"
    )
    
    args = parser.parse_args()
    
    if not args.excel_path.exists():
        print(f"Error: Excel file not found: {args.excel_path}")
        sys.exit(1)
    
    db_store = DuckDBStore(db_path=args.db_path) if args.db_path else DuckDBStore()
    
    try:
        ingest_compiled_dataset(
            excel_path=args.excel_path,
            sheet_name=args.sheet_name,
            db_store=db_store
        )
    finally:
        db_store.close()


if __name__ == "__main__":
    main()

