"""Basic tests for dalog package."""
import pytest
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_package_imports():
    """Test that the main package can be imported."""
    try:
        import dalog
        assert hasattr(dalog, '__version__')
        assert hasattr(dalog, 'DaLogApp')
    except ImportError as e:
        pytest.fail(f"Failed to import dalog package: {e}")


def test_version_exists():
    """Test that version is defined."""
    import dalog
    assert dalog.__version__ is not None
    assert isinstance(dalog.__version__, str)
    assert len(dalog.__version__) > 0


def test_cli_module_imports():
    """Test that CLI module can be imported."""
    try:
        from dalog import cli
        assert hasattr(cli, 'main')
        assert callable(cli.main)
    except ImportError as e:
        pytest.fail(f"Failed to import CLI module: {e}")


def test_app_module_imports():
    """Test that app module can be imported."""
    try:
        from dalog.app import DaLogApp
        assert DaLogApp is not None
    except ImportError as e:
        pytest.fail(f"Failed to import DaLogApp: {e}")


class TestConfig:
    """Test configuration functionality."""
    
    def test_config_module_imports(self):
        """Test that config module can be imported."""
        try:
            from dalog import config
        except ImportError as e:
            pytest.fail(f"Failed to import config module: {e}")


class TestCore:
    """Test core functionality."""
    
    def test_core_module_imports(self):
        """Test that core modules can be imported."""
        try:
            from dalog import core
        except ImportError as e:
            pytest.fail(f"Failed to import core module: {e}")


class TestWidgets:
    """Test widget functionality."""
    
    def test_widgets_module_imports(self):
        """Test that widgets module can be imported."""
        try:
            from dalog import widgets
        except ImportError as e:
            pytest.fail(f"Failed to import widgets module: {e}") 