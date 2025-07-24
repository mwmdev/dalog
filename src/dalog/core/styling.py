"""
Regex-based styling engine for log content.
"""

import bisect
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from rich.style import Style
from rich.text import Text

from ..config.models import StylePattern, StylingConfig


@dataclass
class StyleRange:
    """Represents a styled text range with priority."""

    start: int
    end: int
    style: Style
    priority: int


class OptimizedRangeManager:
    """Optimized range overlap detection using sorted ranges for O(log n) performance."""

    def __init__(self):
        # Keep ranges sorted by start position for binary search
        self.ranges: List[StyleRange] = []

    def can_apply_range(self, start: int, end: int, priority: int) -> bool:
        """Check if a range can be applied without conflicts.

        Uses binary search to find potentially overlapping ranges,
        reducing complexity from O(n) to O(log n).
        """
        if not self.ranges:
            return True

        # Find the insertion point for the start position
        idx = bisect.bisect_left([r.start for r in self.ranges], start)

        # Check ranges that might overlap
        # Check ranges starting before our range
        if idx > 0:
            prev_range = self.ranges[idx - 1]
            if prev_range.end > start and prev_range.priority >= priority:
                return False

        # Check ranges starting at or after our start position
        while idx < len(self.ranges):
            curr_range = self.ranges[idx]
            # If current range starts after our range ends, no more overlaps possible
            if curr_range.start >= end:
                break
            # If ranges overlap and current has higher or equal priority, reject
            if curr_range.priority >= priority:
                return False
            idx += 1

        return True

    def add_range(self, start: int, end: int, style: Style, priority: int) -> None:
        """Add a range to the manager, maintaining sorted order."""
        range_obj = StyleRange(start, end, style, priority)
        # Insert in sorted position
        idx = bisect.bisect_left([r.start for r in self.ranges], start)
        self.ranges.insert(idx, range_obj)

    def clear(self) -> None:
        """Clear all ranges."""
        self.ranges.clear()


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

        # Performance metrics
        self.total_styling_time = 0.0
        self.total_lines_processed = 0
        self.cache_hits = 0
        self.cache_misses = 0

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
            # Import security module
            from ..security.regex_security import (
                RegexComplexityError,
                RegexTimeoutError,
                secure_compile,
            )

            # Compile regex with security protections
            regex = secure_compile(pattern_config.pattern, re.MULTILINE)

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
        except (RegexComplexityError, RegexTimeoutError) as e:
            # Log security-related errors but don't crash
            print(f"Warning: Unsafe regex pattern '{name}' blocked for security: {e}")
            return None

    def apply_styling(self, line: str) -> Text:
        """Apply all matching patterns to a line.

        Args:
            line: Log line to style

        Returns:
            Styled Rich Text object
        """
        start_time = time.perf_counter()
        self.cache_misses += 1

        text = Text(line)

        # Track which character positions have been styled
        # to handle overlapping patterns properly
        styled_ranges: List[Tuple[int, int, Style, int]] = []

        # Apply each pattern
        for compiled in self.compiled_patterns:
            try:
                # Import security module
                from ..security.regex_security import RegexTimeoutError, secure_finditer

                # Use secure finditer with timeout protection
                matches = secure_finditer(compiled.pattern, line)
            except RegexTimeoutError:
                # Skip pattern if it times out during execution
                print(
                    f"Warning: Pattern '{compiled.name}' timed out during execution, skipping"
                )
                continue
            except Exception:
                # Skip pattern if any other error occurs during execution
                continue

            # Process matches
            for match in matches:
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

        # Sort ranges by start position and priority (higher priority first for same start)
        styled_ranges.sort(key=lambda x: (x[0], -x[3]))

        # Use optimized range manager for O(log n) overlap detection
        range_manager = OptimizedRangeManager()

        for start, end, style, priority in styled_ranges:
            # Check if this range can be applied without conflicts
            if range_manager.can_apply_range(start, end, priority):
                text.stylize(style, start, end)
                range_manager.add_range(start, end, style, priority)

        # Update performance metrics
        elapsed_time = time.perf_counter() - start_time
        self.total_styling_time += elapsed_time
        self.total_lines_processed += 1

        return text

    def apply_styling_cached(self, line: str) -> Text:
        """Apply styling with caching for repeated lines.

        Args:
            line: Log line to style

        Returns:
            Styled Rich Text object
        """
        # Use simple cache with cache hit tracking
        if not hasattr(self, "_style_cache"):
            self._style_cache: Dict[str, Text] = {}

        if line in self._style_cache:
            self.cache_hits += 1
            return self._style_cache[line]

        # Cache miss - compute styling
        result = self.apply_styling(line)

        # Keep cache size reasonable
        if len(self._style_cache) >= 1000:
            # Remove oldest 100 entries
            keys_to_remove = list(self._style_cache.keys())[:100]
            for key in keys_to_remove:
                del self._style_cache[key]

        self._style_cache[line] = result
        return result

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

    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics for the styling engine.

        Returns:
            Dictionary with performance metrics
        """
        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0
            else 0.0
        )

        avg_time_per_line = (
            self.total_styling_time / self.total_lines_processed
            if self.total_lines_processed > 0
            else 0.0
        )

        return {
            "total_lines_processed": self.total_lines_processed,
            "total_styling_time": self.total_styling_time,
            "average_time_per_line": avg_time_per_line,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "compiled_patterns_count": len(self.compiled_patterns),
        }

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
        """Validate a regex pattern with security checks.

        Args:
            pattern: Regex pattern to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Import security module
            from ..security.regex_security import (
                RegexComplexityError,
                RegexTimeoutError,
                secure_compile,
            )

            # Use secure compilation for validation
            secure_compile(pattern)
            return True, None
        except re.error as e:
            return False, f"Invalid regex: {e}"
        except (RegexComplexityError, RegexTimeoutError) as e:
            return False, f"Security issue: {e}"

    def style_line(self, line: str) -> Tuple[str, List]:
        """Apply styling to a line and return styled text with matches.

        Args:
            line: Log line to style

        Returns:
            Tuple of (styled_line, matches) where matches is a list of match info
        """
        # For now, return the original line and empty matches list
        # This is a compatibility method for tests
        return line, []
