"""
Regex-based styling engine for log content.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from rich.style import Style
from rich.text import Text

from ..config.models import StylePattern, StylingConfig


@dataclass
class CompiledPattern:
    """Compiled regex pattern with associated style."""

    name: str
    pattern: re.Pattern
    style: Style
    priority: int = 0


class StylingEngine:
    """Apply regex-based styling to log lines."""

    def __init__(self, styling_config: StylingConfig):
        """Initialize the styling engine.

        Args:
            styling_config: Styling configuration from app config
        """
        self.config = styling_config
        self.compiled_patterns: List[CompiledPattern] = []
        self._compile_all_patterns()

    def _compile_all_patterns(self) -> None:
        """Compile all regex patterns for performance."""
        # Clear existing patterns
        self.compiled_patterns.clear()

        # Compile general patterns with priority 1
        for name, pattern_config in self.config.patterns.items():
            compiled = self._compile_pattern(name, pattern_config, priority=1)
            if compiled:
                self.compiled_patterns.append(compiled)

        # Compile timestamp patterns with priority 2 (higher)
        for name, pattern_config in self.config.timestamps.items():
            compiled = self._compile_pattern(name, pattern_config, priority=2)
            if compiled:
                self.compiled_patterns.append(compiled)

        # Compile custom patterns with priority 3 (highest)
        for name, pattern_config in self.config.custom.items():
            compiled = self._compile_pattern(name, pattern_config, priority=3)
            if compiled:
                self.compiled_patterns.append(compiled)

        # Sort by priority (higher priority patterns are applied last)
        self.compiled_patterns.sort(key=lambda x: x.priority)

    def _compile_pattern(
        self, name: str, pattern_config: StylePattern, priority: int = 0
    ) -> Optional[CompiledPattern]:
        """Compile a single pattern configuration.

        Args:
            name: Pattern name
            pattern_config: Pattern configuration
            priority: Pattern priority (higher = applied later)

        Returns:
            CompiledPattern or None if pattern is invalid
        """
        try:
            # Compile regex with flags for better matching
            regex = re.compile(pattern_config.pattern, re.MULTILINE)

            # Create Rich style from configuration
            style_kwargs = {}
            if pattern_config.color:
                style_kwargs["color"] = pattern_config.color
            if pattern_config.background:
                style_kwargs["bgcolor"] = pattern_config.background
            if pattern_config.bold:
                style_kwargs["bold"] = True
            if pattern_config.italic:
                style_kwargs["italic"] = True
            if pattern_config.underline:
                style_kwargs["underline"] = True

            style = Style(**style_kwargs)

            return CompiledPattern(
                name=name, pattern=regex, style=style, priority=priority
            )

        except re.error as e:
            # Log error but don't crash
            print(f"Warning: Invalid regex pattern '{name}': {e}")
            return None

    def apply_styling(self, line: str) -> Text:
        """Apply all matching patterns to a line.

        Args:
            line: Log line to style

        Returns:
            Styled Rich Text object
        """
        text = Text(line)

        # Track which character positions have been styled
        # to handle overlapping patterns properly
        styled_ranges: List[Tuple[int, int, Style, int]] = []

        # Apply each pattern
        for compiled in self.compiled_patterns:
            for match in compiled.pattern.finditer(line):
                # Check if pattern has groups (for contextual highlighting)
                if match.groups():
                    # For patterns with groups, we want to style specific groups
                    # If there's a group 2, style that (the word after the keyword)
                    # Otherwise, style group 1
                    if len(match.groups()) >= 2 and match.group(2):
                        start, end = match.span(2)
                    elif match.group(1):
                        start, end = match.span(1)
                    else:
                        start, end = match.span()
                else:
                    # No groups, style the entire match
                    start, end = match.span()

                styled_ranges.append((start, end, compiled.style, compiled.priority))

        # Sort ranges by start position and priority
        styled_ranges.sort(key=lambda x: (x[0], -x[3]))

        # Apply styles, allowing higher priority styles to override
        applied_ranges = []
        for start, end, style, priority in styled_ranges:
            # Check if this range overlaps with any already applied
            can_apply = True
            for applied_start, applied_end, applied_priority in applied_ranges:
                # If ranges overlap and applied has higher priority, skip
                if (
                    start < applied_end
                    and end > applied_start
                    and applied_priority >= priority
                ):
                    can_apply = False
                    break

            if can_apply:
                text.stylize(style, start, end)
                applied_ranges.append((start, end, priority))

        return text

    @lru_cache(maxsize=1000)
    def apply_styling_cached(self, line: str) -> Text:
        """Apply styling with caching for repeated lines.

        Args:
            line: Log line to style

        Returns:
            Styled Rich Text object
        """
        return self.apply_styling(line)

    def add_custom_pattern(self, name: str, pattern: str, **style_kwargs) -> bool:
        """Add a custom pattern at runtime.

        Args:
            name: Pattern name
            pattern: Regex pattern
            **style_kwargs: Style attributes (color, background, bold, etc.)

        Returns:
            True if pattern was added successfully
        """
        try:
            # Create StylePattern
            style_pattern = StylePattern(
                pattern=pattern,
                color=style_kwargs.get("color"),
                background=style_kwargs.get("background"),
                bold=style_kwargs.get("bold", False),
                italic=style_kwargs.get("italic", False),
                underline=style_kwargs.get("underline", False),
            )

            # Add to custom patterns
            self.config.custom[name] = style_pattern

            # Recompile patterns
            self._compile_all_patterns()

            return True

        except Exception as e:
            print(f"Error adding custom pattern '{name}': {e}")
            return False

    def remove_custom_pattern(self, name: str) -> bool:
        """Remove a custom pattern.

        Args:
            name: Pattern name to remove

        Returns:
            True if pattern was removed
        """
        if name in self.config.custom:
            del self.config.custom[name]
            self._compile_all_patterns()
            return True
        return False

    def get_pattern_names(self) -> Dict[str, List[str]]:
        """Get all pattern names grouped by category.

        Returns:
            Dictionary with categories as keys and pattern names as values
        """
        return {
            "patterns": list(self.config.patterns.keys()),
            "timestamps": list(self.config.timestamps.keys()),
            "custom": list(self.config.custom.keys()),
        }

    def validate_pattern(self, pattern: str) -> Tuple[bool, Optional[str]]:
        """Validate a regex pattern.

        Args:
            pattern: Regex pattern to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            re.compile(pattern)
            return True, None
        except re.error as e:
            return False, str(e)
