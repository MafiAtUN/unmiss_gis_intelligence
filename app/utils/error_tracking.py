"""Error tracking and monitoring setup."""
import os
import logging
from typing import Optional
from pathlib import Path

try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


def filter_sensitive_data(event, hint):
    """Filter sensitive data from Sentry events."""
    # Remove API keys, tokens, passwords, etc.
    if event.get('request'):
        if 'headers' in event.get('request', {}):
            sensitive_headers = ['authorization', 'api-key', 'x-api-key', 'x-auth-token', 
                              'cookie', 'set-cookie', 'password', 'secret']
            event['request']['headers'] = {
                k: '***REDACTED***' if k.lower() in sensitive_headers else v
                for k, v in event['request']['headers'].items()
            }
        
        if 'data' in event.get('request', {}):
            # Redact potential sensitive data
            data = event['request']['data']
            if isinstance(data, dict):
                sensitive_keys = ['password', 'secret', 'api_key', 'token', 'auth']
                for key in sensitive_keys:
                    if key in data:
                        data[key] = '***REDACTED***'
    
    # Filter environment variables that might contain secrets
    if 'environment' in event:
        env = event['environment']
        if isinstance(env, dict):
            sensitive_env_vars = ['API_KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'AUTH']
            for key in list(env.keys()):
                if any(sensitive in key.upper() for sensitive in sensitive_env_vars):
                    env[key] = '***REDACTED***'
    
    return event


def setup_error_tracking(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    release: Optional[str] = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1
):
    """
    Setup Sentry error tracking.
    
    Args:
        dsn: Sentry DSN (if None, will try to get from SENTRY_DSN env var)
        environment: Environment name (development, staging, production)
        release: Release version
        traces_sample_rate: Percentage of transactions to trace (0.0 to 1.0)
        profiles_sample_rate: Percentage of transactions to profile (0.0 to 1.0)
    
    Returns:
        True if Sentry was initialized, False otherwise
    """
    if not SENTRY_AVAILABLE:
        logging.warning("Sentry SDK not available. Install with: pip install sentry-sdk")
        return False
    
    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        logging.info("Sentry DSN not provided. Error tracking disabled.")
        return False
    
    environment = environment or os.getenv("ENVIRONMENT", "development")
    release = release or os.getenv("RELEASE", "unknown")
    
    try:
        # Try to import Streamlit integration
        try:
            from sentry_sdk.integrations.streamlit import StreamlitIntegration
            integrations = [
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                StreamlitIntegration(),
            ]
        except ImportError:
            # Streamlit integration not available, use basic logging integration
            integrations = [
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ]
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            integrations=integrations,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            before_send=filter_sensitive_data,
            # Capture unhandled exceptions
            attach_stacktrace=True,
            # Send default PII (personally identifiable information) - set to False in production
            send_default_pii=False,
            # Debug mode (set to True for troubleshooting)
            debug=os.getenv("SENTRY_DEBUG", "false").lower() == "true",
        )
        
        logging.info(f"Sentry error tracking initialized for environment: {environment}")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize Sentry: {e}")
        return False


def capture_exception(error: Exception, context: Optional[dict] = None):
    """Capture exception and send to Sentry if available."""
    if not SENTRY_AVAILABLE:
        return False
    
    try:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_context(key, {"value": str(value)})
            sentry_sdk.capture_exception(error)
        return True
    except Exception:
        return False


def capture_message(message: str, level: str = "error", context: Optional[dict] = None):
    """Capture message and send to Sentry if available."""
    if not SENTRY_AVAILABLE:
        return False
    
    try:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_context(key, {"value": str(value)})
            sentry_sdk.capture_message(message, level=level)
        return True
    except Exception:
        return False


