#!/usr/bin/env python3
"""
Evaluate location extraction accuracy by comparing extracted locations with matrix data.

This script:
1. Extracts locations from Description column
2. Geocodes them to get boma, payam, county, state, coordinates
3. Compares with existing matrix data (Location of Incident, Payam, County, Lat, long)
4. Measures accuracy and identifies areas for improvement
5. Uses LLM/AI for better extraction when needed
"""

import pandas as pd
import sys
import os
import re
from typing import Optional, Dict, Any, List, Tuple
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder
from app.core.location_extractor import DocumentLocationExtractor
from app.core.azure_ai import AzureAIParser
from app.core.ollama_location_extractor import OllamaLocationExtractor
from app.core.normalization import normalize_text
from app.core.fuzzy import fuzzy_match
from rapidfuzz import fuzz

# Import improved extractor
import sys
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from improved_location_extractor import extract_and_standardize as improved_extract
try:
    from final_improved_extractor import extract_and_standardize_v2 as final_extract
except ImportError:
    final_extract = None


def similarity_score(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings using fuzzy matching (0.0 to 1.0).
    
    Uses RapidFuzz for better matching that handles:
    - Word order differences
    - Partial matches
    - Spelling variations
    """
    if not str1 or not str2:
        return 0.0
    
    # Normalize both strings
    norm1 = normalize_text(str1)
    norm2 = normalize_text(str2)
    
    # Use multiple fuzzy matching strategies and take the best
    scores = [
        fuzz.ratio(norm1, norm2) / 100.0,  # Simple ratio
        fuzz.token_sort_ratio(norm1, norm2) / 100.0,  # Token sort (handles word order)
        fuzz.token_set_ratio(norm1, norm2) / 100.0,  # Token set (handles duplicates)
        fuzz.partial_ratio(norm1, norm2) / 100.0,  # Partial (handles substrings)
        fuzz.WRatio(norm1, norm2) / 100.0,  # Weighted ratio (best overall)
    ]
    
    # Return the best score
    return max(scores)


def extract_location_with_llm(
    description: str, 
    state: Optional[str], 
    azure_parser: Optional[AzureAIParser],
    ollama_extractor: Optional[OllamaLocationExtractor]
) -> Optional[str]:
    """
    Use LLM (Ollama or Azure AI) to extract the primary incident location.
    
    Priority: Ollama (local, fast) -> Azure AI (cloud, accurate)
    
    Args:
        description: Description text
        state: State name for context
        azure_parser: AzureAIParser instance (can be None)
        ollama_extractor: OllamaLocationExtractor instance (can be None)
        
    Returns:
        Extracted location string or None
    """
    # Try Ollama first (local, fast, efficient)
    if ollama_extractor and ollama_extractor.enabled:
        try:
            location = ollama_extractor.extract_primary_location(description, state)
            if location:
                return location
        except Exception as e:
            print(f"  Ollama extraction error: {e}")
    
    # Fallback to Azure AI if Ollama not available or failed
    if azure_parser and azure_parser.enabled:
        try:
            # Create a focused prompt for location extraction
            prompt = f"""Extract the PRIMARY incident location from this description. 
Focus on WHERE the incident occurred, not other locations mentioned.

State context: {state or 'Unknown'}

Description: {description[:1000]}

Return ONLY the location string in the format: "Location Name, Payam Name, County Name" or "Location Name, County Name"
If the location includes Boma, include it: "Boma Name, Payam Name, County Name"
Extract the most specific location where the incident happened.

Return only the location string, nothing else."""

            # Use Azure AI to extract
            deployment = azure_parser.deployment or "gpt-4o-mini"
            response = azure_parser.client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are a location extraction assistant for South Sudan. Extract the primary incident location from text descriptions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            location = response.choices[0].message.content.strip()
            
            # Clean up the response
            location = location.replace('"', '').replace("'", "").strip()
            
            # Remove common prefixes
            if location.lower().startswith("location:"):
                location = location[9:].strip()
            if location.lower().startswith("the location is"):
                location = location[15:].strip()
            
            return location if location else None
        
        except Exception as e:
            print(f"  Azure AI extraction error: {e}")
            return None
    
    return None


def extract_location_enhanced(
    description: str, 
    state: Optional[str], 
    extractor: Optional[DocumentLocationExtractor], 
    azure_parser: Optional[AzureAIParser],
    ollama_extractor: Optional[OllamaLocationExtractor] = None
) -> Optional[str]:
    """
    Enhanced location extraction using multiple methods.
    
    Priority:
    1. LLM extraction (if enabled)
    2. Location extractor (regex + AI)
    3. Regex patterns
    
    Args:
        description: Description text
        state: State name for context
        extractor: DocumentLocationExtractor instance
        azure_parser: AzureAIParser instance
        
    Returns:
        Best extracted location string
    """
    if not description or pd.isna(description):
        return None
    
    description_str = str(description)
    
    # Method 1: Try LLM extraction first (most intelligent)
    # Priority: Ollama (local, fast) -> Azure AI (cloud, accurate)
    llm_location = extract_location_with_llm(description_str, state, azure_parser, ollama_extractor)
    if llm_location:
        return llm_location
    
    # Method 2: Use location extractor
    if extractor:
        try:
            result = extractor.extract_locations(description_str, geocode=False)
            all_locations = result.regex_locations + result.ollama_locations + result.ai_locations
            
            if all_locations:
                # Find the most specific location (prefer ones with Boma/Payam/County)
                best_location = None
                best_specificity = 0
                
                for loc in all_locations:
                    text = loc.original_text
                    # Calculate specificity
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
                
                if best_location:
                    return best_location
        except Exception as e:
            print(f"  Extractor error: {e}")
    
    # Method 3: Simple regex patterns
    patterns = [
        r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Boma|Payam|County|Town|town))(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Payam|County))?)?(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+County)?)?)',
        r'at\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Boma|Payam|County|Town|town))(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Payam|County))?)?(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+County)?)?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description_str, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Remove leading "in " or "at " if still present
            location = re.sub(r'^(in|at)\s+', '', location, flags=re.IGNORECASE).strip()
            return location
    
    return None


def standardize_location_string(location: str) -> str:
    """Standardize location string format."""
    if not location:
        return ""
    
    location = location.strip()
    
    # Remove leading "in " or "at "
    location = re.sub(r'^(in|at)\s+', '', location, flags=re.IGNORECASE).strip()
    
    # Remove trailing punctuation
    location = location.rstrip('.,;')
    
    return location


def compare_locations(extracted: str, actual: str) -> Dict[str, Any]:
    """
    Compare extracted location with actual location from matrix.
    
    Returns:
        Dictionary with comparison metrics
    """
    if not extracted:
        extracted = ""
    if not actual or pd.isna(actual):
        actual = ""
    
    extracted_norm = normalize_text(extracted)
    actual_norm = normalize_text(actual)
    
    similarity = similarity_score(extracted_norm, actual_norm)
    
    # Use fuzzy matching threshold - more lenient for location strings
    # Consider it a match if similarity is >= 0.75 (75%) using fuzzy matching
    # This handles minor variations better than exact matching
    match_threshold = 0.75
    
    return {
        "extracted": extracted,
        "actual": actual,
        "similarity": similarity,
        "match": similarity >= match_threshold,
        "exact_match": extracted_norm == actual_norm,
        "high_confidence": similarity >= 0.85,  # High confidence match
        "medium_confidence": 0.75 <= similarity < 0.85,  # Medium confidence
        "low_confidence": similarity < 0.75  # Low confidence
    }


def compare_geocoding(geocode_result: Dict[str, Any], actual_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare geocoding results with actual matrix data.
    
    Args:
        geocode_result: Result from geocoding
        actual_data: Actual data from matrix (Payam, County, Lat, long)
        
    Returns:
        Dictionary with comparison metrics
    """
    comparisons = {
        "payam_match": False,
        "county_match": False,
        "state_match": False,
        "coordinate_match": False,
        "payam_similarity": 0.0,
        "county_similarity": 0.0,
        "state_similarity": 0.0,
        "coordinate_distance_km": None
    }
    
    # Compare Payam
    extracted_payam = normalize_text(str(geocode_result.get("payam", "") or ""))
    actual_payam = normalize_text(str(actual_data.get("Payam", "") or ""))
    if extracted_payam and actual_payam:
        comparisons["payam_similarity"] = similarity_score(extracted_payam, actual_payam)
        comparisons["payam_match"] = comparisons["payam_similarity"] >= 0.8
    
    # Compare County
    extracted_county = normalize_text(str(geocode_result.get("county", "") or ""))
    actual_county = normalize_text(str(actual_data.get("County", "") or ""))
    if extracted_county and actual_county:
        comparisons["county_similarity"] = similarity_score(extracted_county, actual_county)
        comparisons["county_match"] = comparisons["county_similarity"] >= 0.8
    
    # Compare State
    extracted_state = normalize_text(str(geocode_result.get("state", "") or ""))
    actual_state = normalize_text(str(actual_data.get("Incident State", "") or ""))
    if extracted_state and actual_state:
        comparisons["state_similarity"] = similarity_score(extracted_state, actual_state)
        comparisons["state_match"] = comparisons["state_similarity"] >= 0.8
    
    # Compare coordinates (if both available)
    extracted_lat = geocode_result.get("lat")
    extracted_lon = geocode_result.get("lon")
    actual_lat = actual_data.get("Lat")
    actual_lon = actual_data.get("long")
    
    if (extracted_lat and extracted_lon and 
        actual_lat and actual_lon and 
        not pd.isna(actual_lat) and not pd.isna(actual_lon)):
        
        # Calculate distance in km using Haversine formula
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth radius in km
        
        lat1, lon1 = radians(extracted_lat), radians(extracted_lon)
        lat2, lon2 = radians(float(actual_lat)), radians(float(actual_lon))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        distance = R * c
        comparisons["coordinate_distance_km"] = distance
        comparisons["coordinate_match"] = distance <= 5.0  # Within 5km is considered a match
    
    return comparisons


def evaluate_extraction_accuracy(
    input_file: str,
    max_rows: Optional[int] = None,
    use_llm: bool = True,
    sample_size: int = 50
):
    """
    Evaluate location extraction accuracy.
    
    Args:
        input_file: Path to Excel file
        max_rows: Maximum rows to process
        use_llm: Whether to use LLM for extraction
        sample_size: Number of rows to evaluate in detail
    """
    print("=" * 80)
    print("LOCATION EXTRACTION ACCURACY EVALUATION")
    print("=" * 80)
    
    print(f"\nReading Excel file: {input_file}")
    df = pd.read_excel(input_file)
    
    if max_rows:
        df = df.head(max_rows)
        print(f"Processing first {max_rows} rows")
    
    print(f"Total rows: {len(df)}")
    
    # Initialize components
    print("\nInitializing geocoding system...")
    try:
        db_store = DuckDBStore()
    except Exception as e:
        if "lock" in str(e).lower() or "conflicting" in str(e).lower():
            print(f"Warning: Database is locked. Trying read-only mode...")
            # Try to continue without database (will fail on geocoding but can test extraction)
            print("Note: Geocoding will be skipped if database is locked")
            db_store = None
        else:
            raise
    
    if db_store:
        geocoder = Geocoder(db_store)
        extractor = DocumentLocationExtractor(geocoder)
    else:
        geocoder = None
        extractor = None
    
    # Initialize LLM extractors
    azure_parser = AzureAIParser()
    ollama_extractor = OllamaLocationExtractor()
    
    if ollama_extractor.enabled:
        print(f"  ✓ Ollama enabled (model: {ollama_extractor.model})")
    else:
        print(f"  ✗ Ollama not available")
    
    if azure_parser.enabled:
        print(f"  ✓ Azure AI enabled (deployment: {azure_parser.deployment})")
    else:
        print(f"  ✗ Azure AI not configured")
    
    if use_llm and not azure_parser.enabled:
        print("Warning: LLM extraction requested but Azure AI is not enabled")
        print("  Set ENABLE_AI_EXTRACTION=True and configure Azure credentials")
        use_llm = False
    
    # Statistics
    stats = {
        "total": len(df),
        "has_description": 0,
        "has_location_of_incident": 0,
        "extraction_attempted": 0,
        "extraction_successful": 0,
        "geocoding_attempted": 0,
        "geocoding_successful": 0,
        "location_string_matches": 0,
        "payam_matches": 0,
        "county_matches": 0,
        "state_matches": 0,
        "coordinate_matches": 0,
        "detailed_evaluations": []
    }
    
    # Process rows
    print("\nProcessing rows...")
    for idx, row in df.iterrows():
        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(df)} rows...")
        
        state = row.get('Incident State')
        actual_location = row.get('Location of Incident')
        description = row.get('Description')
        actual_payam = row.get('Payam')
        actual_county = row.get('County')
        actual_lat = row.get('Lat')
        actual_lon = row.get('long')
        
        # Track what we have
        if description and not pd.isna(description):
            stats["has_description"] += 1
        if actual_location and not pd.isna(actual_location):
            stats["has_location_of_incident"] += 1
        
        # Extract location from description
        extracted_location = None
        if description and not pd.isna(description):
            stats["extraction_attempted"] += 1
            
            # Try final improved extraction first (if available)
            if final_extract:
                extracted_location = final_extract(description, state)
            
            # Fallback to improved extraction
            if not extracted_location:
                extracted_location = improved_extract(description, state)
            
            # Fallback to enhanced extraction with LLM if improved extraction fails
            if not extracted_location:
                if extractor:
                    if use_llm:
                        extracted_location = extract_location_enhanced(description, state, extractor, azure_parser, ollama_extractor)
                    else:
                        extracted_location = extract_location_enhanced(description, state, extractor, None, None)
                else:
                    # Fallback to simple regex if extractor not available
                    if use_llm:
                        extracted_location = extract_location_enhanced(description, state, None, azure_parser, ollama_extractor)
                    else:
                        extracted_location = extract_location_enhanced(description, state, None, None, None)
            
            if extracted_location:
                extracted_location = standardize_location_string(extracted_location)
                stats["extraction_successful"] += 1
        
        # Geocode extracted location
        geocode_result = None
        if extracted_location and geocoder:
            stats["geocoding_attempted"] += 1
            
            # Add state context for better matching
            location_with_state = f"{extracted_location}, {state}" if state else extracted_location
            
            try:
                result = geocoder.geocode(location_with_state, use_cache=True)
                
                geocode_result = {
                    "lat": result.lat,
                    "lon": result.lon,
                    "state": result.state,
                    "county": result.county,
                    "payam": result.payam,
                    "boma": result.boma,
                    "village": result.village,
                    "score": result.score,
                    "success": result.score >= 0.7 and result.lon is not None and not result.resolution_too_coarse
                }
                
                if geocode_result["success"]:
                    stats["geocoding_successful"] += 1
            except Exception as e:
                print(f"  Row {idx + 1}: Geocoding error: {e}")
                geocode_result = {"success": False, "error": str(e)}
        
        # Compare with actual data (for detailed evaluation on sample)
        if idx < sample_size and extracted_location:
            location_comparison = compare_locations(extracted_location, str(actual_location) if actual_location else "")
            
            geocoding_comparison = {}
            if geocode_result:
                actual_data = {
                    "Payam": actual_payam,
                    "County": actual_county,
                    "Lat": actual_lat,
                    "long": actual_lon,
                    "Incident State": state
                }
                geocoding_comparison = compare_geocoding(geocode_result, actual_data)
                
                # Update stats
                if geocoding_comparison.get("payam_match"):
                    stats["payam_matches"] += 1
                if geocoding_comparison.get("county_match"):
                    stats["county_matches"] += 1
                if geocoding_comparison.get("state_match"):
                    stats["state_matches"] += 1
                if geocoding_comparison.get("coordinate_match"):
                    stats["coordinate_matches"] += 1
            
            if location_comparison.get("match"):
                stats["location_string_matches"] += 1
            
            # Store detailed evaluation
            stats["detailed_evaluations"].append({
                "row": idx + 1,
                "state": state,
                "extracted_location": extracted_location,
                "actual_location": str(actual_location) if actual_location else "",
                "location_match": location_comparison,
                "geocode_result": geocode_result,
                "geocoding_comparison": geocoding_comparison,
                "description_preview": str(description)[:200] if description else ""
            })
    
    # Print statistics
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS")
    print("=" * 80)
    
    print(f"\nData Availability:")
    print(f"  Total rows: {stats['total']}")
    print(f"  Rows with Description: {stats['has_description']} ({stats['has_description']/stats['total']*100:.1f}%)")
    print(f"  Rows with Location of Incident: {stats['has_location_of_incident']} ({stats['has_location_of_incident']/stats['total']*100:.1f}%)")
    
    print(f"\nExtraction Performance:")
    if stats['extraction_attempted'] > 0:
        print(f"  Extraction attempted: {stats['extraction_attempted']}")
        print(f"  Extraction successful: {stats['extraction_successful']} ({stats['extraction_successful']/stats['extraction_attempted']*100:.1f}%)")
    
    print(f"\nGeocoding Performance:")
    if stats['geocoding_attempted'] > 0:
        print(f"  Geocoding attempted: {stats['geocoding_attempted']}")
        print(f"  Geocoding successful: {stats['geocoding_successful']} ({stats['geocoding_successful']/stats['geocoding_attempted']*100:.1f}%)")
    
    print(f"\nAccuracy (on {min(sample_size, len(stats['detailed_evaluations']))} sample rows):")
    if stats['detailed_evaluations']:
        sample_count = len(stats['detailed_evaluations'])
        print(f"  Location string match: {stats['location_string_matches']}/{sample_count} ({stats['location_string_matches']/sample_count*100:.1f}%)")
        print(f"  Payam match: {stats['payam_matches']}/{sample_count} ({stats['payam_matches']/sample_count*100:.1f}%)")
        print(f"  County match: {stats['county_matches']}/{sample_count} ({stats['county_matches']/sample_count*100:.1f}%)")
        print(f"  State match: {stats['state_matches']}/{sample_count} ({stats['state_matches']/sample_count*100:.1f}%)")
        print(f"  Coordinate match (within 5km): {stats['coordinate_matches']}/{sample_count} ({stats['coordinate_matches']/sample_count*100:.1f}%)")
    
    # Print detailed examples
    print("\n" + "=" * 80)
    print("DETAILED EXAMPLES (First 10)")
    print("=" * 80)
    
    for eval_data in stats['detailed_evaluations'][:10]:
        print(f"\n--- Row {eval_data['row']} ---")
        print(f"State: {eval_data['state']}")
        print(f"Description: {eval_data['description_preview']}...")
        print(f"Extracted: {eval_data['extracted_location']}")
        print(f"Actual: {eval_data['actual_location']}")
        print(f"Location Match: {eval_data['location_match']['match']} (similarity: {eval_data['location_match']['similarity']:.2f})")
        
        if eval_data['geocode_result']:
            geo = eval_data['geocode_result']
            print(f"Geocoded: {geo.get('county')}, {geo.get('payam')} (score: {geo.get('score', 0):.2f})")
            print(f"  Coordinates: ({geo.get('lat')}, {geo.get('lon')})")
            
            if eval_data['geocoding_comparison']:
                comp = eval_data['geocoding_comparison']
                print(f"  Payam match: {comp.get('payam_match')} (similarity: {comp.get('payam_similarity', 0):.2f})")
                print(f"  County match: {comp.get('county_match')} (similarity: {comp.get('county_similarity', 0):.2f})")
                if comp.get('coordinate_distance_km') is not None:
                    print(f"  Coordinate distance: {comp['coordinate_distance_km']:.2f} km")
    
    return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate location extraction accuracy")
    parser.add_argument(
        "--input",
        default="resources/casualty_tracking/casualty_matrix.xlsx",
        help="Input Excel file path"
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum number of rows to process"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=50,
        help="Number of rows to evaluate in detail"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Don't use LLM for extraction"
    )
    
    args = parser.parse_args()
    
    evaluate_extraction_accuracy(
        args.input,
        max_rows=args.max_rows,
        use_llm=not args.no_llm,
        sample_size=args.sample_size
    )

