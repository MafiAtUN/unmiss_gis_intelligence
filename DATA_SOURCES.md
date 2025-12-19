# South Sudan Administrative Boundary Data Sources

## Current Status

**No shapefiles or GeoJSON files are currently in the project.** The application is ready to ingest data once you have it.

## Where to Find South Sudan Administrative Boundaries

### 1. UN/OCHA Sources
- **HDX (Humanitarian Data Exchange)**: https://data.humdata.org/
  - Search for "South Sudan administrative boundaries"
  - Often includes State, County, Payam, and Boma levels
  - Usually in Shapefile or GeoJSON format

### 2. Government Sources
- **South Sudan National Bureau of Statistics**
- **Ministry of Local Government**
- **South Sudan Land Commission**

### 3. Humanitarian Organizations
- **UNMISS** (UN Mission in South Sudan) - may have internal datasets
- **OCHA** (Office for the Coordination of Humanitarian Affairs)
- **IOM** (International Organization for Migration)
- **UNHCR** (UN Refugee Agency)

### 4. Academic/Research Sources
- **GADM** (Global Administrative Areas): https://gadm.org/
  - May have State and County levels
  - Download as Shapefile or GeoJSON

### 5. OpenStreetMap
- **OSM** data can be extracted for South Sudan
- Requires processing to extract admin boundaries
- May not have complete Boma/Payam coverage

## Required Data Format

The application accepts:

### Option 1: GeoJSON (Recommended)
- **Format**: GeoJSON FeatureCollection
- **Required fields**: 
  - `name` (or configurable name field)
  - `geometry` (Polygon or MultiPolygon for admin layers)
- **Optional fields**:
  - `aliases` (comma-separated alternate names)
  - `admin1Name`, `admin2Name`, etc. (parent admin names)

**Example structure:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "name": "Juba County",
        "admin1Name": "Central Equatoria"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[...]]
      }
    }
  ]
}
```

### Option 2: Shapefile
- Can be converted to GeoJSON using:
  - QGIS
  - GDAL/OGR command line
  - Python (geopandas)

**Conversion command:**
```bash
ogr2ogr -f GeoJSON output.geojson input.shp
```

### Option 3: CSV (for Settlements)
- **Required columns**: `lon`, `lat`, `name`
- **Optional columns**: `aliases` (comma-separated)

**Example:**
```csv
lon,lat,name,aliases
31.5825,4.8517,Juba,"Juba Town,Capital"
```

## Data Requirements by Layer

### admin1_state.geojson
- **Level**: State
- **Geometry**: Polygon
- **Examples**: Central Equatoria, Unity, Upper Nile, etc.
- **Typical count**: 10 states

### admin2_county.geojson
- **Level**: County
- **Geometry**: Polygon
- **Examples**: Juba County, Bentiu County, etc.
- **Typical count**: 80+ counties

### admin3_payam.geojson
- **Level**: Payam
- **Geometry**: Polygon
- **Examples**: Juba Payam, etc.
- **Typical count**: 500+ payams

### admin4_boma.geojson
- **Level**: Boma
- **Geometry**: Polygon
- **Examples**: Various bomas
- **Typical count**: 2000+ bomas

### settlements.csv or settlements.geojson
- **Level**: Village/Settlement
- **Geometry**: Point (or CSV with lon/lat)
- **Examples**: Individual villages, towns, settlements
- **Typical count**: 1000+ settlements

## How to Prepare Your Data

### 1. If you have Shapefiles:

**Convert to GeoJSON:**
```python
import geopandas as gpd

# Read shapefile
gdf = gpd.read_file("path/to/admin1_state.shp")

# Ensure WGS84
if gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs("EPSG:4326")

# Save as GeoJSON
gdf.to_file("admin1_state.geojson", driver="GeoJSON")
```

**Or use command line:**
```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 admin1_state.geojson admin1_state.shp
```

### 2. If you have GeoJSON:

**Verify structure:**
```python
import geopandas as gpd
import json

# Load and check
gdf = gpd.read_file("admin1_state.geojson")
print(f"CRS: {gdf.crs}")
print(f"Features: {len(gdf)}")
print(f"Columns: {gdf.columns.tolist()}")
print(f"Has 'name' field: {'name' in gdf.columns}")
```

### 3. If you have CSV for settlements:

**Verify format:**
```python
import pandas as pd

df = pd.read_csv("settlements.csv")
required = ["lon", "lat", "name"]
assert all(col in df.columns for col in required), "Missing required columns"
```

## Uploading to the Application

Once you have your data files:

1. **Start the application**:
   ```bash
   streamlit run app/streamlit_app.py
   ```

2. **Go to Data Manager page**

3. **Upload each layer**:
   - Select "GeoJSON (Admin layers)"
   - Choose the file (e.g., `admin1_state.geojson`)
   - Select the layer name from dropdown
   - Specify the name field (usually "name")
   - Click "Ingest GeoJSON"

4. **Upload settlements**:
   - Select "CSV (Settlements)"
   - Upload your CSV file
   - Specify field names (lon, lat, name)
   - Click "Ingest CSV"

5. **Build the index**:
   - Click "Build Index" button
   - This creates the name index for fast fuzzy matching

## Data Quality Tips

1. **Coordinate System**: Ensure all data is in WGS84 (EPSG:4326)
2. **Name Consistency**: Use consistent naming conventions
3. **Aliases**: Include alternate names/spellings in aliases field
4. **Hierarchy**: Include parent admin names if available
5. **Completeness**: More complete data = better geocoding results

## Testing Without Real Data

The application includes test fixtures in `tests/conftest.py` that create synthetic data for testing. You can run tests to see how the system works:

```bash
pytest tests/ -v
```

## Need Help?

If you have shapefiles but need help converting them:
- Use QGIS (free, GUI-based)
- Use GDAL/OGR (command line)
- The application's Data Manager can handle GeoJSON directly

If you need to find data sources:
- Check with UNMISS GIS team
- Contact OCHA South Sudan
- Search HDX for South Sudan datasets

