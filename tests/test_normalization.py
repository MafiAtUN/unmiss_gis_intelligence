"""Tests for text normalization."""
import pytest
from app.core.normalization import normalize_text, generate_ngrams, extract_candidates


def test_normalize_text():
    """Test text normalization."""
    assert normalize_text("Juba") == "juba"
    assert normalize_text("  Juba  ") == "juba"
    assert normalize_text("Juba, South Sudan") == "juba south sudan"
    assert normalize_text("Juba-South-Sudan") == "juba south sudan"
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_generate_ngrams():
    """Test n-gram generation."""
    ngrams = generate_ngrams("juba south sudan")
    assert "juba" in ngrams
    assert "south" in ngrams
    assert "sudan" in ngrams
    assert "juba south" in ngrams
    assert "south sudan" in ngrams
    assert "juba south sudan" in ngrams


def test_extract_candidates():
    """Test candidate extraction."""
    candidates = extract_candidates("Juba, Central Equatoria, South Sudan")
    assert len(candidates) > 0
    assert "juba" in candidates
    assert "central" in candidates
    assert "equatoria" in candidates
    
    # Should filter out stop words
    candidates = extract_candidates("the village of juba")
    assert "the" not in candidates
    assert "of" not in candidates
    assert "juba" in candidates

