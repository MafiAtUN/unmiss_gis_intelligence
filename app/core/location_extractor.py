"""Location extraction from unstructured documents using regex and AI."""
import re
import hashlib
from typing import List, Optional, Dict, Any, Tuple
from app.core.models import ExtractedLocation, ExtractionResult, GeocodeResult
from app.core.geocoder import Geocoder
from app.core.azure_ai import AzureAIParser
from app.core.ollama_helper import OllamaHelper
from app.core.config import FUZZY_THRESHOLD
from app.utils.logging import log_error


class RegexExtractor:
    """Extract location strings from text using regex patterns."""
    
    def __init__(self):
        """Initialize with regex patterns for South Sudan location formats."""
        # Pattern 1: "X Town, Y County, Z State" or "X, Y County, Z State"
        self.patterns = [
            # Hierarchical: Town, County, State
            re.compile(
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Town|town))?)\s*,\s*'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+County|county)?)\s*,\s*'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+State|state|Administrative\s+Area|administrative\s+area)?)',
                re.IGNORECASE
            ),
            # Pattern 2: "X in Y Town, Y County" or "X area, Y Town"
            re.compile(
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:in|area),\s*'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+Town|town)?)',
                re.IGNORECASE
            ),
            # Pattern 3: "X (State)" - parenthetical state
            re.compile(
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+County|county)?)\s*\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\)',
                re.IGNORECASE
            ),
            # Pattern 4: "X Town, Y County" without state
            re.compile(
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+Town|town)?)\s*,\s*'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+County|county)?)',
                re.IGNORECASE
            ),
            # Pattern 5: Simple "X Town" or "X County" or "X State"
            re.compile(
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Town|town|County|county|State|state|Payam|payam|Boma|boma|Administrative\s+Area|administrative\s+area)',
                re.IGNORECASE
            ),
        ]
    
    def _extract_context(self, text: str, start_pos: int, end_pos: int, context_chars: int = 200) -> str:
        """Extract surrounding context for a location mention."""
        context_start = max(0, start_pos - context_chars)
        context_end = min(len(text), end_pos + context_chars)
        return text[context_start:context_end].strip()
    
    def _find_sentence_boundary(self, text: str, pos: int, direction: str = "backward") -> int:
        """Find sentence boundary (period, exclamation, question mark)."""
        if direction == "backward":
            # Look backwards for sentence end
            for i in range(pos - 1, max(0, pos - 500), -1):
                if text[i] in '.!?':
                    return i + 1
            return max(0, pos - 200)
        else:
            # Look forwards for sentence end
            for i in range(pos, min(len(text), pos + 500)):
                if text[i] in '.!?':
                    return i + 1
            return min(len(text), pos + 200)
    
    def extract(self, text: str) -> List[ExtractedLocation]:
        """
        Extract location mentions from text using regex patterns.
        
        Args:
            text: Document text to extract locations from
            
        Returns:
            List of ExtractedLocation objects
        """
        locations = []
        seen_positions = set()  # Track positions to avoid duplicates
        
        for pattern in self.patterns:
            for match in pattern.finditer(text):
                start_pos = match.start()
                end_pos = match.end()
                matched_text = match.group(0).strip()
                
                # Skip if we've already seen this position (overlapping matches)
                if any(abs(start_pos - s) < 10 for s in seen_positions):
                    continue
                
                seen_positions.add(start_pos)
                
                # Extract sentence context
                sentence_start = self._find_sentence_boundary(text, start_pos, "backward")
                sentence_end = self._find_sentence_boundary(text, end_pos, "forward")
                context = text[sentence_start:sentence_end].strip()
                
                # Clean up the matched text (remove extra whitespace)
                matched_text = re.sub(r'\s+', ' ', matched_text)
                
                locations.append(ExtractedLocation(
                    original_text=matched_text,
                    context=context,
                    extraction_method="regex",
                    start_pos=start_pos,
                    end_pos=end_pos
                ))
        
        # Remove duplicates based on text similarity and position
        unique_locations = []
        for loc in locations:
            is_duplicate = False
            for existing in unique_locations:
                # Check if texts are similar and positions overlap
                if (loc.original_text.lower() == existing.original_text.lower() and
                    abs(loc.start_pos - existing.start_pos) < 50):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_locations.append(loc)
        
        return unique_locations


class DocumentLocationExtractor:
    """Main orchestrator for extracting and geocoding locations from documents.
    
    Implements cascading extraction: Regex → Ollama → Azure AI
    """
    
    def __init__(
        self, 
        geocoder: Geocoder, 
        azure_parser: Optional[AzureAIParser] = None,
        ollama_helper: Optional[OllamaHelper] = None,
        confidence_threshold: float = None
    ):
        """
        Initialize the document location extractor.
        
        Args:
            geocoder: Geocoder instance for geocoding extracted locations
            azure_parser: Optional AzureAIParser for AI-based extraction
            ollama_helper: Optional OllamaHelper for local LLM extraction
            confidence_threshold: Minimum geocoding score to consider success (default: FUZZY_THRESHOLD)
        """
        self.geocoder = geocoder
        self.regex_extractor = RegexExtractor()
        self.azure_parser = azure_parser or AzureAIParser()
        self.ollama_helper = ollama_helper or OllamaHelper()
        self.confidence_threshold = confidence_threshold or FUZZY_THRESHOLD
    
    def extract_locations(self, document_text: str, geocode: bool = True) -> ExtractionResult:
        """
        Extract locations from document using cascading method: Regex → Ollama → Azure AI.
        
        Flow:
        1. Extract with regex and geocode
        2. Identify gaps (low confidence or missing regions)
        3. Try Ollama for gaps
        4. If still gaps, try Azure AI (last resort)
        5. Background learning happens asynchronously
        
        Args:
            document_text: Full document text
            geocode: Whether to geocode extracted locations
            
        Returns:
            ExtractionResult with locations from all methods
        """
        # Step 1: Extract using regex (always first)
        regex_locations = self.regex_extractor.extract(document_text)
        
        # Geocode regex results
        if geocode:
            for loc in regex_locations:
                try:
                    loc.geocode_result = self.geocoder.geocode(loc.original_text, use_cache=True)
                except Exception as e:
                    log_error(e, {
                        "module": "location_extractor",
                        "function": "extract",
                        "location_text": loc.original_text,
                        "extraction_method": "regex"
                    })
        
        # Step 2: Identify gaps (regions where regex failed or had low confidence)
        gap_regions = self._identify_gaps(document_text, regex_locations)
        
        # Step 3: Try Ollama extraction for gaps (if enabled)
        ollama_locations = []
        if self.ollama_helper.enabled and gap_regions:
            try:
                ollama_locations = self.ollama_helper.extract_location_strings(
                    document_text, 
                    context_regions=gap_regions
                )
                
                # Geocode Ollama results
                if geocode:
                    for loc in ollama_locations:
                        try:
                            loc.geocode_result = self.geocoder.geocode(loc.original_text, use_cache=True)
                        except Exception as e:
                            log_error(e, {
                                "module": "location_extractor",
                                "function": "extract",
                                "location_text": loc.original_text,
                                "extraction_method": "ollama"
                            })
            except Exception as e:
                # Ollama errors (timeout, not running, etc.) are expected
                # Only log if it's not a timeout/connection error
                import requests
                if not isinstance(e, (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                    log_error(e, {
                        "module": "location_extractor",
                        "function": "extract",
                        "extraction_method": "ollama",
                        "document_length": len(document_text)
                    })
                ollama_locations = []
        
        # Step 4: Check for remaining gaps after Ollama
        remaining_gaps = self._identify_gaps(document_text, regex_locations + ollama_locations)
        
        # Step 5: Try Azure AI as last resort (if enabled and still gaps)
        azure_locations = []
        if self.azure_parser.enabled and remaining_gaps:
            try:
                # Extract from remaining gap regions only
                azure_locations = self.azure_parser.extract_location_strings(document_text)
                
                # Filter to only locations in gap regions (avoid duplicates)
                filtered_azure = []
                for loc in azure_locations:
                    # Check if this location overlaps with any gap region
                    in_gap = any(
                        gap["start_pos"] <= loc.start_pos <= gap["end_pos"] or
                        gap["start_pos"] <= loc.end_pos <= gap["end_pos"]
                        for gap in remaining_gaps
                    )
                    # Also check if it's not already found by regex or ollama
                    is_duplicate = any(
                        abs(loc.start_pos - existing.start_pos) < 20
                        for existing in regex_locations + ollama_locations
                    )
                    if in_gap and not is_duplicate:
                        filtered_azure.append(loc)
                
                azure_locations = filtered_azure
                
                # Geocode Azure results
                if geocode:
                    for loc in azure_locations:
                        try:
                            if not loc.geocode_result:
                                loc.geocode_result = self.geocoder.geocode(loc.original_text, use_cache=True)
                        except Exception as e:
                            log_error(e, {
                                "module": "location_extractor",
                                "function": "extract",
                                "location_text": loc.original_text,
                                "extraction_method": "azure"
                            })
            except Exception as e:
                log_error(e, {
                    "module": "location_extractor",
                    "function": "extract",
                    "extraction_method": "azure",
                    "document_length": len(document_text)
                })
                azure_locations = []
        
        # Step 6: Trigger background learning (non-blocking)
        # This will analyze patterns asynchronously
        self._trigger_learning(regex_locations, ollama_locations, azure_locations)
        
        return ExtractionResult(
            regex_locations=regex_locations,
            ai_locations=azure_locations,  # Keep Azure in ai_locations for compatibility
            ollama_locations=ollama_locations,
            document_text=document_text
        )
    
    def _identify_gaps(
        self, 
        document_text: str, 
        found_locations: List[ExtractedLocation],
        sentence_window: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Identify regions in the document where locations might have been missed.
        
        Args:
            document_text: Full document text
            found_locations: List of already found locations
            sentence_window: Window size around found locations to exclude
            
        Returns:
            List of gap regions (dicts with start_pos, end_pos, context)
        """
        if not found_locations:
            # No locations found, entire document is a gap
            return [{
                "start_pos": 0,
                "end_pos": len(document_text),
                "context": document_text[:1000] if len(document_text) > 1000 else document_text
            }]
        
        # Sort locations by position
        sorted_locations = sorted(found_locations, key=lambda x: x.start_pos)
        
        gaps = []
        
        # Check if regex locations have low confidence geocoding
        low_confidence_regions = []
        for loc in found_locations:
            if loc.geocode_result:
                # Check if geocoding succeeded but with low confidence
                if (loc.geocode_result.score < self.confidence_threshold or 
                    not loc.geocode_result.lon or 
                    loc.geocode_result.resolution_too_coarse):
                    # Mark region around this location for re-extraction
                    low_confidence_regions.append({
                        "start_pos": max(0, loc.start_pos - sentence_window),
                        "end_pos": min(len(document_text), loc.end_pos + sentence_window),
                        "context": loc.context
                    })
        
        # Find gaps between found locations
        prev_end = 0
        for loc in sorted_locations:
            gap_start = prev_end
            gap_end = loc.start_pos
            
            # Only consider gaps larger than a sentence
            if gap_end - gap_start > 100:
                gaps.append({
                    "start_pos": gap_start,
                    "end_pos": gap_end,
                    "context": document_text[max(0, gap_start - 200):min(len(document_text), gap_end + 200)]
                })
            
            prev_end = max(prev_end, loc.end_pos)
        
        # Check end of document
        if prev_end < len(document_text) - 100:
            gaps.append({
                "start_pos": prev_end,
                "end_pos": len(document_text),
                "context": document_text[max(0, prev_end - 200):]
            })
        
        # Combine with low confidence regions
        all_gaps = gaps + low_confidence_regions
        
        # Merge overlapping gaps
        if not all_gaps:
            return []
        
        merged_gaps = []
        sorted_gaps = sorted(all_gaps, key=lambda x: x["start_pos"])
        current_gap = sorted_gaps[0].copy()
        
        for gap in sorted_gaps[1:]:
            if gap["start_pos"] <= current_gap["end_pos"]:
                # Overlapping, merge
                current_gap["end_pos"] = max(current_gap["end_pos"], gap["end_pos"])
                current_gap["context"] = document_text[
                    max(0, current_gap["start_pos"] - 200):
                    min(len(document_text), current_gap["end_pos"] + 200)
                ]
            else:
                merged_gaps.append(current_gap)
                current_gap = gap.copy()
        merged_gaps.append(current_gap)
        
        return merged_gaps
    
    def _trigger_learning(
        self,
        regex_locations: List[ExtractedLocation],
        ollama_locations: List[ExtractedLocation],
        azure_locations: List[ExtractedLocation]
    ):
        """
        Trigger background learning process (non-blocking).
        
        This collects data for pattern improvement but doesn't block the main flow.
        
        Args:
            regex_locations: Locations found by regex
            ollama_locations: Locations found by Ollama
            azure_locations: Locations found by Azure AI
        """
        # This is a placeholder for background learning
        # In a production system, this would:
        # 1. Store extraction statistics
        # 2. Queue learning tasks
        # 3. Process feedback asynchronously
        # 4. Update regex patterns periodically
        
        # For now, we'll just track successes and failures
        # The actual learning can be triggered separately via a learning endpoint/function
        pass
    
    def get_document_hash(self, document_text: str) -> str:
        """Generate hash for document to track feedback."""
        return hashlib.md5(document_text.encode('utf-8')).hexdigest()

