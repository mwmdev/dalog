"""
Remote log reading functionality via SSH.
"""

import io
import re
import stat
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple, Union, Dict, Any
from urllib.parse import urlparse

import paramiko
from paramiko import SSHClient, AutoAddPolicy, SFTPClient

from .log_processor import LogLine


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


class SSHLogReader(LogReader):
    """SSH-based remote log reader."""
    
    SSH_URL_PATTERN = re.compile(
        r'^(?:ssh://)?(?P<user>[^@]+)@(?P<host>[^:/]+)(?::(?P<port>\d+))?:(?P<path>.+)$'
    )
    
    def __init__(self, ssh_url: str, tail_lines: Optional[int] = None):
        """Initialize SSH log reader.
        
        Args:
            ssh_url: SSH URL in format user@host:/path/to/log or ssh://user@host:port/path/to/log
            tail_lines: Optional number of lines to tail from end
        """
        self.ssh_url = ssh_url
        self.tail_lines = tail_lines
        self.encoding = 'utf-8'
        
        # Parse SSH URL
        self._parse_ssh_url()
        
        # SSH connection objects
        self._ssh_client: Optional[SSHClient] = None
        self._sftp_client: Optional[SFTPClient] = None
        self._is_open = False
        self._file_size = 0
        self._total_lines = 0
    
    def _parse_ssh_url(self) -> None:
        """Parse SSH URL to extract connection details."""
        match = self.SSH_URL_PATTERN.match(self.ssh_url)
        if not match:
            raise ValueError(f"Invalid SSH URL format: {self.ssh_url}")
        
        self.user = match.group('user')
        self.host = match.group('host')
        self.port = int(match.group('port') or 22)
        self.remote_path = match.group('path')
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def open(self) -> None:
        """Open SSH connection and prepare for reading."""
        if self._ssh_client is not None:
            return  # Already open
        
        try:
            # Create SSH client
            self._ssh_client = SSHClient()
            self._ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            
            # Connect to SSH server
            self._ssh_client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                look_for_keys=True,
                allow_agent=True
            )
            
            # Create SFTP client
            self._sftp_client = self._ssh_client.open_sftp()
            
            # Check if file exists
            try:
                file_stat = self._sftp_client.stat(self.remote_path)
                self._file_size = file_stat.st_size
                self._is_open = True
            except IOError:
                raise FileNotFoundError(f"Remote file not found: {self.remote_path}")
                
        except Exception as e:
            self.close()
            raise e
    
    def close(self) -> None:
        """Close SSH connection."""
        if self._sftp_client:
            self._sftp_client.close()
            self._sftp_client = None
        
        if self._ssh_client:
            self._ssh_client.close()
            self._ssh_client = None
        
        self._is_open = False
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get remote file information.
        
        Returns:
            Dictionary with file information
        """
        if not self._is_open:
            raise RuntimeError("SSH connection must be open to get file info")
        
        file_stat = self._sftp_client.stat(self.remote_path)
        
        # Count lines if we haven't already
        if self._total_lines == 0:
            self._count_lines()
        
        return {
            "path": f"{self.host}:{self.remote_path}",
            "size": file_stat.st_size,
            "modified": file_stat.st_mtime,
            "lines": self._total_lines,
        }
    
    def get_size(self) -> int:
        """Get the size of the remote file."""
        if not self._is_open:
            raise RuntimeError("SSH connection must be open to get file size")
        
        file_stat = self._sftp_client.stat(self.remote_path)
        return file_stat.st_size
    
    def _count_lines(self) -> None:
        """Count total lines in the remote file."""
        if not self._sftp_client:
            self._total_lines = 0
            return
        
        # Use wc -l command for efficiency
        stdin, stdout, stderr = self._ssh_client.exec_command(f'wc -l "{self.remote_path}"')
        result = stdout.read().decode().strip()
        
        if result:
            # Extract line count from wc output
            parts = result.split()
            if parts:
                try:
                    self._total_lines = int(parts[0])
                except ValueError:
                    self._total_lines = 0
        else:
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
        
        with self._sftp_client.open(self.remote_path, 'r') as remote_file:
            for line in remote_file:
                # Remove newline characters
                content = line.rstrip('\n\r')
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
        """Read last N lines from the remote file efficiently."""
        if not self._ssh_client or num_lines <= 0:
            return
        
        # Use tail command for efficiency
        stdin, stdout, stderr = self._ssh_client.exec_command(
            f'tail -n {num_lines} "{self.remote_path}"'
        )
        
        # Get total line count for proper numbering
        if self._total_lines == 0:
            self._count_lines()
        
        # Calculate starting line number
        start_line = max(1, self._total_lines - num_lines + 1)
        line_number = start_line
        
        # Read tail output
        for line in stdout:
            content = line.rstrip('\n\r')
            yield LogLine(
                line_number=line_number,
                content=content,
                byte_offset=0,  # Not accurate for tail
                byte_length=len(line.encode(self.encoding)),
            )
            line_number += 1


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
    
    def check_for_changes(self) -> bool:
        """Check if the remote file has changed.
        
        Returns:
            True if file has changed, False otherwise
        """
        try:
            sftp = self.ssh_client.open_sftp()
            try:
                file_stat = sftp.stat(self.remote_path)
                current_size = file_stat.st_size
                current_mtime = file_stat.st_mtime
                
                # First check - initialize state
                if self.last_size == 0 and self.last_mtime == 0.0:
                    self.last_size = current_size
                    self.last_mtime = current_mtime
                    return False  # No change on first check
                
                # Check if file has grown or been modified
                changed = (current_size != self.last_size or 
                          current_mtime != self.last_mtime)
                
                if changed:
                    self.last_size = current_size
                    self.last_mtime = current_mtime
                
                return changed
            finally:
                sftp.close()
        except Exception:
            # Error checking file, assume no change
            return False


def is_ssh_url(url: str) -> bool:
    """Check if a URL is an SSH URL.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is an SSH URL, False otherwise
    """
    return bool(SSHLogReader.SSH_URL_PATTERN.match(url))


def create_log_reader(source: str, tail_lines: Optional[int] = None) -> LogReader:
    """Factory function to create appropriate log reader.
    
    Args:
        source: File path or SSH URL
        tail_lines: Optional number of lines to tail
        
    Returns:
        Appropriate LogReader instance
    """
    if is_ssh_url(source):
        return SSHLogReader(source, tail_lines)
    else:
        # For now, return None for local files
        # This will be replaced when we refactor LogProcessor
        raise NotImplementedError("Local file reader not yet implemented as LogReader")