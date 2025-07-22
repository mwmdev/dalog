"""
Unified log reading interface for local and remote files.
"""

import mmap
from pathlib import Path
from typing import Iterator, Optional, Dict, Any, Union

from .log_processor import LogLine, LogProcessor as OriginalLogProcessor
from .remote_reader import LogReader, SSHLogReader, is_ssh_url


class LocalLogReader(LogReader):
    """Local file log reader using memory-mapped files."""
    
    def __init__(self, file_path: Union[str, Path], tail_lines: Optional[int] = None):
        """Initialize local log reader.
        
        Args:
            file_path: Path to the log file
            tail_lines: Optional number of lines to tail from end
        """
        self.file_path = Path(file_path)
        self.tail_lines = tail_lines
        self._processor: Optional[OriginalLogProcessor] = None
        self._is_open = False
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def open(self) -> None:
        """Open the log file for reading."""
        if self._processor is not None:
            return  # Already open
        
        self._processor = OriginalLogProcessor(self.file_path, tail_lines=self.tail_lines)
        self._processor.open()
        self._is_open = True
    
    def close(self) -> None:
        """Close the log file."""
        if self._processor:
            self._processor.close()
            self._processor = None
        self._is_open = False
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get file information.
        
        Returns:
            Dictionary with file information
        """
        if not self._is_open or not self._processor:
            raise RuntimeError("File must be open to get file info")
        
        return self._processor.get_file_info()
    
    def read_lines(self, tail_lines: Optional[int] = None) -> Iterator[LogLine]:
        """Read lines from the file.
        
        Args:
            tail_lines: Override default tail_lines if provided
            
        Yields:
            LogLine objects with line content and metadata
        """
        if not self._is_open or not self._processor:
            raise RuntimeError("File must be open to read lines")
        
        # If tail_lines is provided, create a new processor with that setting
        if tail_lines is not None and tail_lines != self.tail_lines:
            temp_processor = OriginalLogProcessor(self.file_path, tail_lines=tail_lines)
            temp_processor.open()
            try:
                yield from temp_processor.read_lines()
            finally:
                temp_processor.close()
        else:
            yield from self._processor.read_lines()
    
    def get_size(self) -> int:
        """Get the size of the log file."""
        if not self._is_open:
            raise RuntimeError("File must be open to get size")
        
        return self.file_path.stat().st_size
    
    def search_lines(
        self, pattern: str, case_sensitive: bool = False
    ) -> Iterator[tuple[LogLine, list[tuple[int, int]]]]:
        """Search for pattern in lines.
        
        Args:
            pattern: Search pattern (plain text)
            case_sensitive: Whether search is case sensitive
            
        Yields:
            Tuples of (LogLine, match_positions)
        """
        if not self._is_open or not self._processor:
            raise RuntimeError("File must be open to search lines")
        
        yield from self._processor.search_lines(pattern, case_sensitive)
    
    def get_line_at_offset(self, byte_offset: int) -> Optional[LogLine]:
        """Get the line at a specific byte offset.
        
        Args:
            byte_offset: Byte offset in the file
            
        Returns:
            LogLine at that offset or None
        """
        if not self._is_open or not self._processor:
            raise RuntimeError("File must be open to get line at offset")
        
        return self._processor.get_line_at_offset(byte_offset)


def create_unified_log_reader(
    source: Union[str, Path], 
    tail_lines: Optional[int] = None
) -> LogReader:
    """Factory function to create appropriate log reader.
    
    Args:
        source: File path or SSH URL
        tail_lines: Optional number of lines to tail
        
    Returns:
        Appropriate LogReader instance
    """
    source_str = str(source)
    
    if is_ssh_url(source_str):
        return SSHLogReader(source_str, tail_lines)
    else:
        return LocalLogReader(source_str, tail_lines)