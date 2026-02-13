"""PII detection and redaction utilities for QC support notes."""

import re
from typing import List, Dict, Tuple, Optional


# Common UN acronyms that should not be flagged as names
UN_ACRONYMS = {
    "UN", "UNMISS", "UNHCR", "UNICEF", "UNDP", "WFP", "WHO", "FAO",
    "UNESCO", "UNFPA", "IOM", "OHCHR", "OSCE", "UNESCO", "OCHA",
    "DDR", "IDP", "IDPs", "NGO", "NGOs", "GONGO", "SPLA", "SPLM",
    "IGAD", "AU", "EU", "US", "USA", "UK", "UKAID", "DFID"
}


def detect_full_names(text: str) -> List[Dict[str, str]]:
    """Detect potential full names (two capitalized words in sequence).
    
    Args:
        text: The text to scan for names.
        
    Returns:
        List of dicts with 'type': 'name', 'original': matched text, 'masked': redacted version.
    """
    # Pattern: two capitalized words in sequence, not at start of sentence
    # Exclude common titles and words that start sentences
    pattern = r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b'
    
    redactions = []
    seen = set()
    
    for match in re.finditer(pattern, text):
        full_match = match.group(0)
        first_word = match.group(1)
        second_word = match.group(2)
        
        # Skip if it's a UN acronym or common title/word
        if (first_word.upper() in UN_ACRONYMS or 
            second_word.upper() in UN_ACRONYMS or
            first_word.lower() in ['the', 'this', 'that', 'these', 'those']):
            continue
        
        # Skip common location prefixes that might look like names
        if first_word.lower() in ['north', 'south', 'east', 'west', 'new', 'old', 'upper', 'lower']:
            continue
        
        # Create a key to avoid duplicates
        key = (match.start(), match.end())
        if key in seen:
            continue
        seen.add(key)
        
        redactions.append({
            "type": "name",
            "original": full_match,
            "masked": f"[NAME] {second_word[0]}.",
            "start": match.start(),
            "end": match.end()
        })
    
    return redactions


def detect_phone_numbers(text: str) -> List[Dict[str, str]]:
    """Detect phone numbers in various formats.
    
    Args:
        text: The text to scan for phone numbers.
        
    Returns:
        List of dicts with 'type': 'phone', 'original': matched text, 'masked': redacted version.
    """
    # Common patterns: +249-xxx-xxx-xxxx, (249) xxx-xxxx, 249xxxxxxxx, etc.
    patterns = [
        r'\+?\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        r'\d{10,15}',  # Long numeric sequences
    ]
    
    redactions = []
    seen = set()
    
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            matched_text = match.group(0)
            # Filter out dates and years (4-digit years, dates)
            if re.match(r'^(19|20)\d{2}$', matched_text) or len(matched_text) < 8:
                continue
            
            key = (match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            
            redactions.append({
                "type": "phone",
                "original": matched_text,
                "masked": "[PHONE]",
                "start": match.start(),
                "end": match.end()
            })
    
    return redactions


def detect_addresses(text: str) -> List[Dict[str, str]]:
    """Detect exact addresses or house numbers.
    
    Args:
        text: The text to scan for addresses.
        
    Returns:
        List of dicts with 'type': 'address', 'original': matched text, 'masked': redacted version.
    """
    # Pattern: house numbers, street numbers, P.O. boxes
    patterns = [
        r'\b\d+\s+[A-Z][a-z]+(?:\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Place|Pl))',
        r'\bP\.?O\.?\s+Box\s+\d+',
        r'\bHouse\s+No\.?\s+\d+',
        r'\bBlock\s+\d+',
    ]
    
    redactions = []
    seen = set()
    
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matched_text = match.group(0)
            key = (match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            
            redactions.append({
                "type": "address",
                "original": matched_text,
                "masked": "[ADDRESS]",
                "start": match.start(),
                "end": match.end()
            })
    
    return redactions


def detect_ids(text: str) -> List[Dict[str, str]]:
    """Detect ID numbers (passport, national ID, etc.).
    
    Args:
        text: The text to scan for IDs.
        
    Returns:
        List of dicts with 'type': 'id', 'original': matched text, 'masked': redacted version.
    """
    # Pattern: ID numbers, passport numbers (usually alphanumeric, 6-20 chars)
    # Look for phrases like "ID:", "Passport:", followed by alphanumeric
    pattern = r'\b(?:ID|Passport|National\s+ID|Driver\'?s?\s+License)[:;]\s*([A-Z0-9]{6,20})\b'
    
    redactions = []
    seen = set()
    
    for match in re.finditer(pattern, text, re.IGNORECASE):
        matched_text = match.group(0)
        key = (match.start(), match.end())
        if key in seen:
            continue
        seen.add(key)
        
        # Extract the ID type (before the colon)
        id_type_match = match.group(0).split(':')[0] if ':' in match.group(0) else match.group(0).split(';')[0]
        redactions.append({
            "type": "id",
            "original": matched_text,
            "masked": f"{id_type_match} [ID]",
            "start": match.start(),
            "end": match.end()
        })
    
    return redactions


def detect_pii(text: str, enable_confidentiality_scan: bool = True) -> List[Dict[str, str]]:
    """Detect all PII in text.
    
    Args:
        text: The text to scan for PII.
        enable_confidentiality_scan: Whether to perform PII detection.
        
    Returns:
        List of redaction dicts with type, original, masked, start, end.
    """
    if not enable_confidentiality_scan:
        return []
    
    all_redactions = []
    all_redactions.extend(detect_full_names(text))
    all_redactions.extend(detect_phone_numbers(text))
    all_redactions.extend(detect_addresses(text))
    all_redactions.extend(detect_ids(text))
    
    # Sort by start position
    all_redactions.sort(key=lambda x: x["start"])
    
    # Remove overlaps (keep first match)
    filtered_redactions = []
    for redaction in all_redactions:
        overlap = False
        for existing in filtered_redactions:
            if not (redaction["end"] <= existing["start"] or redaction["start"] >= existing["end"]):
                overlap = True
                break
        if not overlap:
            filtered_redactions.append(redaction)
    
    return filtered_redactions


def apply_redactions(text: str, redactions: List[Dict[str, str]]) -> str:
    """Apply redactions to text, replacing originals with masked versions.
    
    Args:
        text: The original text.
        redactions: List of redaction dicts sorted by start position.
        
    Returns:
        Text with redactions applied.
    """
    if not redactions:
        return text
    
    # Apply redactions from end to start to preserve indices
    redacted_text = text
    for redaction in reversed(redactions):
        start = redaction["start"]
        end = redaction["end"]
        redacted_text = redacted_text[:start] + redaction["masked"] + redacted_text[end:]
    
    return redacted_text

