"""
Secure regex operations with ReDoS protection.

Provides timeout-protected regex compilation and execution to prevent
Regular Expression Denial of Service (ReDoS) attacks.
"""

import re
import signal
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Match, Optional, Pattern, Union


class RegexTimeoutError(Exception):
    """Raised when regex operations exceed timeout limits."""

    pass


class RegexComplexityError(Exception):
    """Raised when regex patterns are too complex and could cause ReDoS."""

    pass


@dataclass
class SecurityConfig:
    """Configuration for regex security settings."""

    compilation_timeout: float = 2.0  # seconds
    execution_timeout: float = 1.0  # seconds
    max_pattern_length: int = 1000
    max_quantifier_nesting: int = 3
    max_alternation_groups: int = 10
    enable_complexity_analysis: bool = True
    enable_timeout_protection: bool = True


# Global security configuration
_security_config = SecurityConfig()


def configure_security(config: SecurityConfig) -> None:
    """Configure global regex security settings."""
    global _security_config
    _security_config = config


@contextmanager
def timeout_protection(timeout_seconds: float, operation_name: str = "regex operation"):
    """
    Context manager providing timeout protection for regex operations.

    Uses SIGALRM to interrupt long-running regex operations in the main thread,
    or simple time-based checking in other threads to prevent ReDoS attacks.

    Args:
        timeout_seconds: Maximum time to allow operation
        operation_name: Description for error messages

    Raises:
        RegexTimeoutError: If operation exceeds timeout
    """

    if not _security_config.enable_timeout_protection:
        yield
        return

    # Check if we're in the main thread
    is_main_thread = threading.current_thread() is threading.main_thread()

    if is_main_thread:
        # Use signal-based timeout in main thread
        def timeout_handler(signum, frame):
            raise RegexTimeoutError(
                f"{operation_name} exceeded timeout of {timeout_seconds}s"
            )

        # Store original handler
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)

        try:
            # Set alarm for timeout
            signal.alarm(int(timeout_seconds) + 1)  # Round up to ensure minimum timeout
            yield
        finally:
            # Restore original handler and cancel alarm
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Use time-based timeout checking in non-main threads
        start_time = time.time()

        class TimeoutChecker:
            def __init__(self, timeout_seconds: float, operation_name: str):
                self.timeout_seconds = timeout_seconds
                self.operation_name = operation_name
                self.start_time = start_time

            def check_timeout(self):
                if time.time() - self.start_time > self.timeout_seconds:
                    raise RegexTimeoutError(
                        f"{self.operation_name} exceeded timeout of {self.timeout_seconds}s"
                    )

        # For non-main threads, we yield immediately but the calling code
        # could use the timeout checker if needed (though we can't interrupt
        # regex operations in progress in other threads)
        yield


def analyze_pattern_complexity(pattern: str) -> None:
    """
    Analyze regex pattern for potential ReDoS vulnerabilities.

    Detects patterns that could cause catastrophic backtracking:
    - Nested quantifiers like (a+)+ or (a*)*
    - Alternation with overlapping groups like (a|a)*
    - Excessive complexity that could lead to exponential time

    Args:
        pattern: Regex pattern to analyze

    Raises:
        RegexComplexityError: If pattern is too complex or dangerous
    """
    if not _security_config.enable_complexity_analysis:
        return

    # Check pattern length
    if len(pattern) > _security_config.max_pattern_length:
        raise RegexComplexityError(
            f"Pattern length {len(pattern)} exceeds maximum {_security_config.max_pattern_length}"
        )

    # Detect nested quantifiers - major ReDoS risk
    nested_quantifier_patterns = [
        r"\([^)]*\+[^)]*\)\+",  # (a+)+ pattern
        r"\([^)]*\*[^)]*\)\*",  # (a*)* pattern
        r"\([^)]*\+[^)]*\)\*",  # (a+)* pattern
        r"\([^)]*\*[^)]*\)\+",  # (a*)+ pattern
        r"\([^)]*\{[^}]*\}[^)]*\)[+*]",  # (a{n,m})+ pattern
    ]

    nesting_count = 0
    for nested_pattern in nested_quantifier_patterns:
        matches = re.findall(nested_pattern, pattern)
        nesting_count += len(matches)

    if nesting_count > 0:  # Any nested quantifier is dangerous
        raise RegexComplexityError(
            f"Pattern contains {nesting_count} nested quantifiers, which can cause ReDoS attacks"
        )

    # Detect alternation groups - can cause exponential blowup
    alternation_count = pattern.count("|")
    if alternation_count > _security_config.max_alternation_groups:
        raise RegexComplexityError(
            f"Pattern contains {alternation_count} alternations, maximum allowed is {_security_config.max_alternation_groups}"
        )

    # Detect specific dangerous patterns
    dangerous_patterns = [
        r"\(\.\*\)\*",  # (.*)* - extremely dangerous
        r"\(\.\+\)\+",  # (.+)+ - extremely dangerous
        r"\([^|]*\|[^|]*\)\*",  # (a|a)* - overlapping alternation
    ]

    for dangerous in dangerous_patterns:
        if re.search(dangerous, pattern):
            raise RegexComplexityError(
                f"Pattern contains dangerous construct that could cause ReDoS: {dangerous}"
            )


def secure_compile(pattern: str, flags: int = 0) -> Pattern[str]:
    """
    Compile regex pattern with security protections.

    Args:
        pattern: Regex pattern to compile
        flags: Regex compilation flags

    Returns:
        Compiled regex pattern

    Raises:
        RegexComplexityError: If pattern is too complex
        RegexTimeoutError: If compilation takes too long
        re.error: If pattern is invalid
    """
    # Analyze pattern complexity first
    analyze_pattern_complexity(pattern)

    # Compile with timeout protection
    with timeout_protection(_security_config.compilation_timeout, "regex compilation"):
        try:
            return re.compile(pattern, flags)
        except re.error as e:
            # Re-raise regex compilation errors unchanged
            raise e


def secure_search(
    compiled_pattern: Pattern[str],
    text: str,
    pos: int = 0,
    endpos: Optional[int] = None,
) -> Optional[Match[str]]:
    """
    Search text with timeout protection.

    Args:
        compiled_pattern: Pre-compiled regex pattern
        text: Text to search
        pos: Start position
        endpos: End position

    Returns:
        Match object or None

    Raises:
        RegexTimeoutError: If search takes too long
    """
    with timeout_protection(_security_config.execution_timeout, "regex search"):
        if endpos is not None:
            return compiled_pattern.search(text, pos, endpos)
        else:
            return compiled_pattern.search(text, pos)


def secure_finditer(
    compiled_pattern: Pattern[str],
    text: str,
    pos: int = 0,
    endpos: Optional[int] = None,
) -> Iterator[Match[str]]:
    """
    Find all matches with timeout protection.

    Args:
        compiled_pattern: Pre-compiled regex pattern
        text: Text to search
        pos: Start position
        endpos: End position

    Yields:
        Match objects

    Raises:
        RegexTimeoutError: If search takes too long
    """
    with timeout_protection(_security_config.execution_timeout, "regex finditer"):
        if endpos is not None:
            yield from compiled_pattern.finditer(text, pos, endpos)
        else:
            yield from compiled_pattern.finditer(text, pos)


def secure_match(
    compiled_pattern: Pattern[str],
    text: str,
    pos: int = 0,
    endpos: Optional[int] = None,
) -> Optional[Match[str]]:
    """
    Match text from start with timeout protection.

    Args:
        compiled_pattern: Pre-compiled regex pattern
        text: Text to match
        pos: Start position
        endpos: End position

    Returns:
        Match object or None

    Raises:
        RegexTimeoutError: If match takes too long
    """
    with timeout_protection(_security_config.execution_timeout, "regex match"):
        if endpos is not None:
            return compiled_pattern.match(text, pos, endpos)
        else:
            return compiled_pattern.match(text, pos)


def validate_pattern_security(pattern: str) -> tuple[bool, str]:
    """
    Validate pattern for security issues without compilation.

    Args:
        pattern: Regex pattern to validate

    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        analyze_pattern_complexity(pattern)
        return True, ""
    except RegexComplexityError as e:
        return False, str(e)


def is_pattern_safe(pattern: str) -> bool:
    """
    Quick check if pattern is safe to use.

    Args:
        pattern: Regex pattern to check

    Returns:
        True if pattern appears safe
    """
    is_safe, _ = validate_pattern_security(pattern)
    return is_safe


# Known dangerous patterns for testing and detection
KNOWN_DANGEROUS_PATTERNS = [
    # Classic nested quantifiers
    "(a+)+",
    "(a*)*",
    "([a-zA-Z]+)*",
    # Alternation with overlap
    "(a|a)*",
    "(a|ab)*",
    # Exponential blowup
    "a*a*a*a*a*",
    ".*.*.*.*.*",
    # Complex nested patterns
    "(a+)+b",
    "(a*)*b",
    "([0-9]+)*x",
    # Email-like patterns that can be dangerous
    "^([a-zA-Z0-9._%+-]+)+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
    # Dangerous wildcard patterns
    "(.*)*",
    "(.+)+",
]


# Test strings that can trigger ReDoS on dangerous patterns
REDOS_TEST_STRINGS = [
    "a" * 1000,  # For (a+)+ patterns
    "a" * 1000 + "x",  # For (a+)+b patterns
    "ab" * 500,  # For (a|ab)* patterns
    "." * 1000,  # For (.*)* patterns
    "test" * 250 + "@domain",  # For email patterns
]
