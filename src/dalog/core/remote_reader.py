"""
Remote log reading functionality via SSH.
"""

import io
import os
import re
import shlex
import stat
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
from urllib.parse import urlparse

import paramiko
from paramiko import (
    AuthenticationException,
    BadHostKeyException,
    MissingHostKeyPolicy,
    RejectPolicy,
    SFTPClient,
    SSHClient,
    SSHException,
    WarningPolicy,
)
from paramiko.ssh_exception import NoValidConnectionsError

from .log_processor import LogLine
from .ssh_pool import PooledConnection, get_ssh_connection_pool


class DalogSecureHostKeyPolicy(MissingHostKeyPolicy):
    """Custom host key policy that rejects unknown hosts with clear error messages."""

    def missing_host_key(self, client, hostname, key):
        """Handle missing host key by rejecting with informative error."""
        key_type = key.get_name()
        fingerprint = key.get_fingerprint().hex()

        raise SSHException(
            f"Host key verification failed for {hostname}\n"
            f"Unknown {key_type} key with fingerprint: {fingerprint}\n"
            f"Add this host to your known_hosts file to proceed.\n"
            f"You can do this by running: ssh-keyscan {hostname} >> ~/.ssh/known_hosts"
        )

class DalogWarningHostKeyPolicy(MissingHostKeyPolicy):
    """Custom host key policy that logs a warning and rejects unknown hosts."""

    def missing_host_key(self, client, hostname, key):
        """Log a warning and reject the connection for unknown host keys."""
        key_type = key.get_name()
        fingerprint = key.get_fingerprint().hex()

        print(
            f"WARNING: Host key verification failed for {hostname}\n"
            f"Unknown {key_type} key with fingerprint: {fingerprint}\n"
            f"Connection will be rejected. Add this host to your known_hosts file to proceed.\n"
            f"You can do this by running: ssh-keyscan {hostname} >> ~/.ssh/known_hosts"
        )
        raise SSHException(f"Host key verification failed for {hostname}")


def create_secure_ssh_client(
    host: str,
    port: int,
    username: str,
    strict_host_key_checking: bool = True,
    known_hosts_file: Optional[str] = None,
    connection_timeout: int = 30,
) -> SSHClient:
    """Create SSH client with secure host key verification.

    Args:
        host: SSH hostname
        port: SSH port
        username: SSH username
        strict_host_key_checking: Whether to enforce strict host key checking
        known_hosts_file: Optional path to known_hosts file
        connection_timeout: Connection timeout in seconds

    Returns:
        Configured SSH client with secure defaults
    """
    ssh_client = SSHClient()

    # Load system and user host keys
    ssh_client.load_system_host_keys()

    # Load user known_hosts files
    if known_hosts_file:
        try:
            ssh_client.load_host_keys(known_hosts_file)
        except FileNotFoundError:
            # If custom known_hosts file doesn't exist, continue with defaults
            pass
    else:
        # Load default user known_hosts file
        default_known_hosts = os.path.expanduser("~/.ssh/known_hosts")
        if os.path.exists(default_known_hosts):
            ssh_client.load_host_keys(default_known_hosts)

    # Set secure host key policy
    if strict_host_key_checking:
        ssh_client.set_missing_host_key_policy(DalogSecureHostKeyPolicy())
    else:
        # Even in non-strict mode, use custom warning policy that rejects unknown hosts
        ssh_client.set_missing_host_key_policy(DalogWarningHostKeyPolicy())

    return ssh_client


@dataclass
class RemoteFileInfo:
    """Information about a remote file."""

    path: str
    size: int
    modified: float
    exists: bool


class LogReader(ABC):
    """Abstract base class for log readers."""

    @abstractmethod
    def open(self) -> None:
        """Open the log source for reading."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the log source."""
        pass

    @abstractmethod
    def get_file_info(self) -> Dict[str, Any]:
        """Get information about the log file."""
        pass

    @abstractmethod
    def read_lines(self, tail_lines: Optional[int] = None) -> Iterator[LogLine]:
        """Read lines from the log."""
        pass

    @abstractmethod
    def get_size(self) -> int:
        """Get the size of the log file."""
        pass


@dataclass
class CachedMetadata:
    """Cached file metadata with TTL."""

    size: int
    mtime: float
    line_count: Optional[int]
    timestamp: float

    def is_expired(self, ttl: float) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.timestamp > ttl


class SSHMetadataCache:
    """Thread-safe cache for SSH file metadata with TTL-based expiration."""

    def __init__(self, default_ttl: float = 10.0):
        """Initialize the metadata cache.

        Args:
            default_ttl: Default time-to-live for cache entries in seconds
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, CachedMetadata] = {}
        self._lock = threading.RLock()

        # Performance metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_expirations = 0

    def get_metadata(
        self, file_path: str, ttl: Optional[float] = None
    ) -> Optional[CachedMetadata]:
        """Get cached metadata for a file.

        Args:
            file_path: Remote file path
            ttl: Time-to-live override (uses default if None)

        Returns:
            Cached metadata if valid, None if expired or not found
        """
        if ttl is None:
            ttl = self.default_ttl

        with self._lock:
            if file_path not in self._cache:
                self.cache_misses += 1
                return None

            cached = self._cache[file_path]
            if cached.is_expired(ttl):
                del self._cache[file_path]
                self.cache_expirations += 1
                self.cache_misses += 1
                return None

            self.cache_hits += 1
            return cached

    def set_metadata(
        self, file_path: str, size: int, mtime: float, line_count: Optional[int] = None
    ) -> None:
        """Cache metadata for a file.

        Args:
            file_path: Remote file path
            size: File size in bytes
            mtime: Modification time
            line_count: Number of lines (optional)
        """
        with self._lock:
            self._cache[file_path] = CachedMetadata(
                size=size, mtime=mtime, line_count=line_count, timestamp=time.time()
            )

    def invalidate(self, file_path: str) -> None:
        """Invalidate cache entry for a file.

        Args:
            file_path: Remote file path to invalidate
        """
        with self._lock:
            self._cache.pop(file_path, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0

        with self._lock:
            return {
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_expirations": self.cache_expirations,
                "hit_rate": hit_rate,
                "cached_files": len(self._cache),
                "total_requests": total_requests,
            }


# Global SSH metadata cache instance
_ssh_metadata_cache = SSHMetadataCache()


class SSHLogReader(LogReader):
    """SSH-based remote log reader with metadata caching."""

    # More restrictive SSH URL pattern to prevent injection
    SSH_URL_PATTERN = re.compile(
        r"^(?:ssh://)?(?P<user>[a-zA-Z0-9._-]+)@(?P<host>[a-zA-Z0-9.-]+)"
        r"(?::(?P<port>[1-9][0-9]{0,4}))?:(?P<path>/[^\s;|&$`\"'<>(){}[\]\\*?]+)$"
    )

    def __init__(
        self,
        ssh_url: str,
        tail_lines: Optional[int] = None,
        strict_host_key_checking: bool = True,
        connection_timeout: int = 30,
        command_timeout: int = 60,
        known_hosts_file: Optional[str] = None,
    ):
        """Initialize SSH log reader.

        Args:
            ssh_url: SSH URL in format user@host:/path/to/log or ssh://user@host:port/path/to/log
            tail_lines: Optional number of lines to tail from end
            strict_host_key_checking: Whether to enforce strict host key checking
            connection_timeout: SSH connection timeout in seconds
            command_timeout: SSH command execution timeout in seconds
            known_hosts_file: Optional path to known_hosts file
        """
        self.ssh_url = ssh_url
        self.tail_lines = tail_lines
        self.encoding = "utf-8"

        # SSH security configuration
        self.strict_host_key_checking = strict_host_key_checking
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        self.known_hosts_file = known_hosts_file

        # Parse and validate SSH URL
        self._parse_ssh_url()

        # SSH connection objects
        self._ssh_client: Optional[SSHClient] = None
        self._sftp_client: Optional[SFTPClient] = None
        self._pooled_connection: Optional[PooledConnection] = None
        self._connection_pool = get_ssh_connection_pool()
        self._is_open = False
        self._file_size = 0
        self._total_lines = 0

    def _parse_ssh_url(self) -> None:
        """Parse SSH URL with enhanced validation to prevent injection attacks."""
        # Basic validation - URL length limit
        if not self.ssh_url or len(self.ssh_url) > 2048:
            raise ValueError(
                "SSH URL is empty or exceeds maximum length (2048 characters)"
            )

        match = self.SSH_URL_PATTERN.match(self.ssh_url)
        if not match:
            raise ValueError(f"Invalid SSH URL format: {self.ssh_url}")

        self.user = match.group("user")
        self.host = match.group("host")
        port_str = match.group("port")
        self.remote_path = match.group("path")

        # Parse and validate port
        if port_str:
            try:
                self.port = int(port_str)
                if not (1 <= self.port <= 65535):
                    raise ValueError(
                        f"Port number must be between 1 and 65535, got: {self.port}"
                    )
            except ValueError as e:
                raise ValueError(f"Invalid port in SSH URL: {port_str} - {e}")
        else:
            self.port = 22

        # Validate individual components
        if not self._validate_ssh_components():
            raise ValueError(f"Invalid SSH URL components: {self.ssh_url}")

    def _validate_ssh_components(self) -> bool:
        """Validate individual SSH URL components for security."""
        # Validate username
        if not self.user or len(self.user) > 64:
            return False

        # Additional username validation - no control characters
        if any(ord(c) < 32 for c in self.user):
            return False

        # Validate hostname
        if not self.host or len(self.host) > 253:
            return False

        # Basic hostname format validation
        if self.host.startswith("-") or self.host.endswith("-") or ".." in self.host:
            return False

        # Validate path
        if (
            not self.remote_path
            or not self.remote_path.startswith("/")
            or len(self.remote_path) > 4096
        ):
            return False

        # Check for path traversal attempts and dangerous patterns
        if ".." in self.remote_path or self.remote_path.count("/") > 50:
            return False

        # Check for null bytes
        if "\x00" in self.remote_path:
            return False

        # Check for suspicious characters that could break shell commands
        dangerous_chars = [
            ";",
            "|",
            "&",
            "$",
            "`",
            '"',
            "'",
            "<",
            ">",
            "(",
            ")",
            "{",
            "}",
            "[",
            "]",
            "\\",
            "*",
            "?",
        ]
        if any(char in self.remote_path for char in dangerous_chars):
            return False

        return True

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _create_ssh_connection(self) -> SSHClient:
        """Factory function to create a new SSH connection for the pool."""
        # Create secure SSH client
        ssh_client = create_secure_ssh_client(
            self.host,
            self.port,
            self.user,
            strict_host_key_checking=self.strict_host_key_checking,
            known_hosts_file=self.known_hosts_file,
            connection_timeout=self.connection_timeout,
        )

        # Connect to SSH server with secure settings
        ssh_client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            look_for_keys=True,
            allow_agent=True,
            timeout=self.connection_timeout,
            # Disable less secure authentication methods
            disabled_algorithms={
                "pubkeys": ["ssh-dss"],  # Disable weak DSA keys
                "kex": ["diffie-hellman-group1-sha1"],  # Disable weak key exchange
            },
        )

        return ssh_client

    def open(self) -> None:
        """Open SSH connection using connection pool."""
        if self._is_open:
            return  # Already open

        try:
            # Get connection from pool
            self._pooled_connection = self._connection_pool.get_connection(
                self.host, self.port, self.user, self._create_ssh_connection
            )

            if self._pooled_connection is None:
                raise ConnectionError(
                    f"Unable to get SSH connection for {self.user}@{self.host}:{self.port}"
                )

            # Set up references to the pooled connection's clients
            self._ssh_client = self._pooled_connection.ssh_client
            self._sftp_client = self._connection_pool.get_sftp_client(
                self._pooled_connection
            )

            if self._sftp_client is None:
                raise ConnectionError("Failed to create SFTP client")

            # Check if file exists and get metadata
            try:
                file_stat = self._sftp_client.stat(self.remote_path)
                self._file_size = file_stat.st_size
                self._is_open = True
            except IOError:
                raise FileNotFoundError(
                    f"Remote file not accessible: {os.path.basename(self.remote_path)}"
                )

        except AuthenticationException:
            self.close()
            raise ConnectionError(
                f"SSH authentication failed for {self.user}@{self.host}"
            )
        except BadHostKeyException as e:
            self.close()
            raise ConnectionError(f"Host key verification failed: {e}")
        except NoValidConnectionsError:
            self.close()
            raise ConnectionError(f"Unable to connect to {self.host}:{self.port}")
        except SSHException as e:
            self.close()
            raise ConnectionError(f"SSH connection error: {e}")
        except Exception as e:
            self.close()
            raise e

    def close(self) -> None:
        """Close SSH connection - return pooled connection to pool."""
        # Return connection to pool instead of closing it
        if self._pooled_connection:
            self._connection_pool.return_connection(self._pooled_connection)
            self._pooled_connection = None

        # Clear references but don't close the actual connections (pool manages them)
        self._sftp_client = None
        self._ssh_client = None
        self._is_open = False

    def get_file_info(self) -> Dict[str, Any]:
        """Get remote file information with caching.

        Returns:
            Dictionary with file information
        """
        if not self._is_open:
            raise RuntimeError("SSH connection must be open to get file info")

        # Try to get from cache first
        cached = _ssh_metadata_cache.get_metadata(self.remote_path)
        if cached is not None:
            # Use cached data
            file_size = cached.size
            file_mtime = cached.mtime
            if cached.line_count is not None:
                self._total_lines = cached.line_count
        else:
            # Cache miss - fetch from remote
            file_stat = self._sftp_client.stat(self.remote_path)
            file_size = file_stat.st_size
            file_mtime = file_stat.st_mtime

            # Count lines if we haven't already or not cached
            if self._total_lines == 0:
                self._count_lines()

            # Cache the metadata
            _ssh_metadata_cache.set_metadata(
                self.remote_path, file_size, file_mtime, self._total_lines
            )

        return {
            "path": f"{self.host}:{self.remote_path}",
            "size": file_size,
            "modified": file_mtime,
            "lines": self._total_lines,
        }

    def get_size(self) -> int:
        """Get the size of the remote file with caching."""
        if not self._is_open:
            raise RuntimeError("SSH connection must be open to get file size")

        # Try cache first
        cached = _ssh_metadata_cache.get_metadata(self.remote_path)
        if cached is not None:
            return cached.size

        # Cache miss - fetch from remote
        file_stat = self._sftp_client.stat(self.remote_path)
        size = file_stat.st_size

        # Cache the metadata (without line count for now)
        _ssh_metadata_cache.set_metadata(self.remote_path, size, file_stat.st_mtime)

        return size

    def _execute_safe_command(self, command_args: List[str]) -> Tuple[str, str, int]:
        """Execute a command with proper argument escaping to prevent injection.

        Args:
            command_args: List of command arguments to execute safely

        Returns:
            Tuple of (stdout, stderr, exit_code)

        Raises:
            RuntimeError: If SSH connection is not established
            ConnectionError: If command execution fails
        """
        if not self._ssh_client:
            raise RuntimeError("SSH connection not established")

        # Use shlex.join for Python 3.8+ or manually join for older versions
        try:
            # Python 3.8+
            safe_command = shlex.join(command_args)
        except AttributeError:
            # Fallback for older Python versions
            safe_command = " ".join(shlex.quote(arg) for arg in command_args)

        try:
            stdin, stdout, stderr = self._ssh_client.exec_command(
                safe_command, timeout=self.command_timeout
            )

            # Read outputs with proper error handling
            stdout_data = stdout.read().decode("utf-8", errors="replace")
            stderr_data = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()

            return stdout_data, stderr_data, exit_code

        except Exception as e:
            raise ConnectionError(f"Failed to execute remote command: {e}")

    def _count_lines(self) -> None:
        """Count total lines in the remote file with caching to avoid repeated wc calls."""
        if not self._ssh_client:
            self._total_lines = 0
            return

        # Try to get line count from metadata cache first
        cached = _ssh_metadata_cache.get_metadata(self.remote_path)
        if cached is not None and cached.line_count is not None:
            self._total_lines = cached.line_count
            return

        try:
            # Cache miss - perform expensive wc command
            stdout_data, stderr_data, exit_code = self._execute_safe_command(
                ["wc", "-l", self.remote_path]
            )

            if exit_code != 0:
                # Don't expose error details that might leak path information
                self._total_lines = 0
                return

            # Extract line count from wc output
            result = stdout_data.strip()
            if result:
                parts = result.split()
                if parts:
                    try:
                        self._total_lines = int(parts[0])

                        # Update cache with line count (get current file stats if needed)
                        if cached is not None:
                            # Update existing cache entry with line count
                            _ssh_metadata_cache.set_metadata(
                                self.remote_path,
                                cached.size,
                                cached.mtime,
                                self._total_lines,
                            )
                        else:
                            # Need to get file stats to cache with line count
                            try:
                                file_stat = self._sftp_client.stat(self.remote_path)
                                _ssh_metadata_cache.set_metadata(
                                    self.remote_path,
                                    file_stat.st_size,
                                    file_stat.st_mtime,
                                    self._total_lines,
                                )
                            except Exception:
                                pass  # Don't fail if we can't cache

                    except ValueError:
                        self._total_lines = 0
            else:
                self._total_lines = 0

        except Exception:
            # Silently handle errors to prevent information disclosure
            self._total_lines = 0

    def read_lines(self, tail_lines: Optional[int] = None) -> Iterator[LogLine]:
        """Read lines from the remote file.

        Args:
            tail_lines: Override default tail_lines if provided

        Yields:
            LogLine objects with line content and metadata
        """
        tail = tail_lines if tail_lines is not None else self.tail_lines

        if tail is not None and tail <= 0:
            return  # Return empty iterator
        elif tail:
            yield from self._read_tail_lines(tail)
        else:
            yield from self._read_all_lines()

    def _read_all_lines(self) -> Iterator[LogLine]:
        """Read all lines from the remote file."""
        if not self._sftp_client:
            return

        line_number = 1
        byte_offset = 0

        with self._sftp_client.open(self.remote_path, "r") as remote_file:
            for line in remote_file:
                # Remove newline characters
                content = line.rstrip("\n\r")
                byte_length = len(line.encode(self.encoding))

                yield LogLine(
                    line_number=line_number,
                    content=content,
                    byte_offset=byte_offset,
                    byte_length=byte_length,
                )

                line_number += 1
                byte_offset += byte_length

        self._total_lines = line_number - 1

    def _read_tail_lines(self, num_lines: int) -> Iterator[LogLine]:
        """Read last N lines from the remote file using secure command execution."""
        if not self._ssh_client or num_lines <= 0:
            return

        try:
            # Validate num_lines to prevent injection and resource abuse
            if not isinstance(num_lines, int) or num_lines <= 0 or num_lines > 10000000:
                raise ValueError(f"Invalid line count: {num_lines}")

            # Use secure command execution with proper escaping
            stdout_data, stderr_data, exit_code = self._execute_safe_command(
                ["tail", "-n", str(num_lines), self.remote_path]
            )

            if exit_code != 0:
                # Don't expose error details that might leak information
                return

            # Get total line count for proper numbering
            if self._total_lines == 0:
                self._count_lines()

            # Calculate starting line number
            start_line = max(1, self._total_lines - num_lines + 1)
            line_number = start_line

            # Process tail output line by line
            for line in stdout_data.splitlines():
                content = line.rstrip("\n\r")
                yield LogLine(
                    line_number=line_number,
                    content=content,
                    byte_offset=0,  # Not accurate for tail
                    byte_length=len(line.encode(self.encoding)),
                )
                line_number += 1

        except Exception:
            # Silently handle errors to prevent information disclosure
            return


class RemoteFileWatcher:
    """Watches remote files for changes via SSH."""

    def __init__(self, ssh_client: SSHClient, remote_path: str):
        """Initialize remote file watcher.

        Args:
            ssh_client: Active SSH client connection
            remote_path: Path to remote file to watch
        """
        self.ssh_client = ssh_client
        self.remote_path = remote_path
        self.last_size = 0
        self.last_mtime = 0.0
        self._sftp_client = None

    def check_for_changes(self) -> bool:
        """Check if the remote file has changed using cached metadata.

        Returns:
            True if file has changed, False otherwise
        """
        try:
            # Try to get recent metadata from cache (2 second TTL for file watching)
            cached = _ssh_metadata_cache.get_metadata(self.remote_path, ttl=2.0)

            if cached is not None:
                # Use cached data
                current_size = cached.size
                current_mtime = cached.mtime
            else:
                # Cache miss or expired - fetch from remote
                if self._sftp_client is None:
                    self._sftp_client = self.ssh_client.open_sftp()

                file_stat = self._sftp_client.stat(self.remote_path)
                current_size = file_stat.st_size
                current_mtime = file_stat.st_mtime

                # Cache with short TTL for file watching (2 seconds)
                _ssh_metadata_cache.set_metadata(
                    self.remote_path, current_size, current_mtime
                )

            # First check - initialize state
            if self.last_size == 0 and self.last_mtime == 0.0:
                self.last_size = current_size
                self.last_mtime = current_mtime
                return False  # No change on first check

            # Check if file has grown or been modified
            changed = current_size != self.last_size or current_mtime != self.last_mtime

            if changed:
                self.last_size = current_size
                self.last_mtime = current_mtime
                # Invalidate cache when file changes to ensure fresh data on next access
                _ssh_metadata_cache.invalidate(self.remote_path)

            return changed
        except Exception:
            # Error checking file, assume no change
            # Close broken SFTP connection so it gets recreated next time
            if self._sftp_client:
                try:
                    self._sftp_client.close()
                except:
                    pass
                self._sftp_client = None
            return False

    def close(self) -> None:
        """Close the SFTP connection."""
        if self._sftp_client:
            try:
                self._sftp_client.close()
            except:
                pass
            self._sftp_client = None


def is_ssh_url(url: str) -> bool:
    """Check if a URL is an SSH URL.

    Args:
        url: URL to check

    Returns:
        True if URL is an SSH URL, False otherwise
    """
    return bool(SSHLogReader.SSH_URL_PATTERN.match(url))


def get_ssh_cache_stats() -> Dict[str, Any]:
    """Get SSH metadata cache statistics.

    Returns:
        Dictionary with cache performance metrics
    """
    return _ssh_metadata_cache.get_stats()


def clear_ssh_cache() -> None:
    """Clear the SSH metadata cache."""
    _ssh_metadata_cache.clear()


def get_ssh_pool_stats() -> Dict[str, Any]:
    """Get SSH connection pool statistics.

    Returns:
        Dictionary with connection pool metrics
    """
    return get_ssh_connection_pool().get_pool_stats()


def close_all_ssh_connections() -> None:
    """Close all SSH connections in the pool."""
    get_ssh_connection_pool().close_all_connections()


def create_log_reader(
    source: str,
    tail_lines: Optional[int] = None,
    strict_host_key_checking: bool = True,
    connection_timeout: int = 30,
    command_timeout: int = 60,
    known_hosts_file: Optional[str] = None,
) -> LogReader:
    """Factory function to create appropriate log reader with security options.

    Args:
        source: File path or SSH URL
        tail_lines: Optional number of lines to tail
        strict_host_key_checking: Whether to enforce strict host key checking
        connection_timeout: SSH connection timeout in seconds
        command_timeout: SSH command execution timeout in seconds
        known_hosts_file: Optional path to known_hosts file

    Returns:
        Appropriate LogReader instance
    """
    if is_ssh_url(source):
        return SSHLogReader(
            source,
            tail_lines,
            strict_host_key_checking=strict_host_key_checking,
            connection_timeout=connection_timeout,
            command_timeout=command_timeout,
            known_hosts_file=known_hosts_file,
        )
    else:
        # For now, return None for local files
        # This will be replaced when we refactor LogProcessor
        raise NotImplementedError("Local file reader not yet implemented as LogReader")
