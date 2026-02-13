# Codebase Refactoring Audit Report

## Phase 1: Codebase Audit Findings

### 1. Unused/Dead Code Files

**Root-level debug/test scripts (should be moved to scripts/ or removed):**
- `analyze_database.py` - Debug script, should be in scripts/ or tests/
- `analyze_db_when_ready.py` - Debug script
- `debug_geocoder.py` - Debug script
- `test_constraints.py` - Test script, should be in tests/
- `test_location.py` - Test script, should be in tests/
- `direct_db_check.py` - Debug script
- `clear_cache.py` - Utility script, should be in scripts/

**Incomplete/Placeholder implementations:**
- `app/gazetteers/osm_overpass.py` - Placeholder only, returns empty
- `app/core/scrapers/google_maps_scraper.py` - TODO comments, not implemented

**Virtual environment in repo:**
- `ungis/` - Should be in .gitignore, not committed

**Log files in repo:**
- `streamlit_run.log`, `streamlit.log`, `streamlit.pid` - Should be in .gitignore

### 2. Security Issues

**SQL Injection Vulnerabilities:**
- `app/core/duckdb_store.py`: Multiple f-string SQL queries (lines 31, 65, 739, etc.)
- `app/pages/4_Diagnostics.py`: f-string SQL query (line 65)
- `app/pages/1_Geocoder.py`: f-string SQL query (line 17)
- `app/core/geocoder.py`: f-string SQL query (line 36)

**Risk:** User-controlled input could potentially inject SQL if layer names are not properly validated.

**Recommendation:** Use parameterized queries or validate layer names against whitelist.

### 3. Code Duplication

**Database query patterns:**
- Similar patterns for loading admin layers repeated in multiple places
- Name normalization logic scattered across files
- Error handling patterns inconsistent

**Normalization:**
- `normalize_text()` imported in multiple places but logic is centralized (good)
- Some files have inline normalization instead of using utility

### 4. Naming Inconsistencies

**File naming:**
- Most files use snake_case (good)
- Some inconsistencies in abbreviations (e.g., `osm_overpass.py` vs `osm_scraper.py`)

**Variable naming:**
- Generally consistent snake_case
- Some abbreviations could be clearer (e.g., `gdf`, `bbox`)

**Function naming:**
- Mix of public/private (some `_private` methods, some not)
- Some functions could be more descriptive

### 5. Separation of Concerns Issues

**Streamlit pages mixing concerns:**
- Pages directly access database connections
- Business logic mixed with UI code
- No clear service layer

**Configuration:**
- Config scattered across files
- Some hardcoded values that should be configurable

### 6. Error Handling Issues

**Inconsistent error handling:**
- Some functions use try/except, some don't
- Error messages inconsistent
- Some silent failures

**Database errors:**
- Not all database operations wrapped in try/except
- Connection errors not always handled gracefully

### 7. Performance Risks

**Memory:**
- Admin layers loaded into memory entirely (could be large)
- No pagination for large datasets
- GeoDataFrames kept in memory

**Database:**
- Some queries not optimized (e.g., loading all features)
- No connection pooling
- No query timeout handling

### 8. Testing Gaps

**Missing test coverage:**
- No tests for error handling paths
- No integration tests for full geocoding flow
- No tests for edge cases (null values, empty strings, etc.)
- No performance/load tests

**Test organization:**
- Some test scripts in root instead of tests/
- Test fixtures could be more comprehensive

### 9. Documentation Issues

**Code documentation:**
- Some functions missing docstrings
- Type hints inconsistent (some have, some don't)
- Complex logic not well documented

**Architecture documentation:**
- Multiple markdown files with overlapping info
- No clear architecture diagram
- API contracts not documented

### 10. Dependencies

**Unused dependencies:**
- Need to verify all requirements.txt packages are used
- Some optional dependencies not clearly marked

**Version pinning:**
- Some dependencies use `>=` which could cause breaking changes
- No requirements-dev.txt for development dependencies

### 11. Configuration Management

**Environment variables:**
- Some config values have defaults, some don't
- No validation of required vs optional config
- No config schema/documentation

### 12. Type Safety

**Type hints:**
- Inconsistent use of type hints
- Some functions missing return type annotations
- Optional types not always properly marked

### 13. Import Organization

**Import statements:**
- Some files have circular import risks
- Imports not always organized (stdlib, third-party, local)
- Some unused imports

### 14. Code Quality

**Code complexity:**
- Some functions too long (e.g., `duckdb_store.py` has 1400+ lines)
- Some classes doing too much (violation of SRP)
- Nested conditionals could be simplified

**Magic numbers:**
- Some hardcoded values (thresholds, limits) should be constants
- Coordinate system codes hardcoded in places

## Priority Issues to Address

### Critical (Security/Stability)
1. SQL injection vulnerabilities
2. Missing error handling in critical paths
3. Database connection error handling

### High (Code Quality)
1. Move debug scripts to appropriate locations
2. Remove unused/incomplete code
3. Standardize error handling
4. Add comprehensive tests

### Medium (Maintainability)
1. Refactor large files/classes
2. Improve separation of concerns
3. Standardize naming conventions
4. Add type hints consistently

### Low (Nice to Have)
1. Improve documentation
2. Optimize performance
3. Add more configuration options


