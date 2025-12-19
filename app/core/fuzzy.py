"""Fuzzy matching utilities using RapidFuzz."""
from typing import List, Tuple, Optional, Dict, Any
from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process
from app.core.normalization import normalize_text


def fuzzy_match(
    query: str,
    choices: List[str],
    threshold: float = 0.7,
    limit: int = 5
) -> List[Tuple[str, float, int]]:
    """
    Perform fuzzy matching between query and choices.
    
    Uses token sort ratio and partial ratio for better matching.
    
    Args:
        query: Query string to match
        choices: List of candidate strings
        threshold: Minimum similarity score (0-1)
        limit: Maximum number of results to return
        
    Returns:
        List of tuples (matched_string, score, index) sorted by score descending
    """
    if not query or not choices:
        return []
    
    # Use RapidFuzz process.extract with token_sort_ratio and partial_ratio
    results = process.extract(
        query,
        choices,
        scorer=fuzz.token_sort_ratio,
        limit=limit,
        score_cutoff=int(threshold * 100)
    )
    
    # Also try partial matching for better results
    partial_results = process.extract(
        query,
        choices,
        scorer=fuzz.partial_ratio,
        limit=limit,
        score_cutoff=int(threshold * 100)
    )
    
    # Also try WRatio (weighted ratio) for better overall matching
    wratio_results = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=int(threshold * 100)
    )
    
    # Combine and deduplicate, keeping best scores
    combined = {}
    normalized_query = normalize_text(query)
    query_len = len(normalized_query)
    
    for match, score, idx in results + partial_results + wratio_results:
        score_normalized = score / 100.0
        
        # Penalize substring matches where one is much shorter
        # This prevents "Abi" from matching "Abiemnom" with high score
        normalized_choice = normalize_text(choices[idx])
        choice_len = len(normalized_choice)
        
        # Check if this is a substring match (one contains the other but lengths differ significantly)
        # CRITICAL: Prevent "Abi" from matching "Abiemnom" with high score
        if normalized_query in normalized_choice or normalized_choice in normalized_query:
            length_ratio = min(query_len, choice_len) / max(query_len, choice_len)
            if length_ratio < 0.8:  # One is less than 80% of the other (stricter)
                # This is likely a substring match - reduce score significantly
                # If query is longer (e.g., "abiemnom"), heavily penalize shorter matches (e.g., "abi")
                if query_len > choice_len:
                    score_normalized *= 0.3  # Very strong penalty - query is longer, choice is substring
                else:
                    score_normalized *= 0.5  # Strong penalty - choice is longer, query is substring
        
        if idx not in combined or combined[idx][1] < score_normalized:
            combined[idx] = (match, score_normalized, idx)
    
    # Sort by score descending
    sorted_results = sorted(combined.values(), key=lambda x: x[1], reverse=True)
    
    return sorted_results[:limit]


def progressive_fuzzy_match(
    query: str,
    choices: List[str],
    base_threshold: float = 0.7,
    limit: int = 5
) -> List[Tuple[str, float, int]]:
    """
    Progressive fuzzy matching with multiple stages.
    
    Tries exact match first, then progressively lower thresholds.
    This improves accuracy by prioritizing high-confidence matches.
    
    Args:
        query: Query string to match
        choices: List of candidate strings
        base_threshold: Base similarity score (0-1)
        limit: Maximum number of results to return
        
    Returns:
        List of tuples (matched_string, score, index) sorted by score descending
    """
    if not query or not choices:
        return []
    
    # Stage 1: Exact match (normalized)
    from app.core.normalization import normalize_text
    normalized_query = normalize_text(query)
    exact_matches = []
    for idx, choice in enumerate(choices):
        if normalize_text(choice) == normalized_query:
            exact_matches.append((choice, 1.0, idx))
    
    if exact_matches:
        return exact_matches[:limit]
    
    # Stage 2: High confidence (0.9+) with length preference
    # Prioritize matches where query length is similar to choice length (avoid substring matches)
    high_conf = fuzzy_match(query, choices, threshold=0.9, limit=limit * 2)
    if high_conf:
        # Boost matches where lengths are similar (prefer "Abiemnom" over "Abi" for query "abiemnom")
        scored_high_conf = []
        query_len = len(normalized_query)
        for match_str, score, idx in high_conf:
            choice_len = len(normalize_text(choices[idx]))
            # Penalize if one is much shorter than the other (substring match)
            length_ratio = min(query_len, choice_len) / max(query_len, choice_len)
            if length_ratio < 0.6:  # One is less than 60% of the other
                score *= 0.7  # Reduce score for substring matches
            scored_high_conf.append((match_str, score, idx))
        scored_high_conf.sort(key=lambda x: x[1], reverse=True)
        return scored_high_conf[:limit]
    
    # Stage 3: Medium-high confidence (0.8+)
    medium_high = fuzzy_match(query, choices, threshold=0.8, limit=limit)
    if medium_high:
        return medium_high
    
    # Stage 4: Base threshold (0.7+)
    base_matches = fuzzy_match(query, choices, threshold=base_threshold, limit=limit)
    if base_matches:
        return base_matches
    
    # Stage 5: Lower threshold for partial matches (0.5+)
    # Only if query is short (likely abbreviation or partial name)
    if len(normalized_query.split()) <= 2 or len(normalized_query) <= 5:
        low_conf = fuzzy_match(query, choices, threshold=0.5, limit=limit)
        if low_conf:
            return low_conf
    
    return []


def apply_context_boost(
    matches: List[Tuple[str, float, int]],
    match_data: List[Dict[str, Any]],
    constraints: Optional[Dict[str, Optional[str]]] = None
) -> List[Tuple[str, float, int]]:
    """
    Apply context-aware scoring boost to matches.
    
    Boosts scores for matches that align with hierarchical constraints.
    
    Args:
        matches: List of (matched_string, score, index) tuples
        match_data: List of dictionaries with match metadata (state, county, layer, etc.)
        constraints: Dictionary with state, county, payam, boma constraints
        
    Returns:
        List of tuples with boosted scores
    """
    if not constraints or not match_data:
        return matches
    
    boosted_matches = []
    
    # Layer specificity boost (more specific = higher boost)
    layer_boost = {
        "villages": 0.15,
        "settlements": 0.15,
        "admin4_boma": 0.10,
        "admin3_payam": 0.05,
        "admin2_county": 0.02,
        "admin1_state": 0.01,
    }
    
    for match_str, score, idx in matches:
        boosted_score = score
        
        if idx < len(match_data):
            match_info = match_data[idx]
            
            # Boost if in correct state
            if constraints.get("state"):
                constraint_state = constraints["state"].lower().replace(" state", "").strip()
                match_state = (match_info.get("state") or "").lower().replace(" state", "").strip()
                # Check if states match (handle partial matches)
                if constraint_state in match_state or match_state in constraint_state or constraint_state == match_state:
                    boosted_score += 0.20  # Increased boost
                elif match_state and constraint_state != match_state:
                    # STRONG penalty if in wrong state - this should eliminate wrong matches
                    boosted_score -= 0.50  # Much stronger penalty
            
            # Boost if in correct county
            if constraints.get("county"):
                constraint_county = constraints["county"].lower().replace(" county", "").strip()
                match_county = (match_info.get("county") or "").lower().replace(" county", "").strip()
                if constraint_county in match_county or match_county in constraint_county or constraint_county == match_county:
                    boosted_score += 0.20  # Increased boost
                elif match_county and constraint_county != match_county:
                    # STRONG penalty if in wrong county
                    boosted_score -= 0.30  # Stronger penalty
            
            # Boost if in correct payam
            if constraints.get("payam"):
                constraint_payam = constraints["payam"].lower()
                match_payam = (match_info.get("payam") or "").lower()
                if constraint_payam in match_payam or match_payam in constraint_payam:
                    boosted_score += 0.05
            
            # Boost if in correct boma
            if constraints.get("boma"):
                constraint_boma = constraints["boma"].lower()
                match_boma = (match_info.get("boma") or "").lower()
                if constraint_boma in match_boma or match_boma in constraint_boma:
                    boosted_score += 0.05
            
            # Layer specificity boost
            layer = match_info.get("layer", "")
            boosted_score += layer_boost.get(layer, 0.0)
        
        # Clamp score between 0 and 1
        boosted_score = max(0.0, min(1.0, boosted_score))
        boosted_matches.append((match_str, boosted_score, idx))
    
    # Re-sort by boosted score
    boosted_matches.sort(key=lambda x: x[1], reverse=True)
    
    return boosted_matches


def best_match(
    query: str,
    choices: List[str],
    threshold: float = 0.7
) -> Optional[Tuple[str, float, int]]:
    """
    Get the best fuzzy match for a query.
    
    Args:
        query: Query string to match
        choices: List of candidate strings
        threshold: Minimum similarity score (0-1)
        
    Returns:
        Tuple (matched_string, score, index) or None if no match above threshold
    """
    matches = fuzzy_match(query, choices, threshold, limit=1)
    return matches[0] if matches else None

