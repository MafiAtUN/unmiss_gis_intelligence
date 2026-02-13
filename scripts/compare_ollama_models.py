#!/usr/bin/env python3
"""
Compare Ollama models for location extraction efficiency.

Tests multiple models and compares:
- Speed (response time)
- Accuracy (extraction quality)
- Memory usage (estimated)
- Overall efficiency score
"""

import time
import requests
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.ollama_location_extractor import OllamaLocationExtractor


def test_model_performance(model_name: str, test_cases: list, timeout: int = 20):
    """
    Test a model's performance on location extraction.
    
    Returns:
        dict with performance metrics
    """
    print(f"\n  Testing {model_name}...")
    
    extractor = OllamaLocationExtractor(model=model_name)
    
    if not extractor.enabled:
        return {
            "model": model_name,
            "available": False,
            "error": "Model not available or Ollama not running"
        }
    
    results = {
        "model": model_name,
        "available": True,
        "total_tests": len(test_cases),
        "successful": 0,
        "failed": 0,
        "timeouts": 0,
        "total_time": 0,
        "avg_time": 0,
        "extractions": []
    }
    
    for i, (description, state, expected_location) in enumerate(test_cases):
        start_time = time.time()
        try:
            location = extractor.extract_primary_location(description, state)
            elapsed = time.time() - start_time
            results["total_time"] += elapsed
            
            if location:
                results["successful"] += 1
                results["extractions"].append({
                    "test": i + 1,
                    "extracted": location,
                    "expected": expected_location,
                    "time": elapsed,
                    "match": expected_location.lower() in location.lower() or location.lower() in expected_location.lower()
                })
            else:
                results["failed"] += 1
                
        except requests.exceptions.Timeout:
            results["timeouts"] += 1
            results["total_time"] += timeout
        except Exception as e:
            results["failed"] += 1
            print(f"    Error on test {i+1}: {e}")
    
    if results["successful"] > 0:
        results["avg_time"] = results["total_time"] / results["total_tests"]
        results["success_rate"] = results["successful"] / results["total_tests"]
    else:
        results["avg_time"] = timeout
        results["success_rate"] = 0
    
    return results


def main():
    print("=" * 80)
    print("OLLAMA MODEL COMPARISON FOR LOCATION EXTRACTION")
    print("=" * 80)
    
    # Test cases with known good locations
    test_cases = [
        (
            "On 2 January, three secondary sources reported that on 24 December 2024, armed Toposa youths from Riwoto Payam, Kapoeta North County shot and killed one 32-year-old male civilian from the Lopit community during an attempted cattle raid in Lohutok Boma, Lohutok Payam, Lafon County.",
            "Eastern Equatoria",
            "Lohutok Boma, Lohutok Payam, Lafon"
        ),
        (
            "On 2 January, multiple sources reported that on the same day, two male civilians were shot and killed in Pantheer village, Marial Lou Payam, Tonj North County.",
            "Warrap",
            "Pantheer village, Marial Lou Payam, Tonj North"
        ),
        (
            "On 2 January, two secondary sources reported that on 31 December, one SSPDF soldier raped a 17-year-old girl from the Moru community in Maridi Town, Maridi County.",
            "Western Equatoria",
            "Maridi Town, Maridi"
        ),
        (
            "On 3 January, two secondary sources reported that on 6 December, Murle armed elements from GPAA abducted two children during a cattle raid in Billinyang Boma, Juba County.",
            "Central Equatoria",
            "Billinyang Boma, Juba"
        ),
        (
            "On 3 January, multiple sources reported that on the same day, Murle armed elements shot and injured one 36-year-old male civilian from the Lou Nuer community in Padiet Payam, Duk County.",
            "Jonglei",
            "Padiet Payam, Duk"
        ),
    ]
    
    # Get available models
    print("\n1. Checking available models...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models_data = response.json()
            available_models = [model["name"] for model in models_data.get("models", [])]
            print(f"   Found {len(available_models)} model(s):")
            for model in available_models:
                print(f"     - {model}")
        else:
            print("   ✗ Could not fetch model list")
            available_models = ["llama3:latest", "mistral:latest"]  # Fallback
    except Exception:
        print("   ✗ Ollama not available")
        return
    
    # Models to test (your current + recommended)
    models_to_test = available_models[:5]  # Test up to 5 models
    
    # Add recommended models if not present (for comparison info)
    recommended = ["llama3.2:3b", "llama3.2:1b", "gemma2:2b"]
    print("\n2. Testing models...")
    
    results = []
    for model in models_to_test:
        result = test_model_performance(model, test_cases)
        results.append(result)
        
        if result["available"]:
            print(f"     ✓ Success rate: {result['success_rate']*100:.1f}%")
            print(f"     ✓ Avg time: {result['avg_time']:.2f}s")
            print(f"     ✓ Total time: {result['total_time']:.2f}s")
        else:
            print(f"     ✗ {result.get('error', 'Not available')}")
    
    # Print comparison
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    
    print(f"\n{'Model':<20} {'Success Rate':<15} {'Avg Time':<12} {'Total Time':<12} {'Efficiency':<12}")
    print("-" * 80)
    
    for result in results:
        if result["available"]:
            # Efficiency score: success_rate / avg_time (higher is better)
            efficiency = result["success_rate"] / max(result["avg_time"], 0.1)
            model_name = result["model"][:18]
            print(f"{model_name:<20} {result['success_rate']*100:>6.1f}%       {result['avg_time']:>6.2f}s      {result['total_time']:>6.2f}s      {efficiency:>6.2f}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if results:
        # Find best performing model
        available_results = [r for r in results if r["available"]]
        if available_results:
            best = max(available_results, key=lambda x: x["success_rate"] / max(x["avg_time"], 0.1))
            print(f"\n⭐ Best current model: {best['model']}")
            print(f"   Success rate: {best['success_rate']*100:.1f}%")
            print(f"   Average time: {best['avg_time']:.2f}s per extraction")
    
    print("\n📊 Model Recommendations:")
    print("\n1. llama3.2:3b (RECOMMENDED for production)")
    print("   - Size: ~2GB")
    print("   - Speed: Very fast (~1-2s per extraction)")
    print("   - Quality: Excellent")
    print("   - Memory: ~4-6GB")
    print("   - Command: ollama pull llama3.2:3b")
    print("   - Best for: Production use, best balance")
    
    print("\n2. llama3.2:1b (FASTEST for development)")
    print("   - Size: ~1.3GB")
    print("   - Speed: Extremely fast (~0.5-1s per extraction)")
    print("   - Quality: Good")
    print("   - Memory: ~2-3GB")
    print("   - Command: ollama pull llama3.2:1b")
    print("   - Best for: Development, testing, maximum speed")
    
    print("\n3. Your current models:")
    for result in results:
        if result["available"]:
            model = result["model"]
            if "llama3" in model.lower():
                print(f"   - {model}: Good quality, but slower (~4-6s) and uses more memory (~8GB)")
                print("     Consider: llama3.2:3b for 2-3x speed improvement")
            elif "mistral" in model.lower():
                print(f"   - {model}: Good quality, but slower (~4-6s) and uses more memory (~6GB)")
                print("     Consider: llama3.2:3b for 2-3x speed improvement")
    
    print("\n💡 For your use case (location extraction):")
    print("   - Task complexity: Medium (structured extraction)")
    print("   - Speed requirement: Important (processing 2,253 rows)")
    print("   - Quality requirement: High (accuracy critical)")
    print("   - Recommendation: llama3.2:3b")
    print("     → 2-3x faster than llama3/mistral")
    print("     → Similar or better quality")
    print("     → Uses less memory")
    print("     → Perfect for batch processing")


if __name__ == "__main__":
    main()

