"""HRD Report Processor - Upload dailies and generate compiled reports and matrices."""
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import tempfile
import shutil

# Add project root to path
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.hrd_incident_extractor import HRDIncidentExtractor, HRDIncident
from app.core.hrd_report_compiler import HRDReportCompiler
from app.core.hrd_matrix_generator import HRDMatrixGenerator
from app.core.ollama_location_extractor import OllamaLocationExtractor
from app.core.azure_ai import AzureAIParser
from app.core.geocoder import Geocoder
from app.core.duckdb_store import DuckDBStore
from app.utils.logging import log_structured


def extract_field_office_from_filename(filename: str) -> str:
    """Extract field office name from filename."""
    filename_lower = filename.lower()
    
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


def parse_date_from_filename(filename: str) -> datetime:
    """Try to extract date from filename."""
    # Common patterns: 2025-11-06, 20251106, 06/11/2025
    import re
    
    patterns = [
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),  # 2025-11-06
        (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),  # 20251106
        (r"(\d{2})/(\d{2})/(\d{4})", "%d/%m/%Y"),  # 06/11/2025
        (r"(\d{2})-(\d{2})-(\d{4})", "%d-%m-%Y"),  # 06-11-2025
    ]
    
    for pattern, fmt in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                date_str = match.group(0)
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
    
    # Default to today
    return datetime.now()


def initialize_components():
    """Initialize HRD processing components."""
    if "hrd_extractor" not in st.session_state:
        try:
            db_store = DuckDBStore()
            geocoder = Geocoder(db_store)
        except Exception:
            geocoder = None
        
        ollama_extractor = OllamaLocationExtractor()
        azure_parser = AzureAIParser()
        
        st.session_state.hrd_extractor = HRDIncidentExtractor(
            ollama_extractor=ollama_extractor,
            azure_parser=azure_parser,
            geocoder=geocoder
        )
        st.session_state.hrd_compiler = HRDReportCompiler(st.session_state.hrd_extractor)
        st.session_state.hrd_matrix_gen = HRDMatrixGenerator()


def main():
    """Main HRD Report Processor page."""
    st.set_page_config(
        page_title="HRD Report Processor",
        page_icon="📋",
        layout="wide"
    )
    
    st.title("📋 HRD Report Processor")
    st.markdown("Upload field office dailies and generate compiled reports (DSRs) and weekly matrices")
    
    # Initialize components
    initialize_components()
    
    # Configuration on main page
    st.header("⚙️ Configuration")
    config_col1, config_col2, config_col3, config_col4 = st.columns(4)
    
    with config_col1:
        report_date = st.date_input(
            "Report Date",
            value=datetime.now().date(),
            help="Date for the compiled report"
        )
    
    with config_col2:
        week_start = st.date_input(
            "Week Start (Matrix)",
            value=datetime.now().date() - timedelta(days=datetime.now().weekday()),
            help="Start date for weekly matrix"
        )
    
    with config_col3:
        week_end = st.date_input(
            "Week End (Matrix)",
            value=week_start + timedelta(days=6),
            help="End date for weekly matrix"
        )
    
    with config_col4:
        start_incident_code = st.number_input(
            "Starting Incident Code",
            min_value=1,
            value=1,
            help="Starting number for incident codes in matrix"
        )
    
    output_dir = st.text_input(
        "Output Directory",
        value="resources/Weekly/processed",
        help="Directory to save generated reports and matrices"
    )
    
    st.divider()
    
    # Main content area
    tab1, tab2 = st.tabs(["📁 Folder Processing", "📤 Manual Upload"])
    
    with tab1:
        st.header("Process Dailies from Folder")
        
        dailies_folder = st.text_input(
            "Dailies Folder Path",
            value="resources/Weekly/03-09/Dailies",
            help="Path to folder containing field office daily reports"
        )
        
        if st.button("🔍 Scan Folder", type="primary"):
            folder_path = Path(dailies_folder)
            if not folder_path.exists():
                st.error(f"Folder not found: {dailies_folder}")
            else:
                daily_files = list(folder_path.glob("*.docx"))
                if not daily_files:
                    st.warning(f"No .docx files found in {dailies_folder}")
                else:
                    st.success(f"Found {len(daily_files)} daily report(s)")
                    
                    # Store in session state
                    st.session_state.daily_files = [
                        {
                            "file_path": str(f),
                            "field_office": extract_field_office_from_filename(f.name),
                            "date": parse_date_from_filename(f.name),
                            "filename": f.name
                        }
                        for f in daily_files
                    ]
                    
                    # Display found files
                    st.subheader("Found Daily Reports")
                    df_files = st.session_state.daily_files
                    for i, file_info in enumerate(df_files, 1):
                        st.write(f"{i}. **{file_info['filename']}**")
                        st.write(f"   - Field Office: {file_info['field_office']}")
                        st.write(f"   - Date: {file_info['date'].strftime('%Y-%m-%d')}")
                    
                    # Show action buttons
                    st.divider()
                    st.header("🚀 Generate Reports")
                    st.success(f"✓ Ready to process {len(df_files)} daily report(s)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("📄 Generate Compiled Report (DSR)", type="primary", use_container_width=True, key="gen_dsr_folder"):
                            with st.spinner("Generating compiled reports..."):
                                generate_compiled_report(df_files, report_date, output_dir)
                    
                    with col2:
                        if st.button("📊 Generate Weekly Matrix", type="primary", use_container_width=True, key="gen_matrix_folder"):
                            with st.spinner("Generating weekly matrix..."):
                                generate_weekly_matrix(df_files, week_start, week_end, start_incident_code, output_dir)
                    
                    # Show results if available
                    if "generated_reports" in st.session_state:
                        st.divider()
                        st.subheader("📄 Generated Compiled Reports")
                        for report_path in st.session_state.generated_reports:
                            st.success(f"✓ {Path(report_path).name}")
                            with open(report_path, "rb") as f:
                                st.download_button(
                                    label=f"Download {Path(report_path).name}",
                                    data=f.read(),
                                    file_name=Path(report_path).name,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_report_{Path(report_path).name}"
                                )
                    
                    if "generated_matrix" in st.session_state:
                        st.divider()
                        st.subheader("📊 Generated Weekly Matrix")
                        matrix_path = st.session_state.generated_matrix
                        st.success(f"✓ {Path(matrix_path).name}")
                        with open(matrix_path, "rb") as f:
                            st.download_button(
                                label=f"Download {Path(matrix_path).name}",
                                data=f.read(),
                                file_name=Path(matrix_path).name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="download_matrix_folder"
                            )
                        
                        # Show matrix preview
                        try:
                            import pandas as pd
                            df = pd.read_excel(matrix_path)
                            st.dataframe(df.head(10), use_container_width=True)
                            st.caption(f"Total rows: {len(df)}")
                        except Exception as e:
                            st.warning(f"Could not preview matrix: {e}")
    
    with tab2:
        st.header("Upload Daily Reports Manually")
        
        uploaded_files = st.file_uploader(
            "Upload Field Office Daily Reports",
            type=["docx"],
            accept_multiple_files=True,
            help="Upload one or more .docx files containing field office daily reports"
        )
        
        if uploaded_files:
            st.success(f"Uploaded {len(uploaded_files)} file(s)")
            
            # Save uploaded files temporarily
            if st.button("📥 Process Uploaded Files"):
                temp_dir = Path(tempfile.mkdtemp())
                processed_files = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Processing {uploaded_file.name}...")
                    
                    # Save to temp directory
                    temp_path = temp_dir / uploaded_file.name
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    processed_files.append({
                        "file_path": str(temp_path),
                        "field_office": extract_field_office_from_filename(uploaded_file.name),
                        "date": parse_date_from_filename(uploaded_file.name),
                        "filename": uploaded_file.name
                    })
                    
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                # Store in session state
                st.session_state.daily_files = processed_files
                st.session_state.temp_dir = temp_dir
                
                status_text.text("✓ Files processed and ready!")
                st.success(f"Processed {len(processed_files)} file(s)")
                
                # Display processed files
                st.subheader("Processed Daily Reports")
                for i, file_info in enumerate(processed_files, 1):
                    st.write(f"{i}. **{file_info['filename']}**")
                    st.write(f"   - Field Office: {file_info['field_office']}")
                    st.write(f"   - Date: {file_info['date'].strftime('%Y-%m-%d')}")
                
                # Show action buttons
                st.divider()
                st.header("🚀 Generate Reports")
                st.success(f"✓ Ready to process {len(processed_files)} daily report(s)")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📄 Generate Compiled Report (DSR)", type="primary", use_container_width=True, key="gen_dsr_upload"):
                        with st.spinner("Generating compiled reports..."):
                            generate_compiled_report(processed_files, report_date, output_dir)
                
                with col2:
                    if st.button("📊 Generate Weekly Matrix", type="primary", use_container_width=True, key="gen_matrix_upload"):
                        with st.spinner("Generating weekly matrix..."):
                            generate_weekly_matrix(processed_files, week_start, week_end, start_incident_code, output_dir)
                
                # Show results if available
                if "generated_reports" in st.session_state:
                    st.divider()
                    st.subheader("📄 Generated Compiled Reports")
                    for report_path in st.session_state.generated_reports:
                        st.success(f"✓ {Path(report_path).name}")
                        with open(report_path, "rb") as f:
                            st.download_button(
                                label=f"Download {Path(report_path).name}",
                                data=f.read(),
                                file_name=Path(report_path).name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"download_report_upload_{Path(report_path).name}"
                            )
                
                if "generated_matrix" in st.session_state:
                    st.divider()
                    st.subheader("📊 Generated Weekly Matrix")
                    matrix_path = st.session_state.generated_matrix
                    st.success(f"✓ {Path(matrix_path).name}")
                    with open(matrix_path, "rb") as f:
                        st.download_button(
                            label=f"Download {Path(matrix_path).name}",
                            data=f.read(),
                            file_name=Path(matrix_path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_matrix_upload"
                        )
                    
                    # Show matrix preview
                    try:
                        import pandas as pd
                        df = pd.read_excel(matrix_path)
                        st.dataframe(df.head(10), use_container_width=True)
                        st.caption(f"Total rows: {len(df)}")
                    except Exception as e:
                        st.warning(f"Could not preview matrix: {e}")
    
            # Show action buttons after files are selected
            st.divider()
            st.header("🚀 Generate Reports")
            
            if "daily_files" not in st.session_state or not st.session_state.daily_files:
                st.info("👆 Please upload or select daily reports first")
            else:
                daily_files = st.session_state.daily_files
                st.success(f"✓ Ready to process {len(daily_files)} daily report(s)")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📄 Generate Compiled Report (DSR)", type="primary", use_container_width=True):
                        generate_compiled_report(daily_files, report_date, output_dir)
                
                with col2:
                    if st.button("📊 Generate Weekly Matrix", type="primary", use_container_width=True):
                        generate_weekly_matrix(daily_files, week_start, week_end, start_incident_code, output_dir)
                
                # Show results if available
                if "generated_reports" in st.session_state:
                    st.divider()
                    st.subheader("📄 Generated Compiled Reports")
                    for report_path in st.session_state.generated_reports:
                        st.success(f"✓ {Path(report_path).name}")
                        with open(report_path, "rb") as f:
                            st.download_button(
                                label=f"Download {Path(report_path).name}",
                                data=f.read(),
                                file_name=Path(report_path).name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"download_report_{Path(report_path).name}"
                            )
                
                if "generated_matrix" in st.session_state:
                    st.divider()
                    st.subheader("📊 Generated Weekly Matrix")
                    matrix_path = st.session_state.generated_matrix
                    st.success(f"✓ {Path(matrix_path).name}")
                    with open(matrix_path, "rb") as f:
                        st.download_button(
                            label=f"Download {Path(matrix_path).name}",
                            data=f.read(),
                            file_name=Path(matrix_path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_matrix"
                        )
                    
                    # Show matrix preview
                    try:
                        import pandas as pd
                        df = pd.read_excel(matrix_path)
                        st.dataframe(df.head(10), use_container_width=True)
                        st.caption(f"Total rows: {len(df)}")
                    except Exception as e:
                        st.warning(f"Could not preview matrix: {e}")


def generate_compiled_report(daily_files: List[Dict[str, Any]], report_date: datetime.date, output_dir: str):
    """Generate compiled HRD Daily Report."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Use placeholder for status
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    
    try:
        status_placeholder.info("🔄 Extracting incidents from daily reports...")
        progress_placeholder.progress(0.1)
        
        # Group dailies by date
        dailies_by_date = {}
        for file_info in daily_files:
            date = file_info["date"].date()
            if date not in dailies_by_date:
                dailies_by_date[date] = []
            dailies_by_date[date].append(file_info)
        
        status_placeholder.info(f"🔄 Generating compiled reports for {len(dailies_by_date)} date(s)...")
        progress_placeholder.progress(0.3)
        
        generated_reports = []
        compiler = st.session_state.hrd_compiler
        
        for i, (date, dailies) in enumerate(sorted(dailies_by_date.items())):
            status_placeholder.info(f"🔄 Processing {date}... ({i+1}/{len(dailies_by_date)})")
            progress_placeholder.progress(0.3 + (i + 1) / len(dailies_by_date) * 0.6)
            
            report_filename = f"HRD Daily Report_{date.strftime('%d %B %Y')}.docx"
            report_path = output_path / report_filename
            
            try:
                compiler.compile_daily_report(
                    date=datetime.combine(date, datetime.min.time()),
                    field_office_dailies=dailies,
                    output_path=str(report_path)
                )
                generated_reports.append(str(report_path))
                log_structured("info", f"Generated compiled report: {report_path}")
            except Exception as e:
                error_msg = f"Error generating report for {date}: {str(e)}"
                status_placeholder.error(error_msg)
                log_structured("error", f"Failed to generate report", error=str(e), date=str(date))
                import traceback
                st.exception(e)
        
        # Store results in session state
        st.session_state.generated_reports = generated_reports
        progress_placeholder.progress(1.0)
        
        if generated_reports:
            status_placeholder.success(f"✅ Generated {len(generated_reports)} compiled report(s)!")
        else:
            status_placeholder.warning("⚠️ No reports were generated. Check errors above.")
        
        # Force rerun to show results
        st.rerun()
        
    except Exception as e:
        error_msg = f"Error generating compiled reports: {str(e)}"
        status_placeholder.error(error_msg)
        progress_placeholder.empty()
        log_structured("error", f"Failed to generate compiled reports", error=str(e))
        import traceback
        st.exception(e)


def generate_weekly_matrix(daily_files: List[Dict[str, Any]], week_start: datetime.date, 
                          week_end: datetime.date, start_incident_code: int, output_dir: str):
    """Generate weekly matrix."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    
    try:
        status_placeholder.info("🔄 Extracting incidents from daily reports...")
        progress_placeholder.progress(0.1)
        
        all_incidents = []
        extractor = st.session_state.hrd_extractor
        
        for i, file_info in enumerate(daily_files):
            status_placeholder.info(f"🔄 Processing {file_info['filename']}... ({i+1}/{len(daily_files)})")
            progress_placeholder.progress(0.1 + (i + 1) / len(daily_files) * 0.5)
            
            try:
                from docx import Document
                doc = Document(file_info["file_path"])
                text = "\n".join([para.text for para in doc.paragraphs])
                
                incidents = extractor.extract_incidents_from_text(text, file_info["field_office"])
                all_incidents.extend(incidents)
                
                log_structured("info", f"Extracted {len(incidents)} incidents from {file_info['filename']}")
            except Exception as e:
                error_msg = f"Error processing {file_info['filename']}: {str(e)}"
                status_placeholder.warning(error_msg)
                log_structured("error", f"Failed to extract incidents", error=str(e), file=file_info['filename'])
        
        status_placeholder.info(f"🔄 Generating matrix with {len(all_incidents)} incidents...")
        progress_placeholder.progress(0.6)
        
        # Generate matrix
        matrix_filename = f"Weekly CivCas Matrix-{week_start.strftime('%d-%d')} {week_start.strftime('%B %Y')}.xlsx"
        matrix_path = output_path / matrix_filename
        
        matrix_gen = st.session_state.hrd_matrix_gen
        matrix_gen.generate_matrix(
            incidents=all_incidents,
            start_date=datetime.combine(week_start, datetime.min.time()),
            end_date=datetime.combine(week_end, datetime.min.time()),
            output_path=str(matrix_path),
            start_incident_code=start_incident_code
        )
        
        # Store result in session state
        st.session_state.generated_matrix = str(matrix_path)
        progress_placeholder.progress(1.0)
        status_placeholder.success(f"✅ Generated matrix with {len(all_incidents)} incidents!")
        
        # Force rerun to show results
        st.rerun()
        
    except Exception as e:
        error_msg = f"Error generating matrix: {str(e)}"
        status_placeholder.error(error_msg)
        progress_placeholder.empty()
        log_structured("error", f"Failed to generate matrix", error=str(e))
        import traceback
        st.exception(e)


if __name__ == "__main__":
    main()

