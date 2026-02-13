"""Enhanced structured logging utilities with file rotation and error tracking."""
import json
import logging
import logging.handlers
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import functools

# Global logger instance
_logger = None


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
):
    """
    Setup structured JSON logging with file rotation.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file (enables file logging with rotation)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    global _logger
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler with structured JSON
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation (if log_file specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    _logger = logger
    return logger


def get_logger():
    """Get the configured logger instance."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger()
    return _logger


def log_structured(level: str, message: str, **kwargs):
    """
    Log structured JSON message with context.
    
    Args:
        level: Log level (info, warning, error, etc.)
        message: Log message
        **kwargs: Additional structured fields (module, function, user_id, etc.)
    """
    logger = get_logger()
    
    # Get calling function info if not provided
    if 'module' not in kwargs or 'function' not in kwargs:
        import inspect
        frame = inspect.currentframe().f_back
        if frame:
            if 'module' not in kwargs:
                kwargs['module'] = frame.f_globals.get('__name__', 'unknown')
            if 'function' not in kwargs:
                kwargs['function'] = frame.f_code.co_name
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level.upper(),
        "message": message,
        **kwargs
    }
    
    # Remove None values for cleaner logs
    log_entry = {k: v for k, v in log_entry.items() if v is not None}
    
    getattr(logger, level.lower(), logger.info)(json.dumps(log_entry))


def log_error(error: Exception, context: Optional[Dict[str, Any]] = None, include_traceback: bool = True):
    """
    Log error with full context and traceback.
    
    Args:
        error: Exception instance
        context: Additional context dictionary
        include_traceback: Whether to include full traceback
    """
    logger = get_logger()
    
    # Get calling function info
    import inspect
    frame = inspect.currentframe().f_back
    module_name = 'unknown'
    function_name = 'unknown'
    if frame:
        module_name = frame.f_globals.get('__name__', 'unknown')
        function_name = frame.f_code.co_name
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "ERROR",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "module": module_name,
        "function": function_name,
        **(context or {})
    }
    
    if include_traceback:
        log_entry["traceback"] = traceback.format_exc()
    
    logger.error(json.dumps(log_entry))
    
    # Also send to Sentry if configured
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_context(key, {"value": str(value)})
            scope.set_tag("module", module_name)
            scope.set_tag("function", function_name)
            sentry_sdk.capture_exception(error)
    except ImportError:
        pass  # Sentry not installed
    except Exception:
        pass  # Sentry not configured or error in Sentry itself


def log_critical(message: str, error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
    """
    Log critical error that may cause app crash.
    
    Args:
        message: Critical error message
        error: Optional exception instance
        context: Additional context
    """
    logger = get_logger()
    
    import inspect
    frame = inspect.currentframe().f_back
    module_name = 'unknown'
    function_name = 'unknown'
    if frame:
        module_name = frame.f_globals.get('__name__', 'unknown')
        function_name = frame.f_code.co_name
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "CRITICAL",
        "message": message,
        "module": module_name,
        "function": function_name,
        **(context or {})
    }
    
    if error:
        log_entry["error_type"] = type(error).__name__
        log_entry["error_message"] = str(error)
        log_entry["traceback"] = traceback.format_exc()
    
    logger.critical(json.dumps(log_entry))
    
    # Send to Sentry as critical
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.level = "fatal"
            if context:
                for key, value in context.items():
                    scope.set_context(key, {"value": str(value)})
            scope.set_tag("module", module_name)
            scope.set_tag("function", function_name)
            if error:
                sentry_sdk.capture_exception(error)
            else:
                sentry_sdk.capture_message(message, level="fatal")
    except (ImportError, Exception):
        pass

