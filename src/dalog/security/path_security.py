"""
Secure path operations with traversal and size protection.

Provides validation for file paths to prevent:
- Path traversal attacks
- Symlink exploitation
- File size-based DoS attacks
- Directory traversal via environment variables
"""

import os
from pathlib import Path
from typing import List, Optional, Union


class PathSecurityError(Exception):
    """Raised when path operations violate security policies."""

    pass


class PathTraversalError(PathSecurityError):
    """Raised when path traversal attacks are detected."""

    pass


class FileSizeError(PathSecurityError):
    """Raised when files exceed size limits."""

    pass


class SymlinkError(PathSecurityError):
    """Raised when symlinks are detected in restricted contexts."""

    pass


class PathSecurityConfig:
    """Configuration for path security settings."""

    def __init__(
        self,
        max_config_size: int = 1024 * 1024,  # 1MB
        max_log_size: int = 1024 * 1024 * 1024,  # 1GB
        allow_symlinks: bool = False,
        safe_config_dirs: Optional[List[Union[str, Path]]] = None,
        safe_log_dirs: Optional[List[Union[str, Path]]] = None,
    ):
        self.max_config_size = max_config_size
        self.max_log_size = max_log_size
        self.allow_symlinks = allow_symlinks

        # Default safe directories for configs
        if safe_config_dirs is None:
            safe_config_dirs = [
                Path.home() / ".config",
                Path.home(),
                Path.cwd(),
                Path("/etc/dalog"),
            ]
        self.safe_config_dirs = [Path(d).resolve() for d in safe_config_dirs]

        # Default safe directories for logs (more permissive)
        if safe_log_dirs is None:
            safe_log_dirs = [
                Path.home(),
                Path.cwd(),
                Path("/var/log"),
                Path("/tmp"),
            ]
        self.safe_log_dirs = [Path(d).resolve() for d in safe_log_dirs]


# Global security configuration
_security_config = PathSecurityConfig()


def configure_path_security(config: PathSecurityConfig) -> None:
    """Configure global path security settings."""
    global _security_config
    _security_config = config


def validate_no_path_traversal(path: Union[str, Path]) -> Path:
    """
    Validate that path doesn't contain traversal components.

    Args:
        path: Path to validate

    Returns:
        Resolved, validated path

    Raises:
        PathTraversalError: If path contains traversal components
    """
    path_obj = Path(path)

    # Check for .. components in the path
    if ".." in path_obj.parts:
        raise PathTraversalError(f"Path traversal detected: {path}")

    # Resolve the path and check again
    try:
        resolved_path = path_obj.resolve()
    except (OSError, RuntimeError) as e:
        raise PathTraversalError(f"Invalid path: {path} - {e}")

    # Check if resolved path differs significantly (indicating traversal)
    if ".." in str(resolved_path):
        raise PathTraversalError(f"Path traversal in resolved path: {resolved_path}")

    return resolved_path


def validate_safe_directory(path: Union[str, Path], safe_dirs: List[Path]) -> Path:
    """
    Validate that path is within allowed directories.

    Args:
        path: Path to validate
        safe_dirs: List of allowed base directories

    Returns:
        Validated path

    Raises:
        PathSecurityError: If path is outside safe directories
    """
    path_obj = Path(path).resolve()

    # Check if path is within any safe directory
    for safe_dir in safe_dirs:
        try:
            # Check if path is relative to safe directory
            path_obj.relative_to(safe_dir)
            return path_obj
        except ValueError:
            continue

    # If we get here, path is not in any safe directory
    safe_dirs_str = ", ".join(str(d) for d in safe_dirs)
    raise PathSecurityError(
        f"Path outside allowed directories: {path_obj}\n"
        f"Allowed directories: {safe_dirs_str}"
    )


def validate_no_symlinks(path: Union[str, Path]) -> Path:
    """
    Validate that path and its parents don't contain symlinks.

    Args:
        path: Path to validate

    Returns:
        Validated path

    Raises:
        SymlinkError: If symlinks are detected
    """
    path_obj = Path(path)

    # Check if the path itself is a symlink
    if path_obj.is_symlink():
        raise SymlinkError(f"Symlink detected: {path_obj}")

    # Check all parent directories for symlinks
    for parent in path_obj.parents:
        if parent.is_symlink():
            raise SymlinkError(f"Symlink in path hierarchy: {parent} -> {path_obj}")

    return path_obj


def validate_file_size(path: Union[str, Path], max_size: int) -> Path:
    """
    Validate that file size doesn't exceed limits.

    Args:
        path: Path to file
        max_size: Maximum allowed size in bytes

    Returns:
        Validated path

    Raises:
        FileSizeError: If file exceeds size limit
        PathSecurityError: If file cannot be accessed
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise PathSecurityError(f"File does not exist: {path_obj}")

    if not path_obj.is_file():
        raise PathSecurityError(f"Path is not a file: {path_obj}")

    try:
        file_size = path_obj.stat().st_size
    except OSError as e:
        raise PathSecurityError(f"Cannot access file: {path_obj} - {e}")

    if file_size > max_size:
        raise FileSizeError(
            f"File too large: {path_obj}\n"
            f"Size: {file_size:,} bytes (max: {max_size:,} bytes)"
        )

    return path_obj


def validate_config_path(path: Union[str, Path]) -> Path:
    """
    Comprehensively validate a configuration file path.

    Args:
        path: Configuration file path to validate

    Returns:
        Validated, resolved path

    Raises:
        PathSecurityError: If path fails any security checks
    """
    # Step 1: Check for path traversal
    safe_path = validate_no_path_traversal(path)

    # Step 2: Ensure path is in safe directory
    safe_path = validate_safe_directory(safe_path, _security_config.safe_config_dirs)

    # Step 3: Check for symlinks if not allowed
    if not _security_config.allow_symlinks:
        safe_path = validate_no_symlinks(safe_path)

    # Step 4: Check file size
    if safe_path.exists():
        safe_path = validate_file_size(safe_path, _security_config.max_config_size)

    return safe_path


def validate_log_path(path: Union[str, Path]) -> Path:
    """
    Comprehensively validate a log file path.

    Args:
        path: Log file path to validate

    Returns:
        Validated, resolved path

    Raises:
        PathSecurityError: If path fails any security checks
    """
    # Step 1: Check for path traversal
    safe_path = validate_no_path_traversal(path)

    # Step 2: Ensure path is in safe directory (more permissive for logs)
    safe_path = validate_safe_directory(safe_path, _security_config.safe_log_dirs)

    # Step 3: Check for symlinks if not allowed
    if not _security_config.allow_symlinks:
        safe_path = validate_no_symlinks(safe_path)

    # Step 4: Check file size
    if safe_path.exists():
        safe_path = validate_file_size(safe_path, _security_config.max_log_size)

    return safe_path


def validate_environment_path(env_var: str, default: str) -> str:
    """
    Safely validate environment variable paths.

    Args:
        env_var: Environment variable name
        default: Default value if env var is unsafe

    Returns:
        Safe path value
    """
    env_value = os.environ.get(env_var)
    if not env_value:
        return default

    try:
        # Validate the environment path
        safe_path = validate_no_path_traversal(env_value)

        # Ensure it's a reasonable directory
        if not safe_path.is_dir():
            return default

        return str(safe_path)

    except PathSecurityError:
        # If environment path is unsafe, use default
        return default


def get_safe_config_search_paths() -> List[Path]:
    """
    Get safe configuration search paths with environment validation.

    Returns:
        List of safe paths to search for configuration files
    """
    safe_paths = []

    # Validate XDG_CONFIG_HOME environment variable
    xdg_config = validate_environment_path(
        "XDG_CONFIG_HOME", str(Path.home() / ".config")
    )
    safe_paths.append(Path(xdg_config) / "dalog")

    # Add other safe paths
    safe_paths.extend(
        [
            Path.home() / ".config" / "dalog",
            Path.home() / ".dalog.toml",
            Path.cwd() / "config.toml",
        ]
    )

    # Filter to existing directories/files
    return [p for p in safe_paths if p.exists()]


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def get_security_info() -> dict:
    """Get current security configuration info."""
    return {
        "max_config_size": format_size(_security_config.max_config_size),
        "max_log_size": format_size(_security_config.max_log_size),
        "allow_symlinks": _security_config.allow_symlinks,
        "safe_config_dirs": [str(d) for d in _security_config.safe_config_dirs],
        "safe_log_dirs": [str(d) for d in _security_config.safe_log_dirs],
    }
