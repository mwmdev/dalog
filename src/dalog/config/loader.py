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
        """Load configuration from file or defaults with security validation.

        Args:
            config_path: Optional path to config file

        Returns:
            Configuration object
        """
        if config_path:
            # Try to load from explicit path with security validation
            try:
                from ..security.path_security import validate_config_path

                safe_path = validate_config_path(config_path)

                if safe_path.exists():
                    return cls._load_from_file(safe_path)
                else:
                    # File doesn't exist, return default config
                    config = get_default_config()
                    cls._configure_security(config)
                    return config

            except Exception:
                # If security validation or loading fails, fall back to default
                config = get_default_config()
                cls._configure_security(config)
                return config
        else:
            # Search for config file in standard locations with security
            try:
                from ..security.path_security import get_safe_config_search_paths

                search_paths = get_safe_config_search_paths()
            except Exception:
                # Fallback to basic search if security module fails
                search_paths = [
                    Path.home() / ".config" / "dalog" / "config.toml",
                    Path.home() / ".dalog.toml",
                    Path.cwd() / "config.toml",
                ]

            for path in search_paths:
                if path.exists():
                    try:
                        return cls._load_from_file(path)
                    except Exception:
                        # If loading fails, continue to next location
                        continue

            # No config file found, return defaults
            config = get_default_config()
            cls._configure_security(config)
            return config

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

            # Configure security system with loaded settings
            ConfigLoader._configure_security(merged_config)

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
                        # Import security module
                        from ..security.regex_security import (
                            RegexComplexityError,
                            RegexTimeoutError,
                            secure_compile,
                        )

                        # Use secure compilation for validation
                        secure_compile(pattern.pattern)
                    except re.error as e:
                        errors.append(f"Invalid regex in {category}.{name}: {e}")
                    except (RegexComplexityError, RegexTimeoutError) as e:
                        errors.append(f"Unsafe regex in {category}.{name}: {e}")

        # Validate exclusion patterns
        if config.exclusions and config.exclusions.regex:
            for pattern in config.exclusions.patterns:
                try:
                    # Import security module
                    from ..security.regex_security import (
                        RegexComplexityError,
                        RegexTimeoutError,
                        secure_compile,
                    )

                    # Use secure compilation for validation
                    secure_compile(pattern)
                except re.error as e:
                    errors.append(f"Invalid exclusion regex '{pattern}': {e}")
                except (RegexComplexityError, RegexTimeoutError) as e:
                    errors.append(f"Unsafe exclusion regex '{pattern}': {e}")

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

    @staticmethod
    def _configure_security(config: DaLogConfig) -> None:
        """Configure the security system with loaded configuration.

        Args:
            config: Configuration object with security settings
        """
        try:
            # Configure regex security
            from ..security.regex_security import SecurityConfig as RegexSecurityConfig
            from ..security.regex_security import (
                configure_security as configure_regex_security,
            )

            regex_security_config = RegexSecurityConfig(
                compilation_timeout=config.security.regex_compilation_timeout,
                execution_timeout=config.security.regex_execution_timeout,
                max_pattern_length=config.security.max_pattern_length,
                max_quantifier_nesting=config.security.max_quantifier_nesting,
                max_alternation_groups=config.security.max_alternation_groups,
                enable_complexity_analysis=config.security.enable_complexity_analysis,
                enable_timeout_protection=config.security.enable_timeout_protection,
            )

            configure_regex_security(regex_security_config)

        except Exception as e:
            # Log error but don't crash if regex security configuration fails
            print(f"Warning: Failed to configure regex security: {e}")

        try:
            # Configure path security
            from ..security.path_security import (
                PathSecurityConfig,
                configure_path_security,
            )

            path_security_config = PathSecurityConfig(
                max_config_size=config.security.max_config_file_size,
                max_log_size=config.security.max_log_file_size,
                allow_symlinks=config.security.allow_symlinks,
            )

            configure_path_security(path_security_config)

        except Exception as e:
            # Log error but don't crash if path security configuration fails
            print(f"Warning: Failed to configure path security: {e}")
