"""Fuzzy matching utilities using RapidFuzz."""
from typing import List, Tuple, Optional
from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process


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
    
    # Combine and deduplicate, keeping best scores
    combined = {}
    for match, score, idx in results + partial_results:
        score_normalized = score / 100.0
        if idx not in combined or combined[idx][1] < score_normalized:
            combined[idx] = (match, score_normalized, idx)
    
    # Sort by score descending
    sorted_results = sorted(combined.values(), key=lambda x: x[1], reverse=True)
    
    return sorted_results[:limit]


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

