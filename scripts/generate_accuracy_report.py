#!/usr/bin/env python3
"""
Generate comprehensive accuracy report for location extraction.

This script runs a full evaluation and generates a detailed report with:
- Extraction accuracy metrics
- Geocoding accuracy (when database is available)
- Error analysis
- Recommendations for improvement
"""

import pandas as pd
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from evaluate_location_extraction import evaluate_extraction_accuracy


def generate_report(
    input_file: str,
    output_file: str,
    max_rows: Optional[int] = None,
    use_llm: bool = True,
    sample_size: int = 200
):
    """
    Generate comprehensive accuracy report.
    
    Args:
        input_file: Path to Excel file
        output_file: Path to output report file
        max_rows: Maximum rows to process
        use_llm: Whether to use LLM
        sample_size: Number of rows for detailed evaluation
    """
    print("=" * 80)
    print("GENERATING ACCURACY REPORT")
    print("=" * 80)
    print(f"Started at: {datetime.now()}")
    
    # Run evaluation
    stats = evaluate_extraction_accuracy(
        input_file=input_file,
        max_rows=max_rows,
        use_llm=use_llm,
        sample_size=sample_size
    )
    
    # Generate report
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("LOCATION EXTRACTION ACCURACY REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.now()}")
    report_lines.append(f"Input file: {input_file}")
    report_lines.append(f"Rows evaluated: {stats['total']}")
    report_lines.append("")
    
    # Summary metrics
    report_lines.append("SUMMARY METRICS")
    report_lines.append("-" * 80)
    report_lines.append(f"Extraction Success Rate: {stats['extraction_successful']}/{stats['extraction_attempted']} ({stats['extraction_successful']/stats['extraction_attempted']*100:.1f}%)")
    
    if stats['detailed_evaluations']:
        sample_count = len(stats['detailed_evaluations'])
        report_lines.append(f"Location String Match Rate: {stats['location_string_matches']}/{sample_count} ({stats['location_string_matches']/sample_count*100:.1f}%)")
        report_lines.append(f"Payam Match Rate: {stats['payam_matches']}/{sample_count} ({stats['payam_matches']/sample_count*100:.1f}%)")
        report_lines.append(f"County Match Rate: {stats['county_matches']}/{sample_count} ({stats['county_matches']/sample_count*100:.1f}%)")
        report_lines.append(f"State Match Rate: {stats['state_matches']}/{sample_count} ({stats['state_matches']/sample_count*100:.1f}%)")
        report_lines.append(f"Coordinate Match Rate (within 5km): {stats['coordinate_matches']}/{sample_count} ({stats['coordinate_matches']/sample_count*100:.1f}%)")
    
    report_lines.append("")
    
    # Error analysis
    report_lines.append("ERROR ANALYSIS")
    report_lines.append("-" * 80)
    
    if stats['detailed_evaluations']:
        # Analyze failures
        failures = [e for e in stats['detailed_evaluations'] if not e['location_match']['match']]
        report_lines.append(f"Total location string mismatches: {len(failures)}")
        
        if failures:
            report_lines.append("")
            report_lines.append("Common failure patterns:")
            
            # Group by failure type
            similarity_ranges = {
                "High similarity (0.7-0.8)": [e for e in failures if 0.7 <= e['location_match']['similarity'] < 0.8],
                "Medium similarity (0.5-0.7)": [e for e in failures if 0.5 <= e['location_match']['similarity'] < 0.7],
                "Low similarity (<0.5)": [e for e in failures if e['location_match']['similarity'] < 0.5],
            }
            
            for range_name, range_failures in similarity_ranges.items():
                if range_failures:
                    report_lines.append(f"  {range_name}: {len(range_failures)} cases")
            
            report_lines.append("")
            report_lines.append("Sample failures:")
            for i, failure in enumerate(failures[:10], 1):
                report_lines.append(f"  {i}. Row {failure['row']}")
                report_lines.append(f"     Extracted: {failure['extracted_location']}")
                report_lines.append(f"     Actual: {failure['actual_location']}")
                report_lines.append(f"     Similarity: {failure['location_match']['similarity']:.2f}")
                report_lines.append("")
    
    # Recommendations
    report_lines.append("RECOMMENDATIONS")
    report_lines.append("-" * 80)
    
    extraction_rate = stats['extraction_successful'] / stats['extraction_attempted'] if stats['extraction_attempted'] > 0 else 0
    match_rate = stats['location_string_matches'] / len(stats['detailed_evaluations']) if stats['detailed_evaluations'] else 0
    
    if extraction_rate < 0.95:
        report_lines.append("1. Improve extraction success rate:")
        report_lines.append("   - Add more regex patterns for edge cases")
        report_lines.append("   - Use LLM extraction for complex descriptions")
        report_lines.append("   - Handle multi-line descriptions better")
    
    if match_rate < 0.80:
        report_lines.append("2. Improve location string matching:")
        report_lines.append("   - Better normalization of administrative area names")
        report_lines.append("   - Handle spelling variations (e.g., Billinyang vs Billinang)")
        report_lines.append("   - Remove redundant words while preserving structure")
        report_lines.append("   - Use fuzzy matching for comparison")
    
    if stats['geocoding_successful'] == 0:
        report_lines.append("3. Enable geocoding:")
        report_lines.append("   - Ensure database is not locked")
        report_lines.append("   - Test geocoding separately to verify accuracy")
    
    report_lines.append("")
    report_lines.append("4. General improvements:")
    report_lines.append("   - Use LLM extraction for better accuracy on complex cases")
    report_lines.append("   - Implement feedback loop to learn from corrections")
    report_lines.append("   - Add validation rules for extracted locations")
    report_lines.append("   - Create confidence scoring for extractions")
    
    # Write report
    report_text = "\n".join(report_lines)
    
    with open(output_file, 'w') as f:
        f.write(report_text)
    
    print(f"\nReport saved to: {output_file}")
    print("\n" + report_text)
    
    return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate accuracy report")
    parser.add_argument(
        "--input",
        default="resources/casualty_tracking/casualty_matrix.xlsx",
        help="Input Excel file path"
    )
    parser.add_argument(
        "--output",
        default="resources/casualty_tracking/accuracy_report.txt",
        help="Output report file path"
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum number of rows to process"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=200,
        help="Number of rows to evaluate in detail"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Don't use LLM for extraction"
    )
    
    args = parser.parse_args()
    
    generate_report(
        args.input,
        args.output,
        max_rows=args.max_rows,
        use_llm=not args.no_llm,
        sample_size=args.sample_size
    )

