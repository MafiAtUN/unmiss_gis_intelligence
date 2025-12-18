"""Tests for geocoding engine."""
import pytest
from app.core.models import GeocodeResult


def test_geocode_village(geocoder):
    """Test geocoding a known village."""
    result = geocoder.geocode("Test Village")
    
    assert isinstance(result, GeocodeResult)
    assert result.resolved_layer == "settlements"
    assert result.village == "Test Village"
    assert result.lon is not None
    assert result.lat is not None
    assert result.score > 0


def test_geocode_boma(geocoder):
    """Test geocoding a boma name."""
    result = geocoder.geocode("Test Boma")
    
    assert isinstance(result, GeocodeResult)
    assert result.resolved_layer == "admin4_boma"
    assert result.boma == "Test Boma"
    assert result.lon is not None
    assert result.lat is not None


def test_geocode_payam(geocoder):
    """Test geocoding a payam name."""
    result = geocoder.geocode("Test Payam")
    
    assert isinstance(result, GeocodeResult)
    assert result.resolved_layer == "admin3_payam"
    assert result.payam == "Test Payam"
    assert result.lon is not None
    assert result.lat is not None


def test_geocode_no_match(geocoder):
    """Test geocoding with no match."""
    result = geocoder.geocode("Nonexistent Place XYZ")
    
    assert isinstance(result, GeocodeResult)
    assert result.score == 0.0
    assert result.lon is None
    assert result.lat is None


def test_geocode_cache(geocoder):
    """Test geocoding cache."""
    # First geocode
    result1 = geocoder.geocode("Test Village", use_cache=True)
    
    # Second geocode (should use cache)
    result2 = geocoder.geocode("Test Village", use_cache=True)
    
    assert result1.lon == result2.lon
    assert result1.lat == result2.lat

