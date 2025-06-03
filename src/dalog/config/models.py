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


class AppConfig(BaseModel):
    """Main application configuration."""

    default_tail_lines: int = Field(default=1000, ge=0)
    live_reload: bool = True
    case_sensitive_search: bool = False
    vim_mode: bool = True


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


class DaLogConfig(BaseModel):
    """Complete DaLog configuration."""

    app: AppConfig = Field(default_factory=AppConfig)
    keybindings: KeyBindings = Field(default_factory=KeyBindings)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    styling: StylingConfig = Field(default_factory=StylingConfig)
    html: HtmlConfig = Field(default_factory=HtmlConfig)
    exclusions: ExclusionConfig = Field(default_factory=ExclusionConfig)
