#!/usr/bin/env python3
"""
CLI tool for analyzing unmatched errors and discovering patterns

Usage:
    python scripts/analyze_unmatched_errors.py --min-frequency 3 --output suggested_patterns.py
"""

import argparse
import sys
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent))

from regression_jira_mcp.pattern_learner import PatternLearner


def main():
    parser = argparse.ArgumentParser(description='Analyze unmatched errors and suggest new patterns')
    parser.add_argument(
        '--min-frequency',
        type=int,
        default=3,
        help='Minimum occurrence count (default: 3)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='suggested_patterns.py',
        help='Output filename'
    )
    parser.add_argument(
        '--max-suggestions',
        type=int,
        default=20,
        help='Maximum number of suggestions'
    )
    
    args = parser.parse_args()
    
    # Analyze
    print("Analyzing unmatched errors...")
    learner = PatternLearner()
    result = learner.analyze_patterns(
        min_frequency=args.min_frequency,
        max_suggestions=args.max_suggestions
    )
    
    if result['status'] != 'success':
        print(f"Error: {result.get('message', 'Analysis failed')}")
        return 1
    
    # Display statistics
    stats = result['statistics']
    print("\nStatistics:")
    print(f"  Total records: {stats['total_records']}")
    print(f"  Total error lines: {stats['total_error_lines']}")
    print(f"  Unique tests: {stats['unique_tests']}")
    date_range = stats.get('date_range', {})
    if date_range:
        print(f"  Date range: {date_range.get('first', 'N/A')} to {date_range.get('last', 'N/A')}")
    print()
    
    # Display suggestions
    suggestions = result['suggested_patterns']
    print(f"Found {len(suggestions)} candidate patterns:")
    print()
    
    for i, sugg in enumerate(suggestions[:10], 1):
        print(f"{i}. {sugg['pattern_string']}")
        print(f"   Regex: {sugg['regex']}")
        print(f"   Frequency: {sugg['frequency']} | Confidence: {sugg['confidence']}")
        if sugg.get('examples'):
            print(f"   Example: {sugg['examples'][0][:80]}...")
        print()
    
    # Export code
    if args.output:
        code = learner.export_as_python_code(suggestions)
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"Exported to: {output_path}")
        print()
        print("Next steps:")
        print("  1. Review patterns in suggested_patterns.py")
        print("  2. Test regex accuracy")
        print("  3. Add approved patterns to error_patterns.py")
        print("  4. Restart MCP server")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

