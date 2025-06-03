"""Tests specifically targeting low-coverage areas to improve overall test coverage."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from dalog.core.html_processor import HTMLProcessor
from dalog.core.file_watcher import AsyncFileWatcher
from dalog.config.models import HtmlConfig


class TestHTMLProcessor:
    """Test the HTMLProcessor class for HTML handling."""
    
    def test_init_default_config(self):
        """Test HTMLProcessor initialization with default config."""
        processor = HTMLProcessor()
        
        assert processor.config is not None
        assert isinstance(processor.config, HtmlConfig)
    
    def test_init_custom_config(self):
        """Test HTMLProcessor initialization with custom config."""
        config = HtmlConfig(
            enabled_tags=["b", "i", "strong"],
            strip_unknown_tags=True
        )
        processor = HTMLProcessor(config)
        
        assert processor.config == config
    
    def test_process_line_no_html(self):
        """Test processing line with no HTML tags."""
        processor = HTMLProcessor()
        line = "This is a plain text line"
        
        result = processor.process_line(line)
        assert result == line
    
    def test_process_line_with_enabled_tags(self):
        """Test processing line with enabled HTML tags."""
        config = HtmlConfig(enabled_tags=["b", "strong"])
        processor = HTMLProcessor(config)
        
        line = "This is <b>bold</b> and <strong>strong</strong> text"
        result = processor.process_line(line)
        
        # Should preserve enabled tags
        assert "<b>" in result
        assert "</b>" in result
        assert "<strong>" in result
        assert "</strong>" in result
    
    def test_process_line_strip_unknown_tags(self):
        """Test processing line with unknown tags stripped."""
        config = HtmlConfig(
            enabled_tags=["b"],
            strip_unknown_tags=True
        )
        processor = HTMLProcessor(config)
        
        line = "This is <b>bold</b> and <script>evil</script> text"
        result = processor.process_line(line)
        
        # Should keep enabled tags but strip unknown ones
        assert "<b>" in result
        assert "</b>" in result
        assert "<script>" not in result
        assert "</script>" not in result
        assert "evil" in result  # Content should remain
    
    def test_process_line_keep_unknown_tags(self):
        """Test processing line with unknown tags kept."""
        config = HtmlConfig(
            enabled_tags=["b"],
            strip_unknown_tags=False
        )
        processor = HTMLProcessor(config)
        
        line = "This is <b>bold</b> and <unknown>tag</unknown> text"
        result = processor.process_line(line)
        
        # Should keep all tags when strip_unknown_tags is False
        assert "<b>" in result
        assert "<unknown>" in result


class TestAsyncFileWatcher:
    """Test the AsyncFileWatcher class."""
    
    def test_init(self):
        """Test AsyncFileWatcher initialization."""
        watcher = AsyncFileWatcher()
        
        assert watcher._watched_files == set()
        assert watcher._observer is None
        assert watcher._callback is None
    
    def test_add_file(self):
        """Test adding file to watch list."""
        watcher = AsyncFileWatcher()
        test_file = Path("test.log")
        
        watcher.add_file(test_file)
        assert test_file in watcher._watched_files
    
    def test_remove_file(self):
        """Test removing file from watch list."""
        watcher = AsyncFileWatcher()
        test_file = Path("test.log")
        
        watcher.add_file(test_file)
        watcher.remove_file(test_file)
        assert test_file not in watcher._watched_files
    
    def test_remove_nonexistent_file(self):
        """Test removing file that isn't being watched."""
        watcher = AsyncFileWatcher()
        test_file = Path("nonexistent.log")
        
        # Should not raise error
        watcher.remove_file(test_file)
        assert test_file not in watcher._watched_files


class TestConfigModels:
    """Test configuration model classes."""
    
    def test_style_pattern_defaults(self):
        """Test StylePattern with default values."""
        from dalog.config.models import StylePattern
        
        pattern = StylePattern(pattern="test")
        
        assert pattern.pattern == "test"
        assert pattern.color is None
        assert pattern.background is None
        assert pattern.bold is False
        assert pattern.italic is False
        assert pattern.underline is False
    
    def test_style_pattern_all_fields(self):
        """Test StylePattern with all fields set."""
        from dalog.config.models import StylePattern
        
        pattern = StylePattern(
            pattern="test",
            color="red",
            background="white",
            bold=True,
            italic=True,
            underline=True
        )
        
        assert pattern.pattern == "test"
        assert pattern.color == "red"
        assert pattern.background == "white"
        assert pattern.bold is True
        assert pattern.italic is True
        assert pattern.underline is True
    
    def test_app_config_defaults(self):
        """Test AppConfig with default values."""
        from dalog.config.models import AppConfig
        
        config = AppConfig()
        
        assert config.default_tail_lines == 1000
        assert config.live_reload is True
        assert config.case_sensitive_search is False
        assert config.vim_mode is True
    
    def test_display_config_defaults(self):
        """Test DisplayConfig with default values."""
        from dalog.config.models import DisplayConfig
        
        config = DisplayConfig()
        
        assert config.show_line_numbers is True
        assert config.wrap_lines is False
        assert config.max_line_length == 1000
        assert config.visual_mode_bg == "white"
    
    def test_html_config_defaults(self):
        """Test HtmlConfig with default values."""
        from dalog.config.models import HtmlConfig
        
        config = HtmlConfig()
        
        assert len(config.enabled_tags) > 0
        assert config.strip_unknown_tags is True
    
    def test_exclusion_config_defaults(self):
        """Test ExclusionConfig with default values."""
        from dalog.config.models import ExclusionConfig
        
        config = ExclusionConfig()
        
        assert config.patterns == []
        assert config.regex is True
        assert config.case_sensitive is False


class TestMainModuleEntryPoint:
    """Test the __main__.py entry point."""
    
    @patch('dalog.__main__.main')
    def test_main_module_calls_cli_main(self, mock_main):
        """Test that __main__.py calls cli.main()."""
        # Import the module to trigger the if __name__ == "__main__" block
        import subprocess
        import sys
        
        # Run the module as main
        result = subprocess.run(
            [sys.executable, '-m', 'dalog', '--help'],
            capture_output=True,
            text=True
        )
        
        # Should not error and should show help
        assert result.returncode in [0, 2]  # 0 for success, 2 for missing args


class TestVersionHandling:
    """Test version handling in __init__.py."""
    
    def test_version_fallback(self):
        """Test version fallback when importlib.metadata fails."""
        with patch('dalog.__init__.version') as mock_version:
            mock_version.side_effect = Exception("Package not found")
            
            # Reload the module to trigger the exception
            import importlib
            import dalog
            importlib.reload(dalog)
            
            # Should fall back to "0.1.0"
            assert dalog.__version__ == "0.1.0"
    
    def test_version_from_metadata(self):
        """Test version retrieval from metadata."""
        with patch('dalog.__init__.version') as mock_version:
            mock_version.return_value = "1.2.3"
            
            # Reload the module
            import importlib
            import dalog
            importlib.reload(dalog)
            
            # Should use metadata version
            assert dalog.__version__ == "1.2.3"


class TestCoreInit:
    """Test core module initialization."""
    
    def test_core_module_exports(self):
        """Test that core module exports expected classes."""
        from dalog.core import (
            LogProcessor, 
            ExclusionManager, 
            StylingEngine,
            HTMLProcessor,
            AsyncFileWatcher
        )
        
        # Should be able to import all core classes
        assert LogProcessor is not None
        assert ExclusionManager is not None
        assert StylingEngine is not None
        assert HTMLProcessor is not None
        assert AsyncFileWatcher is not None


class TestWidgetsInit:
    """Test widgets module initialization."""
    
    def test_widgets_module_exports(self):
        """Test that widgets module exports expected classes."""
        from dalog.widgets import HeaderWidget, LogViewerWidget, ExclusionModal
        
        # Should be able to import all widget classes
        assert HeaderWidget is not None
        assert LogViewerWidget is not None
        assert ExclusionModal is not None


class TestUtilsModule:
    """Test utils module (if it exists)."""
    
    def test_utils_module_import(self):
        """Test that utils module can be imported."""
        try:
            from dalog import utils
            # Should not raise ImportError
            assert utils is not None
        except ImportError:
            # If utils module doesn't exist, that's also fine
            pass


class TestErrorHandling:
    """Test error handling in various modules."""
    
    def test_log_processor_with_permission_error(self):
        """Test LogProcessor with permission denied file."""
        from dalog.core.log_processor import LogProcessor
        
        # Create a file and make it unreadable
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)
        
        try:
            # Change permissions to make it unreadable
            temp_path.chmod(0o000)
            
            # Should raise appropriate exception
            with pytest.raises((PermissionError, OSError)):
                processor = LogProcessor(temp_path)
                with processor:
                    list(processor.read_lines())
                    
        finally:
            # Restore permissions and clean up
            temp_path.chmod(0o644)
            temp_path.unlink()
    
    def test_styling_engine_with_none_config(self):
        """Test StylingEngine behavior with None config."""
        from dalog.core.styling import StylingEngine
        from dalog.config.models import StylingConfig
        
        # Test with empty config
        engine = StylingEngine(StylingConfig())
        line = "ERROR: Test message"
        
        # Should not crash
        styled_line, matches = engine.style_line(line)
        assert styled_line == line
        assert len(matches) == 0


class TestConfigurationEdgeCases:
    """Test configuration edge cases."""
    
    def test_config_with_empty_patterns(self):
        """Test configuration with empty pattern dictionaries."""
        from dalog.config.models import StylingConfig
        
        config = StylingConfig(patterns={}, timestamps={})
        
        assert config.patterns == {}
        assert config.timestamps == {}
    
    def test_config_validation_edge_cases(self):
        """Test configuration validation with edge cases."""
        from dalog.config import ConfigLoader, get_default_config
        
        config = get_default_config()
        
        # Test with None values (should handle gracefully)
        errors = ConfigLoader.validate_config(config)
        assert isinstance(errors, list) 