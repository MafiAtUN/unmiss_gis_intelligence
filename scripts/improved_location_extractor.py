#!/usr/bin/env python3
"""
Improved location extraction with better pattern matching and normalization.

This module provides enhanced location extraction that:
1. Handles spelling variations (Billinyang vs Billinang)
2. Normalizes administrative area names (Imehejek Administrative Area vs Lafon County)
3. Removes redundant words while preserving important context
4. Prioritizes the most specific location mentioned
"""

import re
from typing import Optional, List, Tuple
from app.core.normalization import normalize_text


# Common spelling variations in South Sudan locations
SPELLING_VARIATIONS = {
    "billinyang": "billinang",
    "billinang": "billinang",  # Canonical
    "lafon": "lafon",
    "imehejek": "imehejek",
    "jebel": "jebel",
    "padiet": "padiet",
    "pagak": "pagak",
}


def normalize_location_name(name: str) -> str:
    """Normalize location name handling spelling variations."""
    if not name:
        return ""
    
    normalized = normalize_text(name)
    
    # Apply spelling variations
    for variant, canonical in SPELLING_VARIATIONS.items():
        if variant in normalized:
            normalized = normalized.replace(variant, canonical)
    
    return normalized


def extract_primary_location(description: str, state: Optional[str] = None) -> Optional[str]:
    """
    Extract the primary incident location from description.
    
    This function uses multiple strategies to find the most specific location
    where the incident occurred, prioritizing locations with full hierarchy.
    
    Args:
        description: Description text
        state: State name for context
        
    Returns:
        Extracted location string or None
    """
    if not description:
        return None
    
    # Strategy 1: Look for full hierarchical patterns
    # Pattern: "in X Boma, Y Payam, Z County" or similar
    # IMPORTANT: Match must start with location name (capitalized), not context words
    hierarchical_patterns = [
        # Full hierarchy with "in" - most specific, location name must start with capital
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Boma|boma))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Payam|payam))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county|Administrative\s+Area|administrative\s+area))?)',
        # Village/Town with Payam and County - must start with capital
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:village|Village|town|Town))?)\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Payam|payam))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county))?)',
        # Payam and County - must start with capital
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Payam|payam))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county))?)',
        # Town/City with County - must start with capital
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Town|town|City|city)))\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|county))?)',
    ]
    
    best_match = None
    best_specificity = 0
    best_position = len(description)  # Prefer earlier matches
    
    for pattern in hierarchical_patterns:
        matches = re.finditer(pattern, description, re.IGNORECASE)
        for match in matches:
            groups = match.groups()
            
            # Validate: first group must start with capital letter (location name, not context)
            first_group = groups[0].strip()
            if not first_group or not first_group[0].isupper():
                continue
            
            # Additional validation: first group should not contain common context words
            context_words = ['old', 'male', 'female', 'civilian', 'from', 'the', 'community', 'during', 'an', 'attempted']
            first_words = first_group.lower().split()
            if any(word in first_words for word in context_words):
                continue
            
            if len(groups) == 3:
                # Full hierarchy: Boma, Payam, County
                location = f"{groups[0]}, {groups[1]}, {groups[2]}"
                specificity = 5
            elif len(groups) == 2:
                # Partial hierarchy: Payam, County or Town, County
                location = f"{groups[0]}, {groups[1]}"
                specificity = 3
            else:
                continue
            
            # Prefer matches that appear earlier in the description
            # (usually the primary incident location)
            # Also prefer more specific matches
            if specificity > best_specificity or (specificity == best_specificity and match.start() < best_position):
                best_specificity = specificity
                best_position = match.start()
                best_match = location
    
    if best_match:
        return clean_location_string(best_match)
    
    # Strategy 2: Look for simple patterns with word boundaries
    simple_patterns = [
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Boma|Payam|County|Town|town|village))(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Payam|County))?)?(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|Administrative\s+Area))?)?)',
        r'\bat\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Boma|Payam|County|Town|town|village))(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Payam|County))?)?(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:County|Administrative\s+Area))?)?)',
    ]
    
    for pattern in simple_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Additional validation: location should not be too long (likely captured too much)
            if len(location) < 150:  # Reasonable max length for a location string
                return clean_location_string(location)
    
    return None


def clean_location_string(location: str) -> str:
    """
    Clean and standardize location string.
    
    Removes:
    - Leading "in " or "at "
    - Trailing punctuation
    - Extra whitespace
    - Context words that got captured
    
    Preserves:
    - Administrative level keywords (Boma, Payam, County)
    - Location names
    """
    if not location:
        return ""
    
    location = location.strip()
    
    # Remove leading prepositions
    location = re.sub(r'^(in|at)\s+', '', location, flags=re.IGNORECASE).strip()
    
    # Remove common context words that might have been captured
    # These words should not appear at the start of a location name
    context_patterns = [
        r'^(old|male|female|civilian|from|the|community|during|an|attempted|raid|in|at)\s+',
        r'\s+(old|male|female|civilian|from|the|community|during|an|attempted|raid)$',
    ]
    
    for pattern in context_patterns:
        location = re.sub(pattern, '', location, flags=re.IGNORECASE).strip()
    
    # Find the first capitalized word (actual location name)
    # This helps remove any remaining context before the location
    match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', location)
    if match:
        start_pos = match.start()
        if start_pos > 0:
            # There's text before the first location name, remove it
            location = location[start_pos:]
    
    # Remove trailing punctuation
    location = location.rstrip('.,;')
    
    # Normalize whitespace
    location = re.sub(r'\s+', ' ', location)
    
    # Handle "Administrative Area" - sometimes it's part of the county name
    # Keep it as is for now, geocoder will handle it
    
    return location


def standardize_to_matrix_format(location: str) -> str:
    """
    Standardize location string to match matrix format.
    
    Matrix format typically:
    - "Boma Name, Payam Name, County Name" (preferred)
    - "Location Name, Payam Name, County Name"
    - "Location Name, County Name"
    - Removes "County" suffix if redundant
    - Removes "Town" suffix unless it's part of the name
    """
    if not location:
        return ""
    
    location = clean_location_string(location)
    
    # Split by comma to analyze parts
    parts = [p.strip() for p in location.split(',')]
    
    if len(parts) == 0:
        return ""
    
    # Process each part
    cleaned_parts = []
    for part in parts:
        part = part.strip()
        
        # Remove trailing "County" if it's redundant (we'll add it back if needed)
        # But keep "Administrative Area" as it's important
        if part.lower().endswith(" county") and "administrative area" not in part.lower():
            part = part[:-7].strip()
        
        # Keep "Town" if it's part of a compound name like "Jebel Boma Town"
        # But remove standalone "Town"
        if part.lower() == "town":
            continue
        
        cleaned_parts.append(part)
    
    # Reconstruct
    result = ", ".join(cleaned_parts)
    
    return result


def extract_and_standardize(description: str, state: Optional[str] = None) -> Optional[str]:
    """
    Extract location from description and standardize to matrix format.
    
    This is the main function to use for extraction.
    
    Args:
        description: Description text
        state: State name for context
        
    Returns:
        Standardized location string or None
    """
    extracted = extract_primary_location(description, state)
    if extracted:
        return standardize_to_matrix_format(extracted)
    return None

