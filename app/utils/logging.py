"""Structured logging utilities."""
import json
import logging
from datetime import datetime
from typing import Dict, Any


def setup_logging(level: str = "INFO"):
    """Setup structured JSON logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(message)s',
        handlers=[logging.StreamHandler()]
    )


def log_structured(level: str, message: str, **kwargs):
    """
    Log structured JSON message.
    
    Args:
        level: Log level (info, warning, error, etc.)
        message: Log message
        **kwargs: Additional structured fields
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level.upper(),
        "message": message,
        **kwargs
    }
    
    logger = logging.getLogger()
    getattr(logger, level.lower(), logger.info)(json.dumps(log_entry))

