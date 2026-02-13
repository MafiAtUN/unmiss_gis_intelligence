#!/usr/bin/env python3
"""
Final improved location extractor with enhanced validation and post-processing.

This version:
1. Better context word removal
2. Validates extracted locations
3. Handles edge cases better
4. Stops extraction at sentence boundaries when appropriate
"""

import re
from typing import Optional, List, Tuple
from app.core.normalization import normalize_text


# Words that should NOT appear in location names (context words)
CONTEXT_WORDS = {
    'old', 'male', 'female', 'civilian', 'from', 'the', 'community', 
    'during', 'an', 'attempted', 'raid', 'in', 'at', 'for', 'medical',
    'examination', 'treatment', 'and', 'who', 'subsequently', 'informed',
    'authorities', 'reportedly', 'according', 'sources', 'shot', 'killed',
    'injured', 'abducted', 'attacked', 'fled', 'escaped', 'pursued'
}

# Administrative level keywords that should appear in locations
ADMIN_KEYWORDS = ['boma', 'payam', 'county', 'state', 'town', 'village', 
                  'city', 'administrative', 'area', 'settlement']


def is_valid_location_start(text: str) -> bool:
    """Check if text starts with a valid location name."""
    if not text or len(text) < 2:
        return False
    
    # Must start with capital letter
    if not text[0].isupper():
        return False
    
    # First word should not be a context word
    first_word = text.split()[0].lower().rstrip(',')
    if first_word in CONTEXT_WORDS:
        return False
    
    return True


def extract_primary_location_v2(description: str, state: Optional[str] = None) -> Optional[str]:
    """
    Enhanced location extraction with better validation.
    
    Args:
        description: Description text
        state: State name for context
        
    Returns:
        Extracted location string or None
    """
    if not description:
        return None
    
    # Strategy 1: Look for patterns with "in" followed by location
    # Pattern: "in [Location Name], [Payam], [County]"
    patterns = [
        # Full hierarchy: "in X Boma, Y Payam, Z County"
        (r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Boma|boma))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Payam|payam))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county|Administrative\s+Area|administrative\s+area))?)', 5),
        # Village/Town with Payam and County
        (r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:village|Village|town|Town))?)\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Payam|payam))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county))?)', 4),
        # Payam and County
        (r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Payam|payam))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county))?)', 3),
        # Town/City with County
        (r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Town|town|City|city)))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county))?)', 3),
        # Simple: "in [Location], [County]"
        (r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county))?)', 2),
    ]
    
    best_match = None
    best_specificity = 0
    best_position = len(description)
    
    for pattern, specificity in patterns:
        matches = re.finditer(pattern, description, re.IGNORECASE)
        for match in matches:
            groups = match.groups()
            first_group = groups[0].strip()
            
            # Validate: must start with valid location name
            if not is_valid_location_start(first_group):
                continue
            
            # Additional validation: first group should not contain context words
            first_words = set(first_group.lower().split())
            if first_words.intersection(CONTEXT_WORDS):
                continue
            
            # Construct location string
            if len(groups) == 3:
                location = f"{groups[0]}, {groups[1]}, {groups[2]}"
            elif len(groups) == 2:
                location = f"{groups[0]}, {groups[1]}"
            else:
                continue
            
            # Stop at sentence boundaries or common separators
            # Find where the location mention ends
            end_pos = match.end()
            # Look for common separators that indicate end of location
            next_chars = description[end_pos:end_pos+50]
            # Stop if we hit: period, semicolon, or common context words
            stop_pattern = r'[.;]|(?:for|and|who|according|reportedly|the|sources)'
            stop_match = re.search(stop_pattern, next_chars, re.IGNORECASE)
            if stop_match:
                # Check if there's text after location but before stop
                text_between = next_chars[:stop_match.start()].strip()
                # If there's substantial text, it might be part of the location
                # But if it's just a few words, it's probably context
                if text_between and len(text_between.split()) > 3:
                    # Too much text, likely captured context
                    continue
                # Truncate location if needed
                if text_between:
                    # Remove any trailing context
                    location = location.rstrip(' ,')
            
            # Prefer earlier matches and more specific ones
            if specificity > best_specificity or (specificity == best_specificity and match.start() < best_position):
                best_specificity = specificity
                best_position = match.start()
                best_match = location
    
    if best_match:
        return clean_location_string_v2(best_match)
    
    return None


def clean_location_string_v2(location: str) -> str:
    """
    Enhanced cleaning with better context removal.
    """
    if not location:
        return ""
    
    location = location.strip()
    
    # Remove leading prepositions
    location = re.sub(r'^(in|at)\s+', '', location, flags=re.IGNORECASE).strip()
    
    # Split by comma to process each part
    parts = [p.strip() for p in location.split(',')]
    cleaned_parts = []
    
    for part in parts:
        part = part.strip()
        
        # Skip if empty
        if not part:
            continue
        
        # Remove trailing context words
        words = part.split()
        # Remove trailing context words
        while words and words[-1].lower() in CONTEXT_WORDS:
            words.pop()
        
        if not words:
            continue
        
        part = ' '.join(words)
        
        # Remove trailing punctuation
        part = part.rstrip('.,;')
        
        # Validate: part should contain at least one location-like word
        # (either starts with capital or contains admin keyword)
        part_lower = part.lower()
        has_admin_keyword = any(kw in part_lower for kw in ADMIN_KEYWORDS)
        starts_with_capital = part and part[0].isupper()
        
        if has_admin_keyword or starts_with_capital:
            cleaned_parts.append(part)
    
    if not cleaned_parts:
        return ""
    
    result = ", ".join(cleaned_parts)
    
    # Final validation: result should not be too long (likely captured context)
    if len(result) > 150:
        # Too long, likely has context - try to truncate at last admin keyword
        # Find last occurrence of admin keyword
        for keyword in reversed(ADMIN_KEYWORDS):
            if keyword in result.lower():
                idx = result.lower().rfind(keyword)
                # Take everything up to and including the admin keyword and a bit after
                # Find the next comma or end
                next_comma = result.find(',', idx)
                if next_comma > 0:
                    result = result[:next_comma + len(result.split(',')[-1])].strip()
                break
    
    return result


def extract_and_standardize_v2(description: str, state: Optional[str] = None) -> Optional[str]:
    """
    Final extraction function with all improvements.
    """
    extracted = extract_primary_location_v2(description, state)
    if extracted:
        # Additional post-processing
        extracted = clean_location_string_v2(extracted)
        
        # Final validation: must have reasonable length and structure
        if len(extracted) < 3 or len(extracted) > 200:
            return None
        
        # Should contain at least one word that looks like a place name
        words = extracted.split()
        has_place_name = any(len(w) >= 3 and w[0].isupper() for w in words)
        if not has_place_name:
            return None
        
        return extracted
    
    return None

