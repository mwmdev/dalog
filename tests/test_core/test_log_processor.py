"""Tests for log processor functionality."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from dalog.core.log_processor import LogProcessor, LogLine


class TestLogProcessor:
    """Test the LogProcessor class."""
    
    @pytest.fixture
    def sample_log_file(self):
        """Create a temporary log file for testing."""
        content = """2024-01-15 10:30:00 INFO Starting application
2024-01-15 10:30:01 DEBUG Loading config
2024-01-15 10:30:02 ERROR Connection failed
2024-01-15 10:30:03 WARNING High memory usage
2024-01-15 10:30:04 SUCCESS Operation completed"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            return Path(f.name)
    
    @pytest.fixture
    def empty_log_file(self):
        """Create an empty log file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            return Path(f.name)
    
    def test_init_with_valid_file(self, sample_log_file):
        """Test initializing LogProcessor with valid file."""
        try:
            processor = LogProcessor(sample_log_file)
            assert processor.file_path == sample_log_file
            assert processor.tail_lines is None
            assert processor.encoding == 'utf-8'
        finally:
            sample_log_file.unlink()
    
    def test_init_with_tail_lines(self, sample_log_file):
        """Test initializing LogProcessor with tail_lines specified."""
        try:
            processor = LogProcessor(sample_log_file, tail_lines=3)
            assert processor.tail_lines == 3
        finally:
            sample_log_file.unlink()
    
    @pytest.mark.ci_skip
    def test_init_with_nonexistent_file(self):
        """Test initializing LogProcessor with non-existent file."""
        with pytest.raises(FileNotFoundError):
            LogProcessor(Path("/non/existent/file.log"))
    
    def test_get_file_info(self, sample_log_file):
        """Test getting file information."""
        try:
            processor = LogProcessor(sample_log_file)
            with processor:
                file_info = processor.get_file_info()
                
            assert file_info['path'] == str(sample_log_file)
            assert file_info['size'] > 0
            assert 'modified' in file_info
            assert file_info['lines'] == 5  # Sample has 5 lines
        finally:
            sample_log_file.unlink()
    
    def test_get_file_info_empty_file(self, empty_log_file):
        """Test getting file info for empty file."""
        try:
            processor = LogProcessor(empty_log_file)
            with processor:
                file_info = processor.get_file_info()
                
            assert file_info['lines'] == 0
            assert file_info['size'] == 0
        finally:
            empty_log_file.unlink()
    
    def test_read_lines_full_file(self, sample_log_file):
        """Test reading all lines from file."""
        try:
            processor = LogProcessor(sample_log_file)
            with processor:
                lines = list(processor.read_lines())
                
            assert len(lines) == 5
            assert isinstance(lines[0], LogLine)
            assert "Starting application" in lines[0].content
            assert "Operation completed" in lines[4].content
        finally:
            sample_log_file.unlink()
    
    def test_read_lines_with_tail(self, sample_log_file):
        """Test reading lines with tail limit."""
        try:
            processor = LogProcessor(sample_log_file, tail_lines=2)
            with processor:
                lines = list(processor.read_lines())
                
            assert len(lines) == 2
            assert "High memory usage" in lines[0].content
            assert "Operation completed" in lines[1].content
        finally:
            sample_log_file.unlink()
    
    def test_read_lines_tail_larger_than_file(self, sample_log_file):
        """Test reading lines with tail larger than file."""
        try:
            processor = LogProcessor(sample_log_file, tail_lines=10)
            with processor:
                lines = list(processor.read_lines())
                
            # Should return all lines if tail is larger than file
            assert len(lines) == 5
        finally:
            sample_log_file.unlink()
    
    def test_context_manager(self, sample_log_file):
        """Test LogProcessor as context manager."""
        try:
            processor = LogProcessor(sample_log_file)
            
            # Test entering context
            with processor as p:
                assert p is processor
                assert processor._file_handle is not None
                lines = list(p.read_lines())
                assert len(lines) == 5
            
            # Test exiting context
            assert processor._file_handle is None
        finally:
            sample_log_file.unlink()
    
    def test_logline_creation(self):
        """Test LogLine creation and properties."""
        line = LogLine(content="2024-01-15 ERROR Something failed", line_number=42)
        
        assert line.content == "2024-01-15 ERROR Something failed"
        assert line.line_number == 42
        assert line.original_content == "2024-01-15 ERROR Something failed"
        assert str(line) == "2024-01-15 ERROR Something failed"
    
    def test_logline_with_processing(self):
        """Test LogLine with content processing."""
        original = "<b>Bold text</b> with HTML"
        processed = "Bold text with HTML"
        
        line = LogLine(
            content=processed,
            line_number=1,
            original_content=original
        )
        
        assert line.content == processed
        assert line.original_content == original
        assert line.line_number == 1
    
    def test_read_lines_empty_file(self, empty_log_file):
        """Test reading lines from empty file."""
        try:
            processor = LogProcessor(empty_log_file)
            with processor:
                lines = list(processor.read_lines())
                
            assert len(lines) == 0
        finally:
            empty_log_file.unlink()
    
    def test_read_lines_with_encoding_issues(self):
        """Test reading lines with encoding issues."""
        # Create file with non-UTF8 content
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.log', delete=False) as f:
            # Write some bytes that aren't valid UTF-8
            f.write(b"Normal line\n")
            f.write(b"\x80\x81\x82 Invalid UTF-8\n")
            f.write(b"Another normal line\n")
            file_path = Path(f.name)
        
        try:
            processor = LogProcessor(file_path)
            with processor:
                lines = list(processor.read_lines())
                
            # Should handle encoding errors gracefully
            assert len(lines) == 3
            assert "Normal line" in lines[0].content
            assert "Another normal line" in lines[2].content
            # Middle line should have replacement characters or be handled somehow
            
        finally:
            file_path.unlink()
    
    def test_file_modified_during_read(self, sample_log_file):
        """Test behavior when file is modified during reading."""
        try:
            processor = LogProcessor(sample_log_file)
            
            with processor:
                # Read first few lines
                lines = []
                line_iterator = processor.read_lines()
                lines.append(next(line_iterator))
                lines.append(next(line_iterator))
                
                # Modify file during reading
                with open(sample_log_file, 'a') as f:
                    f.write("\n2024-01-15 10:30:05 INFO New line added")
                
                # Continue reading
                remaining_lines = list(line_iterator)
                lines.extend(remaining_lines)
                
            # Should handle gracefully (exact behavior depends on implementation)
            assert len(lines) >= 2
            
        finally:
            sample_log_file.unlink()
    
    @pytest.mark.parametrize("tail_lines,expected_count", [
        (None, 5),
        (0, 0),
        (1, 1),
        (3, 3),
        (10, 5),  # More than file has
    ])
    def test_tail_lines_parameter(self, sample_log_file, tail_lines, expected_count):
        """Test various tail_lines parameter values."""
        try:
            processor = LogProcessor(sample_log_file, tail_lines=tail_lines)
            with processor:
                lines = list(processor.read_lines())
                
            assert len(lines) == expected_count
            
            if expected_count > 0:
                # Should always include the last line when tailing
                assert "Operation completed" in lines[-1].content
                
        finally:
            sample_log_file.unlink()
    
    def test_processor_reusability(self, sample_log_file):
        """Test that processor can be used multiple times."""
        try:
            processor = LogProcessor(sample_log_file)
            
            # First use
            with processor:
                lines1 = list(processor.read_lines())
            
            # Second use
            with processor:
                lines2 = list(processor.read_lines())
            
            # Should get same results
            assert len(lines1) == len(lines2) == 5
            assert lines1[0].content == lines2[0].content
            
        finally:
            sample_log_file.unlink() 