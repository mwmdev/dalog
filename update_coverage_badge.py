#!/usr/bin/env python3
"""
Script to update the coverage badge in README.md with the actual coverage percentage.
Run this after running pytest --cov to get the latest coverage.
"""

import re
import subprocess
import sys
from pathlib import Path


def get_coverage_percentage():
    """Run pytest with coverage and extract the percentage."""
    try:
        # Run pytest with coverage
        result = subprocess.run(
            ["nix-shell", "--run", "pytest --cov --cov-report=term"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        # Extract coverage percentage from output
        # Look for pattern like "TOTAL                                           6413   1125    82%"
        pattern = r"TOTAL\s+\d+\s+\d+\s+(\d+)%"
        match = re.search(pattern, result.stdout)
        
        if match:
            return int(match.group(1))
        else:
            print("Could not find coverage percentage in output")
            print("STDOUT:", result.stdout[-500:])  # Last 500 chars
            print("STDERR:", result.stderr[-500:])  # Last 500 chars
            return None
            
    except Exception as e:
        print(f"Error running coverage: {e}")
        return None


def get_badge_color(percentage):
    """Get badge color based on coverage percentage."""
    if percentage >= 90:
        return "brightgreen"
    elif percentage >= 80:
        return "green"
    elif percentage >= 70:
        return "yellowgreen"
    elif percentage >= 60:
        return "yellow"
    elif percentage >= 50:
        return "orange"
    else:
        return "red"


def update_readme_badge(percentage):
    """Update the coverage badge in README.md."""
    readme_path = Path(__file__).parent / "README.md"
    
    if not readme_path.exists():
        print("README.md not found")
        return False
        
    # Read README
    content = readme_path.read_text()
    
    # Find and replace coverage badge
    color = get_badge_color(percentage)
    new_badge = f"![Coverage](https://img.shields.io/badge/coverage-{percentage}%25-{color})"
    
    # Replace existing coverage badge
    pattern = r"!\[Coverage\]\(https://img\.shields\.io/badge/coverage-[^)]+\)"
    
    if re.search(pattern, content):
        updated_content = re.sub(pattern, new_badge, content)
    else:
        print("Existing coverage badge not found in README.md")
        return False
    
    # Write back to file
    readme_path.write_text(updated_content)
    print(f"Updated coverage badge to {percentage}% ({color})")
    return True


def main():
    """Main function."""
    print("Getting coverage percentage...")
    percentage = get_coverage_percentage()
    
    if percentage is None:
        print("Failed to get coverage percentage")
        sys.exit(1)
    
    print(f"Coverage: {percentage}%")
    
    if update_readme_badge(percentage):
        print("Successfully updated README.md coverage badge")
    else:
        print("Failed to update README.md")
        sys.exit(1)


if __name__ == "__main__":
    main()