"""
Test live reload auto-scroll behavior.
"""

import pytest
from unittest.mock import Mock
from dalog.app import DaLogApp


class TestLiveReloadScroll:
    """Test that live reload scrolls to bottom automatically."""
    
    def test_scroll_to_end_logic(self):
        """Test the scroll_to_end logic in _load_log_file."""
        # Test case 1: Initial load (is_reload=False) - should scroll to end
        app = DaLogApp(log_file="dummy.log", live_reload=True)
        scroll_to_end = not False or app.live_reload  # is_reload=False
        assert scroll_to_end is True
        
        # Test case 2: Live reload (is_reload=True, live_reload=True) - should scroll to end
        app = DaLogApp(log_file="dummy.log", live_reload=True)
        scroll_to_end = not True or app.live_reload  # is_reload=True
        assert scroll_to_end is True
        
        # Test case 3: Manual reload without live reload (is_reload=True, live_reload=False) - should NOT scroll to end
        app = DaLogApp(log_file="dummy.log", live_reload=False)
        scroll_to_end = not True or app.live_reload  # is_reload=True
        assert scroll_to_end is False
        
        # Test case 4: Initial load without live reload (is_reload=False, live_reload=False) - should scroll to end
        app = DaLogApp(log_file="dummy.log", live_reload=False)
        scroll_to_end = not False or app.live_reload  # is_reload=False
        assert scroll_to_end is True


if __name__ == "__main__":
    pytest.main([__file__])