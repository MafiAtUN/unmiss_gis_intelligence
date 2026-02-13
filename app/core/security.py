"""Security utilities for input validation and sanitization."""
from typing import Optional
from app.core.config import LAYER_NAMES


def validate_layer_name(layer_name: str) -> bool:
    """
    Validate that a layer name is in the allowed whitelist.
    
    Args:
        layer_name: Layer name to validate
        
    Returns:
        True if layer name is valid, False otherwise
    """
    return layer_name in LAYER_NAMES.values()


def sanitize_layer_name(layer_name: str) -> Optional[str]:
    """
    Sanitize and validate a layer name.
    
    Returns the layer name if valid, None otherwise.
    This prevents SQL injection by ensuring only whitelisted table names are used.
    
    Args:
        layer_name: Layer name to sanitize
        
    Returns:
        Validated layer name or None if invalid
    """
    if not layer_name or not isinstance(layer_name, str):
        return None
    
    # Remove any whitespace
    layer_name = layer_name.strip()
    
    # Check against whitelist
    if validate_layer_name(layer_name):
        return layer_name
    
    return None


def validate_feature_id(feature_id: str) -> bool:
    """
    Validate a feature ID format.
    
    Args:
        feature_id: Feature ID to validate
        
    Returns:
        True if feature ID appears valid
    """
    if not feature_id or not isinstance(feature_id, str):
        return False
    
    # Feature IDs should be non-empty strings
    # Add more validation if needed based on actual format
    return len(feature_id.strip()) > 0 and len(feature_id) < 1000  # Reasonable max length


