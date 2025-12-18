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
            # Log error but return empty structure
            print(f"Azure AI extraction error: {e}")
            return {
                "country": "South Sudan",
                "state_candidates": [],
                "county_candidates": [],
                "payam_candidates": [],
                "boma_candidates": [],
                "village_candidates": [],
            }

