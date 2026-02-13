# Error Handling & Logging System

This document describes the comprehensive error handling and logging system implemented in the application.

## Overview

The application now includes:
- **Structured JSON logging** with file rotation
- **Error tracking** via Sentry (optional)
- **Global exception handling** for uncaught errors
- **Comprehensive error context** (module, function, traceback, etc.)
- **Error dashboard** for viewing and analyzing errors
- **Automatic error reporting** to help diagnose issues

## Features

### 1. Enhanced Logging

All errors are logged with:
- Timestamp (UTC)
- Error type and message
- Module and function where error occurred
- Full traceback
- Additional context (user actions, input data, etc.)

Logs are written to:
- Console (stdout) - for immediate visibility
- Log file: `data/logs/app.log` - with automatic rotation (10MB files, 5 backups)

### 2. Error Tracking (Sentry)

Optional integration with Sentry for production error monitoring:
- Automatic error capture
- Error aggregation and grouping
- Performance monitoring
- Release tracking
- Sensitive data filtering

### 3. Global Exception Handler

Uncaught exceptions are automatically:
- Logged with full context
- Sent to error tracking (if configured)
- Displayed in Streamlit UI (when possible)
- Prevented from crashing the app silently

### 4. Error Dashboard

Access the error dashboard via the Streamlit sidebar: **"7_Error_Logs"**

Features:
- View all errors and critical issues
- Filter by level (ERROR, CRITICAL) and module
- Error statistics and breakdowns
- View full tracebacks and context
- Download log files

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Logging Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=data/logs/app.log        # Path to log file (or leave empty for default)
LOG_MAX_BYTES=10485760            # 10MB - max log file size before rotation
LOG_BACKUP_COUNT=5                # Number of backup log files to keep

# Error Tracking (Sentry) - Optional
SENTRY_DSN=your_sentry_dsn_here   # Get from https://sentry.io
ENVIRONMENT=development            # development, staging, production
RELEASE=1.0.0                     # Application version/release
SENTRY_DEBUG=false                 # Enable Sentry debug mode
```

### Setting Up Sentry (Optional)

1. Create a free account at https://sentry.io
2. Create a new project (Python)
3. Copy your DSN
4. Add `SENTRY_DSN=your_dsn_here` to your `.env` file
5. Restart the application

Sentry will automatically:
- Capture all errors
- Group similar errors
- Track error frequency
- Provide performance insights
- Send email notifications (configurable)

## Usage

### Logging Errors in Code

Instead of using `print()` for errors, use the logging utilities:

```python
from app.utils.logging import log_error, log_structured

# Log an error with context
try:
    # Your code here
    pass
except Exception as e:
    log_error(e, {
        "module": "my_module",
        "function": "my_function",
        "user_id": user_id,
        "input_data": str(input_data)
    })

# Log structured information
log_structured("info", "Operation completed", 
               module="my_module",
               function="my_function",
               records_processed=100)
```

### Error Handler Decorator

For Streamlit pages, wrap functions with error handling:

```python
from app.utils.error_handler import handle_streamlit_errors

@handle_streamlit_errors()
def my_streamlit_function():
    # Your code here
    pass
```

### Safe Execution

For functions that should not crash the app:

```python
from app.utils.error_handler import safe_execute

result = safe_execute(
    risky_function,
    arg1, arg2,
    default_return=None  # Return this on error
)
```

## Log File Location

By default, logs are stored at:
```
data/logs/app.log
```

Log files are automatically rotated:
- When file exceeds 10MB
- Old files are renamed: `app.log.1`, `app.log.2`, etc.
- Maximum 5 backup files kept

## Viewing Logs

### Via Streamlit Dashboard

1. Open the application
2. Navigate to "Error Logs" page in sidebar
3. View errors, filter, and analyze

### Via Command Line

```bash
# View recent errors
tail -f data/logs/app.log | grep -i error

# View all errors
cat data/logs/app.log | grep -i error

# View last 100 lines
tail -n 100 data/logs/app.log
```

### Log Format

Logs are in JSON format, one entry per line:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "ERROR",
  "error_type": "ValueError",
  "error_message": "Invalid input",
  "module": "app.core.geocoder",
  "function": "geocode",
  "traceback": "Traceback (most recent call last):\n...",
  "context_key": "context_value"
}
```

## Error Types

### ERROR
Regular errors that don't crash the app but should be investigated:
- Failed geocoding requests
- API call failures
- Data validation errors

### CRITICAL
Errors that may cause app crashes or data loss:
- Database connection failures
- Memory errors
- Uncaught exceptions

## Best Practices

1. **Always log errors with context**: Include relevant data that helps diagnose the issue
2. **Don't log sensitive data**: Passwords, API keys, etc. are automatically filtered
3. **Use appropriate log levels**: 
   - DEBUG: Detailed information for debugging
   - INFO: General information
   - WARNING: Something unexpected but handled
   - ERROR: Error occurred but app continues
   - CRITICAL: Serious error that may crash app
4. **Check error dashboard regularly**: Monitor for recurring issues
5. **Set up Sentry alerts**: Get notified of critical errors in production

## Troubleshooting

### Logs not appearing

1. Check `LOG_FILE` path in `.env`
2. Ensure `data/logs/` directory exists and is writable
3. Check `LOG_LEVEL` - may be set too high (e.g., ERROR won't show INFO)

### Sentry not working

1. Verify `SENTRY_DSN` is set correctly
2. Check internet connection (Sentry requires network access)
3. Set `SENTRY_DEBUG=true` to see Sentry initialization messages
4. Check Sentry dashboard for project status

### Too many log files

1. Reduce `LOG_BACKUP_COUNT` in `.env`
2. Reduce `LOG_MAX_BYTES` for smaller files
3. Manually delete old log files: `rm data/logs/app.log.*`

## Integration with Cursor

When errors occur, the system automatically:
1. Logs detailed error information to `data/logs/app.log`
2. Captures full context (module, function, inputs, etc.)
3. Records tracebacks for debugging
4. Sends to Sentry (if configured) for remote monitoring

This information helps Cursor and developers:
- Understand what went wrong
- Identify patterns in errors
- Debug issues more efficiently
- Improve error handling

## Support

For issues with the error handling system itself:
1. Check this documentation
2. Review log files
3. Check Sentry dashboard (if configured)
4. Review application code for error handling patterns


