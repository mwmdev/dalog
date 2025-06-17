"""
Efficient log file processing with large file support.
"""

import mmap
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Dict, Any


@dataclass
class LogLine:
    """Represents a single log line with metadata."""

    line_number: int
    content: str
    byte_offset: int = 0
    byte_length: int = 0
    original_content: Optional[str] = None

    def __str__(self) -> str:
        """Return the content of the line."""
        return self.content

    def __post_init__(self):
        """Set default values after initialization."""
        if self.original_content is None:
            self.original_content = self.content
        if self.byte_length == 0:
            self.byte_length = len(self.content.encode('utf-8'))


class LogProcessor:
    """Efficient log file processing with large file support."""

    def __init__(self, file_path: Path, tail_lines: Optional[int] = None):
        """Initialize the log processor.

        Args:
            file_path: Path to the log file
            tail_lines: Optional number of lines to tail from end
            
        Raises:
            FileNotFoundError: If the log file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
            
        self.file_path = file_path
        self.tail_lines = tail_lines
        self.encoding = 'utf-8'
        self._file_size = 0
        self._line_offsets: List[int] = []
        self._total_lines = 0
        self._file_handle = None
        self._mmap = None
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
        if self._file_handle is not None:
            return  # Already open

        try:
            self._file_handle = open(self.file_path, "rb")
            self._file_size = self.file_path.stat().st_size
            self._is_open = True

            if self._file_size > 0:
                self._mmap = mmap.mmap(
                    self._file_handle.fileno(), 0, access=mmap.ACCESS_READ
                )
        except Exception as e:
            self.close()
            raise e

    def close(self) -> None:
        """Close the log file."""
        if self._mmap:
            self._mmap.close()
            self._mmap = None

        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
            
        self._is_open = False

    def get_file_info(self) -> Dict[str, Any]:
        """Get file information including size, modification time, and line count.

        Returns:
            Dictionary with file information
        """
        if not self._is_open:
            raise RuntimeError("File must be open to get file info")

        # Count lines if we haven't already
        if self._total_lines == 0:
            # Count lines by reading through the file
            self._count_lines()

        stat = self.file_path.stat()
        return {
            "path": str(self.file_path),
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "lines": self._total_lines,
        }

    def _count_lines(self) -> None:
        """Count total lines in the file."""
        if not self._mmap:
            self._total_lines = 0
            return
            
        line_count = 0
        for i in range(len(self._mmap)):
            if self._mmap[i] == ord("\n"):
                line_count += 1
                
        # Handle case where file doesn't end with newline
        if len(self._mmap) > 0 and self._mmap[-1] != ord("\n"):
            line_count += 1
            
        self._total_lines = line_count

    def read_lines(self) -> Iterator[LogLine]:
        """Read lines from the file.

        Yields:
            LogLine objects with line content and metadata
        """
        if self.tail_lines is not None and self.tail_lines <= 0:
            return  # Return empty iterator for tail_lines=0
        elif self.tail_lines:
            yield from self._read_tail_lines()
        else:
            yield from self._read_all_lines()

    def _read_all_lines(self) -> Iterator[LogLine]:
        """Read all lines from the file."""
        if not self._mmap:
            self._total_lines = 0
            return

        line_number = 1
        start_offset = 0

        # Iterate through the memory-mapped file
        for i in range(len(self._mmap)):
            if self._mmap[i] == ord("\n"):
                # Found end of line
                line_content = self._mmap[start_offset:i].decode(
                    "utf-8", errors="replace"
                )
                yield LogLine(
                    line_number=line_number,
                    content=line_content.rstrip("\r"),
                    byte_offset=start_offset,
                    byte_length=i - start_offset,
                )
                line_number += 1
                start_offset = i + 1

        # Handle last line if file doesn't end with newline
        if start_offset < len(self._mmap):
            line_content = self._mmap[start_offset:].decode("utf-8", errors="replace")
            yield LogLine(
                line_number=line_number,
                content=line_content.rstrip("\r\n"),
                byte_offset=start_offset,
                byte_length=len(self._mmap) - start_offset,
            )
            line_number += 1

        self._total_lines = line_number - 1

    def _read_tail_lines(self) -> Iterator[LogLine]:
        """Read last N lines efficiently."""
        if not self._mmap or self.tail_lines <= 0:
            self._total_lines = 0
            return

        # Find line breaks from the end
        newline_positions = []
        for i in range(len(self._mmap) - 1, -1, -1):
            if self._mmap[i] == ord("\n"):
                newline_positions.append(i)
                if len(newline_positions) >= self.tail_lines + 1:
                    break

        # Determine start position
        if len(newline_positions) >= self.tail_lines:
            start_pos = newline_positions[self.tail_lines - 1] + 1
        else:
            start_pos = 0

        # Count total lines for line numbering
        total_lines_before = 0
        for i in range(start_pos):
            if self._mmap[i] == ord("\n"):
                total_lines_before += 1

        # Read lines from start position
        line_number = total_lines_before + 1
        current_pos = start_pos

        for i in range(start_pos, len(self._mmap)):
            if self._mmap[i] == ord("\n"):
                line_content = self._mmap[current_pos:i].decode(
                    "utf-8", errors="replace"
                )
                yield LogLine(
                    line_number=line_number,
                    content=line_content.rstrip("\r"),
                    byte_offset=current_pos,
                    byte_length=i - current_pos,
                )
                line_number += 1
                current_pos = i + 1

        # Handle last line
        if current_pos < len(self._mmap):
            line_content = self._mmap[current_pos:].decode("utf-8", errors="replace")
            yield LogLine(
                line_number=line_number,
                content=line_content.rstrip("\r\n"),
                byte_offset=current_pos,
                byte_length=len(self._mmap) - current_pos,
            )
            line_number += 1

        self._total_lines = line_number - 1

    def search_lines(
        self, pattern: str, case_sensitive: bool = False
    ) -> Iterator[Tuple[LogLine, List[Tuple[int, int]]]]:
        """Search for pattern in lines.

        Args:
            pattern: Search pattern (plain text)
            case_sensitive: Whether search is case sensitive

        Yields:
            Tuples of (LogLine, match_positions) where match_positions
            is a list of (start, end) positions of matches in the line
        """
        search_pattern = pattern if case_sensitive else pattern.lower()

        for line in self.read_lines():
            search_content = line.content if case_sensitive else line.content.lower()
            matches = []

            # Find all occurrences
            start = 0
            while True:
                pos = search_content.find(search_pattern, start)
                if pos == -1:
                    break
                matches.append((pos, pos + len(search_pattern)))
                start = pos + 1

            if matches:
                yield (line, matches)

    def get_line_at_offset(self, byte_offset: int) -> Optional[LogLine]:
        """Get the line at a specific byte offset.

        Args:
            byte_offset: Byte offset in the file

        Returns:
            LogLine at that offset or None
        """
        if not self._mmap or byte_offset >= len(self._mmap):
            return None

        # Find start of line
        start = byte_offset
        while start > 0 and self._mmap[start - 1] != ord("\n"):
            start -= 1

        # Find end of line
        end = byte_offset
        while end < len(self._mmap) and self._mmap[end] != ord("\n"):
            end += 1

        # Count line number
        line_number = 1
        for i in range(start):
            if self._mmap[i] == ord("\n"):
                line_number += 1

        line_content = self._mmap[start:end].decode("utf-8", errors="replace")
        return LogLine(
            line_number=line_number,
            content=line_content.rstrip("\r"),
            byte_offset=start,
            byte_length=end - start,
        )
