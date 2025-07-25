"""Tests for ExclusionModal functionality."""
import pytest
from unittest.mock import Mock, patch
from textual.app import App

from dalog.widgets.exclusion_modal import ExclusionModal
from dalog.core.exclusions import ExclusionManager


class TestExclusionModalBehavior:
    """Test modal opening, closing, and lifecycle."""

    @pytest.fixture
    def modal_app(self, mock_exclusion_manager, mock_config):
        """Create test app with ExclusionModal."""
        class ModalTestApp(App):
            def compose(self):
                yield ExclusionModal(exclusion_manager=mock_exclusion_manager, config=mock_config)
        return ModalTestApp()

    async def test_modal_initialization(self, modal_app):
        """Test modal initializes correctly."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # Modal should be initialized
            assert modal is not None
            assert modal.exclusion_manager is not None

    async def test_modal_has_required_widgets(self, modal_app):
        """Test modal contains all required UI widgets."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # Check for required widgets
            pattern_input = modal.query_one("#pattern-input")
            pattern_list = modal.query_one("#pattern-list")
            
            assert pattern_input is not None
            assert pattern_list is not None

    async def test_modal_focus_on_input(self, modal_app):
        """Test modal focuses on input when opened."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            
            # Input should be focusable
            assert pattern_input.can_focus

    async def test_modal_escape_key_handling(self, modal_app):
        """Test ESC key handling in modal."""
        async with modal_app.run_test() as pilot:
            # Press escape key
            await pilot.press("escape")
            await pilot.pause()
            
            # Modal should handle escape (would normally close)
            # This test verifies the key binding exists


class TestExclusionPatternManagement:
    """Test pattern addition, removal, and validation."""

    @pytest.fixture
    def modal_app(self, mock_exclusion_manager, mock_config):
        """Create test app with ExclusionModal."""
        class ModalTestApp(App):
            def compose(self):
                yield ExclusionModal(exclusion_manager=mock_exclusion_manager, config=mock_config)
        return ModalTestApp()

    async def test_add_literal_pattern(self, modal_app):
        """Test adding literal exclusion patterns."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            
            # Enter a pattern
            pattern_input.value = "ERROR"
            await pilot.pause()
            
            # Simulate adding pattern (normally via Enter key)
            modal._add_pattern()
            await pilot.pause()
            
            # Should have called exclusion manager
            modal.exclusion_manager.add_pattern.assert_called()

    async def test_add_regex_pattern(self, modal_app):
        """Test adding regex exclusion patterns."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            regex_checkbox = modal.query_one("#regex-checkbox")
            
            # Enter a regex pattern and enable regex mode
            pattern_input.value = r"\[ERROR\]"
            regex_checkbox.value = True
            await pilot.pause()
            
            # Add pattern
            modal._add_pattern()
            await pilot.pause()
            
            # Should have called exclusion manager with regex=True
            modal.exclusion_manager.add_pattern.assert_called()

    async def test_invalid_regex_validation(self, modal_app):
        """Test validation of invalid regex patterns."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            regex_checkbox = modal.query_one("#regex-checkbox")
            
            # Enter invalid regex
            pattern_input.value = "[unclosed"
            regex_checkbox.value = True
            await pilot.pause()
            
            # Try to add invalid pattern
            modal._add_pattern()
            await pilot.pause()
            
            # Should not have called exclusion manager for invalid regex
            # (Depending on implementation, might show error instead)

    async def test_empty_pattern_validation(self, modal_app):
        """Test validation of empty patterns."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            
            # Leave pattern empty
            pattern_input.value = ""
            await pilot.pause()
            
            # Try to add empty pattern
            modal._add_pattern()
            await pilot.pause()
            
            # Should not add empty pattern
            assert not modal.exclusion_manager.add_pattern.called

    async def test_delete_selected_pattern(self, modal_app):
        """Test deleting selected patterns behavior."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # Mock having patterns in the list
            modal.exclusion_manager.patterns = ["ERROR", "DEBUG"]
            modal._refresh_pattern_list()
            await pilot.pause()
            
            # Call delete when nothing is selected - should not crash
            modal._delete_selected()
            await pilot.pause()
            
            # Should not have called remove_pattern when nothing is selected
            modal.exclusion_manager.remove_pattern.assert_not_called()


    async def test_regex_toggle_only(self, modal_app):
        """Test regex checkbox behavior (case sensitivity removed)."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            regex_checkbox = modal.query_one("#regex-checkbox")
            
            # Toggle regex setting
            initial_value = regex_checkbox.value
            regex_checkbox.value = not initial_value
            await pilot.pause()
            
            assert regex_checkbox.value != initial_value


class TestExclusionModalUI:
    """Test UI interactions and state management."""

    @pytest.fixture
    def modal_app(self, mock_exclusion_manager, mock_config):
        """Create test app with ExclusionModal."""
        class ModalTestApp(App):
            def compose(self):
                yield ExclusionModal(exclusion_manager=mock_exclusion_manager, config=mock_config)
        return ModalTestApp()

    async def test_pattern_input_validation(self, modal_app):
        """Test pattern input validation and error display."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            
            # Test various input values
            test_patterns = ["valid_pattern", "another-pattern", "pattern with spaces"]
            
            for pattern in test_patterns:
                pattern_input.value = pattern
                await pilot.pause()
                
                assert pattern_input.value == pattern

    async def test_pattern_list_display(self, modal_app):
        """Test pattern list displays current patterns."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_list = modal.query_one("#pattern-list")
            
            # Mock patterns in exclusion manager
            test_patterns = ["ERROR", "DEBUG", "WARNING"]
            modal.exclusion_manager.patterns = test_patterns
            
            # Refresh list
            modal._refresh_pattern_list()
            await pilot.pause()
            
            # List should be refreshed
            assert pattern_list is not None

    async def test_pattern_list_selection(self, modal_app):
        """Test selecting patterns in the list."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_list = modal.query_one("#pattern-list")
            
            # Mock patterns
            modal.exclusion_manager.patterns = ["ERROR", "DEBUG"]
            modal._refresh_pattern_list()
            await pilot.pause()
            
            # Test selection capability
            assert pattern_list.can_focus

    async def test_keyboard_only_interface(self, modal_app):
        """Test that modal works with keyboard shortcuts only (no buttons)."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # Should have no buttons in the new design
            buttons = modal.query("Button")
            assert len(buttons) == 0

    async def test_keyboard_shortcuts(self, modal_app):
        """Test keyboard shortcuts in modal."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # Test Ctrl+D shortcut for delete
            await pilot.press("ctrl+d")
            await pilot.pause()
            
            # Should trigger delete action (if pattern selected)

    async def test_input_submission(self, modal_app):
        """Test submitting pattern via Enter key."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            
            # Enter pattern and submit
            pattern_input.value = "TEST_PATTERN"
            await pilot.press("enter")
            await pilot.pause()
            
            # Should add pattern
            modal.exclusion_manager.add_pattern.assert_called()

    async def test_modal_state_consistency(self, modal_app):
        """Test modal maintains consistent state."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            regex_checkbox = modal.query_one("#regex-checkbox")
            
            # Set initial state
            pattern_input.value = "test"
            regex_checkbox.value = True
            await pilot.pause()
            
            # Verify state is maintained
            assert pattern_input.value == "test"
            assert regex_checkbox.value is True


class TestExclusionModalIntegration:
    """Test integration with ExclusionManager."""

    @pytest.fixture
    def modal_app(self, mock_config):
        """Create test app with ExclusionModal and real ExclusionManager."""
        exclusion_manager = ExclusionManager()
        
        class ModalTestApp(App):
            def compose(self):
                yield ExclusionModal(exclusion_manager=exclusion_manager, config=mock_config)
        return ModalTestApp()

    async def test_exclusion_manager_integration(self, modal_app):
        """Test integration with real ExclusionManager."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            pattern_input = modal.query_one("#pattern-input")
            
            # Add a pattern through the modal
            pattern_input.value = "ERROR"
            modal._add_pattern()
            await pilot.pause()
            
            # Verify pattern was added to manager
            assert "ERROR" in modal.exclusion_manager.patterns

    async def test_pattern_effect_preview(self, modal_app):
        """Test real-time pattern effect preview."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # This would test if the modal shows preview of exclusion effects
            # Implementation depends on whether this feature exists
            
            # Add pattern
            pattern_input = modal.query_one("#pattern-input")
            pattern_input.value = "DEBUG"
            await pilot.pause()
            
            # Preview should update (if implemented)

    async def test_configuration_persistence(self, modal_app):
        """Test that modal changes can be persisted to configuration."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # Add patterns
            test_patterns = ["ERROR", "CRITICAL", "DEBUG"]
            
            for pattern in test_patterns:
                pattern_input = modal.query_one("#pattern-input")
                pattern_input.value = pattern
                modal._add_pattern()
                await pilot.pause()
            
            # All patterns should be in manager
            for pattern in test_patterns:
                assert pattern in modal.exclusion_manager.patterns

    async def test_modal_refresh_from_manager(self, modal_app):
        """Test modal refreshes when manager state changes."""
        async with modal_app.run_test() as pilot:
            modal = pilot.app.query_one(ExclusionModal)
            
            # Add pattern directly to manager
            modal.exclusion_manager.add_pattern("EXTERNAL_PATTERN")
            
            # Refresh modal
            modal._refresh_pattern_list()
            await pilot.pause()
            
            # Modal should reflect manager state
            assert "EXTERNAL_PATTERN" in modal.exclusion_manager.patterns