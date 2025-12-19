# How the South Sudan Geocoding Application Works

## Overview

The application is a Streamlit-based web application that geocodes free text location strings into precise coordinates using hierarchical administrative boundaries (State → County → Payam → Boma → Village) for South Sudan.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI (Frontend)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Geocoder  │  │Data Mgr  │  │Settings  │  │Diagnostics│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Geocoder Engine (Core)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │Normalization │  │Fuzzy Match   │  │Spatial Ops   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  DuckDB      │  │ Azure AI     │  │ GeoPandas    │
│  Storage     │  │ Foundry      │  │ Shapely      │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Application Flow

### 1. Startup & Initialization

When you run `streamlit run app/streamlit_app.py`:

1. **Loads Configuration** (`config.py`)
   - Reads `.env` file for Azure credentials
   - Sets up paths (data directory, DuckDB location)
   - Configures geocoding parameters

2. **Initializes Components**
   - Creates `DuckDBStore` connection to database
   - Creates `Geocoder` instance with database store
   - Sets up logging

3. **Streamlit Session State**
   - Stores database connection (persists across page navigations)
   - Stores geocoder instance (cached for performance)

### 2. Data Ingestion Flow (Data Manager Page)

```
User uploads GeoJSON/CSV
        │
        ▼
Validate file format
        │
        ▼
Load into GeoPandas
        │
        ▼
Reproject to EPSG:4326 (WGS84)
        │
        ▼
Compute centroids (for polygons)
        │
        ▼
Store in DuckDB (WKB format)
        │
        ▼
Build name index (fuzzy matching)
        │
        ▼
Ready for geocoding
```

**Steps:**
1. User uploads GeoJSON for admin layers or CSV for settlements
2. System validates schema (checks for required fields like `name`)
3. Data is loaded into GeoPandas GeoDataFrame
4. Geometries are reprojected to EPSG:4326 if needed
5. For polygons, centroids are computed in UTM Zone 36N, then converted back to WGS84
6. Data is stored in DuckDB as WKB (Well-Known Binary) for fast spatial queries
7. Name index is built with normalized names and aliases for fuzzy matching

### 3. Geocoding Flow (Main Process)

When a user enters a location string and clicks "Resolve":

```
User Input: "Juba, Central Equatoria"
        │
        ▼
┌───────────────────────────────────────┐
│ 1. Normalize Text                     │
│    - Lowercase, remove punctuation    │
│    - Unicode normalization            │
│    - Collapse whitespace              │
│    Result: "juba central equatoria"   │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 2. Check Cache                        │
│    - Look up normalized text in DB    │
│    - If found, return cached result   │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 3. Extract Candidates                 │
│    A. Deterministic parsing:          │
│       - Generate n-grams              │
│       - Filter stop words             │
│    B. AI extraction (if enabled):    │
│       - Call Azure AI Foundry         │
│       - Extract structured candidates │
│       - Merge with deterministic      │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 4. Hierarchical Resolution            │
│    Try in order:                      │
│    1. Village/Settlement (points)     │
│    2. Boma (polygons)                 │
│    3. Payam (polygons)                 │
│    (County/State = too coarse)        │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 5. For Each Level:                    │
│    - Search name index (fuzzy match)   │
│    - Get best match above threshold   │
│    - Verify containment (spatial)     │
│    - Get admin hierarchy              │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 6. Return Result                      │
│    - Coordinates (lon, lat)           │
│    - Admin hierarchy                  │
│    - Match score                      │
│    - Alternative matches              │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 7. Cache Result                       │
│    - Store in geocode_cache table     │
│    - For future fast lookups          │
└───────────────────────────────────────┘
```

### 4. Detailed Component Interactions

#### A. Text Normalization (`normalization.py`)
- Converts "Juba, Central Equatoria" → "juba central equatoria"
- Handles Unicode, punctuation, whitespace
- Generates n-grams for candidate extraction

#### B. Fuzzy Matching (`fuzzy.py`)
- Uses RapidFuzz library
- Token sort ratio + partial ratio
- Finds best matches above threshold (default 0.7)
- Returns top 5 alternatives per layer

#### C. Spatial Operations (`spatial.py`)
- Point-in-polygon containment checks
- Spatial joins using GeoPandas
- Hierarchical lookup (point → boma → payam → county → state)
- All in EPSG:4326 (WGS84)

#### D. Azure AI Integration (`azure_ai.py`)
- Optional AI-powered text parsing
- Calls Azure AI Foundry (UNMISS project)
- Uses `gpt-4.1-mini` by default (cost-effective)
- Extracts structured place names:
  ```json
  {
    "country": "South Sudan",
    "state_candidates": ["Central Equatoria"],
    "county_candidates": [],
    "payam_candidates": [],
    "boma_candidates": [],
    "village_candidates": ["Juba"]
  }
  ```
- AI output is **never trusted** - always verified against name index

#### E. DuckDB Storage (`duckdb_store.py`)
- Stores geometries as WKB (fast, compact)
- Also stores GeoJSON text (for visualization)
- Name index for fast fuzzy lookup
- Geocode cache for repeated queries
- All with proper indexing

#### F. Centroid Computation (`centroids.py`)
- For polygons, computes centroid in UTM Zone 36N (EPSG:32736)
- More accurate than WGS84 for South Sudan region
- Converts back to WGS84 for output

### 5. Resolution Logic

The geocoder tries to find the **most specific** location:

1. **Village/Settlement** (Point)
   - Exact or fuzzy name match
   - Returns point coordinates
   - Computes full admin hierarchy (boma → payam → county → state)

2. **Boma** (Polygon)
   - If village not found, try boma name
   - Returns boma centroid
   - Computes hierarchy above (payam → county → state)

3. **Payam** (Polygon)
   - If boma not found, try payam name
   - Returns payam centroid
   - Computes hierarchy above (county → state)

4. **County/State Only**
   - If only county or state found
   - **Does NOT return coordinates** (too coarse)
   - Returns best match suggestions without coordinates

### 6. Caching Strategy

- **Query Cache**: Normalized input text → full result
- **Name Index**: Pre-computed normalized names for fast lookup
- **Admin Layers**: Loaded into memory on first use, cached in session

### 7. UI Pages

#### Geocoder Page
- Text input area
- Resolve button
- Results display:
  - Match details (name, score, coordinates)
  - Admin hierarchy
  - Interactive map (pydeck)
  - Alternative matches

#### Data Manager Page
- File upload (GeoJSON/CSV)
- Schema validation
- Data preview
- Build index button
- Data status dashboard

#### Settings Page
- Fuzzy threshold slider
- Centroid CRS selection
- Azure AI toggle
- Configuration display

#### Diagnostics Page
- Cache statistics
- Recent queries
- Database info
- Layer statistics
- Cache management

## Current Configuration

### Azure AI Foundry (UNMISS Project)
- **Endpoint**: `https://<your-endpoint>.cognitiveservices.azure.com/`
- **Project**: `unmiss / proj-default`
- **Default Model**: `gpt-4.1-mini` (cost-effective)
- **Available Models**: 9 deployments (OpenAI, Anthropic, xAI, Meta)
- **Status**: Enabled by default (`ENABLE_AI_EXTRACTION=true`)

### Database
- **Storage**: DuckDB (local file)
- **Location**: `./data/duckdb/geocoder.duckdb`
- **Format**: WKB for geometries, JSON for metadata

### Geocoding Settings
- **Fuzzy Threshold**: 0.7 (70% similarity)
- **Centroid CRS**: EPSG:32736 (UTM Zone 36N)
- **Cache TTL**: 86400 seconds (24 hours)

## How to Run

1. **Activate virtual environment**:
   ```bash
   source ungis/bin/activate
   ```

2. **Start Streamlit**:
   ```bash
   streamlit run app/streamlit_app.py
   ```

3. **Access in browser**:
   - Default: `http://localhost:8501`

## Example Workflow

1. **First Time Setup**:
   - Go to Data Manager
   - Upload `admin1_state.geojson`
   - Upload `admin2_county.geojson`
   - Upload `admin3_payam.geojson`
   - Upload `admin4_boma.geojson`
   - Upload `settlements.csv` (with lon, lat, name columns)
   - Click "Build Index"

2. **Geocode a Location**:
   - Go to Geocoder page
   - Enter: "Juba, Central Equatoria"
   - Click "Resolve"
   - View results with map

3. **Monitor Performance**:
   - Go to Diagnostics page
   - Check cache hit rate
   - View recent queries

## Performance Features

- **Caching**: Prevents repeated computation
- **Indexed Lookup**: O(log n) name matching
- **Vectorized Operations**: GeoPandas spatial joins
- **Lazy Loading**: Admin layers loaded on demand
- **Target**: 100+ queries/second for cached results

## Error Handling

- Graceful degradation if AI extraction fails
- Fallback to deterministic parsing
- Clear error messages in UI
- Validation at each step

## Security

- All secrets in `.env` (not committed)
- No hardcoded credentials
- Environment-based configuration
- Ready for Azure Managed Identity (future)

