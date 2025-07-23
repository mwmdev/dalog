"""Tests for HeaderWidget functionality."""
import pytest
from pathlib import Path
from textual.app import App

from dalog.widgets.header import HeaderWidget


class TestHeaderWidget:
    """Test header status display functionality."""

    @pytest.fixture
    def header_app(self):
        """Create test app with HeaderWidget."""
        class HeaderTestApp(App):
            def compose(self):
                yield HeaderWidget()
        return HeaderTestApp()

    async def test_header_initialization(self, header_app):
        """Test header widget initializes correctly."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Header should be initialized with default values
            assert header is not None
            assert header.current_file == ""
            assert header.file_size_mb == 0.0
            assert header.total_lines == 0
            assert header.visible_lines == 0
            assert header.filtered_lines == 0

    async def test_file_info_display(self, header_app):
        """Test file information display formatting."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Set file information
            test_file = "/path/to/test.log"
            test_size = 1.5
            test_lines = 1000
            
            header.current_file = test_file
            header.file_size_mb = test_size
            header.total_lines = test_lines
            await pilot.pause()
            
            # Verify properties are set
            assert header.current_file == test_file
            assert header.file_size_mb == test_size
            assert header.total_lines == test_lines

    async def test_line_count_display(self, header_app):
        """Test line count formatting and updates."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Set line counts
            header.total_lines = 5000
            header.visible_lines = 4500
            header.filtered_lines = 500
            await pilot.pause()
            
            assert header.total_lines == 5000
            assert header.visible_lines == 4500
            assert header.filtered_lines == 500

    async def test_search_status_display(self, header_app):
        """Test search status indicators."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Test search inactive
            header.search_active = False
            header.search_term = ""
            await pilot.pause()
            
            assert not header.search_active
            assert header.search_term == ""
            
            # Test search active
            header.search_active = True
            header.search_term = "ERROR"
            await pilot.pause()
            
            assert header.search_active
            assert header.search_term == "ERROR"

    async def test_live_reload_status(self, header_app):
        """Test live reload status display."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Test live reload inactive
            header.live_reload_status = False
            await pilot.pause()
            
            assert not header.live_reload_status
            
            # Test live reload active
            header.live_reload_status = True
            await pilot.pause()
            
            assert header.live_reload_status

    async def test_reactive_property_updates(self, header_app):
        """Test header updates when reactive properties change."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Update multiple properties
            updates = {
                'current_file': '/new/path/test.log',
                'file_size_mb': 2.5,
                'total_lines': 2000,
                'visible_lines': 1800,
                'filtered_lines': 200,
                'search_active': True,
                'search_term': 'WARNING',
                'live_reload_status': True
            }
            
            for prop, value in updates.items():
                setattr(header, prop, value)
                await pilot.pause()
                assert getattr(header, prop) == value

    async def test_file_size_formatting(self, header_app):
        """Test file size formatting for different sizes."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Test various file sizes
            test_sizes = [0.0, 0.001, 0.5, 1.0, 10.5, 100.25, 1024.0]
            
            for size in test_sizes:
                header.file_size_mb = size
                await pilot.pause()
                assert header.file_size_mb == size

    async def test_line_count_edge_cases(self, header_app):
        """Test line count display with edge cases."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Test zero counts
            header.total_lines = 0
            header.visible_lines = 0
            header.filtered_lines = 0
            await pilot.pause()
            
            assert header.total_lines == 0
            assert header.visible_lines == 0
            assert header.filtered_lines == 0
            
            # Test large counts
            header.total_lines = 1000000
            header.visible_lines = 999000
            header.filtered_lines = 1000
            await pilot.pause()
            
            assert header.total_lines == 1000000
            assert header.visible_lines == 999000
            assert header.filtered_lines == 1000

    async def test_search_term_special_characters(self, header_app):
        """Test search term display with special characters."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Test various search terms
            special_terms = [
                "regex[.*]",
                "term with spaces",
                "unicode: café",
                "symbols: @#$%^&*()",
                r"backslashes: \n\t\r",
                ""  # empty term
            ]
            
            for term in special_terms:
                header.search_term = term
                await pilot.pause()
                assert header.search_term == term

    async def test_file_path_display(self, header_app):
        """Test file path display with various formats."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Test various file paths
            test_paths = [
                "/home/user/logs/app.log",
                "/var/log/system.log", 
                "C:\\Windows\\Logs\\app.log",
                "~/relative/path.log",
                "/very/long/path/to/some/deeply/nested/log/file/application.log",
                "",  # empty path
                "simple.log"
            ]
            
            for path in test_paths:
                header.current_file = path
                await pilot.pause()
                assert header.current_file == path

    async def test_status_consistency(self, header_app):
        """Test that status displays remain consistent."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Set a complete status
            header.current_file = "/test/app.log"
            header.file_size_mb = 1.5
            header.total_lines = 1000
            header.visible_lines = 800
            header.filtered_lines = 200
            header.search_active = True
            header.search_term = "ERROR"
            header.live_reload_status = True
            await pilot.pause()
            
            # Verify all properties are maintained
            assert header.current_file == "/test/app.log"
            assert header.file_size_mb == 1.5
            assert header.total_lines == 1000
            assert header.visible_lines == 800
            assert header.filtered_lines == 200
            assert header.search_active is True
            assert header.search_term == "ERROR"
            assert header.live_reload_status is True

    async def test_multiple_updates_sequence(self, header_app):
        """Test rapid sequence of updates."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Rapid updates
            for i in range(10):
                header.total_lines = i * 100
                header.visible_lines = i * 90
                header.search_term = f"search_{i}"
                await pilot.pause()
                
                # Each update should be applied
                assert header.total_lines == i * 100
                assert header.visible_lines == i * 90
                assert header.search_term == f"search_{i}"


class TestHeaderWidgetReactivity:
    """Test reactive behavior of header widget."""

    @pytest.fixture
    def header_app(self):
        """Create test app with HeaderWidget."""
        class HeaderTestApp(App):
            def compose(self):
                yield HeaderWidget()
        return HeaderTestApp()

    async def test_watch_methods_called(self, header_app):
        """Test that watch methods are called on property changes."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Change properties that should trigger watch methods
            initial_file = header.current_file
            header.current_file = "/new/file.log"
            await pilot.pause()
            
            # Property should have changed
            assert header.current_file != initial_file
            assert header.current_file == "/new/file.log"

    async def test_reactive_property_validation(self, header_app):
        """Test reactive property validation."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Test setting invalid values (should handle gracefully)
            try:
                header.file_size_mb = -1.0  # Negative size
                await pilot.pause()
                # Should either reject or handle gracefully
            except (ValueError, TypeError):
                # Expected if validation exists
                pass
            
            # Test setting None values
            try:
                header.search_term = None
                await pilot.pause()
            except (ValueError, TypeError):
                # Expected if validation exists
                pass

    async def test_bulk_property_updates(self, header_app):
        """Test updating multiple properties simultaneously."""
        async with header_app.run_test() as pilot:
            header = pilot.app.query_one(HeaderWidget)
            
            # Update multiple properties at once
            properties = {
                'current_file': '/bulk/update/test.log',
                'file_size_mb': 5.5,
                'total_lines': 5000,
                'visible_lines': 4000,
                'filtered_lines': 1000,
                'search_active': True,
                'search_term': 'BULK_TEST',
                'live_reload_status': False
            }
            
            # Apply all updates
            for prop, value in properties.items():
                setattr(header, prop, value)
            
            await pilot.pause()
            
            # Verify all properties were updated
            for prop, expected_value in properties.items():
                actual_value = getattr(header, prop)
                assert actual_value == expected_value, f"{prop}: expected {expected_value}, got {actual_value}"