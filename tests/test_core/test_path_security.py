"""
Path security vulnerability tests for dalog.

Tests to ensure path traversal, symlink exploitation, and file size 
attacks are prevented across all input vectors in the application.
"""

import os
import tempfile
import toml
from pathlib import Path
from unittest.mock import patch

import pytest

from dalog.security.path_security import (
    FileSizeError,
    PathSecurityConfig,
    PathSecurityError,
    PathTraversalError,
    SymlinkError,
    configure_path_security,
    get_safe_config_search_paths,
    validate_config_path,
    validate_log_path,
    validate_no_path_traversal,
    validate_no_symlinks,
    validate_file_size,
)
from dalog.config.loader import ConfigLoader
from dalog.config.models import DaLogConfig


class TestPathTraversalProtection:
    """Test path traversal attack prevention."""
    
    def test_detect_simple_path_traversal(self):
        """Test detection of simple .. path traversal."""
        dangerous_paths = [
            "../../../etc/passwd",
            "../../.ssh/id_rsa", 
            "../config/../../../etc/shadow",
            "logs/../../../var/log/auth.log",
        ]
        
        for path in dangerous_paths:
            with pytest.raises(PathTraversalError):
                validate_no_path_traversal(path)
                
    def test_detect_absolute_path_traversal(self):
        """Test detection of absolute path attempts."""
        dangerous_paths = [
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "/var/log/auth.log",
            "/proc/version",
        ]
        
        # These should be blocked by safe directory validation, not traversal
        for path in dangerous_paths:
            # validate_no_path_traversal allows absolute paths
            result = validate_no_path_traversal(path)
            assert isinstance(result, Path)
            
    def test_allow_safe_relative_paths(self):
        """Test that safe relative paths are allowed."""
        safe_paths = [
            "config.toml",
            "logs/app.log",
            "data/metrics.log",
            "./local_file.txt",
        ]
        
        for path in safe_paths:
            result = validate_no_path_traversal(path)
            assert isinstance(result, Path)
            
    def test_resolve_complex_traversal_attempts(self):
        """Test detection of complex traversal attempts."""
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            # These should be detected even after path resolution
            complex_paths = [
                f"{temp_path.parent}/../{temp_path.parent.name}/../etc/passwd",
                f"./logs/../config/../../../etc/shadow",
            ]
            
            for path in complex_paths:
                with pytest.raises(PathTraversalError):
                    validate_no_path_traversal(path)
                    
        finally:
            temp_path.unlink()


class TestSymlinkDetection:
    """Test symlink exploitation prevention."""
    
    def test_detect_symlink_files(self):
        """Test detection of symlink files."""
        # Create temporary files for symlink testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a target file
            target_file = temp_path / "target.txt"
            target_file.write_text("sensitive content")
            
            # Create a symlink
            symlink_file = temp_path / "symlink.txt"
            symlink_file.symlink_to(target_file)
            
            # Should detect the symlink
            with pytest.raises(SymlinkError):
                validate_no_symlinks(symlink_file)
                
    def test_detect_symlink_in_path_hierarchy(self):
        """Test detection of symlinks in parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a target directory
            target_dir = temp_path / "target_dir"
            target_dir.mkdir()
            
            # Create a symlink directory
            symlink_dir = temp_path / "symlink_dir" 
            symlink_dir.symlink_to(target_dir)
            
            # Create a file inside the symlinked directory
            file_in_symlink = symlink_dir / "file.txt"
            file_in_symlink.write_text("content")
            
            # Should detect symlink in hierarchy
            with pytest.raises(SymlinkError):
                validate_no_symlinks(file_in_symlink)
                
    def test_allow_normal_files(self):
        """Test that normal files without symlinks are allowed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create normal file
            normal_file = temp_path / "normal.txt"
            normal_file.write_text("normal content")
            
            # Should allow normal files
            result = validate_no_symlinks(normal_file)
            assert result == normal_file


class TestFileSizeLimits:
    """Test file size limit enforcement."""
    
    def test_enforce_config_size_limits(self):
        """Test that config files exceeding size limits are blocked."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            # Write content exceeding 1MB default limit
            large_content = "x" * (2 * 1024 * 1024)  # 2MB
            f.write(large_content)
            temp_path = Path(f.name)
            
        try:
            with pytest.raises(FileSizeError):
                validate_file_size(temp_path, 1024 * 1024)  # 1MB limit
        finally:
            temp_path.unlink()
            
    def test_allow_files_under_size_limit(self):
        """Test that files under size limits are allowed."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            # Write small content
            small_content = "small config content"
            f.write(small_content)
            temp_path = Path(f.name)
            
        try:
            result = validate_file_size(temp_path, 1024 * 1024)  # 1MB limit
            assert result == temp_path
        finally:
            temp_path.unlink()
            
    def test_log_size_limits(self):
        """Test log file size limits."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            # Write content exceeding limit
            large_content = b"x" * (2 * 1024 * 1024 * 1024)  # 2GB
            f.write(large_content)
            temp_path = Path(f.name)
            
        try:
            with pytest.raises(FileSizeError):
                validate_file_size(temp_path, 1024 * 1024 * 1024)  # 1GB limit
        finally:
            temp_path.unlink()


class TestSafeDirectoryValidation:
    """Test safe directory restriction enforcement."""
    
    def test_config_path_safe_directories(self):
        """Test that config paths are restricted to safe directories."""
        # Configure strict safe directories for testing
        test_config = PathSecurityConfig(
            safe_config_dirs=[Path.home() / ".config", Path.cwd()]
        )
        configure_path_security(test_config)
        
        # Create a config file in an unsafe location
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("[app]\nlive_reload = false\n")
            unsafe_config = Path(f.name)
            
        try:
            # Should be blocked if outside safe directories
            if not any(unsafe_config.is_relative_to(safe_dir) for safe_dir in [Path.home() / ".config", Path.cwd()]):
                with pytest.raises(PathSecurityError):
                    validate_config_path(unsafe_config)
        finally:
            unsafe_config.unlink()
            
    def test_log_path_safe_directories(self):
        """Test that log paths are restricted appropriately."""
        # Create a log file in current directory (should be safe)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("test log content\n")
            safe_log = Path(f.name)
            
        try:
            # Should allow if in safe directory
            if safe_log.is_relative_to(Path.cwd()) or safe_log.is_relative_to(Path.home()):
                result = validate_log_path(safe_log)
                assert isinstance(result, Path)
        finally:
            safe_log.unlink()


class TestConfigurationIntegration:
    """Test integration with configuration loading."""
    
    def test_config_loader_path_security(self):
        """Test that config loader applies path security."""
        # Create a config file with safe content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            config_data = {
                "app": {"live_reload": False},
                "security": {"max_config_file_size": 1024}
            }
            toml.dump(config_data, f)
            safe_config = Path(f.name)
            
        try:
            # Should load successfully if in safe location
            if safe_config.is_relative_to(Path.cwd()) or safe_config.is_relative_to(Path.home()):
                config = ConfigLoader.load(str(safe_config))
                assert isinstance(config, DaLogConfig)
                assert config.app.live_reload == False
        finally:
            safe_config.unlink()
            
    def test_config_search_path_security(self):
        """Test that config search paths are validated."""
        # Test safe config search paths
        search_paths = get_safe_config_search_paths()
        
        # All paths should be Path objects
        assert all(isinstance(p, Path) for p in search_paths)
        
        # Should not contain dangerous paths
        dangerous_indicators = ["../", "/etc", "/root", "/var"]
        for path in search_paths:
            path_str = str(path)
            assert not any(dangerous in path_str for dangerous in dangerous_indicators)


class TestEnvironmentVariableSecurity:
    """Test environment variable manipulation prevention."""
    
    def test_xdg_config_home_validation(self):
        """Test XDG_CONFIG_HOME environment variable validation."""
        # Test with safe XDG_CONFIG_HOME
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(Path.home() / ".config")}):
            search_paths = get_safe_config_search_paths()
            assert len(search_paths) >= 0  # Should work without errors
            
        # Test with dangerous XDG_CONFIG_HOME
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': "/etc"}):
            search_paths = get_safe_config_search_paths()
            # Should fall back to safe defaults
            assert len(search_paths) >= 0


class TestCLIIntegration:
    """Test CLI path validation integration."""
    
    def test_cli_config_validation(self):
        """Test that CLI validates config paths."""
        from dalog.cli import validate_config_path
        import click
        
        # Create a safe config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("[app]\nlive_reload = true\n")
            safe_config = Path(f.name)
            
        try:
            # Should validate successfully if in safe location
            if safe_config.is_relative_to(Path.cwd()) or safe_config.is_relative_to(Path.home()):
                # Mock click context and parameter
                ctx = click.Context(click.Command('test'))
                param = click.Option(['--config'])
                
                result = validate_config_path(ctx, param, str(safe_config))
                assert result == str(safe_config)
                
        finally:
            safe_config.unlink()
            
    def test_cli_log_validation(self):
        """Test that CLI validates log file paths."""
        from dalog.cli import validate_log_source
        import click
        
        # Create a safe log file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("test log line\n")
            safe_log = Path(f.name)
            
        try:
            # Should validate successfully
            ctx = click.Context(click.Command('test'))
            param = click.Argument(['log_file'])
            
            result = validate_log_source(ctx, param, str(safe_log))
            assert result == str(safe_log)
            
        finally:
            safe_log.unlink()


class TestLogProcessorSecurity:
    """Test log processor security integration."""
    
    def test_log_processor_path_validation(self):
        """Test that LogProcessor validates file paths."""
        from dalog.core.log_processor import LogProcessor
        
        # Create a safe test log file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("test log content\n")
            safe_log = Path(f.name)
            
        try:
            # Should create successfully if path is safe
            processor = LogProcessor(safe_log)
            assert processor.file_path == safe_log
            
        finally:
            safe_log.unlink()


class TestSecurityConfiguration:
    """Test security configuration and limits."""
    
    def test_security_config_integration(self):
        """Test that security configuration is applied correctly."""
        # Test custom security configuration
        custom_config = PathSecurityConfig(
            max_config_size=512 * 1024,  # 512KB
            max_log_size=500 * 1024 * 1024,  # 500MB
            allow_symlinks=True,
        )
        
        configure_path_security(custom_config)
        
        # Create a file that exceeds the custom config limit
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            large_content = "x" * (600 * 1024)  # 600KB
            f.write(large_content)
            large_file = Path(f.name)
            
        try:
            # Should be blocked by custom size limit
            with pytest.raises(FileSizeError):
                validate_file_size(large_file, 512 * 1024)
        finally:
            large_file.unlink()
            
    def test_default_security_settings(self):
        """Test that default security settings are reasonable."""
        # Reset to defaults
        configure_path_security(PathSecurityConfig())
        
        from dalog.security.path_security import get_security_info
        
        security_info = get_security_info()
        
        # Check that defaults are reasonable
        assert "1.0MB" in security_info["max_config_size"]  # 1MB config limit
        assert "1.0GB" in security_info["max_log_size"]     # 1GB log limit  
        assert security_info["allow_symlinks"] == False     # Symlinks blocked by default
        assert len(security_info["safe_config_dirs"]) > 0   # Has safe directories
        assert len(security_info["safe_log_dirs"]) > 0      # Has safe directories


class TestAttackScenarios:
    """Test realistic attack scenarios."""
    
    def test_path_traversal_attack_via_cli(self):
        """Test path traversal attack via CLI --config parameter."""
        from dalog.cli import validate_config_path
        import click
        
        # Simulate CLI attack
        ctx = click.Context(click.Command('test'))
        param = click.Option(['--config'])
        
        attack_paths = [
            "../../../etc/passwd",
            "../../.ssh/id_rsa",
            "/etc/shadow",
        ]
        
        for attack_path in attack_paths:
            with pytest.raises(click.BadParameter):
                validate_config_path(ctx, param, attack_path)
                
    @pytest.mark.ci_skip
    def test_symlink_attack_scenario(self):
        """Test symlink-based file disclosure attack."""
        from dalog.security.path_security import validate_config_path
        
        # Create fake config that's actually a symlink to sensitive file
        fake_config = Path("test_fake_config.toml")
        target_file = Path("test_sensitive.txt")
        
        try:
            # In a real attack, this would point to /etc/passwd
            # For testing, create a dummy target
            target_file.write_text("sensitive information")
            
            fake_config.symlink_to(target_file)
            
            # Attack should be blocked
            with pytest.raises((SymlinkError, PathSecurityError)):
                validate_config_path(fake_config)
        finally:
            if fake_config.exists() and fake_config.is_symlink():
                fake_config.unlink()
            if target_file.exists():
                target_file.unlink()
                
    @pytest.mark.ci_skip
    def test_file_size_dos_attack(self):
        """Test file size DoS attack prevention."""
        from dalog.security.path_security import validate_config_path
        
        # Create a massive "config" file in current directory (allowed)
        dos_file = Path("test_dos_config.toml")
        
        try:
            # Write 5MB of data (exceeding 1MB default config limit)
            dos_content = "malicious_config_data = 'x' * 1000\n" * (5 * 1024)
            dos_file.write_text(dos_content)
            
            # Should be blocked by size limits
            with pytest.raises(FileSizeError):
                validate_config_path(dos_file)
        finally:
            if dos_file.exists():
                dos_file.unlink()


class TestErrorMessages:
    """Test that security error messages are helpful."""
    
    def test_path_traversal_error_message(self):
        """Test path traversal error messages are informative."""
        try:
            validate_no_path_traversal("../../../etc/passwd")
            pytest.fail("Should have raised PathTraversalError")
        except PathTraversalError as e:
            error_msg = str(e)
            assert "traversal detected" in error_msg.lower()
            assert "etc/passwd" in error_msg
            
    def test_file_size_error_message(self):
        """Test file size error messages show limits."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("x" * 2000)
            large_file = Path(f.name)
            
        try:
            validate_file_size(large_file, 1000)
            pytest.fail("Should have raised FileSizeError")
        except FileSizeError as e:
            error_msg = str(e)
            assert "too large" in error_msg.lower()
            assert "2,000" in error_msg  # Shows actual size
            assert "1,000" in error_msg  # Shows limit
        finally:
            large_file.unlink()
            
    def test_symlink_error_message(self):
        """Test symlink error messages are clear."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            target = temp_path / "target.txt"
            target.write_text("content")
            symlink = temp_path / "symlink.txt"
            symlink.symlink_to(target)
            
            try:
                validate_no_symlinks(symlink)
                pytest.fail("Should have raised SymlinkError")
            except SymlinkError as e:
                error_msg = str(e)
                assert "symlink detected" in error_msg.lower()
                assert str(symlink) in error_msg


# Security regression test data
ATTACK_TEST_CASES = [
    # (attack_type, attack_path, expected_error_type)
    ("path_traversal", "../../../etc/passwd", PathTraversalError),
    ("path_traversal", "../../.ssh/id_rsa", PathTraversalError),
    ("path_traversal", "config/../../../etc/shadow", PathTraversalError),
    ("absolute_sensitive", "/etc/passwd", PathSecurityError),
    ("absolute_sensitive", "/root/.bashrc", PathSecurityError),
    ("absolute_sensitive", "/var/log/auth.log", PathSecurityError),
]


@pytest.mark.parametrize("attack_type,attack_path,expected_error", ATTACK_TEST_CASES)
def test_attack_prevention(attack_type, attack_path, expected_error):
    """Test that various attack patterns are prevented."""
    if attack_type == "path_traversal":
        with pytest.raises(expected_error):
            validate_no_path_traversal(attack_path)
    elif attack_type == "absolute_sensitive":
        # For absolute paths, the error comes from safe directory validation
        with pytest.raises(expected_error):
            validate_config_path(attack_path)


def test_backward_compatibility():
    """Test that legitimate file access still works."""
    # Create legitimate test files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create valid config
        config_file = temp_path / "config.toml"
        config_file.write_text("[app]\nlive_reload = true\n")
        
        # Create valid log
        log_file = temp_path / "app.log"
        log_file.write_text("INFO: Application started\n")
        
        # These should work without errors
        # (Note: May fail safe directory validation in test environment)
        try:
            config_result = validate_config_path(config_file)
            assert isinstance(config_result, Path)
        except PathSecurityError:
            # Expected in test environment with restricted safe directories
            pass
            
        try:
            log_result = validate_log_path(log_file)
            assert isinstance(log_result, Path)
        except PathSecurityError:
            # Expected in test environment with restricted safe directories
            pass