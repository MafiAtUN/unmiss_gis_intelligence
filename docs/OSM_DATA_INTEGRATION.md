# OSM Data Integration

This document describes the OpenStreetMap (OSM) data integration for the UNMISS HRD GIS AI application. This feature allows you to extract, store, and visualize roads and points of interest (POIs) from OpenStreetMap for South Sudan.

## Overview

The OSM integration includes:

1. **Data Extraction**: Extract roads and POIs from OpenStreetMap for South Sudan
2. **Database Storage**: Store extracted data in DuckDB for fast spatial queries
3. **Map Visualization**: Display OSM features on interactive maps
4. **Proximity Analysis**: Analyze distances from locations to nearby hospitals, schools, UNMISS bases, and other infrastructure

## Features

### Extracted POI Categories

#### Essential Infrastructure
- **Hospitals**: Hospitals, clinics, health centers (Red)
- **Schools**: Schools, universities, colleges, kindergartens (Blue)
- **Healthcare**: Doctor offices, pharmacies, dentists, optometrists (Orange)
- **Water**: Water points, drinking water, wells (Light Blue)

#### Security & Military
- **Military**: Military bases, barracks, airfields, checkpoints (Brown)
- **Police**: Police stations (Dark Blue)
- **Prison**: Prisons and jails (Indigo)
- **Court**: Courthouses (Sienna)
- **Checkpoint**: Checkpoints and border controls (Crimson)
- **Border**: Border crossings and customs (Deep Pink)

#### Transportation
- **Airport**: Airports, airfields, helipads (Pink)
- **Roads**: Major roads and highways (excluding footpaths and cycleways) (Gray)

#### International Organizations
- **UNMISS**: UNMISS facilities and bases (Green)
- **NGO**: NGO offices, charity organizations, UN facilities (Deep Sky Blue)

#### Displacement & Humanitarian
- **IDP Camp**: IDP camps, refugee sites (Orange)

#### Governance & Administration
- **Government**: Government offices, town halls (Gray)

#### Economic & Social
- **Market**: Marketplaces and shops (Yellow)
- **Bank**: Banks and ATMs (Forest Green)
- **Fuel**: Fuel stations, gas stations (Red Orange)

#### Infrastructure
- **Power**: Power stations, substations, generators (Gold)
- **Communication**: Communication towers, masts (Silver)

#### Religious
- **Religious**: Churches, mosques, places of worship (Purple)

## Usage

### 1. Extracting OSM Data

Use the extraction script to download and store OSM data:

```bash
# Extract all POI categories and roads for entire South Sudan
python scripts/extract_osm_data.py

# Extract specific categories only
python scripts/extract_osm_data.py --categories hospital school healthcare unmiss

# Extract without roads
python scripts/extract_osm_data.py --no-roads

# Extract for a specific bounding box
python scripts/extract_osm_data.py --bbox 31.0 4.0 32.0 5.0

# Dry run (see what would be extracted without storing)
python scripts/extract_osm_data.py --dry-run
```

**Note**: The extraction process can take a while depending on the amount of data. For the entire country, expect 10-30 minutes.

### 2. Viewing OSM Data on Maps

Once data is extracted, it will automatically appear on the Geocoder map:

1. Go to the **Geocoder** page
2. Geocode a location
3. Scroll to the **Map** section
4. Use the checkboxes to toggle:
   - **Show Roads**: Display road network
   - **Show Points of Interest**: Display POIs
   - **Show Admin Boundaries**: Display administrative boundaries

5. Select which POI categories to display using the multi-select dropdown

### 3. Proximity Analysis

The map automatically shows proximity analysis for the geocoded location:

- **Nearest Hospital**: Distance to closest hospital
- **Nearest School**: Distance to closest school
- **Nearest Healthcare**: Distance to closest healthcare facility
- **Nearest UNMISS Base**: Distance to closest UNMISS base

Click "View All Nearby POIs" to see a detailed list of all nearby points of interest within 10km.

## API Usage

### Extract OSM Data Programmatically

```python
from app.core.scrapers.osm_data_extractor import OSMDataExtractor
from app.core.duckdb_store import DuckDBStore

# Initialize extractor
extractor = OSMDataExtractor()

# Extract features
gdfs = extractor.extract_features(
    feature_types=["hospital", "school", "unmiss"],
    include_roads=True
)

# Store in database
db_store = DuckDBStore()
db_store.ingest_osm_roads(gdfs["roads"])
db_store.ingest_osm_pois(gdfs["hospital"])
db_store.ingest_osm_pois(gdfs["school"])
db_store.ingest_osm_pois(gdfs["unmiss"])
```

### Query Nearby Features

```python
from app.core.duckdb_store import DuckDBStore
from app.core.proximity import analyze_location_proximity

db_store = DuckDBStore()

# Get nearby hospitals within 5km
hospitals = db_store.get_nearby_osm_pois(
    lon=31.5825,
    lat=4.8517,
    distance_km=5.0,
    categories=["hospital"]
)

# Get nearby roads
roads = db_store.get_nearby_osm_roads(
    lon=31.5825,
    lat=4.8517,
    distance_km=5.0
)

# Complete proximity analysis
analysis = analyze_location_proximity(
    db_store,
    lon=31.5825,
    lat=4.8517,
    radius_km=10.0
)

print(f"Nearest hospital: {analysis['summary']['nearest_hospital']['distance_miles']} miles")
```

### Get Features in Bounding Box

```python
# Get POIs in a bounding box
pois_gdf = db_store.get_osm_pois_in_bbox(
    min_lon=31.0,
    min_lat=4.0,
    max_lon=32.0,
    max_lat=5.0,
    categories=["hospital", "school"]
)

# Get roads in a bounding box
roads_gdf = db_store.get_osm_roads_in_bbox(
    min_lon=31.0,
    min_lat=4.0,
    max_lon=32.0,
    max_lat=5.0
)
```

## Database Schema

### `osm_roads` Table

- `feature_id`: Unique identifier (PRIMARY KEY)
- `osm_id`: OSM element ID
- `osm_type`: OSM element type (node/way/relation)
- `name`: Road name
- `highway`: Road type (e.g., "primary", "secondary", "tertiary")
- `surface`: Road surface type
- `geometry_wkb`: Road geometry (WKB format)
- `geometry_geojson`: Road geometry (GeoJSON format)
- `centroid_lon`, `centroid_lat`: Road centroid coordinates
- `properties`: Additional OSM tags (JSON)
- `created_at`: Timestamp

### `osm_pois` Table

- `feature_id`: Unique identifier (PRIMARY KEY)
- `osm_id`: OSM element ID
- `osm_type`: OSM element type (node/way/relation)
- `name`: POI name
- `category`: POI category (hospital, school, etc.)
- `lon`, `lat`: POI coordinates
- `geometry_wkb`: POI geometry (WKB format)
- `geometry_geojson`: POI geometry (GeoJSON format)
- `properties`: Additional OSM tags (JSON)
- `created_at`: Timestamp

## Human Rights Investigation Use Cases

This OSM data integration is particularly useful for human rights investigations:

1. **Incident Analysis**: When investigating an incident at a location, quickly identify:
   - Distance to nearest hospital (for medical emergencies)
   - Distance to nearest school (for attacks on education)
   - Distance to nearest UNMISS base (for UN presence)
   - Nearby infrastructure (roads, markets, water sources)

2. **Pattern Analysis**: Analyze patterns of incidents relative to infrastructure:
   - Are incidents more common near schools?
   - Are incidents more common far from hospitals?
   - What is the accessibility situation (roads) around incident locations?

3. **Reporting**: Include proximity information in reports:
   - "The incident occurred 5.2 miles from the nearest hospital"
   - "The location is near a primary road, facilitating access"
   - "There are 3 schools within 10km of the incident location"

## Limitations

1. **⚠️ OSM Data Coverage**: OSM data coverage in South Sudan is **limited**. 
   - Roads: ~32% estimated coverage (~143,000 km mapped)
   - POIs: Coverage is sparse, especially for:
     - Military bases (may not be publicly mapped)
     - UNMISS bases (limited mapping)
     - IDP camps (sparse coverage)
     - Police stations, checkpoints (limited)
   - **Many categories may return zero or very few results**
   - See `OSM_DATA_LIMITATIONS.md` for detailed coverage information

2. **Data Freshness**: OSM data is updated by volunteers. The extracted data reflects OSM at the time of extraction. Average data age in South Sudan is about 4 years.

3. **Performance**: Large extractions (entire country) can take significant time and will likely hit Overpass API rate limits. **Start with small bounding boxes**.

4. **API Rate Limits**: The public Overpass API has rate limits. You may encounter 429 (Too Many Requests) or 504 (Timeout) errors when querying large areas or many categories.

5. **Recommended Approach**: 
   - Test with small areas first using `scripts/test_osm_availability.py`
   - Focus on categories with better coverage (roads, major infrastructure)
   - Consider using OSM extracts from Geofabrik or HotOSM instead of live API queries
   - Supplement with other data sources (UN OCHA, HDX, etc.)

## Troubleshooting

### Extraction Fails

- Check internet connection
- Try extracting smaller bounding boxes
- Check Overpass API status: https://overpass-api.de/status/
- Use `--dry-run` to test queries without storing

### No Data on Map

- Ensure data has been extracted using the script
- Check that POI categories are selected in the map interface
- Verify the location is within the extracted bounding box

### Slow Performance

- Extract data for specific regions instead of entire country
- Use bounding boxes to limit extraction area
- Consider extracting categories separately

## Future Enhancements

Potential improvements:

1. Incremental updates (only fetch new/changed features)
2. Additional POI categories (IDP camps, checkpoints, etc.)
3. Road network analysis (shortest paths, connectivity)
4. Heat maps of infrastructure density
5. Temporal analysis (changes over time)
6. Integration with other data sources (UN OCHA, etc.)

