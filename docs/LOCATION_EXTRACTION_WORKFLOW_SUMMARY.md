# Location Extraction Workflow Summary

## Quick Reference

### For New Data Entry

1. **Read the Description column** - Find location mentions in narrative text
2. **Extract location string** - Copy the most specific location (Boma/Village > Payam > County)
3. **Standardize format** - Format as "Location, Payam, County" or "Location, County"
4. **Copy to Location of Incident** - Update the Location of Incident column
5. **Geocode** - Use the geocoder to get boma, payam, county, and GPS coordinates
6. **Update columns** - Fill in Payam, County, Lat, long columns

### Example Workflow

```
Description: "in Lohutok Boma, Lohutok Payam, Lafon County"
    ↓
Extract: "Lohutok Boma, Lohutok Payam, Lafon"
    ↓
Copy to Location of Incident: "Lohutok Boma, Lohutok Payam, Lafon"
    ↓
Geocode with State context: "Lohutok Boma, Lohutok Payam, Lafon, Eastern Equatoria"
    ↓
Result:
  - Lat: 4.1234
  - long: 32.5678
  - Payam: "Lohutok Payam"
  - County: "Lafon"
  - Boma: "Lohutok Boma"
```

## Key Patterns in Data

### Location of Incident Formats (from 2,253 rows)

- **Boma, Payam, County** (23%): "Lohutok Boma, Lohutok Payam, Lafon"
- **Village, Payam, County** (29%): "Pantheer village, Marial Lou Payam, Tonj North"
- **Town, County** (16%): "Maridi town, Maridi"
- **Payam, County** (17%): "Padiet Payam, Duk"
- **Other** (15%): Various formats

### Description Column Patterns

Locations in descriptions typically appear as:
- `"in [Location]"` - e.g., "in Lohutok Boma, Lohutok Payam, Lafon County"
- `"at [Location]"` - e.g., "at Pantheer village"
- `"[Location], [County]"` - e.g., "Billinyang Boma, Juba County"

## Using the Geocoding System

### Python Code Example

```python
from app.core.duckdb_store import DuckDBStore
from app.core.geocoder import Geocoder
from app.core.location_extractor import DocumentLocationExtractor

# Initialize
db_store = DuckDBStore()
geocoder = Geocoder(db_store)
extractor = DocumentLocationExtractor(geocoder)

# Option 1: Extract from Description
description = "in Lohutok Boma, Lohutok Payam, Lafon County"
result = extractor.extract_locations(description, geocode=True)
location = result.regex_locations[0].original_text  # "Lohutok Boma, Lohutok Payam, Lafon County"

# Option 2: Geocode existing Location of Incident
location_text = "Lohutok Boma, Lohutok Payam, Lafon"
state = "Eastern Equatoria"
location_with_state = f"{location_text}, {state}"
geocode_result = geocoder.geocode(location_with_state)

# Get results
print(f"Lat: {geocode_result.lat}")
print(f"Lon: {geocode_result.lon}")
print(f"State: {geocode_result.state}")
print(f"County: {geocode_result.county}")
print(f"Payam: {geocode_result.payam}")
print(f"Boma: {geocode_result.boma}")
print(f"Confidence: {geocode_result.score}")
```

### GeocodeResult Fields

- `lat`, `lon`: GPS coordinates (WGS84)
- `state`: State name
- `county`: County name
- `payam`: Payam name
- `boma`: Boma name
- `village`: Village/settlement name (if point match)
- `score`: Confidence score (0.0-1.0, >= 0.7 is good)
- `resolved_layer`: Which layer matched ("villages", "admin4_boma", "admin3_payam", etc.)
- `resolution_too_coarse`: True if only County/State matched (no coordinates)

## Batch Processing Script

Use the provided script to process the entire matrix:

```bash
# Process all rows
python scripts/process_casualty_matrix_locations.py \
    --input resources/casualty_tracking/casualty_matrix.xlsx \
    --output resources/casualty_tracking/casualty_matrix_geocoded.xlsx

# Test with first 10 rows
python scripts/process_casualty_matrix_locations.py \
    --input resources/casualty_tracking/casualty_matrix.xlsx \
    --output resources/casualty_tracking/casualty_matrix_geocoded.xlsx \
    --max-rows 10

# Dry run (no output file)
python scripts/process_casualty_matrix_locations.py \
    --input resources/casualty_tracking/casualty_matrix.xlsx \
    --dry-run
```

## Best Practices

1. **Always include State context** when geocoding for better accuracy
2. **Prefer most specific location** (Boma/Village > Payam > County)
3. **Validate results**: Check confidence score >= 0.7 and coordinates exist
4. **Standardize format**: Use consistent "Location, Payam, County" format
5. **Handle edge cases**: Multiple locations in description → use primary incident location

## Files Created

1. **CASUALTY_MATRIX_LOCATION_EXTRACTION.md** - Detailed documentation
2. **scripts/process_casualty_matrix_locations.py** - Batch processing script
3. **scripts/analyze_location_patterns.py** - Pattern analysis script

## Next Steps

1. Review the detailed documentation in `CASUALTY_MATRIX_LOCATION_EXTRACTION.md`
2. Test the workflow with a small sample using `--max-rows 10`
3. Process the full matrix when ready
4. Review and validate geocoding results
5. Manually correct any low-confidence or failed geocoding results

