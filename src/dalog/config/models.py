"""
Configuration models for DaLog.
"""

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class StylePattern(BaseModel):
    """Styling pattern configuration."""

    pattern: str
    color: Optional[str] = None
    background: Optional[str] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False

    @field_validator("pattern")
    def validate_regex(cls, v):
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {v} - {e}")

        # Import here to avoid circular dependency
        from ..security.regex_security import validate_pattern_security

        is_safe, error_msg = validate_pattern_security(v)
        if not is_safe:
            raise ValueError(f"Unsafe regex pattern: {v} - {error_msg}")

        return v


class KeyBindings(BaseModel):
    """Keybinding configuration."""

    search: str = "/"
    reload: str = "r"
    toggle_live_reload: str = "L"
    toggle_wrap: str = "w"
    quit: str = "q"
    show_exclusions: str = "e"
    scroll_down: str = "j"
    scroll_up: str = "k"
    scroll_left: str = "h"
    scroll_right: str = "l"
    scroll_home: str = "g"
    scroll_end: str = "G"
    show_help: str = "?"

    # Page scrolling
    scroll_page_up: str = "ctrl+u"
    scroll_page_down: str = "ctrl+d"

    # Visual mode
    enter_visual_mode: str = "V"
    start_selection: str = "v"
    yank_lines: str = "y"

    # Footer display configuration
    display_in_footer: List[str] = Field(
        default_factory=lambda: [
            "search",
            "reload",
            "toggle_live_reload",
            "show_exclusions",
            "toggle_wrap",
            "quit",
            "show_help",
        ],
        description="List of keybinding actions to display in footer",
    )


class AppConfig(BaseModel):
    """Main application configuration."""

    default_tail_lines: int = Field(default=1000, ge=0)
    live_reload: bool = True
    case_sensitive_search: bool = False


class DisplayConfig(BaseModel):
    """Display configuration."""

    show_line_numbers: bool = True
    wrap_lines: bool = False
    max_line_length: int = Field(default=1000, ge=100)
    visual_mode_bg: str = Field(
        default="white", description="Background color for visual mode selection"
    )


class StylingConfig(BaseModel):
    """Styling configuration."""

    patterns: Dict[str, StylePattern] = Field(default_factory=dict)
    timestamps: Dict[str, StylePattern] = Field(default_factory=dict)
    custom: Dict[str, StylePattern] = Field(default_factory=dict)


class HtmlConfig(BaseModel):
    """HTML rendering configuration."""

    enabled_tags: List[str] = Field(
        default_factory=lambda: ["b", "i", "em", "strong", "span"]
    )
    strip_unknown_tags: bool = True


class ExclusionConfig(BaseModel):
    """Exclusion configuration."""

    patterns: List[str] = Field(default_factory=list)
    regex: bool = True
    case_sensitive: bool = False


class SSHConfig(BaseModel):
    """SSH connection security configuration."""

    strict_host_key_checking: bool = True
    connection_timeout: int = 30
    command_timeout: int = 60
    max_tail_lines: int = 1000000
    known_hosts_file: Optional[str] = None

    # File watching configuration
    poll_interval: float = Field(default=1.0, ge=0.1, le=60.0)
    max_poll_interval: float = Field(default=2.0, ge=0.5, le=300.0)

    @field_validator("connection_timeout", "command_timeout")
    def validate_timeouts(cls, v):
        if not isinstance(v, int) or v <= 0 or v > 300:
            raise ValueError("Timeout must be between 1 and 300 seconds")
        return v

    @field_validator("max_tail_lines")
    def validate_max_lines(cls, v):
        if not isinstance(v, int) or v <= 0 or v > 10000000:
            raise ValueError("Max tail lines must be between 1 and 10,000,000")
        return v

    @field_validator("poll_interval", "max_poll_interval")
    def validate_poll_intervals(cls, v):
        if not isinstance(v, (int, float)) or v <= 0:
            raise ValueError("Poll interval must be a positive number")
        return float(v)

    def model_post_init(self, __context) -> None:
        """Validate that max_poll_interval is greater than poll_interval."""
        if self.max_poll_interval <= self.poll_interval:
            raise ValueError("max_poll_interval must be greater than poll_interval")


class SecurityConfig(BaseModel):
    """Security configuration for regex and path operations."""

    # Regex security
    regex_compilation_timeout: float = Field(default=2.0, ge=0.1, le=10.0)
    regex_execution_timeout: float = Field(default=1.0, ge=0.1, le=5.0)
    max_pattern_length: int = Field(default=1000, ge=10, le=10000)
    max_quantifier_nesting: int = Field(default=3, ge=1, le=10)
    max_alternation_groups: int = Field(default=10, ge=1, le=100)
    enable_complexity_analysis: bool = True
    enable_timeout_protection: bool = True

    # Path security
    max_config_file_size: int = Field(
        default=1024 * 1024, ge=1024, le=10 * 1024 * 1024
    )  # 1MB default, max 10MB
    max_log_file_size: int = Field(
        default=1024 * 1024 * 1024, ge=1024 * 1024, le=10 * 1024 * 1024 * 1024
    )  # 1GB default, max 10GB
    allow_symlinks: bool = Field(
        default=False, description="Allow following symlinks in file paths"
    )
    enable_path_validation: bool = Field(
        default=True, description="Enable path traversal and security validation"
    )
    block_sensitive_paths: bool = Field(
        default=True, description="Block access to sensitive system paths"
    )

    @field_validator("regex_compilation_timeout", "regex_execution_timeout")
    def validate_timeouts(cls, v):
        if not isinstance(v, (int, float)) or v <= 0:
            raise ValueError("Timeout must be a positive number")
        return float(v)

    @field_validator(
        "max_pattern_length", "max_quantifier_nesting", "max_alternation_groups"
    )
    def validate_limits(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError("Limit must be a positive integer")
        return v

    @field_validator("max_config_file_size", "max_log_file_size")
    def validate_file_sizes(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError("File size limit must be a positive integer")
        return v


class DaLogConfig(BaseModel):
    """Complete DaLog configuration."""

    app: AppConfig = Field(default_factory=AppConfig)
    keybindings: KeyBindings = Field(default_factory=KeyBindings)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    styling: StylingConfig = Field(default_factory=StylingConfig)
    html: HtmlConfig = Field(default_factory=HtmlConfig)
    exclusions: ExclusionConfig = Field(default_factory=ExclusionConfig)
    ssh: SSHConfig = Field(default_factory=SSHConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
