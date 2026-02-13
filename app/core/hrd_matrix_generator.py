"""Generate Weekly CivCas Matrix from compiled reports or incidents."""
import pandas as pd
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from app.core.hrd_incident_extractor import HRDIncident
from app.utils.logging import log_error


class HRDMatrixGenerator:
    """Generate Weekly CivCas Matrix Excel files."""
    
    def __init__(self):
        """Initialize matrix generator."""
        self.column_order = [
            "Incident Code",
            "Date of Interview",
            "Month of interview/report",
            "Date of Incident",
            "Reporting Field Office",
            "Incident State",
            "Location of Incident",
            "Source Information",
            "Types of violations",
            "Generalized Violations",
            "Alleged Perpetrator(s)",
            "Involved in Hostilities",
            "Origin of Alleged Perpetrators",
            "Ethnicity/Tribe of victim/survivor",
            "Total Victims",
            "Male (#)",
            "Female (#)",
            "Minor (M)",
            "Minor (F)",
            "Source of the information",
            "Description",
            "Update",
            "Remarks by CMC/CRVT",
            "Corroborated/Verified",
            "Payam",
            "County",
        ]
    
    def generate_matrix(self, 
                       incidents: List[HRDIncident],
                       start_date: datetime,
                       end_date: datetime,
                       output_path: str,
                       start_incident_code: int = 1) -> str:
        """
        Generate weekly matrix from incidents.
        
        Args:
            incidents: List of HRDIncident objects
            start_date: Week start date
            end_date: Week end date
            output_path: Path to save Excel file
            start_incident_code: Starting incident code
            
        Returns:
            Path to generated matrix
        """
        # Convert incidents to DataFrame
        rows = []
        incident_code = start_incident_code
        
        for incident in incidents:
            row = incident.to_dict()
            
            # Add matrix-specific fields
            row["Incident Code"] = float(incident_code)
            row["Month of interview/report"] = start_date.strftime("%B")
            row["Source of the information"] = row.get("Source Information")
            row["Update"] = None
            row["Remarks by CMC/CRVT"] = None
            
            # Ensure all columns are present
            for col in self.column_order:
                if col not in row:
                    row[col] = None
            
            rows.append(row)
            incident_code += 1
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        
        # Reorder columns
        existing_columns = [col for col in self.column_order if col in df.columns]
        df = df[existing_columns]
        
        # Save to Excel
        df.to_excel(output_path, index=False, engine='openpyxl')
        
        return output_path
    
    def generate_from_compiled_reports(self,
                                      compiled_reports: List[str],
                                      start_date: datetime,
                                      end_date: datetime,
                                      output_path: str,
                                      start_incident_code: int = 1) -> str:
        """
        Generate matrix from compiled HRD Daily Reports.
        
        Args:
            compiled_reports: List of paths to compiled report DOCX files
            start_date: Week start date
            end_date: Week end date
            output_path: Path to save Excel file
            start_incident_code: Starting incident code
            
        Returns:
            Path to generated matrix
        """
        from app.core.hrd_incident_extractor import HRDIncidentExtractor
        from docx import Document
        
        extractor = HRDIncidentExtractor()
        all_incidents = []
        
        # Extract incidents from compiled reports
        for report_path in compiled_reports:
            try:
                doc = Document(report_path)
                text = "\n".join([para.text for para in doc.paragraphs])
                
                # Extract incidents
                incidents = extractor.extract_incidents_from_text(text)
                all_incidents.extend(incidents)
            except Exception as e:
                log_error(e, {
                    "module": "hrd_matrix_generator",
                    "report_path": report_path
                })
        
        # Generate matrix
        return self.generate_matrix(
            all_incidents,
            start_date,
            end_date,
            output_path,
            start_incident_code
        )

