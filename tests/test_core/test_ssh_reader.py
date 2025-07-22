"""
Tests for SSH log reading functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from dalog.core.remote_reader import SSHLogReader, is_ssh_url, RemoteFileWatcher
from dalog.core.log_processor import LogLine


class TestSSHURLParsing:
    """Test SSH URL parsing functionality."""
    
    def test_is_ssh_url_valid_formats(self):
        """Test that valid SSH URLs are recognized."""
        valid_urls = [
            "user@host:/path/to/log",
            "user@host:/var/log/app.log",
            "admin@192.168.1.1:/logs/error.log",
            "user@host:22:/path/to/log",
            "ssh://user@host:2222/path/to/log",
        ]
        
        for url in valid_urls:
            assert is_ssh_url(url), f"Failed to recognize valid SSH URL: {url}"
    
    def test_is_ssh_url_invalid_formats(self):
        """Test that invalid URLs are not recognized as SSH."""
        invalid_urls = [
            "/path/to/local/file",
            "C:\\Windows\\logs\\app.log",
            "./relative/path.log",
            "http://example.com/log",
            "https://example.com/log",
            "file:///path/to/log",
        ]
        
        for url in invalid_urls:
            assert not is_ssh_url(url), f"Incorrectly recognized as SSH URL: {url}"
    
    def test_ssh_url_parsing(self):
        """Test SSH URL parsing extracts correct components."""
        reader = SSHLogReader("user@example.com:/var/log/app.log")
        reader._parse_ssh_url()
        
        assert reader.user == "user"
        assert reader.host == "example.com"
        assert reader.port == 22
        assert reader.remote_path == "/var/log/app.log"
    
    def test_ssh_url_parsing_with_port(self):
        """Test SSH URL parsing with custom port."""
        reader = SSHLogReader("admin@server.local:2222:/logs/error.log")
        reader._parse_ssh_url()
        
        assert reader.user == "admin"
        assert reader.host == "server.local"
        assert reader.port == 2222
        assert reader.remote_path == "/logs/error.log"


class TestSSHLogReader:
    """Test SSH log reader functionality."""
    
    @patch('dalog.core.remote_reader.SSHClient')
    def test_open_connection(self, mock_ssh_client_class):
        """Test opening SSH connection."""
        # Setup mocks
        mock_ssh_client = Mock()
        mock_sftp_client = Mock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.open_sftp.return_value = mock_sftp_client
        
        # Mock file stats
        mock_stat = Mock()
        mock_stat.st_size = 1024
        mock_sftp_client.stat.return_value = mock_stat
        
        # Create reader and open connection
        reader = SSHLogReader("user@host:/path/to/log")
        reader.open()
        
        # Verify connection was made
        mock_ssh_client.connect.assert_called_once_with(
            hostname="host",
            port=22,
            username="user",
            look_for_keys=True,
            allow_agent=True
        )
        
        # Verify SFTP was opened
        mock_ssh_client.open_sftp.assert_called_once()
        
        # Verify file was checked
        mock_sftp_client.stat.assert_called_once_with("/path/to/log")
        
        assert reader._is_open is True
        assert reader._file_size == 1024
    
    @patch('dalog.core.remote_reader.SSHClient')
    def test_file_not_found(self, mock_ssh_client_class):
        """Test handling of non-existent remote file."""
        # Setup mocks
        mock_ssh_client = Mock()
        mock_sftp_client = Mock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.open_sftp.return_value = mock_sftp_client
        
        # Mock file not found
        mock_sftp_client.stat.side_effect = IOError("File not found")
        
        # Create reader and try to open
        reader = SSHLogReader("user@host:/nonexistent.log")
        
        with pytest.raises(FileNotFoundError):
            reader.open()
        
        # Verify connection was closed
        assert reader._ssh_client is None
        assert reader._is_open is False
    
    @patch('dalog.core.remote_reader.SSHClient')
    def test_read_all_lines(self, mock_ssh_client_class):
        """Test reading all lines from remote file."""
        # Setup mocks
        mock_ssh_client = Mock()
        mock_sftp_client = Mock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.open_sftp.return_value = mock_sftp_client
        
        # Mock file stats
        mock_stat = Mock()
        mock_stat.st_size = 100
        mock_sftp_client.stat.return_value = mock_stat
        
        # Mock file content with context manager
        mock_file = MagicMock()
        mock_file.__iter__ = Mock(return_value=iter([
            "Line 1\n",
            "Line 2\n",
            "Line 3\n",
        ]))
        # Create a mock context manager
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_file
        mock_context.__exit__.return_value = None
        mock_sftp_client.open.return_value = mock_context
        
        # Create reader and read lines
        reader = SSHLogReader("user@host:/path/to/log")
        reader.open()
        
        lines = list(reader.read_lines())
        
        assert len(lines) == 3
        assert lines[0].line_number == 1
        assert lines[0].content == "Line 1"
        assert lines[1].line_number == 2
        assert lines[1].content == "Line 2"
        assert lines[2].line_number == 3
        assert lines[2].content == "Line 3"
    
    @patch('dalog.core.remote_reader.SSHClient')
    def test_read_tail_lines(self, mock_ssh_client_class):
        """Test reading tail lines from remote file."""
        # Setup mocks
        mock_ssh_client = Mock()
        mock_sftp_client = Mock()
        mock_ssh_client_class.return_value = mock_ssh_client
        mock_ssh_client.open_sftp.return_value = mock_sftp_client
        
        # Mock file stats
        mock_stat = Mock()
        mock_stat.st_size = 1000
        mock_sftp_client.stat.return_value = mock_stat
        
        # Mock tail command output
        mock_stdout = Mock()
        mock_stdout.__iter__ = Mock(return_value=iter([
            "Line 98\n",
            "Line 99\n",
            "Line 100\n",
        ]))
        mock_ssh_client.exec_command.return_value = (None, mock_stdout, None)
        
        # Create reader with tail_lines
        reader = SSHLogReader("user@host:/path/to/log", tail_lines=3)
        reader.open()
        reader._total_lines = 100  # Mock total lines
        
        lines = list(reader.read_lines())
        
        assert len(lines) == 3
        assert lines[0].content == "Line 98"
        assert lines[1].content == "Line 99"
        assert lines[2].content == "Line 100"
        
        # Verify tail command was used
        mock_ssh_client.exec_command.assert_called_with(
            'tail -n 3 "/path/to/log"'
        )


class TestRemoteFileWatcher:
    """Test remote file watching functionality."""
    
    @patch('paramiko.SSHClient')
    def test_check_for_changes(self, mock_ssh_client_class):
        """Test detecting file changes."""
        # Setup mocks
        mock_ssh_client = Mock()
        mock_sftp_client = Mock()
        mock_ssh_client.open_sftp.return_value = mock_sftp_client
        
        # Mock file stats
        mock_stat1 = Mock()
        mock_stat1.st_size = 1000
        mock_stat1.st_mtime = 1234567890.0
        
        mock_stat2 = Mock()
        mock_stat2.st_size = 1100  # File has grown
        mock_stat2.st_mtime = 1234567900.0  # And been modified
        
        # Create watcher
        watcher = RemoteFileWatcher(mock_ssh_client, "/path/to/log")
        
        # First check - initialize state
        mock_sftp_client.stat.return_value = mock_stat1
        assert watcher.check_for_changes() is False  # First check returns False (no change)
        
        # Second check - file changed
        mock_sftp_client.stat.return_value = mock_stat2
        assert watcher.check_for_changes() is True
        
        # Third check - no change
        assert watcher.check_for_changes() is False


if __name__ == "__main__":
    pytest.main([__file__])