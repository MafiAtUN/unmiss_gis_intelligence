"""Azure AI Foundry integration for text parsing."""
import json
import os
from typing import Dict, List, Optional
from openai import AzureOpenAI
from app.core.config import (
    AZURE_FOUNDRY_ENDPOINT,
    AZURE_FOUNDRY_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    ENABLE_AI_EXTRACTION
)
from app.core.models import ExtractedLocation
from app.utils.logging import log_error, log_structured


class AzureAIParser:
    """Azure AI Foundry parser for extracting structured place names from text."""
    
    def __init__(self):
        """Initialize Azure OpenAI client."""
        self.enabled = ENABLE_AI_EXTRACTION and bool(AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY)
        
        if self.enabled:
            self.client = AzureOpenAI(
                api_key=AZURE_FOUNDRY_API_KEY,
                api_version="2024-02-15-preview",
                azure_endpoint=AZURE_FOUNDRY_ENDPOINT
            )
            self.deployment = AZURE_OPENAI_DEPLOYMENT or "gpt-4"
        else:
            self.client = None
            self.deployment = None
    
    def extract_candidates(self, text: str) -> Dict[str, List[str]]:
        """
        Extract structured place name candidates from free text.
        
        Args:
            text: Free text location string
            
        Returns:
            Dictionary with country, state_candidates, county_candidates, etc.
        """
        if not self.enabled:
            return {
                "country": "South Sudan",
                "state_candidates": [],
                "county_candidates": [],
                "payam_candidates": [],
                "boma_candidates": [],
                "village_candidates": [],
            }
        
        system_prompt = """You are a geocoding assistant for South Sudan. Extract place name candidates from free text location strings.
Return a JSON object with the following structure:
{
  "country": "South Sudan",
  "state_candidates": ["list of state names"],
  "county_candidates": ["list of county names"],
  "payam_candidates": ["list of payam names"],
  "boma_candidates": ["list of boma names"],
  "village_candidates": ["list of village/settlement names"]
}

Extract all plausible place names from the text. Return empty arrays if no candidates found for a level."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract place names from: {text}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Validate structure
            required_keys = [
                "country", "state_candidates", "county_candidates",
                "payam_candidates", "boma_candidates", "village_candidates"
            ]
            
            for key in required_keys:
                if key not in result:
                    result[key] = []
            
            return result
            
        except Exception as e:
            # Check if it's a content filter error (common with UNMISS reports)
            error_str = str(e)
            if "content_filter" in error_str or "ResponsibleAIPolicyViolation" in error_str:
                # Content was filtered - this is expected for some documents
                # Return empty structure gracefully without logging as error
                return {
                    "country": "South Sudan",
                    "state_candidates": [],
                    "county_candidates": [],
                    "payam_candidates": [],
                    "boma_candidates": [],
                    "village_candidates": [],
                }
            
            # Log other errors
            log_error(e, {
                "module": "azure_ai",
                "function": "extract_candidates",
                "text_length": len(text),
                "deployment": self.deployment
            })
            return {
                "country": "South Sudan",
                "state_candidates": [],
                "county_candidates": [],
                "payam_candidates": [],
                "boma_candidates": [],
                "village_candidates": [],
            }
    
    def extract_location_strings(self, document_text: str) -> List[ExtractedLocation]:
        """
        Extract full location strings from a document with context and positions.
        
        This method extracts complete location mentions (not just candidates)
        and returns them with their context and positions in the document.
        
        Args:
            document_text: Full document text to extract locations from
            
        Returns:
            List of ExtractedLocation objects with context and positions
        """
        if not self.enabled:
            return []
        
        system_prompt = """You are a location extraction assistant for South Sudan. 
Extract all location mentions from the document text. For each location, return:
1. The exact location string as it appears in the text
2. The character position where it starts (0-based index)
3. The character position where it ends

Return a JSON object with the following structure:
{
  "locations": [
    {
      "text": "exact location string as found",
      "start_pos": 123,
      "end_pos": 145
    }
  ]
}

Extract locations in formats like:
- "X Town, Y County, Z State"
- "X in Y Town"
- "X area, Y Town"
- "X (State)"
- Any administrative location names in South Sudan

Only extract actual location mentions, not general references. Return empty array if no locations found."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract all location mentions from this document:\n\n{document_text}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            locations = []
            if "locations" in result and isinstance(result["locations"], list):
                for loc_data in result["locations"]:
                    if "text" in loc_data and "start_pos" in loc_data and "end_pos" in loc_data:
                        start_pos = int(loc_data["start_pos"])
                        end_pos = int(loc_data["end_pos"])
                        text = loc_data["text"]
                        
                        # Extract context (200 chars before and after)
                        context_start = max(0, start_pos - 200)
                        context_end = min(len(document_text), end_pos + 200)
                        context = document_text[context_start:context_end].strip()
                        
                        locations.append(ExtractedLocation(
                            original_text=text,
                            context=context,
                            extraction_method="ai",
                            start_pos=start_pos,
                            end_pos=end_pos
                        ))
            
            return locations
            
        except Exception as e:
            # Check if it's a content filter error
            error_str = str(e)
            if "content_filter" in error_str or "ResponsibleAIPolicyViolation" in error_str:
                # Content was filtered - return empty gracefully
                return []
            
            # Log other errors
            log_error(e, {
                "module": "azure_ai",
                "function": "extract_location_strings",
                "document_length": len(document_text),
                "deployment": self.deployment
            })
            return []

