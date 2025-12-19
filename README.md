# South Sudan Administrative Geocoder

A production-quality Streamlit application for geocoding free text locations in South Sudan using hierarchical administrative boundaries (State, County, Payam, Boma) and settlement points.

## Features

- **Hierarchical Resolution**: Resolves locations in order: Village → Boma → Payam (no coordinates for County/State only)
- **Fuzzy Matching**: Uses RapidFuzz for robust name matching with spelling variants
- **DuckDB Storage**: Fast local database for geospatial data and caching
- **Azure AI Integration**: Optional AI-powered text parsing for messy addresses
- **Streamlit UI**: Multi-page interface for geocoding, data management, settings, and diagnostics

## Architecture

- **Core Engine**: Deterministic parsing + optional AI extraction
- **Spatial Operations**: GeoPandas/Shapely for containment and centroid computation
- **Storage**: DuckDB with WKB geometry storage
- **Matching**: RapidFuzz with token sort ratio and partial ratio
- **Caching**: Built-in query cache to prevent repeated computation

## Installation

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd unmiss_hrd_gis_ai
```

2. Create virtual environment:
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

5. Edit `.env` with your configuration:
   - Azure AI Foundry credentials (required for AI extraction, enabled by default for better accuracy)
   - Set `ENABLE_AI_EXTRACTION=false` to disable if Azure credentials are not available

6. Run the application:
```bash
streamlit run app/streamlit_app.py
```

### Docker Deployment

1. Build the image:
```bash
docker build -t south-sudan-geocoder .
```

2. Run the container:
```bash
docker run -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  south-sudan-geocoder
```

3. Access at `http://localhost:8501`

### Azure Container Apps

The Dockerfile is configured for Azure Container Apps. Deploy using:

```bash
az containerapp create \
  --name south-sudan-geocoder \
  --resource-group <your-rg> \
  --image <your-registry>/south-sudan-geocoder:latest \
  --env-vars-file .env \
  --target-port 8501 \
  --ingress external
```

## Usage

### 1. Data Ingestion

1. Navigate to **Data Manager** page
2. Upload GeoJSON files for admin layers:
   - `admin1_state.geojson`
   - `admin2_county.geojson`
   - `admin3_payam.geojson`
   - `admin4_boma.geojson`
3. Upload CSV file for settlements with columns: `lon`, `lat`, `name`
4. Click **Build Index** to create the name index

### 2. Geocoding

1. Navigate to **Geocoder** page
2. Enter a free text location string (e.g., "Juba, Central Equatoria")
3. Click **Resolve**
4. View results with coordinates, admin hierarchy, and map visualization

### 3. Settings

Configure:
- Fuzzy matching threshold
- Centroid computation CRS
- Azure AI extraction (optional)

## Data Format

### GeoJSON Admin Layers

Required fields:
- `name`: Feature name
- `geometry`: Polygon geometry (EPSG:4326)

Optional fields:
- `aliases`: Comma-separated alternate names
- `admin1Name`, `admin2Name`, etc.: Parent admin names

### Settlements CSV

Required columns:
- `lon`: Longitude (EPSG:4326)
- `lat`: Latitude (EPSG:4326)
- `name`: Settlement name

Optional columns:
- `aliases`: Comma-separated alternate names

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=app --cov-report=html
```

## Project Structure

```
app/
  core/
    config.py          # Configuration management
    models.py          # Data models
    normalization.py   # Text normalization
    fuzzy.py           # Fuzzy matching
    spatial.py         # Spatial operations
    centroids.py       # Centroid computation
    duckdb_store.py    # DuckDB storage layer
    geocoder.py        # Core geocoding engine
    azure_ai.py        # Azure AI integration
  gazetteers/
    base.py            # Gazetteer base class
    geonames.py        # GeoNames provider
    osm_overpass.py    # OSM provider (optional)
    csv_provider.py    # CSV provider
  pages/
    1_Geocoder.py      # Geocoder UI
    2_Data_Manager.py   # Data ingestion UI
    3_Settings.py      # Settings UI
    4_Diagnostics.py   # Diagnostics UI
  utils/
    logging.py         # Structured logging
    timing.py          # Performance timing
  streamlit_app.py     # Main app entry point
tests/
  test_*.py            # Test suites
data/
  duckdb/              # DuckDB database files
  ingested/            # Uploaded data files
requirements.txt       # Python dependencies
Dockerfile             # Docker configuration
.env.example           # Environment variables template
README.md              # This file
```

## Performance

- **Indexed Lookup**: O(log n) name matching
- **Spatial Joins**: Vectorized operations with GeoPandas
- **Caching**: Query cache prevents repeated computation
- **Target**: 100+ queries/second for cached results

## Security

- All secrets loaded from environment variables
- No hardcoded credentials
- `.env` file excluded from version control
- Azure Managed Identity support ready (key-based for now)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2024 Mafizul Islam

## Contributing

[Contributing guidelines]

