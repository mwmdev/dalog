"""
Configuration loader for DaLog.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Any, Dict
import re

import toml

from .models import DaLogConfig, AppConfig, KeyBindings, DisplayConfig, StylingConfig, HtmlConfig, ExclusionConfig
from .defaults import get_default_config, DEFAULT_CONFIG_TOML


class ConfigLoader:
    """Load and manage configuration from various sources."""
    
    # Configuration file search locations in priority order
    CONFIG_LOCATIONS = [
        lambda: os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')) + '/dalog/config.toml',
        lambda: os.path.expanduser('~/.config/dalog/config.toml'),
        lambda: os.path.expanduser('~/.dalog.toml'),
        lambda: 'config.toml',
    ]
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> DaLogConfig:
        """Load configuration with priority order.
        
        Args:
            config_path: Optional explicit configuration file path
            
        Returns:
            Loaded configuration or defaults
        """
        # If explicit path provided, use it
        if config_path:
            return cls._load_from_file(Path(config_path))
        
        # Search in default locations
        for location_func in cls.CONFIG_LOCATIONS:
            try:
                path = Path(location_func())
                if path.exists():
                    return cls._load_from_file(path)
            except Exception:
                continue
        
        # Return default config if no file found
        return get_default_config()
    
    @staticmethod
    def _load_from_file(path: Path) -> DaLogConfig:
        """Load configuration from TOML file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            Loaded configuration
            
        Raises:
            Exception: If file cannot be loaded or parsed
        """
        try:
            with open(path, 'r') as f:
                data = toml.load(f)
            
            # Merge with defaults to ensure all fields are present
            default_config = get_default_config()
            merged_data = ConfigLoader._merge_configs(default_config.model_dump(), data)
            
            return DaLogConfig(**merged_data)
            
        except toml.TomlDecodeError as e:
            raise Exception(f"Invalid TOML in {path}: {e}")
        except Exception as e:
            raise Exception(f"Error loading config from {path}: {e}")
    
    @staticmethod
    def _merge_configs(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries.
        
        Args:
            default: Default configuration dict
            override: Override configuration dict
            
        Returns:
            Merged configuration dict
        """
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dicts
                result[key] = ConfigLoader._merge_configs(result[key], value)
            else:
                # Override value
                result[key] = value
                
        return result
    
    @staticmethod
    def save(config: DaLogConfig, path: Path) -> None:
        """Save configuration to TOML file.
        
        Args:
            config: Configuration to save
            path: Path to save to
        """
        # Create parent directory if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and save
        data = config.model_dump(exclude_none=True)
        
        with open(path, 'w') as f:
            toml.dump(data, f)
    
    @staticmethod
    def validate_config(config: DaLogConfig) -> List[str]:
        """Validate configuration and return list of errors.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Validate keybindings
        if config.keybindings:
            for name, key in config.keybindings.model_dump().items():
                if not key or len(key) == 0:
                    errors.append(f"Keybinding '{name}' cannot be empty")
        
        # Validate styling patterns
        if config.styling:
            for category in ['patterns', 'timestamps', 'custom']:
                patterns = getattr(config.styling, category, {})
                for name, pattern in patterns.items():
                    try:
                        re.compile(pattern.pattern)
                    except re.error as e:
                        errors.append(f"Invalid regex in {category}.{name}: {e}")
        
        # Validate exclusion patterns
        if config.exclusions and config.exclusions.regex:
            for pattern in config.exclusions.patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    errors.append(f"Invalid exclusion regex '{pattern}': {e}")
        
        return errors
    
    @staticmethod
    def get_config_paths() -> List[Path]:
        """Get list of all possible configuration file paths.
        
        Returns:
            List of configuration file paths
        """
        paths = []
        for location_func in ConfigLoader.CONFIG_LOCATIONS:
            try:
                paths.append(Path(location_func()))
            except Exception:
                pass
        return paths
    
    @classmethod
    def save_default_config(cls, path: Optional[Path] = None) -> Path:
        """Save default configuration to file.
        
        Args:
            path: Optional path to save to
            
        Returns:
            Path where config was saved
        """
        if path is None:
            # Use XDG config home or fallback
            config_dir = Path(os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))) / 'dalog'
            config_dir.mkdir(parents=True, exist_ok=True)
            path = config_dir / 'config.toml'
        
        path.write_text(DEFAULT_CONFIG_TOML)
        return path 