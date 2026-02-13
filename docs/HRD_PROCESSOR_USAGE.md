# HRD Report Processor - User Guide

## Overview

The HRD Report Processor is a Streamlit-based interface for processing field office daily reports and generating:
1. **Compiled HRD Daily Reports (DSRs)** - Formatted Word documents
2. **Weekly CivCas Matrices** - Structured Excel files

## Access

The HRD Report Processor is available as a page in the Streamlit app:
- Run: `streamlit run app/streamlit_app.py`
- Navigate to: **"5_HRD_Report_Processor"** page

## Features

### 1. Folder Processing
- **Scan a folder** containing field office daily reports
- Automatically detects all `.docx` files
- Extracts field office names from filenames
- Parses dates from filenames

### 2. Manual Upload
- **Upload daily reports** directly through the web interface
- Supports multiple file uploads
- Automatically processes and prepares files

### 3. Generate Reports
- **Compiled Reports (DSRs)**: Generate formatted HRD Daily Reports
- **Weekly Matrix**: Generate structured Excel matrices

## Step-by-Step Usage

### Option 1: Process from Folder

1. **Navigate to "Folder Processing" tab**
2. **Enter folder path** (e.g., `resources/Weekly/03-09/Dailies`)
3. **Click "Scan Folder"**
4. System will:
   - Find all `.docx` files
   - Extract field office names
   - Parse dates from filenames
   - Display found files

### Option 2: Manual Upload

1. **Navigate to "Manual Upload" tab**
2. **Click "Browse files"** or drag and drop
3. **Select one or more `.docx` files**
4. **Click "Process Uploaded Files"**
5. System will:
   - Save files temporarily
   - Extract field office names
   - Parse dates
   - Display processed files

### Generate Compiled Report (DSR)

1. **Go to "Results" tab**
2. **Configure settings** (in sidebar):
   - Report Date
   - Output Directory
3. **Click "Generate Compiled Report (DSR)"**
4. System will:
   - Extract incidents from all dailies
   - Group by date
   - Generate formatted Word documents
   - Save to output directory
5. **Download** generated reports

### Generate Weekly Matrix

1. **Go to "Results" tab**
2. **Configure settings** (in sidebar):
   - Week Start Date
   - Week End Date
   - Starting Incident Code
   - Output Directory
3. **Click "Generate Weekly Matrix"**
4. System will:
   - Extract all incidents from dailies
   - Structure data into Excel format
   - Include all 26 columns
   - Geocode locations (if available)
5. **Download** generated matrix
6. **Preview** matrix data in the interface

## Configuration Options

### Sidebar Settings

- **Report Date**: Date for compiled reports
- **Week Start/End**: Date range for weekly matrix
- **Starting Incident Code**: First incident code number
- **Output Directory**: Where to save generated files

## File Requirements

### Input Files (Dailies)
- **Format**: `.docx` (Word documents)
- **Naming**: Should include field office name and date
- **Content**: Field office daily reports with incident descriptions

### Output Files

#### Compiled Reports (DSRs)
- **Format**: `.docx` (Word documents)
- **Naming**: `HRD Daily Report_[Date].docx`
- **Structure**:
  - Header (UNMISS HRD)
  - Highlights section
  - Incidents grouped by state
  - Footer

#### Weekly Matrix
- **Format**: `.xlsx` (Excel)
- **Naming**: `Weekly CivCas Matrix-[Date Range].xlsx`
- **Columns**: 26 standard columns
- **Content**: Structured incident data

## Field Office Detection

The system automatically detects field offices from filenames:
- Bor
- Bentiu
- Rumbek
- Yei
- Yambio
- Aweil
- FOT
- Juba
- Torit
- Wau
- Malakal

## Date Parsing

The system supports multiple date formats in filenames:
- `YYYY-MM-DD` (e.g., 2025-11-06)
- `YYYYMMDD` (e.g., 20251106)
- `DD/MM/YYYY` (e.g., 06/11/2025)
- `DD-MM-YYYY` (e.g., 06-11-2025)

## Processing Workflow

```
Field Office Dailies
        ↓
[Upload/Select Files]
        ↓
[Extract Incidents using LLM]
        ↓
[Generate Reports]
        ├──→ Compiled Reports (DSRs)
        └──→ Weekly Matrix
```

## Tips

1. **Batch Processing**: Process multiple dailies at once
2. **Date Organization**: System groups dailies by date automatically
3. **Preview Results**: Check matrix preview before downloading
4. **Output Directory**: Use organized folder structure for outputs
5. **Incident Codes**: Set starting code to continue from previous week

## Troubleshooting

### No files found
- Check folder path is correct
- Ensure files are `.docx` format
- Check file permissions

### Processing errors
- Check file format (must be valid Word documents)
- Verify Ollama/Azure AI is available
- Check logs for detailed error messages

### Download issues
- Files are saved to output directory
- Can also download directly from interface
- Check browser download settings

## Performance

- **Processing Speed**: ~0.4-0.7 seconds per incident (Ollama)
- **Batch Size**: Can process 40+ dailies in 2-3 minutes
- **Memory Usage**: ~4-6GB (with Ollama)

## Next Steps

After generating reports:
1. Review compiled reports for accuracy
2. Check matrix data completeness
3. Validate incident codes
4. Verify location geocoding
5. Export for further use

