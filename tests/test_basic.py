"""Basic tests for dalog package."""
import pytest
import sys
import tempfile
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_package_functionality():
    """Comprehensive test of core package functionality and imports."""
    # Test main package imports and attributes
    import dalog
    assert hasattr(dalog, '__version__')
    assert hasattr(dalog, 'create_dalog_app')
    assert isinstance(dalog.__version__, str)
    assert len(dalog.__version__) > 0
    
    # Test CLI functionality
    from dalog import cli
    assert hasattr(cli, 'main')
    assert callable(cli.main)
    
    # Test core module classes can be imported and instantiated
    from dalog.core import LogProcessor, ExclusionManager, StylingEngine
    from dalog.config import get_default_config
    
    # Test that core classes are callable
    assert callable(LogProcessor)
    assert callable(ExclusionManager)
    assert callable(StylingEngine)
    
    # Test ExclusionManager basic functionality
    exclusion_manager = ExclusionManager(patterns=["DEBUG:"], is_regex=False)
    assert exclusion_manager.should_exclude("DEBUG: test message")
    assert not exclusion_manager.should_exclude("INFO: test message")
    
    # Test StylingEngine basic functionality
    config = get_default_config()
    styling_engine = StylingEngine(config.styling)
    styled = styling_engine.apply_styling("ERROR: test message")
    assert styled.plain == "ERROR: test message"
    
    # Test config loading
    from dalog.config import ConfigLoader
    default_config = get_default_config()
    assert default_config is not None
    errors = ConfigLoader.validate_config(default_config)
    assert len(errors) == 0  # Default config should be valid
    
    # Test widgets can be imported
    from dalog.widgets import HeaderWidget, LogViewerWidget, ExclusionModal
    assert HeaderWidget is not None
    assert LogViewerWidget is not None
    assert ExclusionModal is not None


def test_app_instantiation():
    """Test that the main DaLogApp can be instantiated with a real file."""
    from dalog.app import create_dalog_app
    
    # Create a temporary log file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write("2024-01-15 10:30:00 INFO Application started\n")
        f.write("2024-01-15 10:30:01 ERROR Connection failed\n")
        temp_path = Path(f.name)
    
    try:
        # Should be able to create app instance
        DaLogApp = create_dalog_app()
        app = DaLogApp(log_file=str(temp_path))
        assert app is not None
        assert hasattr(app, 'run')
        
        # Test that app has required attributes
        assert hasattr(app, 'log_file')
        assert str(app.log_file) == str(temp_path)
        
    finally:
        temp_path.unlink()


def test_log_processor_basic_functionality():
    """Test LogProcessor with actual file processing."""
    from dalog.core.log_processor import LogProcessor
    
    # Create test log file
    content = """2024-01-15 10:30:00 INFO Starting application
2024-01-15 10:30:01 DEBUG Loading config
2024-01-15 10:30:02 ERROR Connection failed"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)
    
    try:
        processor = LogProcessor(temp_path)
        with processor:
            lines = list(processor.read_lines())
            
        assert len(lines) == 3
        assert "Starting application" in lines[0].content
        assert "Loading config" in lines[1].content
        assert "Connection failed" in lines[2].content
        
        # Test file info
        with processor:
            file_info = processor.get_file_info()
        assert file_info['lines'] == 3
        assert file_info['size'] > 0
        
    finally:
        temp_path.unlink() 