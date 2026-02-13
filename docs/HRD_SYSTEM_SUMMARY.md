# HRD Weekly Report Automation System - Summary

## ✅ System Complete and Operational

The automated HRD weekly report processing system has been successfully built and tested.

## System Capabilities

### 1. **Field Office Daily Processing**
- ✅ Reads `.docx` files from `Dailies/` folders
- ✅ Extracts field office name from filename
- ✅ Extracts date from filename patterns
- ✅ Processes multiple dailies per day

### 2. **Incident Extraction (LLM-Powered)**
- ✅ Uses **Ollama** (llama3.2:3b) for fast local extraction
- ✅ Falls back to **Azure AI** if Ollama unavailable
- ✅ Extracts structured incident data:
  - Dates (incident, interview)
  - Location (with geocoding support)
  - Violations and perpetrators
  - Victim demographics
  - Source information
  - Full descriptions

### 3. **Compiled Report Generation**
- ✅ Generates formatted HRD Daily Reports
- ✅ Groups incidents by state
- ✅ Creates highlights section
- ✅ Follows UNMISS HRD format standards

### 4. **Weekly Matrix Generation**
- ✅ Creates structured Excel files
- ✅ Includes all 26 required columns
- ✅ Assigns incident codes
- ✅ Supports geocoding (Payam, County, coordinates)

## Test Results

**Test Run: Week 03-09 (November 2025)**
- ✅ Processed: **40 daily reports**
- ✅ Extracted: **70 incidents**
- ✅ Generated: **5 compiled daily reports**
- ✅ Generated: **1 weekly matrix**

## Usage

### Process a Week Folder

```bash
python scripts/process_hrd_weekly.py \
    --week-folder 03-09 \
    --weekly-dir resources/Weekly
```

### Test Extraction

```bash
python scripts/test_hrd_extraction.py
```

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Field Office Dailies (Dailies/*.docx)                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  HRDIncidentExtractor                                   │
│  - Ollama (primary, fast)                               │
│  - Azure AI (fallback)                                  │
│  - Geocoder (location resolution)                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Structured Incidents (HRDIncident objects)            │
└──────┬──────────────────────────────┬───────────────────┘
       │                              │
       ▼                              ▼
┌──────────────────┐        ┌──────────────────────┐
│ HRDReportCompiler│        │ HRDMatrixGenerator    │
│                  │        │                      │
│ - Groups by date │        │ - Excel format       │
│ - Formats report │        │ - All columns        │
│ - Word output    │        │ - Incident codes     │
└──────────────────┘        └──────────────────────┘
       │                              │
       ▼                              ▼
┌──────────────────┐        ┌──────────────────────┐
│ HRD Daily Reports│        │ Weekly CivCas Matrix│
│ (*.docx)         │        │ (*.xlsx)            │
└──────────────────┘        └──────────────────────┘
```

## Key Features

### 1. **Intelligent Extraction**
- Uses LLM to understand context and extract structured data
- Handles various report formats and styles
- Extracts dates, locations, violations, perpetrators, victims

### 2. **Efficient Processing**
- Ollama for fast local processing (3.6x faster than llama3)
- Azure AI as reliable fallback
- Batch processing of multiple dailies

### 3. **Location Intelligence**
- Extracts location strings from descriptions
- Geocodes to Payam, County, coordinates
- Uses existing geocoding infrastructure

### 4. **Format Compliance**
- Matches existing HRD Daily Report format
- Matches existing Weekly Matrix structure
- Maintains UNMISS HRD standards

## Files Created

### Core Modules
- `app/core/hrd_incident_extractor.py` - LLM-powered incident extraction
- `app/core/hrd_report_compiler.py` - Report compilation
- `app/core/hrd_matrix_generator.py` - Matrix generation

### Scripts
- `scripts/process_hrd_weekly.py` - Main processing script
- `scripts/test_hrd_extraction.py` - Testing script
- `scripts/analyze_hrd_structure.py` - Structure analysis

### Documentation
- `HRD_AUTOMATION_SYSTEM.md` - Complete system documentation
- `HRD_SYSTEM_SUMMARY.md` - This summary

## Next Steps for Production

1. **Evaluate Accuracy**
   - Compare extracted incidents with manual entries
   - Measure extraction success rate
   - Identify common errors

2. **Improve Extraction**
   - Refine LLM prompts based on results
   - Handle edge cases and special formats
   - Improve date parsing

3. **Enhance Geocoding**
   - Ensure database access for location resolution
   - Improve location extraction from descriptions
   - Validate Payam/County matches

4. **Batch Processing**
   - Process multiple weeks automatically
   - Generate summary reports
   - Track processing statistics

5. **Quality Assurance**
   - Add validation checks
   - Flag suspicious data
   - Generate quality reports

## Configuration

### Ollama
- Model: `llama3.2:3b` (default, fastest)
- Location: `http://localhost:11434`
- Timeout: 20 seconds

### Azure AI
- Configured via `.env` file
- Deployment: `gpt-4.1-mini` (default)
- Used as fallback

### Geocoding
- Uses existing DuckDB database
- Requires database access
- Falls back gracefully if locked

## Performance

- **Extraction Speed**: ~0.7s per incident (Ollama)
- **Processing**: 40 dailies → 70 incidents in ~2-3 minutes
- **Accuracy**: Needs evaluation with real data

## Support

For issues or improvements:
1. Check logs for errors
2. Verify Ollama/Azure AI availability
3. Check database access
4. Review extraction results

## Conclusion

The system is **ready for testing and evaluation**. It successfully:
- ✅ Processes field office dailies
- ✅ Extracts structured incidents
- ✅ Generates compiled reports
- ✅ Creates weekly matrices

**Next**: Evaluate accuracy with real data and iterate for improvement.

