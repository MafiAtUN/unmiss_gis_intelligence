#!/usr/bin/env python3
"""
Run full evaluation with all improvements enabled.

This script:
1. Tests with improved fuzzy matching
2. Tests with LLM extraction (if available)
3. Generates comprehensive reports
4. Provides recommendations
"""

import sys
import os
import subprocess
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run_evaluation_with_improvements():
    """Run comprehensive evaluation with all improvements."""
    
    print("=" * 80)
    print("FULL EVALUATION WITH IMPROVEMENTS")
    print("=" * 80)
    print(f"Started at: {datetime.now()}\n")
    
    input_file = "resources/casualty_tracking/casualty_matrix.xlsx"
    
    # Test 1: Without LLM (baseline)
    print("\n" + "=" * 80)
    print("TEST 1: Baseline (No LLM)")
    print("=" * 80)
    
    result1 = subprocess.run([
        sys.executable, "scripts/evaluate_location_extraction.py",
        "--input", input_file,
        "--max-rows", "500",
        "--sample-size", "500",
        "--no-llm"
    ], capture_output=True, text=True)
    
    print(result1.stdout)
    if result1.stderr:
        print("Errors:", result1.stderr)
    
    # Test 2: With LLM (if available)
    print("\n" + "=" * 80)
    print("TEST 2: With LLM Extraction (if available)")
    print("=" * 80)
    
    result2 = subprocess.run([
        sys.executable, "scripts/evaluate_location_extraction.py",
        "--input", input_file,
        "--max-rows", "500",
        "--sample-size", "500"
        # LLM enabled by default if configured
    ], capture_output=True, text=True)
    
    print(result2.stdout)
    if result2.stderr:
        print("Errors:", result2.stderr)
    
    # Generate comprehensive report
    print("\n" + "=" * 80)
    print("GENERATING COMPREHENSIVE REPORT")
    print("=" * 80)
    
    report_file = f"resources/casualty_tracking/accuracy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    result3 = subprocess.run([
        sys.executable, "scripts/generate_accuracy_report.py",
        "--input", input_file,
        "--output", report_file,
        "--max-rows", "500",
        "--sample-size", "500"
    ], capture_output=True, text=True)
    
    print(result3.stdout)
    if result3.stderr:
        print("Errors:", result3.stderr)
    
    print(f"\nReport saved to: {report_file}")
    print(f"\nCompleted at: {datetime.now()}")


if __name__ == "__main__":
    run_evaluation_with_improvements()

