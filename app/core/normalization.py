"""Text normalization utilities for place name matching."""
import re
import unicodedata
from typing import List, Set


def normalize_text(text: str) -> str:
    """
    Normalize text for matching: lowercase, strip punctuation, collapse whitespace, unicode normalize.
    
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
    
    # Remove punctuation except spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    
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

