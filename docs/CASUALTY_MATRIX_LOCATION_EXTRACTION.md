# Casualty Matrix Location Extraction Workflow

## Overview

This document explains how to extract location information from the casualty matrix Excel file, specifically from the `Description` column, and use the geocoding system to identify administrative boundaries (Boma, Payam, County) and GPS coordinates.

## Understanding the Data Structure

### Columns Used
- **Incident State**: The state where the incident occurred (e.g., "Eastern Equatoria", "Warrap")
- **Location of Incident**: Structured location string (e.g., "Lohutok Boma, Lohutok Payam, Lafon")
- **Description**: Narrative text containing location mentions embedded in sentences

### Location Format Patterns

Based on analysis of 2,253 rows, the `Location of Incident` column follows these patterns:

1. **Boma, Payam, County** (517 rows - 23%)
   - Example: "Lohutok Boma, Lohutok Payam, Lafon"
   - Example: "Lalanga Boma, Lohutok Payam, Imehejek Administrative Area"

2. **Village, Payam, County** (654 rows - 29%)
   - Example: "Pantheer village, Marial Lou Payam, Tonj North"
   - Example: "Ugin village, Malual Chum Payam, Tonj East"

3. **Town, County** (360 rows - 16%)
   - Example: "Maridi town, Maridi"
   - Example: "Billinang, Juba"

4. **Payam, County** (384 rows - 17%)
   - Example: "Padiet Payam, Duk"
   - Example: "Otogo Payam, Yei River"

5. **Other formats** (333 rows - 15%)
   - Various other formats including incomplete data

## Location Extraction from Description Column

### Common Patterns in Descriptions

The `Description` column contains narrative text with location mentions in various formats:

1. **Full hierarchical path**:
   ```
   "in Lohutok Boma, Lohutok Payam, Lafon County"
   "in Billinyang Boma, Juba County"
   "in Padiet Payam, Duk County"
   ```

2. **With preposition "in" or "at"**:
   ```
   "in Maridi Town, Maridi County"
   "at Pantheer village, Marial Lou Payam, Tonj North County"
   ```

3. **Partial information** (needs state context):
   ```
   "in Jebel Boma Town, Jebel Boma County, GPAA"
   ```

### Extraction Strategy

1. **Parse Description text** to find location mentions using:
   - Regex patterns (see `app/core/location_extractor.py`)
   - AI extraction (Azure AI or Ollama) for complex cases
   - Look for patterns like: "in [Location]", "at [Location]", "[Location], [County]"

2. **Extract the most specific location**:
   - Priority: Boma/Village > Payam > County
   - Look for hierarchical strings: "X Boma, Y Payam, Z County"

3. **Combine with Incident State** if location is incomplete:
   - If only County is found, use State from `Incident State` column
   - If only Payam is found, try to infer County from context

4. **Standardize format**:
   - Preferred: "Location Name, Payam Name, County Name"
   - Alternative: "Location Name, County Name" (if Payam unknown)
   - Remove redundant words like "in", "at", "town" (unless part of name)

## Geocoding Workflow

### Step-by-Step Process

1. **Extract location string from Description**
   ```python
   from app.core.location_extractor import DocumentLocationExtractor
   from app.core.geocoder import Geocoder
   from app.core.duckdb_store import DuckDBStore
   
   # Initialize
   db_store = DuckDBStore()
   geocoder = Geocoder(db_store)
   extractor = DocumentLocationExtractor(geocoder)
   
   # Extract from description
   description = "in Lohutok Boma, Lohutok Payam, Lafon County"
   result = extractor.extract_locations(description, geocode=True)
   ```

2. **Or use existing Location of Incident if available**
   ```python
   location_text = "Lohutok Boma, Lohutok Payam, Lafon"
   geocode_result = geocoder.geocode(location_text)
   ```

3. **Get structured data from geocode result**
   ```python
   # GeocodeResult contains:
   - geocode_result.lat, geocode_result.lon  # GPS coordinates
   - geocode_result.state                    # State name
   - geocode_result.county                   # County name
   - geocode_result.payam                    # Payam name
   - geocode_result.boma                     # Boma name
   - geocode_result.village                  # Village name (if point match)
   - geocode_result.score                    # Confidence score (0.0-1.0)
   - geocode_result.resolved_layer           # Which layer matched (villages, admin4_boma, etc.)
   ```

4. **Update Location of Incident column**
   - If Description has better/more specific location, update `Location of Incident`
   - Format: "Boma/Village, Payam, County" or "Location, County"

5. **Add/Update administrative columns**
   - Update `Payam` column with `geocode_result.payam`
   - Update `County` column with `geocode_result.county`
   - Update `Lat` column with `geocode_result.lat`
   - Update `long` column with `geocode_result.lon`

## Complete Workflow for Processing Matrix

### For New Data Entry

1. **Read Description column**
   - Extract location string using `DocumentLocationExtractor`
   - Or manually identify location mention in narrative

2. **Copy extracted address to Location of Incident**
   - Standardize format: "Location, Payam, County" or "Location, County"
   - Include State information if needed for context

3. **Geocode the location**
   ```python
   location_text = "Lohutok Boma, Lohutok Payam, Lafon"
   # Optionally add state for better matching:
   location_with_state = f"{location_text}, Eastern Equatoria"
   result = geocoder.geocode(location_with_state)
   ```

4. **Validate geocoding result**
   - Check `result.score >= 0.7` (confidence threshold)
   - Verify `result.lon` and `result.lat` are not None
   - Check that `result.resolution_too_coarse` is False (for County/State-only matches)

5. **Update Excel columns**
   - `Location of Incident`: Standardized location string
   - `Payam`: `result.payam`
   - `County`: `result.county`
   - `Lat`: `result.lat`
   - `long`: `result.lon`

### For Existing Data (Bulk Processing)

1. **Read Excel file**
2. **For each row**:
   - If `Location of Incident` is empty or incomplete:
     - Extract from `Description`
     - Update `Location of Incident`
   - If `Lat`/`long` are empty:
     - Geocode `Location of Incident` (with `Incident State` for context)
     - Update `Lat`, `long`, `Payam`, `County` columns
3. **Save updated Excel file**

## Example: Extracting from Description

### Example 1: Full hierarchical path
```
Description: "in Lohutok Boma, Lohutok Payam, Lafon County"
Extracted: "Lohutok Boma, Lohutok Payam, Lafon"
Geocode Result:
  - lat: 4.1234, lon: 32.5678
  - state: "Eastern Equatoria"
  - county: "Lafon"
  - payam: "Lohutok Payam"
  - boma: "Lohutok Boma"
```

### Example 2: Partial information
```
Description: "in Maridi Town, Maridi County"
Location of Incident: "Maridi town, Maridi" (already filled)
Geocode Result:
  - lat: 4.5678, lon: 30.1234
  - state: "Western Equatoria"
  - county: "Maridi"
  - payam: None (if not found)
  - village: "Maridi"
```

### Example 3: Needs state context
```
Description: "in Jebel Boma Town, Jebel Boma County, GPAA"
Location of Incident: "in Jebel Boma Town, Jebel Boma County"
Note: GPAA = Greater Pibor Administrative Area (state-level)
Geocode with state context:
  location = "Jebel Boma Town, Jebel Boma County, Greater Pibor Administrative Area"
```

## Best Practices

1. **Always include State context** when geocoding:
   - Use `Incident State` column to improve matching accuracy
   - Format: "Location, Payam, County, State"

2. **Prefer most specific location**:
   - Boma/Village > Payam > County
   - More specific = better GPS accuracy

3. **Validate geocoding results**:
   - Check confidence score (should be >= 0.7)
   - Verify coordinates are within South Sudan bounds
   - Check that administrative hierarchy makes sense

4. **Handle edge cases**:
   - Multiple location mentions in Description → use the primary incident location
   - Ambiguous locations → use AI extraction or manual review
   - Low confidence geocoding → flag for manual review

5. **Standardize location format**:
   - Use consistent capitalization
   - Remove redundant words ("in", "at", "town" unless part of name)
   - Use full administrative names (e.g., "Lohutok Payam" not just "Lohutok")

## Integration with Geocoding System

The geocoding system (`app/core/geocoder.py`) uses:

1. **Text normalization** (`app/core/normalization.py`):
   - Lowercase, remove punctuation
   - Handle South Sudan abbreviations (e.g., "C Equatoria" → "Central Equatoria")
   - Unicode normalization

2. **Fuzzy matching** (`app/core/fuzzy.py`):
   - RapidFuzz for approximate string matching
   - Handles spelling variations and typos

3. **Hierarchical resolution**:
   - Tries: Village/Settlement (point) → Boma (polygon) → Payam (polygon)
   - Does NOT return coordinates for County/State-only matches

4. **Spatial operations** (`app/core/spatial.py`):
   - Point-in-polygon checks
   - Computes full admin hierarchy from coordinates

5. **Data sources**:
   - Villages table (point locations)
   - Admin boundaries (Boma, Payam, County, State polygons)
   - All stored in DuckDB for fast queries

## Troubleshooting

### Low confidence geocoding
- **Cause**: Location name not in database or spelling mismatch
- **Solution**: 
  - Check spelling variations
  - Try with/without "Town", "Boma", etc.
  - Use AI extraction for complex cases

### Missing GPS coordinates
- **Cause**: Only County/State matched (too coarse)
- **Solution**: 
  - Extract more specific location from Description
  - Look for Boma/Village names in narrative
  - Use AI extraction to find specific locations

### Wrong administrative boundaries
- **Cause**: Ambiguous location name (exists in multiple counties)
- **Solution**: 
  - Always include State/County context when geocoding
  - Use hierarchical constraints in geocoder

## Future Improvements

1. **Automated extraction script**: Batch process entire matrix
2. **AI-powered extraction**: Use Azure AI or Ollama to extract locations from descriptions
3. **Validation rules**: Check consistency between State, County, Payam
4. **Feedback loop**: Learn from manual corrections to improve extraction

