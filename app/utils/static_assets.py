"""Utility functions for loading and displaying static assets like logos."""
from pathlib import Path
import streamlit as st
from typing import Optional


def get_project_root() -> Path:
    """Get the project root directory."""
    # This file is at app/utils/static_assets.py
    # Project root is 2 levels up
    return Path(__file__).parent.parent.parent


def get_static_path(filename: str) -> Path:
    """
    Get the full path to a static asset file.
    
    Args:
        filename: Name of the file in .streamlit/static/ directory
        
    Returns:
        Path object pointing to the static asset
        
    Example:
        logo_path = get_static_path("logo.png")
    """
    project_root = get_project_root()
    static_dir = project_root / ".streamlit" / "static"
    return static_dir / filename


def static_file_exists(filename: str) -> bool:
    """
    Check if a static asset file exists.
    
    Args:
        filename: Name of the file in .streamlit/static/ directory
        
    Returns:
        True if file exists, False otherwise
    """
    return get_static_path(filename).exists()


def display_logo(
    filename: str,
    width: Optional[int] = None,
    use_column_width: bool = False,
    caption: Optional[str] = None
) -> None:
    """
    Display a logo image from the static assets directory.
    
    Args:
        filename: Name of the logo file (e.g., "logo.png")
        width: Width in pixels (optional)
        use_column_width: If True, use column width instead of fixed width
        caption: Optional caption text below the image
        
    Example:
        display_logo("logo.png", width=200)
    """
    logo_path = get_static_path(filename)
    
    if not logo_path.exists():
        st.warning(f"Logo file not found: {logo_path}")
        return
    
    st.image(
        str(logo_path),
        width=width,
        use_column_width=use_column_width,
        caption=caption
    )


def get_logo_html(filename: str, width: Optional[int] = None) -> str:
    """
    Get HTML code for embedding a logo (useful for custom layouts).
    
    Args:
        filename: Name of the logo file
        width: Width in pixels (optional)
        
    Returns:
        HTML string with img tag
        
    Example:
        st.markdown(get_logo_html("logo.png", width=150), unsafe_allow_html=True)
    """
    logo_path = get_static_path(filename)
    
    if not logo_path.exists():
        return f"<!-- Logo not found: {logo_path} -->"
    
    # Use relative path from Streamlit's static serving
    # Streamlit serves .streamlit/static/ files automatically
    static_url = f"/.streamlit/static/{filename}"
    
    width_attr = f' width="{width}"' if width else ""
    return f'<img src="{static_url}"{width_attr} alt="Logo">'

