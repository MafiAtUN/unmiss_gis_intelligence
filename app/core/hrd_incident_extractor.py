"""HRD Incident Extraction from Field Office Daily Reports using LLM."""
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from app.core.ollama_location_extractor import OllamaLocationExtractor
from app.core.azure_ai import AzureAIParser
from app.core.geocoder import Geocoder
from app.core.duckdb_store import DuckDBStore
from app.utils.logging import log_error


class HRDIncident:
    """Represents a human rights incident extracted from reports."""
    
    def __init__(self):
        self.date_of_incident: Optional[datetime] = None
        self.date_of_interview: Optional[datetime] = None
        self.reporting_field_office: Optional[str] = None
        self.incident_state: Optional[str] = None
        self.location_of_incident: Optional[str] = None
        self.source_information: Optional[str] = None
        self.types_of_violations: Optional[str] = None
        self.generalized_violations: Optional[str] = None
        self.alleged_perpetrators: Optional[str] = None
        self.involved_in_hostilities: Optional[str] = None
        self.origin_of_perpetrators: Optional[str] = None
        self.ethnicity_tribe_victim: Optional[str] = None
        self.total_victims: Optional[int] = None
        self.male_count: Optional[int] = None
        self.female_count: Optional[int] = None
        self.minor_male: Optional[int] = None
        self.minor_female: Optional[int] = None
        self.description: Optional[str] = None
        self.corroborated_verified: Optional[str] = None
        self.payam: Optional[str] = None
        self.county: Optional[str] = None
        self.lat: Optional[float] = None
        self.lon: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Excel export."""
        return {
            "Date of Interview": self.date_of_interview,
            "Date of Incident": self.date_of_incident,
            "Reporting Field Office": self.reporting_field_office,
            "Incident State": self.incident_state,
            "Location of Incident": self.location_of_incident,
            "Source Information": self.source_information,
            "Types of violations": self.types_of_violations,
            "Generalized Violations": self.generalized_violations,
            "Alleged Perpetrator(s)": self.alleged_perpetrators,
            "Involved in Hostilities": self.involved_in_hostilities,
            "Origin of Alleged Perpetrators": self.origin_of_perpetrators,
            "Ethnicity/Tribe of victim/survivor": self.ethnicity_tribe_victim,
            "Total Victims": self.total_victims,
            "Male (#)": self.male_count,
            "Female (#)": self.female_count,
            "Minor (M)": self.minor_male,
            "Minor (F)": self.minor_female,
            "Description": self.description,
            "Corroborated/Verified": self.corroborated_verified,
            "Payam": self.payam,
            "County": self.county,
            "Lat": self.lat,
            "long": self.lon,
        }


class HRDIncidentExtractor:
    """Extract structured HRD incidents from field office daily reports using LLM."""
    
    def __init__(self, ollama_extractor: Optional[OllamaLocationExtractor] = None, 
                 azure_parser: Optional[AzureAIParser] = None,
                 geocoder: Optional[Geocoder] = None):
        """
        Initialize incident extractor.
        
        Args:
            ollama_extractor: Ollama location extractor
            azure_parser: Azure AI parser
            geocoder: Geocoder for location resolution
        """
        self.ollama_extractor = ollama_extractor or OllamaLocationExtractor()
        self.azure_parser = azure_parser or AzureAIParser()
        self.geocoder = geocoder
        if not geocoder:
            try:
                db_store = DuckDBStore()
                self.geocoder = Geocoder(db_store)
            except Exception:
                self.geocoder = None
    
    def extract_incidents_from_text(self, text: str, field_office: Optional[str] = None) -> List[HRDIncident]:
        """
        Extract structured incidents from report text using LLM.
        
        Args:
            text: Report text
            field_office: Field office name (if known)
            
        Returns:
            List of HRDIncident objects
        """
        if not text or len(text.strip()) < 50:
            return []
        
        # Use LLM to extract structured incidents
        incidents = []
        
        # Try Ollama first (fast, local)
        if self.ollama_extractor.enabled:
            try:
                incidents = self._extract_with_ollama(text, field_office)
                if incidents:
                    return incidents
            except Exception as e:
                log_error(e, {"module": "hrd_incident_extractor", "method": "ollama"})
        
        # Fallback to Azure AI
        if self.azure_parser.enabled:
            try:
                incidents = self._extract_with_azure(text, field_office)
                if incidents:
                    return incidents
            except Exception as e:
                log_error(e, {"module": "hrd_incident_extractor", "method": "azure"})
        
        return incidents
    
    def _extract_with_ollama(self, text: str, field_office: Optional[str]) -> List[HRDIncident]:
        """Extract incidents using Ollama."""
        # Truncate text for efficiency
        text_truncated = text[:2000] if len(text) > 2000 else text
        
        prompt = f"""Extract human rights incidents from this UNMISS HRD report.

Field Office: {field_office or 'Unknown'}

Text: {text_truncated}

Extract incidents as JSON array. Each incident should have:
- date_of_incident (YYYY-MM-DD format or null)
- date_of_interview (YYYY-MM-DD format or null)  
- reporting_field_office (field office name)
- incident_state (state name)
- location_of_incident (full location string)
- source_information (e.g., "Three secondary sources")
- types_of_violations (e.g., "Killed", "Injured")
- generalized_violations (generalized category)
- alleged_perpetrators (perpetrator description)
- total_victims (number or null)
- male_count (number or null)
- female_count (number or null)
- minor_male (number or null)
- minor_female (number or null)
- description (full incident description)
- corroborated_verified ("Yes", "No", or "Unknown")

Return JSON array only, no other text."""

        try:
            base_url = self.ollama_extractor.base_url or "http://localhost:11434"
            response = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": self.ollama_extractor.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1500,  # Reduced for speed
                    }
                },
                timeout=20  # Reduced timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("response", "").strip()
                
                # Parse JSON
                try:
                    # Clean up response
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    # Try to find JSON array
                    if content.startswith("["):
                        incidents_data = json.loads(content)
                    elif "[" in content:
                        # Extract JSON array from text
                        start = content.find("[")
                        end = content.rfind("]") + 1
                        incidents_data = json.loads(content[start:end])
                    else:
                        # Try parsing as single object
                        incidents_data = [json.loads(content)]
                    
                    if isinstance(incidents_data, list):
                        incidents = []
                        for inc in incidents_data:
                            try:
                                parsed = self._parse_incident_data(inc)
                                if parsed.description or parsed.location_of_incident:
                                    incidents.append(parsed)
                            except Exception as e:
                                log_error(e, {"module": "hrd_incident_extractor", "incident_data": str(inc)[:100]})
                        return incidents
                except json.JSONDecodeError as e:
                    log_error(e, {"module": "hrd_incident_extractor", "content_preview": content[:300]})
        
        except requests.exceptions.Timeout:
            # Timeout is expected - return empty list
            return []
        except Exception as e:
            log_error(e, {"module": "hrd_incident_extractor", "method": "ollama"})
        
        return []
    
    def _extract_with_azure(self, text: str, field_office: Optional[str]) -> List[HRDIncident]:
        """Extract incidents using Azure AI."""
        if not self.azure_parser.enabled:
            return []
        
        system_prompt = """You are a human rights documentation specialist. Extract structured incident data from UNMISS HRD field office reports.

Extract each incident and return as JSON array with complete structured data."""
        
        user_prompt = f"""Extract all human rights incidents from this report:

Field Office: {field_office or 'Unknown'}

{text[:3000]}

Return JSON array with incident data. Include all fields."""
        
        try:
            response = self.azure_parser.client.chat.completions.create(
                model=self.azure_parser.deployment or "gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Handle different response formats
            if "incidents" in result:
                incidents_data = result["incidents"]
            elif isinstance(result, list):
                incidents_data = result
            else:
                incidents_data = [result]
            
            return [self._parse_incident_data(inc) for inc in incidents_data]
        
        except Exception as e:
            log_error(e, {"module": "hrd_incident_extractor", "method": "azure"})
            return []
    
    def _parse_incident_data(self, data: Dict[str, Any]) -> HRDIncident:
        """Parse incident data dictionary into HRDIncident object."""
        incident = HRDIncident()
        
        # Parse dates
        if data.get("date_of_incident"):
            incident.date_of_incident = self._parse_date(data["date_of_incident"])
        if data.get("date_of_interview"):
            incident.date_of_interview = self._parse_date(data["date_of_interview"])
        
        # Basic fields
        incident.reporting_field_office = data.get("reporting_field_office")
        incident.incident_state = data.get("incident_state")
        incident.location_of_incident = data.get("location_of_incident")
        incident.source_information = data.get("source_information")
        
        # Handle violations (could be string or list)
        violations = data.get("types_of_violations")
        if isinstance(violations, list):
            incident.types_of_violations = ", ".join(violations) if violations else None
        else:
            incident.types_of_violations = violations
        
        generalized = data.get("generalized_violations")
        if isinstance(generalized, list):
            incident.generalized_violations = ", ".join(generalized) if generalized else incident.types_of_violations
        else:
            incident.generalized_violations = generalized or incident.types_of_violations
        incident.alleged_perpetrators = data.get("alleged_perpetrators")
        incident.involved_in_hostilities = data.get("involved_in_hostilities")
        incident.origin_of_perpetrators = data.get("origin_of_perpetrators")
        incident.ethnicity_tribe_victim = data.get("ethnicity_tribe_victim")
        incident.description = data.get("description")
        incident.corroborated_verified = data.get("corroborated_verified", "Unknown")
        
        # Victim counts
        incident.total_victims = self._parse_int(data.get("total_victims"))
        incident.male_count = self._parse_int(data.get("male_count"))
        incident.female_count = self._parse_int(data.get("female_count"))
        incident.minor_male = self._parse_int(data.get("minor_male"))
        incident.minor_female = self._parse_int(data.get("minor_female"))
        
        # Geocode location if available
        if incident.location_of_incident and self.geocoder:
            try:
                location_with_state = f"{incident.location_of_incident}, {incident.incident_state}" if incident.incident_state else incident.location_of_incident
                geocode_result = self.geocoder.geocode(location_with_state, use_cache=True)
                if geocode_result and geocode_result.lon:
                    incident.lat = geocode_result.lat
                    incident.lon = geocode_result.lon
                    incident.payam = geocode_result.payam
                    incident.county = geocode_result.county
            except Exception:
                pass
        
        return incident
    
    def _parse_date(self, date_str: Any) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        
        if isinstance(date_str, datetime):
            return date_str
        
        date_str = str(date_str).strip()
        
        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _parse_int(self, value: Any) -> Optional[int]:
        """Parse integer value."""
        if value is None:
            return None
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return None

