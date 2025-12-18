"""Tests for fuzzy matching."""
import pytest
from app.core.fuzzy import fuzzy_match, best_match


def test_fuzzy_match():
    """Test fuzzy matching."""
    choices = ["Juba", "Bentiu", "Malakal", "Wau"]
    
    matches = fuzzy_match("Juba", choices, threshold=0.7)
    assert len(matches) > 0
    assert matches[0][0] == "Juba"
    assert matches[0][1] >= 0.7
    
    matches = fuzzy_match("juba", choices, threshold=0.7)
    assert len(matches) > 0
    
    matches = fuzzy_match("xyz", choices, threshold=0.7)
    assert len(matches) == 0


def test_best_match():
    """Test best match function."""
    choices = ["Juba", "Bentiu", "Malakal"]
    
    match = best_match("Juba", choices, threshold=0.7)
    assert match is not None
    assert match[0] == "Juba"
    
    match = best_match("xyz", choices, threshold=0.7)
    assert match is None

