"""Centralized error handling for Streamlit pages and functions."""
import streamlit as st
import traceback
import functools
from typing import Callable, Any, Optional
from app.utils.logging import log_error, log_critical


def handle_streamlit_errors(show_details: bool = True, reraise: bool = False):
    """
    Decorator to handle errors in Streamlit pages.
    
    Args:
        show_details: Whether to show error details in expander
        reraise: Whether to re-raise the exception (for development)
    
    Usage:
        @handle_streamlit_errors()
        def my_streamlit_page():
            # Your code here
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log error with full context
                log_error(e, {
                    "module": func.__module__,
                    "function": func.__name__,
                    "streamlit_page": True,
                })
                
                # Show user-friendly error
                st.error(f"❌ An error occurred: {str(e)}")
                
                # Show detailed error in expander (for debugging)
                if show_details:
                    with st.expander("🔍 Error Details (for debugging)", expanded=False):
                        st.code(traceback.format_exc(), language="python")
                        
                        # Additional context
                        st.markdown("**Error Context:**")
                        st.json({
                            "module": func.__module__,
                            "function": func.__name__,
                            "error_type": type(e).__name__,
                        })
                
                # Re-raise if in development mode
                if reraise or st.get_option("server.runOnSave"):
                    raise
        
        return wrapper
    return decorator


def safe_execute(func: Callable, *args, default_return: Any = None, **kwargs) -> Any:
    """
    Safely execute a function and return default value on error.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        default_return: Value to return on error
        **kwargs: Keyword arguments
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_error(e, {
            "module": func.__module__ if hasattr(func, '__module__') else 'unknown',
            "function": func.__name__ if hasattr(func, '__name__') else 'unknown',
            "safe_execute": True,
        })
        return default_return


def catch_and_log(func: Callable) -> Callable:
    """
    Decorator to catch and log errors without stopping execution.
    
    Usage:
        @catch_and_log
        def my_function():
            # Your code here
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_error(e, {
                "module": func.__module__ if hasattr(func, '__module__') else 'unknown',
                "function": func.__name__ if hasattr(func, '__name__') else 'unknown',
                "catch_and_log": True,
            })
            return None
    
    return wrapper


