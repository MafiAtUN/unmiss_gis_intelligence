# HRD Weekly Report Automation System

## Overview

This system automates the processing of UNMISS Human Rights Division (HRD) weekly reports:

**Workflow:**
1. **Field Office Dailies** → Extract incidents using LLM (Ollama/Azure AI)
2. **Compiled HRD Daily Reports** → Generate formatted Word documents
3. **Weekly CivCas Matrix** → Generate structured Excel files

## System Components

### 1. HRD Incident Extractor (`app/core/hrd_incident_extractor.py`)

Extracts structured incident data from field office daily reports using LLM.

**Features:**
- Uses Ollama (local, fast) as primary extraction method
- Falls back to Azure AI if Ollama unavailable
- Extracts all incident fields:
  - Dates (incident, interview)
  - Location (with geocoding)
  - Violations
  - Perpetrators
  - Victim demographics
  - Source information
  - Full description

**Usage:**
```python
from app.core.hrd_incident_extractor import HRDIncidentExtractor

extractor = HRDIncidentExtractor()
incidents = extractor.extract_incidents_from_text(report_text, field_office="Torit")
```

### 2. HRD Report Compiler (`app/core/hrd_report_compiler.py`)

Compiles field office dailies into formatted HRD Daily Reports.

**Features:**
- Groups incidents by state
- Generates highlights section
- Formats according to UNMISS HRD standards
- Creates Word documents (.docx)

**Usage:**
```python
from app.core.hrd_report_compiler import HRDReportCompiler
from datetime import datetime

compiler = HRDReportCompiler()
compiler.compile_daily_report(
    date=datetime(2025, 11, 4),
    field_office_dailies=[
        {"file_path": "path/to/daily.docx", "field_office": "Torit"}
    ],
    output_path="HRD Daily Report_4 November 2025.docx"
)
```

### 3. HRD Matrix Generator (`app/core/hrd_matrix_generator.py`)

Generates Weekly CivCas Matrix Excel files from incidents.

**Features:**
- Creates structured Excel files with all required columns
- Assigns incident codes
- Includes geocoded locations (Payam, County, coordinates)
- Matches format of existing matrices

**Usage:**
```python
from app.core.hrd_matrix_generator import HRDMatrixGenerator
from datetime import datetime

generator = HRDMatrixGenerator()
generator.generate_matrix(
    incidents=incidents,
    start_date=datetime(2025, 11, 3),
    end_date=datetime(2025, 11, 9),
    output_path="Weekly CivCas Matrix-3-9 November 2025.xlsx",
    start_incident_code=1402
)
```

## Main Processing Script

### `scripts/process_hrd_weekly.py`

Automates the entire workflow for a week folder.

**Usage:**
```bash
python scripts/process_hrd_weekly.py \
    --week-folder 03-09 \
    --weekly-dir resources/Weekly \
    --output-dir resources/Weekly/03-09
```

**What it does:**
1. Reads all `.docx` files from `Dailies/` folder
2. Extracts incidents from each daily report
3. Groups dailies by date
4. Generates compiled HRD Daily Reports for each date
5. Generates Weekly CivCas Matrix Excel file

## Testing

### Test Incident Extraction

```bash
python scripts/test_hrd_extraction.py
```

This tests:
- Ollama availability
- Azure AI availability
- Geocoder availability
- Incident extraction from sample text

## Configuration

### Ollama Setup

The system uses `llama3.2:3b` by default (configured in `app/core/config.py`).

**Check Ollama:**
```bash
ollama list
ollama pull llama3.2:3b  # If not installed
```

### Azure AI Setup

Configure in `.env`:
```
AZURE_FOUNDRY_ENDPOINT=...
AZURE_FOUNDRY_API_KEY=...
AZURE_UNMISS_DEPLOYMENT_GPT41_MINI=gpt-4.1-mini
```

## Data Flow

```
Field Office Dailies (Dailies/*.docx)
    ↓
[LLM Extraction] → Structured Incidents
    ↓
[Report Compiler] → HRD Daily Reports (*.docx)
    ↓
[Matrix Generator] → Weekly CivCas Matrix (*.xlsx)
```

## Output Structure

### Compiled HRD Daily Report Format

```
UNITED NATIONS         ألأمم المتحدة
United Nations Mission in South Sudan (UNMISS)
Human Rights Division (HRD)
Daily Situation Report
[Date]

Highlights
- [Brief summary of incidents]

[State Name]
[Detailed incident descriptions]

End    -
```

### Weekly Matrix Columns

1. Incident Code
2. Date of Interview
3. Month of interview/report
4. Date of Incident
5. Reporting Field Office
6. Incident State
7. Location of Incident
8. Source Information
9. Types of violations
10. Generalized Violations
11. Alleged Perpetrator(s)
12. Involved in Hostilities
13. Origin of Alleged Perpetrators
14. Ethnicity/Tribe of victim/survivor
15. Total Victims
16. Male (#)
17. Female (#)
18. Minor (M)
19. Minor (F)
20. Source of the information
21. Description
22. Update
23. Remarks by CMC/CRVT
24. Corroborated/Verified
25. Payam
26. County

## Accuracy & Quality

The system uses:
- **LLM extraction** for intelligent parsing of unstructured text
- **Geocoding** for location resolution (Payam, County, coordinates)
- **Fuzzy matching** for location name matching
- **Validation** to ensure data quality

**Current Status:**
- ✅ Incident extraction working
- ✅ Report compilation working
- ✅ Matrix generation working
- ⚠️ Geocoding requires database access (may be locked)
- ⚠️ Extraction accuracy needs evaluation with real data

## Next Steps

1. **Test with real data**: Process a week folder and compare with existing reports
2. **Evaluate accuracy**: Compare extracted incidents with manual entries
3. **Improve prompts**: Refine LLM prompts based on results
4. **Handle edge cases**: Improve parsing for various report formats
5. **Batch processing**: Process multiple weeks automatically

## Troubleshooting

### Ollama Timeout
- Check if Ollama is running: `ollama list`
- Reduce `num_predict` in extraction code
- Use smaller model (e.g., `llama3.2:1b`)

### Database Lock
- Close other applications using DuckDB
- Use read-only mode for geocoding
- Process without geocoding (locations will be extracted but not resolved)

### Azure AI Errors
- Check API keys in `.env`
- Verify endpoint URLs
- Check deployment names

## Human Rights Documentation Standards

The system follows UNMISS HRD documentation standards:
- **Source verification**: Tracks source information (primary/secondary, number of sources)
- **Victim demographics**: Records gender and age breakdown
- **Location precision**: Includes Boma, Payam, County hierarchy
- **Violation categorization**: Uses standardized violation types
- **Corroboration status**: Tracks verification status

