"""Simple test runner for widget tests without requiring pytest-textual-snapshot."""
import pytest
import sys
from pathlib import Path

def run_widget_tests():
    """Run widget tests with appropriate configuration."""
    test_dir = Path(__file__).parent
    
    # Configure pytest for asyncio
    pytest_args = [
        str(test_dir),
        "-v",
        "--asyncio-mode=auto",
        "-x",  # Stop on first failure
        "--tb=short"  # Short traceback format
    ]
    
    # Skip snapshot tests if pytest-textual-snapshot not available
    try:
        import pytest_textual_snapshot
    except ImportError:
        pytest_args.extend(["-k", "not snapshot"])
        print("⚠️  Skipping snapshot tests (pytest-textual-snapshot not installed)")
    
    print("🧪 Running dalog widget tests...")
    result = pytest.main(pytest_args)
    
    if result == 0:
        print("✅ All widget tests passed!")
    else:
        print("❌ Some tests failed")
    
    return result

if __name__ == "__main__":
    sys.exit(run_widget_tests())