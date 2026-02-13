"""Optimized Ollama-based location extraction for casualty matrix descriptions."""
import json
from typing import Optional, List
import requests
from app.core.config import OLLAMA_BASE_URL, OLLAMA_MODEL, ENABLE_OLLAMA
from app.core.models import ExtractedLocation
from app.utils.logging import log_error


class OllamaLocationExtractor:
    """Optimized Ollama extractor specifically for primary incident location extraction."""
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Ollama location extractor.
        
        Args:
            base_url: Base URL for Ollama API
            model: Model name (defaults to llama3.2:3b for efficiency)
        """
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        # Default to efficient model if not specified
        self.model = model or OLLAMA_MODEL or "llama3.2:3b"
        self.enabled = ENABLE_OLLAMA and self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def extract_primary_location(self, description: str, state: Optional[str] = None) -> Optional[str]:
        """
        Extract the PRIMARY incident location from description using Ollama.
        
        This is optimized for efficiency:
        - Uses a focused prompt
        - Returns only the location string
        - Fast response time
        
        Args:
            description: Description text
            state: State name for context
            
        Returns:
            Extracted location string or None
        """
        if not self.enabled or not description:
            return None
        
        # Truncate description if too long (for efficiency)
        # Keep first 800 chars which usually contains the incident location
        description_short = description[:800] if len(description) > 800 else description
        
        # Optimized prompt for fast, accurate extraction
        prompt = f"""Extract the PRIMARY incident location from this description. Focus on WHERE the incident occurred.

State context: {state or 'Unknown'}

Description: {description_short}

Return ONLY the location string in format: "Location Name, Payam Name, County Name" or "Location Name, County Name"
If location includes Boma, include it: "Boma Name, Payam Name, County Name"

Extract the most specific location where the incident happened. Return only the location, nothing else."""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent results
                        "num_predict": 100,  # Limit response length for speed
                    }
                },
                timeout=15  # Short timeout for efficiency
            )
            
            if response.status_code == 200:
                result = response.json()
                location = result.get("response", "").strip()
                
                # Clean up the response
                location = location.replace('"', '').replace("'", "").strip()
                
                # Remove common prefixes
                prefixes = ["location:", "the location is", "location is", "extracted location:"]
                for prefix in prefixes:
                    if location.lower().startswith(prefix):
                        location = location[len(prefix):].strip()
                
                # Remove trailing punctuation and context
                location = location.rstrip('.,;')
                
                # Validate: should be reasonable length and contain location-like words
                if location and 3 <= len(location) <= 200:
                    # Check if it contains location indicators
                    location_lower = location.lower()
                    has_location_indicators = any(
                        word in location_lower for word in 
                        ['boma', 'payam', 'county', 'town', 'village', 'city', 'state']
                    ) or any(word[0].isupper() for word in location.split()[:3])
                    
                    if has_location_indicators:
                        return location
            
            return None
            
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Timeout/connection errors are expected - return None gracefully
            return None
        except Exception as e:
            log_error(e, {
                "module": "ollama_location_extractor",
                "function": "extract_primary_location",
                "description_length": len(description)
            })
            return None
    
    def extract_location_strings(self, document_text: str, context_regions: Optional[List[dict]] = None) -> List[ExtractedLocation]:
        """
        Extract location strings from document (compatible with DocumentLocationExtractor).
        
        Args:
            document_text: Full document text
            context_regions: Optional regions to focus on
            
        Returns:
            List of ExtractedLocation objects
        """
        if not self.enabled:
            return []
        
        # Extract primary location
        primary_location = self.extract_primary_location(document_text)
        
        if primary_location:
            # Find position in text
            location_lower = primary_location.lower()
            text_lower = document_text.lower()
            
            # Try to find the location in the text
            start_pos = text_lower.find(location_lower)
            if start_pos == -1:
                # Try finding parts of the location
                first_part = primary_location.split(',')[0].strip().lower()
                start_pos = text_lower.find(first_part)
            
            if start_pos != -1:
                end_pos = start_pos + len(primary_location)
                context_start = max(0, start_pos - 200)
                context_end = min(len(document_text), end_pos + 200)
                context = document_text[context_start:context_end].strip()
                
                return [ExtractedLocation(
                    original_text=primary_location,
                    context=context,
                    extraction_method="ollama",
                    start_pos=start_pos,
                    end_pos=end_pos
                )]
        
        return []

