"""
Configuration loader for DaLog.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import toml

from .defaults import DEFAULT_CONFIG_TOML, get_default_config
from .models import (
    AppConfig,
    DaLogConfig,
    DisplayConfig,
    ExclusionConfig,
    HtmlConfig,
    KeyBindings,
    StylingConfig,
)


class ConfigLoader:
    """Load and manage configuration from various sources."""

    # Configuration file search locations in priority order
    CONFIG_LOCATIONS = [
        lambda: os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        + "/dalog/config.toml",
        lambda: os.path.expanduser("~/.config/dalog/config.toml"),
        lambda: os.path.expanduser("~/.dalog.toml"),
        lambda: "config.toml",
    ]

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> DaLogConfig:
        """Load configuration from file or defaults.

        Args:
            config_path: Optional path to config file

        Returns:
            Configuration object
        """
        if config_path:
            # Try to load from explicit path
            path = Path(config_path)
            if path.exists():
                try:
                    return cls._load_from_file(path)
                except Exception:
                    # If loading fails, fall back to default
                    return get_default_config()
            else:
                # File doesn't exist, return default config
                return get_default_config()
        else:
            # Search for config file in standard locations
            for location_func in cls.CONFIG_LOCATIONS:
                path = Path(location_func())
                if path.exists():
                    try:
                        return cls._load_from_file(path)
                    except Exception:
                        # If loading fails, continue to next location
                        continue

            # No config file found, return defaults
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
            with open(path, "r") as f:
                data = toml.load(f)

            # Merge with defaults to ensure all fields are present
            default_config = get_default_config()
            merged_config = ConfigLoader._merge_configs(default_config, data)

            return merged_config

        except toml.TomlDecodeError as e:
            raise Exception(f"Invalid TOML in {path}: {e}")
        except Exception as e:
            raise Exception(f"Error loading config from {path}: {e}")

    @staticmethod
    def _merge_configs(
        default: Union[Dict[str, Any], DaLogConfig], override: Dict[str, Any]
    ) -> DaLogConfig:
        """Recursively merge configuration dictionaries.

        Args:
            default: Default configuration dict or DaLogConfig object
            override: Override configuration dict

        Returns:
            Merged configuration object
        """
        # Convert DaLogConfig to dict if needed
        if isinstance(default, DaLogConfig):
            result = default.model_dump()
        else:
            result = default.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dicts (return dict for intermediate merges)
                result[key] = ConfigLoader._merge_configs_dict(result[key], value)
            else:
                # Override value
                result[key] = value

        # Return as DaLogConfig object
        return DaLogConfig(**result)

    @staticmethod
    def _merge_configs_dict(
        default: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries (dict version).

        Args:
            default: Default configuration dict
            override: Override configuration dict

        Returns:
            Merged configuration dict
        """
        result = default.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dicts
                result[key] = ConfigLoader._merge_configs_dict(result[key], value)
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

        with open(path, "w") as f:
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
            keybindings_dict = config.keybindings.model_dump()

            # Check for empty keybindings (skip non-string fields like display_in_footer)
            for name, value in keybindings_dict.items():
                if name == "display_in_footer":  # Skip the list field
                    continue
                if isinstance(value, str) and (not value or len(value) == 0):
                    errors.append(f"Keybinding '{name}' cannot be empty")

            # Check for keybinding conflicts (same key assigned to multiple actions)
            key_to_actions = {}
            for name, value in keybindings_dict.items():
                if name == "display_in_footer":  # Skip the list field
                    continue
                if isinstance(value, str) and value and len(value) > 0:
                    if value in key_to_actions:
                        key_to_actions[value].append(name)
                    else:
                        key_to_actions[value] = [name]

            # Report conflicts (except for some special cases like ctrl+c)
            for key, actions in key_to_actions.items():
                if len(actions) > 1:
                    # Allow certain keys to be shared (like escape, ctrl+c)
                    if key not in ["escape", "ctrl+c"]:
                        actions_str = "', '".join(actions)
                        errors.append(
                            f"Keybinding conflict: '{key}' assigned to '{actions_str}'"
                        )

        # Validate styling patterns
        if config.styling:
            for category in ["patterns", "timestamps", "custom"]:
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
            config_dir = (
                Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")))
                / "dalog"
            )
            config_dir.mkdir(parents=True, exist_ok=True)
            path = config_dir / "config.toml"

        path.write_text(DEFAULT_CONFIG_TOML)
        return path
