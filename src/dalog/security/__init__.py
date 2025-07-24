"""
Security module for dalog.

Provides security-hardened implementations of common operations
that could be vulnerable to attacks.
"""

from .path_security import (
    FileSizeError,
    PathSecurityError,
    PathTraversalError,
    SymlinkError,
    configure_path_security,
    get_safe_config_search_paths,
    get_security_info,
    validate_config_path,
    validate_log_path,
)
from .regex_security import (
    RegexComplexityError,
    RegexTimeoutError,
    secure_compile,
    secure_finditer,
    secure_match,
    secure_search,
    validate_pattern_security,
)

__all__ = [
    # Regex security
    "RegexComplexityError",
    "RegexTimeoutError",
    "secure_compile",
    "secure_finditer",
    "secure_match",
    "secure_search",
    "validate_pattern_security",
    # Path security
    "FileSizeError",
    "PathSecurityError",
    "PathTraversalError",
    "SymlinkError",
    "configure_path_security",
    "validate_config_path",
    "validate_log_path",
    "get_safe_config_search_paths",
    "get_security_info",
]
