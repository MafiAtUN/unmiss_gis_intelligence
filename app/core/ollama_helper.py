"""Ollama integration for local LLM-based pattern learning."""
import json
from typing import Optional, List, Dict, Any
import requests
from app.core.config import OLLAMA_BASE_URL, OLLAMA_MODEL, ENABLE_OLLAMA
from app.core.models import ExtractedLocation
from app.utils.logging import log_error


class OllamaHelper:
    """Helper class for using Ollama (local LLM) for pattern learning."""
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Ollama helper.
        
        Args:
            base_url: Base URL for Ollama API (defaults to OLLAMA_BASE_URL from config)
            model: Model name to use (defaults to OLLAMA_MODEL from config)
        """
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model or OLLAMA_MODEL
        self.enabled = ENABLE_OLLAMA and self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def generate_regex_pattern(
        self,
        examples: List[str],
        corrections: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a regex pattern based on examples and corrections.
        
        Args:
            examples: List of example location strings that should be matched
            corrections: Optional list of corrected location strings
            description: Optional description of what the pattern should match
            
        Returns:
            Generated regex pattern string, or None if Ollama is not available
        """
        if not self.enabled:
            return None
        
        prompt = f"""You are a regex pattern expert. Generate a Python regex pattern that matches location strings in South Sudan administrative format.

Examples that should match:
{json.dumps(examples, indent=2)}
"""
        
        if corrections:
            prompt += f"""
Corrected examples (what users actually wanted):
{json.dumps(corrections, indent=2)}
"""
        
        if description:
            prompt += f"\nDescription: {description}\n"
        
        prompt += """
Generate a single Python regex pattern (as a raw string, e.g., r"...") that matches these location strings.
Return ONLY the regex pattern, nothing else."""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                pattern = result.get("response", "").strip()
                # Clean up the pattern (remove markdown code blocks if present)
                pattern = pattern.replace("```python", "").replace("```", "").strip()
                if pattern.startswith("r'"):
                    pattern = pattern[2:-1] if pattern.endswith("'") else pattern[2:]
                elif pattern.startswith('r"'):
                    pattern = pattern[2:-1] if pattern.endswith('"') else pattern[2:]
                return pattern
        except Exception as e:
            log_error(e, {
                "module": "ollama_helper",
                "function": "generate_pattern_from_examples",
                "examples_count": len(examples)
            })
        
        return None
    
    def analyze_feedback_patterns(
        self,
        feedback_data: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze feedback data to identify common patterns and suggest improvements.
        
        Args:
            feedback_data: List of feedback dictionaries with extracted_text, user_corrected_text, etc.
            
        Returns:
            Dictionary with analysis results and suggestions, or None if Ollama is not available
        """
        if not self.enabled or not feedback_data:
            return None
        
        # Prepare examples
        incorrect_extractions = [
            f["extracted_text"] for f in feedback_data 
            if f.get("is_correct") is False and f.get("extracted_text")
        ]
        corrections = [
            f["user_corrected_text"] for f in feedback_data
            if f.get("user_corrected_text")
        ]
        
        if not incorrect_extractions:
            return None
        
        prompt = f"""Analyze these incorrect location extractions and their corrections to identify patterns.

Incorrect extractions:
{json.dumps(incorrect_extractions[:10], indent=2)}

Corrections provided:
{json.dumps(corrections[:10], indent=2)}

Provide analysis in JSON format with:
1. common_mistakes: list of common error patterns
2. suggestions: list of suggestions for improving extraction
3. pattern_improvements: specific regex pattern improvements

Return ONLY valid JSON, no other text."""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis_text = result.get("response", "").strip()
                # Try to parse JSON (may need cleanup)
                try:
                    return json.loads(analysis_text)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    if "```json" in analysis_text:
                        json_start = analysis_text.find("```json") + 7
                        json_end = analysis_text.find("```", json_start)
                        analysis_text = analysis_text[json_start:json_end].strip()
                        return json.loads(analysis_text)
        except Exception as e:
            log_error(e, {
                "module": "ollama_helper",
                "function": "analyze_feedback_patterns",
                "feedback_count": len(feedback_data)
            })
        
        return None
    
    def extract_location_strings(self, document_text: str, context_regions: Optional[List[Dict[str, Any]]] = None) -> List[ExtractedLocation]:
        """
        Extract full location strings from a document with context and positions.
        
        This method extracts complete location mentions (similar to Azure AI's extract_location_strings)
        but can focus on specific regions where regex failed.
        
        Args:
            document_text: Full document text to extract locations from
            context_regions: Optional list of regions where regex failed (dicts with start_pos, end_pos, context)
            
        Returns:
            List of ExtractedLocation objects with context and positions
        """
        if not self.enabled:
            return []
        
        # If context_regions provided, extract from those regions only
        if context_regions:
            all_locations = []
            for region in context_regions:
                region_start = region.get("start_pos", 0)
                region_end = region.get("end_pos", len(document_text))
                region_text = document_text[region_start:region_end]
                region_context = region.get("context", region_text[:500])
                
                locations = self._extract_from_text(region_text, region_start, region_context)
                all_locations.extend(locations)
            return all_locations
        else:
            # Extract from full document
            return self._extract_from_text(document_text, 0, document_text[:500])
    
    def _extract_from_text(self, text: str, text_offset: int = 0, context_prefix: str = "") -> List[ExtractedLocation]:
        """Extract locations from a text segment."""
        system_prompt = """You are a location extraction assistant for South Sudan. Extract all location mentions from the text. For each location, return:
1. The exact location string as it appears in the text
2. The character position where it starts (0-based index relative to the provided text)
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
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{system_prompt}\n\nExtract all location mentions from this text:\n\n{text}",
                    "stream": False,
                    "format": "json"
                },
                timeout=30
            )
            
            # Check for timeout or connection errors
            if response.status_code != 200:
                # Non-200 status - return empty list gracefully
                return []
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("response", "").strip()
                
                # Try to parse JSON
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    if "```json" in content:
                        json_start = content.find("```json") + 7
                        json_end = content.find("```", json_start)
                        content = content[json_start:json_end].strip()
                        parsed = json.loads(content)
                    else:
                        return []
                
                locations = []
                if "locations" in parsed and isinstance(parsed["locations"], list):
                    for loc_data in parsed["locations"]:
                        if "text" in loc_data and "start_pos" in loc_data and "end_pos" in loc_data:
                            rel_start = int(loc_data["start_pos"])
                            rel_end = int(loc_data["end_pos"])
                            start_pos = rel_start + text_offset
                            end_pos = rel_end + text_offset
                            text_str = loc_data["text"]
                            
                            # Extract context (200 chars before and after) from the text segment
                            context_start = max(0, rel_start - 200)
                            context_end = min(len(text), rel_end + 200)
                            context = (context_prefix[:200] + " ... " if context_prefix else "") + text[context_start:context_end].strip()
                            
                            locations.append(ExtractedLocation(
                                original_text=text_str,
                                context=context,
                                extraction_method="ollama",
                                start_pos=start_pos,
                                end_pos=end_pos
                            ))
                
                return locations
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Ollama timeout or connection error - this is expected if Ollama is not running
            # Don't log as error, just return empty list
            return []
        except Exception as e:
            log_error(e, {
                "module": "ollama_helper",
                "function": "_extract_from_text",
                "text_length": len(text) if text else 0,
                "text_offset": text_offset
            })
        
        return []

