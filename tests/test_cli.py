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
    
    def test_version_option(self, cli_runner):
        """Test --version option."""
        result = cli_runner.invoke(main, ['--version'])
        assert result.exit_code == 0
        assert __version__ in result.output
    
    def test_version_short_option(self, cli_runner):
        """Test -V version option."""
        result = cli_runner.invoke(main, ['-V'])
        assert result.exit_code == 0
        assert __version__ in result.output
    
    def test_help_option(self, cli_runner):
        """Test --help option."""
        result = cli_runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "dalog" in result.output
        assert "View and search a log file" in result.output
        assert "Examples:" in result.output
    
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
    
    @patch('dalog.cli.DaLogApp')
    def test_config_option(self, mock_app_class, cli_runner, sample_log_file):
        """Test --config option."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        config_file = Path("test_config.toml")
        
        try:
            # Create a dummy config file
            config_file.touch()
            
            result = cli_runner.invoke(main, [
                '--config', str(config_file),
                str(sample_log_file)
            ])
            
            # Should pass config_path to DaLogApp
            call_args = mock_app_class.call_args
            assert call_args[1]['config_path'] == str(config_file)
            
        finally:
            sample_log_file.unlink()
            if config_file.exists():
                config_file.unlink()
    
    @patch('dalog.cli.DaLogApp')
    def test_search_option(self, mock_app_class, cli_runner, sample_log_file):
        """Test --search option."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        try:
            result = cli_runner.invoke(main, [
                '--search', 'ERROR',
                str(sample_log_file)
            ])
            
            # Should pass initial_search to DaLogApp
            call_args = mock_app_class.call_args
            assert call_args[1]['initial_search'] == 'ERROR'
            
        finally:
            sample_log_file.unlink()
    
    @patch('dalog.cli.DaLogApp')
    def test_tail_option(self, mock_app_class, cli_runner, sample_log_file):
        """Test --tail option."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        try:
            result = cli_runner.invoke(main, [
                '--tail', '100',
                str(sample_log_file)
            ])
            
            # Should pass tail_lines to DaLogApp
            call_args = mock_app_class.call_args
            assert call_args[1]['tail_lines'] == 100
            
        finally:
            sample_log_file.unlink()
    
    @patch('dalog.cli.DaLogApp')
    def test_theme_option(self, mock_app_class, cli_runner, sample_log_file):
        """Test --theme option."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app
        
        try:
            result = cli_runner.invoke(main, [
                '--theme', 'nord',
                str(sample_log_file)
            ])
            
            # Should pass theme to DaLogApp
            call_args = mock_app_class.call_args
            assert call_args[1]['theme'] == 'nord'
            
        finally:
            sample_log_file.unlink()
    
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
    
    def test_short_options(self, cli_runner, sample_log_file):
        """Test short option variants."""
        with patch('dalog.cli.DaLogApp') as mock_app_class:
            mock_app = Mock()
            mock_app_class.return_value = mock_app
            
            config_file = Path("test_config.toml")
            
            try:
                config_file.touch()
                
                result = cli_runner.invoke(main, [
                    '-c', str(config_file),
                    '-s', 'INFO',
                    '-t', '50',
                    str(sample_log_file)
                ])
                
                # Should work the same as long options
                call_args = mock_app_class.call_args
                assert call_args[1]['config_path'] == str(config_file)
                assert call_args[1]['initial_search'] == 'INFO'
                assert call_args[1]['tail_lines'] == 50
                
            finally:
                sample_log_file.unlink()
                if config_file.exists():
                    config_file.unlink()
    
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
    
    def test_negative_tail_value(self, cli_runner, sample_log_file):
        """Test CLI with negative tail value."""
        with patch('dalog.cli.DaLogApp') as mock_app_class:
            mock_app = Mock()
            mock_app_class.return_value = mock_app
            
            try:
                result = cli_runner.invoke(main, [
                    '--tail', '-10',
                    str(sample_log_file)
                ])
                
                # Should accept negative values (implementation decides what to do)
                call_args = mock_app_class.call_args
                assert call_args[1]['tail_lines'] == -10
                
            finally:
                sample_log_file.unlink()
    
    def test_zero_tail_value(self, cli_runner, sample_log_file):
        """Test CLI with zero tail value."""
        with patch('dalog.cli.DaLogApp') as mock_app_class:
            mock_app = Mock()
            mock_app_class.return_value = mock_app
            
            try:
                result = cli_runner.invoke(main, [
                    '--tail', '0',
                    str(sample_log_file)
                ])
                
                # Should accept zero tail value
                call_args = mock_app_class.call_args
                assert call_args[1]['tail_lines'] == 0
                
            finally:
                sample_log_file.unlink()
    
    def test_path_resolution(self, cli_runner):
        """Test that log file path is properly resolved."""
        with patch('dalog.cli.DaLogApp') as mock_app_class:
            mock_app = Mock()
            mock_app_class.return_value = mock_app
            
            # Create a log file in a subdirectory
            temp_dir = Path(tempfile.mkdtemp())
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