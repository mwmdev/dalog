"""
Exclusion system for filtering log entries.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ExclusionPattern:
    """Represents an exclusion pattern."""

    pattern: str
    is_regex: bool
    case_sensitive: bool
    compiled: Optional[re.Pattern] = None

    def __post_init__(self):
        """Compile regex pattern if needed."""
        if self.is_regex:
            try:
                flags = 0 if self.case_sensitive else re.IGNORECASE
                self.compiled = re.compile(self.pattern, flags)
            except re.error:
                # Invalid regex, treat as plain text
                self.is_regex = False
                self.compiled = None

    def matches(self, text: str) -> bool:
        """Check if text matches this exclusion pattern.

        Args:
            text: Text to check

        Returns:
            True if text matches the pattern
        """
        if self.is_regex and self.compiled:
            return bool(self.compiled.search(text))
        else:
            # Plain text matching
            if self.case_sensitive:
                return self.pattern in text
            else:
                return self.pattern.lower() in text.lower()


class ExclusionManager:
    """Manages exclusion patterns for filtering."""

    def __init__(
        self,
        patterns: Optional[List[str]] = None,
        is_regex: bool = True,
        case_sensitive: bool = False,
    ):
        """Initialize the exclusion manager.

        Args:
            patterns: Initial list of patterns
            is_regex: Whether patterns are regex by default
            case_sensitive: Whether matching is case sensitive
        """
        self.patterns: List[ExclusionPattern] = []
        self.is_regex_default = is_regex
        self.case_sensitive_default = case_sensitive
        self._excluded_lines: Dict[str, Set[int]] = {}  # pattern -> line numbers

        # Load initial patterns
        if patterns:
            for pattern in patterns:
                self.add_pattern(pattern)

    def add_pattern(
        self,
        pattern: str,
        is_regex: Optional[bool] = None,
        case_sensitive: Optional[bool] = None,
    ) -> bool:
        """Add an exclusion pattern.

        Args:
            pattern: Pattern to add
            is_regex: Whether pattern is regex (uses default if None)
            case_sensitive: Whether matching is case sensitive

        Returns:
            True if pattern was added successfully
        """
        # Check if pattern already exists
        for existing in self.patterns:
            if existing.pattern == pattern:
                return False

        # Use defaults if not specified
        if is_regex is None:
            is_regex = self.is_regex_default
        if case_sensitive is None:
            case_sensitive = self.case_sensitive_default

        # Create and add pattern
        exclusion = ExclusionPattern(
            pattern=pattern, is_regex=is_regex, case_sensitive=case_sensitive
        )

        # Validate regex if applicable
        if is_regex and exclusion.compiled is None:
            return False

        self.patterns.append(exclusion)
        self._excluded_lines[pattern] = set()
        return True

    def remove_pattern(self, pattern: str) -> bool:
        """Remove an exclusion pattern.

        Args:
            pattern: Pattern to remove

        Returns:
            True if pattern was removed
        """
        for i, exclusion in enumerate(self.patterns):
            if exclusion.pattern == pattern:
                self.patterns.pop(i)
                if pattern in self._excluded_lines:
                    del self._excluded_lines[pattern]
                return True
        return False

    def clear_patterns(self) -> None:
        """Clear all exclusion patterns."""
        self.patterns.clear()
        self._excluded_lines.clear()

    def reset_excluded_lines(self) -> None:
        """Reset the excluded lines counter for a new filtering pass."""
        for pattern in self._excluded_lines:
            self._excluded_lines[pattern].clear()

    def is_excluded(self, text: str, line_number: int) -> bool:
        """Check if a line should be excluded.

        Args:
            text: Line text to check
            line_number: Line number for tracking

        Returns:
            True if line should be excluded
        """
        for pattern in self.patterns:
            if pattern.matches(text):
                self._excluded_lines[pattern.pattern].add(line_number)
                return True
        return False

    def get_excluded_count(self) -> int:
        """Get total number of excluded lines.

        Returns:
            Number of excluded lines
        """
        all_excluded = set()
        for line_numbers in self._excluded_lines.values():
            all_excluded.update(line_numbers)
        return len(all_excluded)

    def get_pattern_stats(self) -> List[Tuple[str, int]]:
        """Get statistics for each pattern.

        Returns:
            List of (pattern, excluded_count) tuples
        """
        stats = []
        for pattern in self.patterns:
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
                re.compile(pattern)
                return True, None
            except re.error as e:
                return False, f"Invalid regex: {str(e)}"
        else:
            return True, None

    def save_to_file(self, file_path: Path) -> None:
        """Save exclusion patterns to a file.

        Args:
            file_path: Path to save patterns to
        """
        data = []
        for pattern in self.patterns:
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
        for pattern in self.patterns:
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
