#!/usr/bin/env python3
"""
Process casualty matrix to extract locations from Description and geocode them.

This script demonstrates the workflow:
1. Extract location strings from Description column
2. Standardize and copy to Location of Incident column
3. Geocode to get boma, payam, county, GPS coordinates
4. Update Excel file with geocoded data
"""

import pandas as pd
import sys
import os
from typing import Optional, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder
from app.core.location_extractor import DocumentLocationExtractor


def extract_location_from_description(description: str, extractor: DocumentLocationExtractor) -> Optional[str]:
    """
    Extract location string from description text.
    
    Args:
        description: Description text
        extractor: DocumentLocationExtractor instance
        
    Returns:
        Extracted location string or None
    """
    if not description or pd.isna(description):
        return None
    
    description_str = str(description)
    
    # Use location extractor to find locations
    try:
        result = extractor.extract_locations(description_str, geocode=False)
        
        # Get all extracted locations
        all_locations = result.regex_locations + result.ollama_locations + result.ai_locations
        
        if not all_locations:
            return None
        
        # Find the most specific location (prefer ones with Boma/Payam/County)
        best_location = None
        best_specificity = 0
        
        for loc in all_locations:
            text = loc.original_text
            # Calculate specificity: count of admin levels mentioned
            specificity = 0
            if any(word in text.lower() for word in ['boma', 'village', 'town', 'settlement']):
                specificity += 3
            if 'payam' in text.lower():
                specificity += 2
            if 'county' in text.lower():
                specificity += 1
            
            if specificity > best_specificity:
                best_specificity = specificity
                best_location = text
        
        return best_location
    
    except Exception as e:
        print(f"Error extracting location: {e}")
        return None


def standardize_location(location: str, state: Optional[str] = None) -> str:
    """
    Standardize location string format.
    
    Args:
        location: Location string
        state: Optional state name for context
        
    Returns:
        Standardized location string
    """
    if not location:
        return ""
    
    # Remove leading "in " or "at "
    location = location.strip()
    if location.lower().startswith("in "):
        location = location[3:].strip()
    if location.lower().startswith("at "):
        location = location[3:].strip()
    
    # Remove trailing " County" if present (we'll add it back if needed)
    # But keep it if it's part of the hierarchy
    
    # Capitalize properly (simple version)
    # In production, you might want more sophisticated capitalization
    
    return location


def geocode_location(location: str, state: Optional[str], geocoder: Geocoder) -> Dict[str, Any]:
    """
    Geocode a location string and return structured data.
    
    Args:
        location: Location string
        state: Optional state name for better matching
        geocoder: Geocoder instance
        
    Returns:
        Dictionary with geocoding results
    """
    if not location:
        return {
            "lat": None,
            "lon": None,
            "state": state,
            "county": None,
            "payam": None,
            "boma": None,
            "village": None,
            "score": 0.0,
            "success": False
        }
    
    # Add state context if available
    if state:
        location_with_state = f"{location}, {state}"
    else:
        location_with_state = location
    
    try:
        result = geocoder.geocode(location_with_state, use_cache=True)
        
        return {
            "lat": result.lat,
            "lon": result.lon,
            "state": result.state or state,
            "county": result.county,
            "payam": result.payam,
            "boma": result.boma,
            "village": result.village,
            "score": result.score,
            "success": result.score >= 0.7 and result.lon is not None and not result.resolution_too_coarse,
            "resolved_layer": result.resolved_layer,
            "matched_name": result.matched_name
        }
    except Exception as e:
        print(f"Error geocoding '{location}': {e}")
        return {
            "lat": None,
            "lon": None,
            "state": state,
            "county": None,
            "payam": None,
            "boma": None,
            "village": None,
            "score": 0.0,
            "success": False,
            "error": str(e)
        }


def process_casualty_matrix(
    input_file: str,
    output_file: str,
    max_rows: Optional[int] = None,
    dry_run: bool = False
):
    """
    Process casualty matrix to extract and geocode locations.
    
    Args:
        input_file: Path to input Excel file
        output_file: Path to output Excel file
        max_rows: Maximum number of rows to process (None for all)
        dry_run: If True, don't write output file
    """
    print(f"Reading Excel file: {input_file}")
    df = pd.read_excel(input_file)
    
    if max_rows:
        df = df.head(max_rows)
        print(f"Processing first {max_rows} rows only")
    
    print(f"Total rows: {len(df)}")
    
    # Initialize geocoding components
    print("Initializing geocoding system...")
    db_store = DuckDBStore()
    geocoder = Geocoder(db_store)
    extractor = DocumentLocationExtractor(geocoder)
    
    # Statistics
    stats = {
        "total": len(df),
        "locations_extracted": 0,
        "locations_geocoded": 0,
        "locations_updated": 0,
        "geocoding_failed": 0
    }
    
    # Process each row
    print("\nProcessing rows...")
    for idx, row in df.iterrows():
        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(df)} rows...")
        
        state = row.get('Incident State')
        current_location = row.get('Location of Incident')
        description = row.get('Description')
        
        # Step 1: Extract location from Description if Location of Incident is empty/incomplete
        extracted_location = None
        if pd.isna(current_location) or str(current_location).strip() == "":
            extracted_location = extract_location_from_description(description, extractor)
            if extracted_location:
                stats["locations_extracted"] += 1
                # Standardize and update
                standardized = standardize_location(extracted_location, state)
                df.at[idx, 'Location of Incident'] = standardized
                current_location = standardized
        
        # Step 2: Geocode if we have a location and missing coordinates
        location_to_geocode = current_location if not pd.isna(current_location) else extracted_location
        
        if location_to_geocode and (pd.isna(row.get('Lat')) or pd.isna(row.get('long'))):
            geocode_result = geocode_location(location_to_geocode, state, geocoder)
            
            if geocode_result["success"]:
                stats["locations_geocoded"] += 1
                
                # Update columns
                if geocode_result["lat"]:
                    df.at[idx, 'Lat'] = geocode_result["lat"]
                if geocode_result["lon"]:
                    df.at[idx, 'long'] = geocode_result["lon"]
                if geocode_result["county"] and pd.isna(row.get('County')):
                    df.at[idx, 'County'] = geocode_result["county"]
                if geocode_result["payam"] and pd.isna(row.get('Payam')):
                    df.at[idx, 'Payam'] = geocode_result["payam"]
                
                stats["locations_updated"] += 1
            else:
                stats["geocoding_failed"] += 1
                if geocode_result.get("score", 0) > 0:
                    print(f"  Row {idx + 1}: Low confidence geocoding for '{location_to_geocode}' (score: {geocode_result['score']:.2f})")
    
    # Print statistics
    print("\n" + "=" * 80)
    print("PROCESSING STATISTICS")
    print("=" * 80)
    print(f"Total rows processed: {stats['total']}")
    print(f"Locations extracted from Description: {stats['locations_extracted']}")
    print(f"Locations successfully geocoded: {stats['locations_geocoded']}")
    print(f"Rows updated with geocoding data: {stats['locations_updated']}")
    print(f"Geocoding failures: {stats['geocoding_failed']}")
    
    # Save output
    if not dry_run:
        print(f"\nSaving to: {output_file}")
        df.to_excel(output_file, index=False)
        print("Done!")
    else:
        print("\nDry run - no file written")
    
    return df, stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process casualty matrix locations")
    parser.add_argument(
        "--input",
        default="resources/casualty_tracking/casualty_matrix.xlsx",
        help="Input Excel file path"
    )
    parser.add_argument(
        "--output",
        default="resources/casualty_tracking/casualty_matrix_geocoded.xlsx",
        help="Output Excel file path"
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum number of rows to process (for testing)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write output file"
    )
    
    args = parser.parse_args()
    
    process_casualty_matrix(
        args.input,
        args.output,
        max_rows=args.max_rows,
        dry_run=args.dry_run
    )

