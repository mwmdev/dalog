"""Tests for configuration loading functionality."""
import pytest
import tempfile
import toml
from pathlib import Path
from unittest.mock import patch, mock_open

from dalog.config import ConfigLoader, DaLogConfig, get_default_config


class TestConfigLoader:
    """Test the ConfigLoader class."""
    
    def test_load_default_config_when_no_file_exists(self):
        """Test loading default config when no configuration file exists."""
        with patch.object(Path, 'exists', return_value=False):
            config = ConfigLoader.load()
            
        assert isinstance(config, DaLogConfig)
        assert config.app.default_tail_lines == 1000
        assert config.app.live_reload is True
        assert config.keybindings.search == "/"
        assert config.display.show_line_numbers is True
    
    @pytest.mark.ci_skip
    def test_load_config_from_explicit_path(self):
        """Test loading config from explicitly provided path."""
        config_data = {
            "app": {
                "default_tail_lines": 500,
                "live_reload": False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = ConfigLoader.load(config_path)
            assert config.app.default_tail_lines == 500
            assert config.app.live_reload is False
        finally:
            Path(config_path).unlink()
    
    def test_load_config_with_invalid_path(self):
        """Test loading config with non-existent path."""
        config = ConfigLoader.load("/non/existent/path.toml")
        # Should fall back to default config
        assert isinstance(config, DaLogConfig)
        assert config.app.default_tail_lines == 1000
    
    def test_load_config_with_malformed_toml(self):
        """Test loading config with malformed TOML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("invalid toml content [[[")
            config_path = f.name
        
        try:
            config = ConfigLoader.load(config_path)
            # Should fall back to default config
            assert isinstance(config, DaLogConfig)
        finally:
            Path(config_path).unlink()
    
    def test_validate_config_with_valid_data(self):
        """Test config validation with valid data."""
        config = get_default_config()
        errors = ConfigLoader.validate_config(config)
        assert len(errors) == 0
    
    def test_validate_config_with_invalid_pattern(self):
        """Test config validation with invalid regex pattern."""
        config = get_default_config()
        
        # We need to bypass the StylePattern validation to create an invalid pattern
        # We'll do this by creating a mock StylePattern-like object
        class InvalidStylePattern:
            def __init__(self, pattern, color):
                self.pattern = pattern
                self.color = color
                self.background = None
                self.bold = False
                self.italic = False
                self.underline = False
        
        # Create invalid regex pattern by bypassing normal validation
        config.styling.patterns["bad_pattern"] = InvalidStylePattern(
            pattern="[invalid regex",  # Unclosed bracket
            color="red"
        )
        
        errors = ConfigLoader.validate_config(config)
        assert len(errors) > 0
        assert any("bad_pattern" in error for error in errors)
    
    def test_merge_configs_partial_override(self):
        """Test merging configurations with partial override."""
        base_config = get_default_config()
        override_data = {
            "app": {
                "default_tail_lines": 2000
                # live_reload not specified, should keep default
            },
            "display": {
                "wrap_lines": True
                # other display settings should keep defaults
            }
        }
        
        merged = ConfigLoader._merge_configs(base_config, override_data)
        
        # Override values should be applied
        assert merged.app.default_tail_lines == 2000
        assert merged.display.wrap_lines is True
        
        # Non-overridden values should remain default
        assert merged.app.live_reload is True  # default
        assert merged.display.show_line_numbers is True  # default
    
    def test_load_from_file_with_complete_config(self):
        """Test loading a complete configuration file."""
        config_data = {
            "app": {
                "default_tail_lines": 2000,
                "live_reload": False,
                "case_sensitive_search": True
            },
            "keybindings": {
                "search": "?",
                "quit": "x"
            },
            "display": {
                "show_line_numbers": False,
                "wrap_lines": True,
                "max_line_length": 2000
            },
            "styling": {
                "patterns": {
                    "custom_error": {
                        "pattern": "CUSTOM_ERROR",
                        "color": "white",
                        "background": "red",
                        "bold": True
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = ConfigLoader._load_from_file(Path(config_path))
            
            # Verify app settings
            assert config.app.default_tail_lines == 2000
            assert config.app.live_reload is False
            assert config.app.case_sensitive_search is True
            
            # Verify keybindings
            assert config.keybindings.search == "?"
            assert config.keybindings.quit == "x"
            
            # Verify display settings
            assert config.display.show_line_numbers is False
            assert config.display.wrap_lines is True
            assert config.display.max_line_length == 2000
            
            # Verify custom styling
            assert "custom_error" in config.styling.patterns
            custom_pattern = config.styling.patterns["custom_error"]
            assert custom_pattern.pattern == "CUSTOM_ERROR"
            assert custom_pattern.color == "white"
            assert custom_pattern.background == "red"
            assert custom_pattern.bold is True
            
        finally:
            Path(config_path).unlink()
    
    @patch.dict('os.environ', {'XDG_CONFIG_HOME': '/tmp/test_xdg'})
    def test_config_search_locations(self):
        """Test that configuration search locations are correct."""
        locations = [func() for func in ConfigLoader.CONFIG_LOCATIONS]
        
        assert '/tmp/test_xdg/dalog/config.toml' in locations
        assert any('/.config/dalog/config.toml' in loc for loc in locations)
        assert any('/.dalog.toml' in loc for loc in locations)
        assert 'config.toml' in locations
    
    @pytest.mark.ci_skip
    def test_load_with_missing_sections(self):
        """Test loading config with some sections missing."""
        config_data = {
            "app": {
                "default_tail_lines": 500
            }
            # Missing other sections - should use defaults
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = ConfigLoader.load(config_path)
            
            # Specified values should be applied
            assert config.app.default_tail_lines == 500
            
            # Missing sections should use defaults
            assert config.app.live_reload is True  # default
            assert config.keybindings.search == "/"  # default
            assert config.display.show_line_numbers is True  # default
            
        finally:
            Path(config_path).unlink() 