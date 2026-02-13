#!/usr/bin/env python3
"""
Process HRD Weekly Reports: From Field Office Dailies → Compiled Reports → Weekly Matrix

This script automates the entire workflow:
1. Read field office daily reports from Dailies folder
2. Extract incidents using LLM (Ollama/Azure AI)
3. Compile into HRD Daily Reports
4. Generate Weekly CivCas Matrix Excel file
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.hrd_incident_extractor import HRDIncidentExtractor
from app.core.hrd_report_compiler import HRDReportCompiler
from app.core.hrd_matrix_generator import HRDMatrixGenerator
from app.core.ollama_location_extractor import OllamaLocationExtractor
from app.core.azure_ai import AzureAIParser
from app.core.geocoder import Geocoder
from app.core.duckdb_store import DuckDBStore
from app.utils.logging import log_structured


def parse_week_folder(week_folder: str) -> tuple[datetime, datetime]:
    """
    Parse week folder name (e.g., "03-09") to date range.
    
    Args:
        week_folder: Folder name like "03-09" (assumes current month/year)
        
    Returns:
        (start_date, end_date)
    """
    # For now, assume November 2025 (can be made configurable)
    current_year = 2025
    current_month = 11
    
    try:
        start_day, end_day = map(int, week_folder.split("-"))
        start_date = datetime(current_year, current_month, start_day)
        end_date = datetime(current_year, current_month, end_day)
        return start_date, end_date
    except Exception:
        # Default to current week
        today = datetime.now()
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        return start_date, end_date


def extract_field_office_from_filename(filename: str) -> str:
    """Extract field office name from filename."""
    filename_lower = filename.lower()
    
    # Common field office patterns
    field_offices = {
        "bor": "Bor",
        "bentiu": "Bentiu",
        "rumbek": "Rumbek",
        "yei": "Yei",
        "yambio": "Yambio",
        "aweil": "Aweil",
        "fot": "FOT",
        "juba": "Juba",
        "torit": "Torit",
        "wau": "Wau",
        "malakal": "Malakal",
    }
    
    for key, value in field_offices.items():
        if key in filename_lower:
            return value
    
    return "Unknown"


def process_weekly_folder(week_folder_path: Path, output_dir: Path) -> Dict[str, Any]:
    """
    Process a weekly folder: dailies → compiled reports → matrix.
    
    Args:
        week_folder_path: Path to week folder (e.g., "03-09")
        output_dir: Directory to save outputs
        
    Returns:
        Processing results
    """
    week_folder_name = week_folder_path.name
    start_date, end_date = parse_week_folder(week_folder_name)
    
    log_structured("info", f"Processing week folder: {week_folder_name}",
                   start_date=start_date.strftime("%Y-%m-%d"),
                   end_date=end_date.strftime("%Y-%m-%d"))
    
    # Initialize components
    try:
        db_store = DuckDBStore()
        geocoder = Geocoder(db_store)
    except Exception:
        geocoder = None
    
    ollama_extractor = OllamaLocationExtractor()
    azure_parser = AzureAIParser()
    incident_extractor = HRDIncidentExtractor(
        ollama_extractor=ollama_extractor,
        azure_parser=azure_parser,
        geocoder=geocoder
    )
    report_compiler = HRDReportCompiler(incident_extractor)
    matrix_generator = HRDMatrixGenerator()
    
    # 1. Read field office dailies
    dailies_dir = week_folder_path / "Dailies"
    if not dailies_dir.exists():
        log_structured("warning", "Dailies folder not found", folder=str(dailies_dir))
        return {"error": "Dailies folder not found"}
    
    daily_files = list(dailies_dir.glob("*.docx"))
    log_structured("info", f"Found {len(daily_files)} daily reports")
    
    # Group dailies by date
    dailies_by_date: Dict[datetime, List[Dict[str, Any]]] = {}
    
    for daily_file in daily_files:
        # Try to extract date from filename
        date = None
        try:
            # Common patterns: "2025-11-06", "20251106", "06/11/2025"
            filename = daily_file.stem
            for pattern in ["%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"]:
                try:
                    date_str = filename[:10] if len(filename) >= 10 else filename
                    date = datetime.strptime(date_str, pattern)
                    break
                except ValueError:
                    continue
        except Exception:
            pass
        
        if not date:
            # Default to start_date
            date = start_date
        
        field_office = extract_field_office_from_filename(daily_file.name)
        
        if date not in dailies_by_date:
            dailies_by_date[date] = []
        
        dailies_by_date[date].append({
            "file_path": str(daily_file),
            "field_office": field_office
        })
    
    # 2. Generate compiled daily reports
    compiled_reports = []
    all_incidents = []
    
    for date, dailies in sorted(dailies_by_date.items()):
        log_structured("info", f"Compiling report for {date.strftime('%Y-%m-%d')}",
                     dailies_count=len(dailies))
        
        output_path = output_dir / f"HRD Daily Report_{date.strftime('%d %B %Y')}.docx"
        
        try:
            compiled_path = report_compiler.compile_daily_report(
                date=date,
                field_office_dailies=dailies,
                output_path=str(output_path)
            )
            compiled_reports.append(compiled_path)
            log_structured("info", f"Generated compiled report: {compiled_path}")
        except Exception as e:
            log_structured("error", f"Failed to compile report for {date}",
                          error=str(e))
    
    # 3. Extract all incidents for matrix
    for daily_file in daily_files:
        try:
            from docx import Document
            doc = Document(daily_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            field_office = extract_field_office_from_filename(daily_file.name)
            
            incidents = incident_extractor.extract_incidents_from_text(text, field_office)
            all_incidents.extend(incidents)
        except Exception as e:
            log_structured("error", f"Failed to extract incidents from {daily_file.name}",
                          error=str(e))
    
    log_structured("info", f"Extracted {len(all_incidents)} total incidents")
    
    # 4. Generate weekly matrix
    matrix_filename = f"Weekly CivCas Matrix-{start_date.strftime('%d-%d')} {start_date.strftime('%B %Y')}.xlsx"
    matrix_path = output_dir / matrix_filename
    
    try:
        # Get next incident code (could be improved by reading existing matrices)
        start_incident_code = 1
        
        matrix_generator.generate_matrix(
            incidents=all_incidents,
            start_date=start_date,
            end_date=end_date,
            output_path=str(matrix_path),
            start_incident_code=start_incident_code
        )
        
        log_structured("info", f"Generated weekly matrix: {matrix_path}")
    except Exception as e:
        log_structured("error", f"Failed to generate matrix", error=str(e))
        return {"error": str(e)}
    
    return {
        "success": True,
        "compiled_reports": compiled_reports,
        "matrix_path": str(matrix_path),
        "incidents_count": len(all_incidents),
        "dailies_processed": len(daily_files)
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process HRD Weekly Reports: Dailies → Compiled Reports → Matrix"
    )
    parser.add_argument(
        "--week-folder",
        type=str,
        required=True,
        help="Week folder name (e.g., '03-09') or path to week folder"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: same as week folder)"
    )
    parser.add_argument(
        "--weekly-dir",
        type=str,
        default="resources/Weekly",
        help="Base directory containing week folders"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    weekly_base = Path(args.weekly_dir)
    if not weekly_base.exists():
        print(f"Error: Weekly directory not found: {weekly_base}")
        return 1
    
    # Check if week_folder is a path or name
    week_folder_path = Path(args.week_folder)
    if not week_folder_path.is_absolute():
        week_folder_path = weekly_base / args.week_folder
    
    if not week_folder_path.exists():
        print(f"Error: Week folder not found: {week_folder_path}")
        return 1
    
    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = week_folder_path
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process
    print(f"Processing week folder: {week_folder_path}")
    print(f"Output directory: {output_dir}")
    print("-" * 80)
    
    results = process_weekly_folder(week_folder_path, output_dir)
    
    if "error" in results:
        print(f"Error: {results['error']}")
        return 1
    
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Compiled Reports: {len(results.get('compiled_reports', []))}")
    print(f"Matrix: {results.get('matrix_path')}")
    print(f"Incidents Extracted: {results.get('incidents_count', 0)}")
    print(f"Dailies Processed: {results.get('dailies_processed', 0)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

