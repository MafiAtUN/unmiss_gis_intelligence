"""Timing utilities for performance monitoring."""
import time
from functools import wraps
from typing import Callable, Any
from app.utils.logging import log_structured


def time_function(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        
        log_structured(
            "info",
            f"Function {func.__name__} executed",
            function=func.__name__,
            elapsed_seconds=elapsed
        )
        
        return result
    return wrapper


class Timer:
    """Context manager for timing code blocks."""
    
    def __init__(self, operation: str):
        """
        Initialize timer.
        
        Args:
            operation: Name of the operation being timed
        """
        self.operation = operation
        self.start = None
        self.elapsed = None
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.elapsed = time.time() - self.start
        log_structured(
            "info",
            f"Operation {self.operation} completed",
            operation=self.operation,
            elapsed_seconds=self.elapsed
        )

