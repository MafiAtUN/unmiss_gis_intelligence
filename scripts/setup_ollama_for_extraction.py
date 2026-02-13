#!/usr/bin/env python3
"""
Setup and test Ollama for efficient location extraction.

This script:
1. Checks Ollama availability
2. Recommends efficient models
3. Tests extraction with available models
4. Provides setup instructions
"""

import subprocess
import sys
import requests
import json


def check_ollama_available():
    """Check if Ollama is running."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def get_installed_models():
    """Get list of installed Ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            models = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            return models
    except Exception:
        pass
    return []


def test_model_extraction(model_name: str):
    """Test location extraction with a model."""
    test_description = """On 2 January, three secondary sources reported that on 24 December 2024, 
armed Toposa youths from Riwoto Payam, Kapoeta North County shot and killed one 32-year-old male 
civilian from the Lopit community during an attempted cattle raid in Lohutok Boma, Lohutok Payam, 
Lafon County."""
    
    prompt = f"""Extract the PRIMARY incident location from this description. Focus on WHERE the incident occurred.

Description: {test_description}

Return ONLY the location string in format: "Location Name, Payam Name, County Name"
Return only the location, nothing else."""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 100,
                }
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            location = result.get("response", "").strip()
            return location, True
        else:
            return None, False
    except Exception as e:
        return None, False


def main():
    print("=" * 80)
    print("OLLAMA SETUP FOR LOCATION EXTRACTION")
    print("=" * 80)
    
    # Check if Ollama is available
    print("\n1. Checking Ollama availability...")
    if not check_ollama_available():
        print("   ✗ Ollama is not running or not accessible")
        print("   → Start Ollama: ollama serve")
        print("   → Or install Ollama: https://ollama.ai")
        return
    else:
        print("   ✓ Ollama is running")
    
    # Get installed models
    print("\n2. Checking installed models...")
    installed_models = get_installed_models()
    if installed_models:
        print(f"   Found {len(installed_models)} model(s):")
        for model in installed_models:
            print(f"     - {model}")
    else:
        print("   No models found")
    
    # Recommend efficient models
    print("\n3. Recommended models for efficient extraction:")
    print("   ⭐ llama3.2:3b (RECOMMENDED)")
    print("      - Size: ~2GB")
    print("      - Speed: Very fast")
    print("      - Quality: Excellent")
    print("      - Command: ollama pull llama3.2:3b")
    print()
    print("   ⚡ llama3.2:1b (FASTEST)")
    print("      - Size: ~1.3GB")
    print("      - Speed: Extremely fast")
    print("      - Quality: Good")
    print("      - Command: ollama pull llama3.2:1b")
    
    # Test existing models
    if installed_models:
        print("\n4. Testing existing models...")
        for model in installed_models[:3]:  # Test up to 3 models
            print(f"\n   Testing {model}...")
            location, success = test_model_extraction(model)
            if success:
                print(f"     ✓ Success: {location[:80]}...")
            else:
                print(f"     ✗ Failed or timeout")
    
    # Configuration instructions
    print("\n" + "=" * 80)
    print("CONFIGURATION")
    print("=" * 80)
    print("\nTo use Ollama for location extraction:")
    print("\n1. Set environment variable (recommended):")
    print("   export OLLAMA_MODEL=llama3.2:3b")
    print("   export ENABLE_OLLAMA=true")
    print("\n2. Or add to .env file:")
    print("   OLLAMA_MODEL=llama3.2:3b")
    print("   ENABLE_OLLAMA=true")
    print("\n3. Or use existing models:")
    if installed_models:
        print(f"   OLLAMA_MODEL={installed_models[0]}")
    print("   ENABLE_OLLAMA=true")
    
    print("\n" + "=" * 80)
    print("READY TO USE")
    print("=" * 80)
    print("\nThe system will automatically:")
    print("  - Use Ollama first (local, fast, efficient)")
    print("  - Fallback to Azure AI if Ollama unavailable")
    print("  - Fallback to regex patterns if both unavailable")


if __name__ == "__main__":
    main()

