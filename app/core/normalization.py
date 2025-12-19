"""Text normalization utilities for place name matching."""
import re
import unicodedata
from typing import List, Set, Dict, Optional


# South Sudan specific abbreviations and expansions
SOUTH_SUDAN_ABBREVIATIONS = {
    "c equatoria": "central equatoria",
    "w equatoria": "western equatoria",
    "e equatoria": "eastern equatoria",
    "n bahr el ghazal": "northern bahr el ghazal",
    "w bahr el ghazal": "western bahr el ghazal",
    "n bahr": "northern bahr el ghazal",
    "w bahr": "western bahr el ghazal",
    "c eq": "central equatoria",
    "w eq": "western equatoria",
    "e eq": "eastern equatoria",
}

# Common transliterations and variations
TRANSLITERATIONS = {
    "jubba": "juba",
    "malakel": "malakal",
    "bentui": "bentiu",
    "waw": "wau",
    "yambio": "yambio",  # Keep as is
    "torit": "torit",  # Keep as is
    # Handle common spelling variations
    "abiemnom": "abiemnhom",  # Common misspelling - normalize to database spelling
    "abiemnhom": "abiemnhom",  # Correct spelling in database
}

# Words to preserve (don't remove)
PRESERVE_WORDS = {"el", "al", "de", "la"}  # Important in "Bahr el Ghazal"


def normalize_text(text: str) -> str:
    """
    Normalize text for matching: lowercase, strip punctuation, collapse whitespace, unicode normalize.
    Enhanced for South Sudan with abbreviations and transliterations.
    
    Args:
        text: Input text string
        
    Returns:
        Normalized text string
    """
    if not text:
        return ""
    
    # Unicode normalization
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    
    # Lowercase
    text = text.lower()
    
    # Handle South Sudan abbreviations BEFORE removing punctuation
    for abbrev, expansion in SOUTH_SUDAN_ABBREVIATIONS.items():
        # Match whole word or at word boundary
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
    
    # Handle transliterations
    for variant, canonical in TRANSLITERATIONS.items():
        pattern = r'\b' + re.escape(variant) + r'\b'
        text = re.sub(pattern, canonical, text, flags=re.IGNORECASE)
    
    # Remove punctuation except spaces (but preserve important words)
    # First, protect preserve words
    protected = {}
    for i, word in enumerate(PRESERVE_WORDS):
        placeholder = f"__PRESERVE_{i}__"
        protected[placeholder] = word
        text = re.sub(r'\b' + re.escape(word) + r'\b', placeholder, text, flags=re.IGNORECASE)
    
    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Restore preserved words
    for placeholder, word in protected.items():
        text = text.replace(placeholder, word)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Strip
    text = text.strip()
    
    return text


def generate_ngrams(text: str, min_length: int = 2, max_length: int = 5) -> List[str]:
    """
    Generate n-grams from normalized text for candidate extraction.
    
    Args:
        text: Normalized text string
        min_length: Minimum n-gram length
        max_length: Maximum n-gram length
        
    Returns:
        List of n-gram strings
    """
    words = text.split()
    if not words:
        return []
    
    ngrams = []
    
    # Single words
    for word in words:
        if len(word) >= min_length:
            ngrams.append(word)
    
    # Multi-word n-grams
    for n in range(2, min(max_length + 1, len(words) + 1)):
        for i in range(len(words) - n + 1):
            ngram = " ".join(words[i:i + n])
            if len(ngram) >= min_length:
                ngrams.append(ngram)
    
    # Full text
    full_text = " ".join(words)
    if len(full_text) >= min_length and full_text not in ngrams:
        ngrams.append(full_text)
    
    return ngrams


def extract_candidates(text: str) -> Set[str]:
    """
    Extract candidate place name tokens from free text.
    
    Args:
        text: Input text string
        
    Returns:
        Set of candidate place name strings
    """
    normalized = normalize_text(text)
    ngrams = generate_ngrams(normalized)
    
    # Filter out very short candidates and common words
    stop_words = {"the", "of", "in", "at", "on", "to", "for", "and", "or", "a", "an"}
    candidates = {ng for ng in ngrams if len(ng) >= 3 and ng not in stop_words}
    
    return candidates


def parse_hierarchical_constraints(text: str) -> Dict[str, Optional[str]]:
    """
    Parse hierarchical administrative constraints from input text.
    
    Attempts to identify state, county, payam, boma, and village from the text
    by looking for keywords and patterns.
    
    Args:
        text: Input text string (e.g., "Abiemnom Town, Abiemnom County, Unity")
        
    Returns:
        Dictionary with keys: state, county, payam, boma, village
    """
    constraints = {
        "state": None,
        "county": None,
        "payam": None,
        "boma": None,
        "village": None,
    }
    
    if not text:
        return constraints
    
    # Normalize text for matching
    normalized = normalize_text(text)
    words = normalized.split()
    
    # Common keywords that indicate administrative levels
    state_keywords = ["state", "states"]
    county_keywords = ["county", "counties"]
    payam_keywords = ["payam", "payams"]
    boma_keywords = ["boma", "bomas"]
    village_keywords = ["town", "village", "villages", "settlement", "settlements", "city", "cities"]
    
    # Known South Sudan states (for better matching) - normalized versions
    # Based on South Sudan's 10 states + 3 administrative areas
    # States can be named with or without "State" suffix
    south_sudan_states = [
        # Original 10 states
        "unity", "unity state",
        "upper nile", "upper nile state",
        "jonglei", "jonglei state",
        "warrap", "warrap state",
        "northern bahr el ghazal", "northern bahr el ghazal state", "n bahr el ghazal",
        "western bahr el ghazal", "western bahr el ghazal state", "w bahr el ghazal",
        "lakes", "lakes state",
        "western equatoria", "western equatoria state", "w equatoria",
        "central equatoria", "central equatoria state", "c equatoria",
        "eastern equatoria", "eastern equatoria state", "e equatoria",
        # Administrative areas (created later)
        "ruweng", "ruweng state", "ruweng administrative area",
        "pibor", "pibor state", "pibor administrative area",
        "akobo", "akobo state", "akobo administrative area",
        "apex", "apex state", "apex administrative area",
        # Additional variations
        "gogrial", "gogrial state",
        "tonj", "tonj state"
    ]
    
    # Split by common delimiters (comma, semicolon, etc.)
    parts = re.split(r'[,;]', text)
    parts = [p.strip() for p in parts if p.strip()]
    
    # Process each part to identify its level
    for part in parts:
        part_normalized = normalize_text(part)
        part_words = part_normalized.split()
        
        # Check for state
        if any(keyword in part_normalized for keyword in state_keywords):
            # Extract state name (remove keyword)
            state_name = part_normalized
            for kw in state_keywords:
                state_name = state_name.replace(kw, "").strip()
            if state_name:
                constraints["state"] = state_name
        # Check if it's a known state name (check if any state name is contained in this part)
        elif any(state in part_normalized or part_normalized in state for state in south_sudan_states):
            for state in south_sudan_states:
                if state in part_normalized or part_normalized in state:
                    constraints["state"] = state.replace(" state", "").strip()
                    break
        
        # Check for county
        elif any(keyword in part_normalized for keyword in county_keywords):
            county_name = part_normalized
            for kw in county_keywords:
                county_name = county_name.replace(kw, "").strip()
            if county_name:
                constraints["county"] = county_name
        
        # Check for payam
        elif any(keyword in part_normalized for keyword in payam_keywords):
            payam_name = part_normalized
            for kw in payam_keywords:
                payam_name = payam_name.replace(kw, "").strip()
            if payam_name:
                constraints["payam"] = payam_name
        
        # Check for boma
        elif any(keyword in part_normalized for keyword in boma_keywords):
            boma_name = part_normalized
            for kw in boma_keywords:
                boma_name = boma_name.replace(kw, "").strip()
            if boma_name:
                constraints["boma"] = boma_name
        
        # Check for village/town (usually first part or has village keywords)
        elif any(keyword in part_normalized for keyword in village_keywords):
            village_name = part_normalized
            for kw in village_keywords:
                village_name = village_name.replace(kw, "").strip()
            if village_name:
                constraints["village"] = village_name
    
    # If no explicit keywords found, try to infer from position
    # Usually: village, county, state (or similar order)
    # Also check if any part matches known states
    if len(parts) >= 2:
        # Last part is often state - check if it matches a known state
        if not constraints["state"]:
            last_part = normalize_text(parts[-1])
            # Don't treat it as state if it contains "county", "payam", "boma", "town", "village"
            if not any(kw in last_part for kw in ["county", "payam", "boma", "town", "village"]):
                # Check if it's a known state (exact or partial match)
                for state in south_sudan_states:
                    state_normalized = normalize_text(state.replace(" state", "").strip())
                    if state_normalized == last_part or last_part in state_normalized or state_normalized in last_part:
                        constraints["state"] = state_normalized
                        break
                # If still no match and it's short (likely a state name), use it
                # But only if it doesn't look like a county/town name
                if not constraints["state"] and len(last_part.split()) <= 2:
                    # Check if it's a known state name (even if not in the list)
                    # Don't assume single words are states - they could be counties
                    pass  # Don't auto-assign state from last part if uncertain
        
        # Second-to-last is often county
        if not constraints["county"] and len(parts) >= 2:
            second_last = normalize_text(parts[-2])
            # Remove common suffixes
            for suffix in ["county", "town", "village"]:
                if second_last.endswith(suffix):
                    second_last = second_last[:-len(suffix)].strip()
            constraints["county"] = second_last
        
        # First part is often village/town
        if not constraints["village"] and len(parts) >= 1:
            first_part = normalize_text(parts[0])
            # Remove common suffixes
            for suffix in ["town", "village", "settlement"]:
                if first_part.endswith(suffix):
                    first_part = first_part[:-len(suffix)].strip()
            constraints["village"] = first_part
    
    # Also check last part for county if it wasn't already identified
    if not constraints["county"] and len(parts) >= 1:
        last_part = normalize_text(parts[-1])
        if "county" in last_part:
            county_name = last_part.replace("county", "").strip()
            if county_name:
                constraints["county"] = county_name
    
    return constraints

