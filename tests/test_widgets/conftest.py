"""Test fixtures for widget testing."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Any, Dict, List

from dalog.config.models import KeyBindings, DaLogConfig
from dalog.core.log_processor import LogProcessor
from dalog.core.exclusions import ExclusionManager
from dalog.core.styling import StylingEngine


@pytest.fixture
def mock_config():
    """Provides a test configuration with default keybindings."""
    return DaLogConfig(
        keybindings=KeyBindings(),
        theme="gruvbox-dark",
        live_reload=True,
        tail_lines=1000
    )


@pytest.fixture
def sample_log_content():
    """Provides sample log content for testing."""
    return """2024-01-20T08:00:00.123Z [INFO] Application starting
2024-01-20T08:00:01.234Z [DEBUG] Loading configuration
2024-01-20T08:00:02.345Z [WARNING] High memory usage: 85%
2024-01-20T08:00:03.456Z [ERROR] Database connection failed
2024-01-20T08:00:04.567Z [CRITICAL] System shutdown imminent
2024-01-20T08:00:05.678Z [INFO] Recovery successful
2024-01-20T08:00:06.789Z [DEBUG] Background task completed
2024-01-20T08:00:07.890Z [INFO] User login: john.doe@example.com
2024-01-20T08:00:08.901Z [WARNING] Security alert: multiple failed attempts
2024-01-20T08:00:09.012Z [ERROR] Payment processing failed"""


@pytest.fixture
def large_log_content():
    """Provides large log content for performance testing."""
    lines = []
    for i in range(1000):
        level = ["INFO", "DEBUG", "WARNING", "ERROR"][i % 4]
        lines.append(f"2024-01-20T08:00:{i:02d}.{i:03d}Z [{level}] Log entry {i}")
    return "\n".join(lines)


@pytest.fixture
def temp_log_file(sample_log_content):
    """Creates a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write(sample_log_content)
        f.flush()
        yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def large_temp_log_file(large_log_content):
    """Creates a large temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write(large_log_content)
        f.flush()
        yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def mock_log_processor(sample_log_content):
    """Mock LogProcessor with test data."""
    from dalog.core.log_processor import LogLine
    processor = Mock(spec=LogProcessor)
    lines = sample_log_content.split('\n')
    
    # Create LogLine objects for realistic mock data
    log_lines = []
    for i, line in enumerate(lines):
        log_line = LogLine(
            line_number=i + 1,
            content=line,
            byte_offset=0,  # Simplified for testing
            original_content=line
        )
        log_lines.append(log_line)
    
    # Fix method names to match actual interface
    processor.read_lines.return_value = iter(log_lines)
    processor.search_lines.return_value = iter(log_lines)
    processor.get_file_info.return_value = {
        "path": "/test/mock.log",
        "size_mb": 0.001,
        "total_lines": len(lines)
    }
    processor.file_path = Path("/test/mock.log")
    processor.total_lines = len(lines)
    return processor


@pytest.fixture
def mock_exclusion_manager():
    """Mock ExclusionManager for testing."""
    manager = Mock(spec=ExclusionManager)
    manager.should_exclude.return_value = False
    manager.patterns = []
    manager.add_pattern = Mock()
    manager.remove_pattern = Mock(return_value=True)
    manager.clear_patterns = Mock()
    manager.get_patterns_list.return_value = []
    manager.validate_pattern.return_value = (True, None)  # (is_valid, error_message)
    return manager


@pytest.fixture
def mock_styling_engine():
    """Mock StylingEngine for testing."""
    engine = Mock(spec=StylingEngine)
    engine.apply_styling.side_effect = lambda text: f"[styled]{text}[/styled]"
    return engine


@pytest.fixture
def mock_pyperclip():
    """Mock pyperclip for clipboard testing."""
    with patch('dalog.widgets.log_viewer.pyperclip') as mock:
        mock.copy = Mock()
        mock.paste = Mock(return_value="test clipboard content")
        yield mock


@pytest.fixture
def widget_test_app():
    """Factory for creating test apps with single widgets."""
    from textual.app import App
    
    def _create_app(widget_class, **widget_kwargs):
        class TestApp(App):
            def compose(self):
                yield widget_class(**widget_kwargs)
        return TestApp()
    return _create_app


@pytest.fixture
def mock_file_watcher():
    """Mock file watcher for testing."""
    with patch('dalog.core.file_watcher.AsyncFileWatcher') as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance


# Additional test data fixtures

@pytest.fixture
def unicode_log_content():
    """Unicode and international text log content."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "widget_test_data" / "unicode_log.txt"
    if fixture_path.exists():
        return fixture_path.read_text(encoding='utf-8')
    return "2024-01-20T08:00:00.123Z [INFO] Unicode test: café ☕"


@pytest.fixture
def malformed_log_content():
    """Malformed log entries for error handling tests.""" 
    fixture_path = Path(__file__).parent.parent / "fixtures" / "widget_test_data" / "malformed_log.txt"
    if fixture_path.exists():
        return fixture_path.read_text(encoding='utf-8', errors='ignore')
    return "[MALFORMED] No timestamp\n2024-INVALID-DATE [ERROR] Bad format"


@pytest.fixture
def multiline_log_content():
    """Log content with multiline entries."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "widget_test_data" / "multiline_log.txt"
    if fixture_path.exists():
        return fixture_path.read_text(encoding='utf-8')
    return "2024-01-20T08:00:00.123Z [ERROR] Stack trace:\n    at line 1\n    at line 2"


@pytest.fixture
def regex_test_log_content():
    """Log content designed for regex pattern testing."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "widget_test_data" / "regex_test_log.txt"
    if fixture_path.exists():
        return fixture_path.read_text(encoding='utf-8')
    return "2024-01-20T08:00:00.123Z [INFO] Email: user@domain.com\n2024-01-20T08:00:01.234Z [ERROR] IP: 192.168.1.1"


@pytest.fixture
def performance_log_content():
    """Large log content for performance testing."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "widget_test_data" / "large_log.txt"
    if fixture_path.exists():
        return fixture_path.read_text(encoding='utf-8')
    # Fallback: generate small test data
    lines = []
    for i in range(100):
        lines.append(f"2024-01-20T08:00:{i:02d}.123Z [INFO] Performance test line {i}")
    return "\n".join(lines)


@pytest.fixture
def test_config_file():
    """Path to test configuration file."""
    return Path(__file__).parent.parent / "fixtures" / "mock_configs" / "test_keybindings.toml"


@pytest.fixture
def custom_config_file():
    """Path to custom configuration file."""
    return Path(__file__).parent.parent / "fixtures" / "mock_configs" / "custom_keybindings.toml"