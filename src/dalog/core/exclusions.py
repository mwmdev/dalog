"""
Exclusion system for filtering log entries.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple, Union


@dataclass
class ExclusionPattern:
    """Represents an exclusion pattern."""

    pattern: str
    is_regex: bool
    case_sensitive: bool
    compiled: Optional[re.Pattern] = None
    is_valid: bool = True  # Track if pattern is valid

    def __post_init__(self):
        """Compile regex pattern if needed."""
        if self.is_regex:
            try:
                # Import security module
                from ..security.regex_security import (
                    RegexComplexityError,
                    RegexTimeoutError,
                    secure_compile,
                )

                flags = 0 if self.case_sensitive else re.IGNORECASE
                self.compiled = secure_compile(self.pattern, flags)
                self.is_valid = True
            except re.error:
                # Invalid regex, mark as invalid
                self.compiled = None
                self.is_valid = False
            except (RegexComplexityError, RegexTimeoutError):
                # Unsafe regex, mark as invalid for security
                self.compiled = None
                self.is_valid = False

    def matches(self, text: str) -> bool:
        """Check if text matches this exclusion pattern.

        Args:
            text: Text to check

        Returns:
            True if text matches the pattern
        """
        # Skip invalid patterns
        if not self.is_valid:
            return False

        if self.is_regex and self.compiled:
            try:
                # Import security module
                from ..security.regex_security import RegexTimeoutError, secure_search

                # Use secure search with timeout protection
                result = secure_search(self.compiled, text)
                return bool(result)
            except RegexTimeoutError:
                # If pattern times out, skip it (don't match)
                return False
        elif not self.is_regex:
            # Plain text matching
            if self.case_sensitive:
                return self.pattern in text
            else:
                return self.pattern.lower() in text.lower()
        else:
            return False


class ExclusionManager:
    """Manages exclusion patterns for filtering log entries."""

    def __init__(
        self,
        patterns: Optional[List[str]] = None,
        is_regex: bool = True,
        case_sensitive: bool = False,
    ):
        """Initialize the exclusion manager.

        Args:
            patterns: List of patterns to exclude
            is_regex: Whether patterns are regex
            case_sensitive: Whether matching is case sensitive
        """
        self.is_regex = is_regex
        self.case_sensitive = case_sensitive
        self._patterns: List[ExclusionPattern] = []
        self._excluded_count = 0
        self._excluded_lines: Dict[str, Set[int]] = {}

        if patterns:
            for pattern in patterns:
                self.add_pattern(pattern)

    @property
    def patterns(self) -> List[str]:
        """Get patterns as strings for compatibility with tests."""
        return [p.pattern for p in self._patterns]

    def add_pattern(
        self,
        pattern: str,
        is_regex: Optional[bool] = None,
        case_sensitive: Optional[bool] = None,
    ) -> bool:
        """Add an exclusion pattern.

        Args:
            pattern: Pattern string to exclude
            is_regex: Override default regex setting
            case_sensitive: Override default case sensitivity

        Returns:
            True if pattern was added, False if it already exists
        """
        # Use instance defaults if not specified
        regex = is_regex if is_regex is not None else self.is_regex
        case_sens = (
            case_sensitive if case_sensitive is not None else self.case_sensitive
        )

        # Check for duplicates
        for existing in self._patterns:
            if (
                existing.pattern == pattern
                and existing.is_regex == regex
                and existing.case_sensitive == case_sens
            ):
                return False  # Don't add duplicates

        exclusion_pattern = ExclusionPattern(
            pattern=pattern, is_regex=regex, case_sensitive=case_sens
        )
        self._patterns.append(exclusion_pattern)
        return True

    def remove_pattern(self, pattern: str) -> bool:
        """Remove an exclusion pattern.

        Args:
            pattern: Pattern to remove

        Returns:
            True if pattern was removed, False if not found
        """
        for i, p in enumerate(self._patterns):
            if p.pattern == pattern:
                self._patterns.pop(i)
                # Also remove tracking for this pattern
                if pattern in self._excluded_lines:
                    del self._excluded_lines[pattern]
                return True
        return False

    def clear_patterns(self) -> None:
        """Clear all exclusion patterns."""
        self._patterns.clear()
        self._excluded_lines.clear()

    def should_exclude(self, line: str) -> bool:
        """Check if a line should be excluded.

        Args:
            line: Log line to check

        Returns:
            True if line should be excluded
        """
        for pattern in self._patterns:
            # Skip invalid patterns
            if not pattern.is_valid:
                continue

            if pattern.is_regex:
                # For regex patterns, only match if compiled successfully
                if pattern.compiled:
                    try:
                        if pattern.compiled.search(line):
                            return True
                    except Exception:
                        # If there's an error during matching, skip this pattern
                        continue
            else:
                # Literal match
                if not pattern.case_sensitive:
                    if pattern.pattern.lower() in line.lower():
                        return True
                else:
                    if pattern.pattern in line:
                        return True
        return False

    def filter_lines(
        self, lines: Union[List[str], Generator[str, None, None]]
    ) -> List[str]:
        """Filter out excluded lines.

        Args:
            lines: Lines to filter

        Returns:
            Filtered lines
        """
        result = []
        for line in lines:
            if self.should_exclude(line):
                self._excluded_count += 1
            else:
                result.append(line)
        return result

    def get_excluded_count(self) -> int:
        """Get the number of excluded lines."""
        return self._excluded_count

    def reset_excluded_count(self) -> None:
        """Reset the excluded line count."""
        self._excluded_count = 0
        self._excluded_lines.clear()

    def get_pattern_stats(self) -> List[Tuple[str, int]]:
        """Get statistics for each pattern.

        Returns:
            List of (pattern, excluded_count) tuples
        """
        stats = []
        for pattern in self._patterns:
            count = len(self._excluded_lines.get(pattern.pattern, set()))
            stats.append((pattern.pattern, count))
        return stats

    def validate_pattern(
        self, pattern: str, is_regex: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Validate a pattern before adding.

        Args:
            pattern: Pattern to validate
            is_regex: Whether pattern should be treated as regex

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not pattern:
            return False, "Pattern cannot be empty"

        if is_regex:
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
                return False, f"Invalid regex: {str(e)}"
            except (RegexComplexityError, RegexTimeoutError) as e:
                return False, f"Security issue: {str(e)}"
        else:
            return True, None

    def save_to_file(self, file_path: Path) -> None:
        """Save exclusion patterns to a file.

        Args:
            file_path: Path to save patterns to
        """
        data = []
        for pattern in self._patterns:
            data.append(
                {
                    "pattern": pattern.pattern,
                    "is_regex": pattern.is_regex,
                    "case_sensitive": pattern.case_sensitive,
                }
            )

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, file_path: Path) -> None:
        """Load exclusion patterns from a file.

        Args:
            file_path: Path to load patterns from
        """
        if not file_path.exists():
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            self.clear_patterns()
            for item in data:
                self.add_pattern(
                    pattern=item["pattern"],
                    is_regex=item.get("is_regex", True),
                    case_sensitive=item.get("case_sensitive", False),
                )
        except Exception as e:
            print(f"Error loading exclusions: {e}")

    def get_patterns_list(self) -> List[Dict[str, any]]:
        """Get list of patterns with their properties.

        Returns:
            List of pattern dictionaries
        """
        result = []
        for pattern in self._patterns:
            result.append(
                {
                    "pattern": pattern.pattern,
                    "is_regex": pattern.is_regex,
                    "case_sensitive": pattern.case_sensitive,
                    "excluded_count": len(
                        self._excluded_lines.get(pattern.pattern, set())
                    ),
                }
            )
        return result
