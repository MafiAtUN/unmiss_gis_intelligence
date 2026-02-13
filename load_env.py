#!/usr/bin/env python3
"""Helper script to load .env file and export variables for shell scripts."""
import os
import sys
from pathlib import Path

def load_env_for_shell():
    """Load .env file and print export statements for shell."""
    env_path = Path('.env')
    if not env_path.exists():
        return
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    # Escape special characters in value for shell
                    value = value.replace('$', '\\$').replace('`', '\\`').replace('"', '\\"')
                    print(f'export {key}="{value}"')
    except PermissionError:
        # If we can't read the file, try using python-dotenv if available
        try:
            from dotenv import dotenv_values
            env_vars = dotenv_values(env_path)
            for key, value in env_vars.items():
                if value:
                    value = str(value).replace('$', '\\$').replace('`', '\\`').replace('"', '\\"')
                    print(f'export {key}="{value}"')
        except ImportError:
            sys.stderr.write("Warning: Could not load .env file\n")
        except Exception as e:
            sys.stderr.write(f"Warning: {e}\n")
    except Exception as e:
        sys.stderr.write(f"Warning: Could not load .env file: {e}\n")

if __name__ == '__main__':
    load_env_for_shell()
