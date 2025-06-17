"""Tests for CLI functionality."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from dalog.cli import main, print_version
from dalog import __version__


class TestCLI:
    """Test the command-line interface."""
    
    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()
    
    @pytest.fixture
    def sample_log_file(self):
        """Create a sample log file for testing."""
        content = "2024-01-15 10:30:00 INFO Test log entry\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            return Path(f.name)
    
    @pytest.mark.parametrize("option_args,expected_attr,expected_value", [
        (['--version'], None, None),  # Special case - just check exit code and output
        (['-V'], None, None),         # Special case - just check exit code and output
        (['--help'], None, None),     # Special case - just check exit code and output
    ])
    def test_info_options(self, cli_runner, option_args, expected_attr, expected_value):
        """Test version and help options."""
        result = cli_runner.invoke(main, option_args)
        assert result.exit_code == 0
        
        if '--version' in option_args or '-V' in option_args:
            assert __version__ in result.output
        elif '--help' in option_args:
            assert "dalog" in result.output
            assert "View and search a log file" in result.output
            assert "Examples:" in result.output
    
    @patch('dalog.cli.DaLogApp')
    @pytest.mark.parametrize("option_args,expected_attr,expected_value", [
        (['--config', 'test_config.toml'], 'config_path', 'test_config.toml'),
        (['-c', 'test_config.toml'], 'config_path', 'test_config.toml'),
        (['--search', 'ERROR'], 'initial_search', 'ERROR'),
        (['-s', 'WARNING'], 'initial_search', 'WARNING'),
        (['--tail', '100'], 'tail_lines', 100),
        (['-t', '50'], 'tail_lines', 50),
        (['--theme', 'nord'], 'theme', 'nord'),
        (['--theme', 'gruvbox'], 'theme', 'gruvbox'),
    ])
    def test_single_options(self, mock_app_class, cli_runner, sample_log_file, option_args, expected_attr, expected_value):
        """Test individual CLI options."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        # Create config file if needed
        config_file = None
        if '--config' in option_args or '-c' in option_args:
            config_file = Path("test_config.toml")
            config_file.touch()
        
        try:
            result = cli_runner.invoke(main, option_args + [str(sample_log_file)])
            
            # Should pass the expected parameter to DaLogApp
            call_args = mock_app_class.call_args
            assert call_args[1][expected_attr] == expected_value
            
        finally:
            sample_log_file.unlink()
            if config_file and config_file.exists():
                config_file.unlink()
    
    @patch('dalog.cli.DaLogApp')
    @pytest.mark.parametrize("tail_value,expected_value", [
        ('100', 100),
        ('0', 0),
        ('-10', -10),  # Negative values should be accepted
    ])
    def test_tail_option_values(self, mock_app_class, cli_runner, sample_log_file, tail_value, expected_value):
        """Test tail option with different values."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        try:
            result = cli_runner.invoke(main, [
                '--tail', tail_value,
                str(sample_log_file)
            ])
            
            # Should accept the tail value
            call_args = mock_app_class.call_args
            assert call_args[1]['tail_lines'] == expected_value
            
        finally:
            sample_log_file.unlink()
    
    def test_missing_log_file_argument(self, cli_runner):
        """Test CLI with missing log file argument."""
        result = cli_runner.invoke(main, [])
        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output
    
    def test_nonexistent_log_file(self, cli_runner):
        """Test CLI with non-existent log file."""
        result = cli_runner.invoke(main, ['/non/existent/file.log'])
        assert result.exit_code != 0
        # Click should handle the path validation
    
    @patch('dalog.cli.DaLogApp')
    def test_valid_log_file(self, mock_app_class, cli_runner, sample_log_file):
        """Test CLI with valid log file."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        try:
            result = cli_runner.invoke(main, [str(sample_log_file)])
            
            # Should create DaLogApp with correct parameters
            mock_app_class.assert_called_once()
            call_args = mock_app_class.call_args
            assert call_args[1]['log_file'] == str(sample_log_file.resolve())
            assert call_args[1]['config_path'] is None
            assert call_args[1]['initial_search'] is None
            assert call_args[1]['tail_lines'] is None
            assert call_args[1]['theme'] is None
            
            # Should call run() on the app
            mock_app.run.assert_called_once()
            
        finally:
            sample_log_file.unlink()
    
    # Individual option tests are now covered by the parametrized test_single_options above
    
    @patch('dalog.cli.DaLogApp')
    def test_all_options_combined(self, mock_app_class, cli_runner, sample_log_file):
        """Test CLI with all options combined."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        config_file = Path("test_config.toml")
        
        try:
            config_file.touch()
            
            result = cli_runner.invoke(main, [
                '--config', str(config_file),
                '--search', 'WARNING',
                '--tail', '500',
                '--theme', 'gruvbox',
                str(sample_log_file)
            ])
            
            # Should pass all parameters to DaLogApp
            call_args = mock_app_class.call_args
            assert call_args[1]['log_file'] == str(sample_log_file.resolve())
            assert call_args[1]['config_path'] == str(config_file)
            assert call_args[1]['initial_search'] == 'WARNING'
            assert call_args[1]['tail_lines'] == 500
            assert call_args[1]['theme'] == 'gruvbox'
            
        finally:
            sample_log_file.unlink()
            if config_file.exists():
                config_file.unlink()
    
    # Short option variants are covered by test_single_options parametrized tests
    
    @patch('dalog.cli.DaLogApp')
    def test_keyboard_interrupt_handling(self, mock_app_class, cli_runner, sample_log_file):
        """Test handling of KeyboardInterrupt (Ctrl+C)."""
        mock_app = Mock()
        mock_app.run.side_effect = KeyboardInterrupt()
        mock_app_class.return_value = mock_app
        
        try:
            result = cli_runner.invoke(main, [str(sample_log_file)])
            
            # Should exit cleanly on KeyboardInterrupt
            assert result.exit_code == 0
            
        finally:
            sample_log_file.unlink()
    
    @patch('dalog.cli.DaLogApp')
    def test_general_exception_handling(self, mock_app_class, cli_runner, sample_log_file):
        """Test handling of general exceptions."""
        mock_app = Mock()
        mock_app.run.side_effect = RuntimeError("Something went wrong")
        mock_app_class.return_value = mock_app
        
        try:
            result = cli_runner.invoke(main, [str(sample_log_file)])
            
            # Should exit with error code and show error message
            assert result.exit_code == 1
            assert "Error:" in result.output
            assert "Something went wrong" in result.output
            
        finally:
            sample_log_file.unlink()
    
    def test_invalid_tail_value(self, cli_runner, sample_log_file):
        """Test CLI with invalid tail value."""
        try:
            result = cli_runner.invoke(main, [
                '--tail', 'not_a_number',
                str(sample_log_file)
            ])
            
            # Click should handle invalid integer conversion
            assert result.exit_code != 0
            
        finally:
            sample_log_file.unlink()
    
    # Tail value tests are now covered by the parametrized test_tail_option_values above
    
    def test_path_resolution(self, cli_runner):
        """Test that log file path is properly resolved."""
        with patch('dalog.cli.DaLogApp') as mock_app_class:
            mock_app = Mock()
            mock_app_class.return_value = mock_app
            
            # Create a log file in a subdirectory of current working directory
            temp_dir = Path.cwd() / "temp_test_dir"
            temp_dir.mkdir(exist_ok=True)
            log_file = temp_dir / "test.log"
            log_file.write_text("test content")
            
            try:
                # Use relative path
                relative_path = str(log_file.relative_to(Path.cwd()))
                result = cli_runner.invoke(main, [relative_path])
                
                # Should resolve to absolute path
                call_args = mock_app_class.call_args
                passed_path = call_args[1]['log_file']
                assert Path(passed_path).is_absolute()
                assert Path(passed_path) == log_file.resolve()
                
            finally:
                log_file.unlink()
                temp_dir.rmdir()
    
    def test_print_version_function(self):
        """Test the print_version callback function."""
        # Create mock context
        ctx = Mock()
        ctx.resilient_parsing = False
        ctx.exit.side_effect = SystemExit(0)  # Make exit() raise SystemExit
        
        # Test with value=True (version requested)
        with pytest.raises(SystemExit):
            print_version(ctx, None, True)
        
        # Test with value=False (version not requested)
        result = print_version(ctx, None, False)
        assert result is None
        
        # Test with resilient parsing
        ctx.resilient_parsing = True
        result = print_version(ctx, None, True)
        assert result is None 