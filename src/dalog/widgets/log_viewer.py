"""
Enhanced log viewer widget with search and styling capabilities.
"""

from typing import List, Optional, Tuple, Set
from dataclasses import dataclass

from textual.widgets import RichLog
from textual.reactive import reactive
from rich.text import Text
from rich.style import Style
from rich.highlighter import Highlighter

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

from ..core.log_processor import LogProcessor, LogLine
from ..core.styling import StylingEngine
from ..core.exclusions import ExclusionManager
from ..core.html_processor import HTMLProcessor
from ..config import DaLogConfig


@dataclass
class SearchMatch:
    """Represents a search match in a log line."""
    line_number: int
    start: int
    end: int


class LogViewerWidget(RichLog):
    """Enhanced log viewer with search and styling capabilities."""
    
    # Reactive properties
    search_term = reactive("", always_update=True)
    search_active = reactive(False)
    total_lines = reactive(0)
    visible_lines = reactive(0)
    filtered_lines = reactive(0)
    
    # Visual mode properties
    visual_mode = reactive(False)
    visual_cursor_line = reactive(-1)  # Current cursor position in visual mode
    visual_selection_active = reactive(False)  # Whether selection is active
    visual_start_line = reactive(-1)  # Selection start
    visual_end_line = reactive(-1)  # Selection end
    
    def __init__(
        self,
        config: DaLogConfig,
        **kwargs
    ):
        """Initialize the log viewer.
        
        Args:
            config: Application configuration
            **kwargs: Additional arguments for RichLog
        """
        super().__init__(
            highlight=True,
            markup=True,
            wrap=config.display.wrap_lines,
            auto_scroll=True,
            **kwargs
        )
        self.config = config
        self.all_lines: List[LogLine] = []
        self.displayed_lines: List[int] = []  # Line numbers of displayed lines
        self.search_matches: List[SearchMatch] = []
        
        # Initialize styling engine
        self.styling_engine = StylingEngine(config.styling)
        
        # Initialize HTML processor
        self.html_processor = HTMLProcessor(config.html)
        
        # Initialize exclusion manager - this should be passed in or shared
        self.exclusion_manager = ExclusionManager(
            patterns=config.exclusions.patterns,
            is_regex=config.exclusions.regex,
            case_sensitive=config.exclusions.case_sensitive
        )
        
    def load_from_processor(self, processor: LogProcessor) -> None:
        """Load lines from a log processor.
        
        Args:
            processor: LogProcessor instance
        """
        # Clear existing content
        self.clear()
        self.all_lines.clear()
        self.displayed_lines.clear()
        self.search_matches.clear()
        
        # Load all lines
        for line in processor.read_lines():
            self.all_lines.append(line)
            
        self.total_lines = len(self.all_lines)
        
        # Apply initial display
        self._refresh_display()
        
    def _refresh_display(self) -> None:
        """Refresh the display based on current filters and search."""
        self.clear()
        self.displayed_lines.clear()
        
        # Reset excluded lines counter for accurate counts
        self.exclusion_manager.reset_excluded_lines()
        
        line_index = 0
        for line in self.all_lines:
            # Check exclusion patterns
            if self.exclusion_manager.is_excluded(line.content, line.line_number):
                continue
                
            # Apply search filter if active
            if self.search_active and self.search_term:
                if not self._matches_search(line):
                    continue
                    
            # Display the line
            styled_text = self._style_line(line, line_index)
            self.write(styled_text)
            self.displayed_lines.append(line.line_number)
            line_index += 1
            
        self.visible_lines = len(self.displayed_lines)
        self.filtered_lines = self.total_lines - self.visible_lines
        
    def _matches_search(self, line: LogLine) -> bool:
        """Check if a line matches the current search term.
        
        Args:
            line: LogLine to check
            
        Returns:
            True if line matches search
        """
        if not self.search_term:
            return True
            
        search_content = line.content
        search_pattern = self.search_term
        
        if not self.config.app.case_sensitive_search:
            search_content = search_content.lower()
            search_pattern = search_pattern.lower()
            
        return search_pattern in search_content
        
    def _style_line(self, line: LogLine, display_index: Optional[int] = None) -> Text:
        """Apply styling to a log line.
        
        Args:
            line: LogLine to style
            display_index: Index in displayed lines (for visual mode highlighting)
            
        Returns:
            Styled Rich Text object
        """
        # First, process HTML in the line
        html_segments = self.html_processor.process_html(line.content)
        
        # Create text with HTML styling
        text = Text()
        for content, style in html_segments:
            if style:
                text.append(content, style=style)
            else:
                text.append(content)
        
        # Then apply regex-based styling on top
        # Get the plain text to apply patterns
        plain_text = text.plain
        
        # Use styling engine to find pattern matches
        pattern_text = self.styling_engine.apply_styling(plain_text)
        
        # Merge pattern styles with HTML styles
        # Pattern styles take precedence over HTML styles
        for start, end, style in pattern_text._spans:
            text.stylize(style, start, end)
        
        # Add line number if configured
        if self.config.display.show_line_numbers:
            line_num_text = Text(f"{line.line_number:6d} │ ", style="dim")
            text = line_num_text + text
            
        # Apply visual mode highlighting if applicable
        if self.visual_mode and display_index is not None:
            if self._is_visual_line(display_index):
                bg_color = self.config.display.visual_mode_bg
                text.stylize(f"black on {bg_color}", 0, len(text))
        
        return text
    
    def _is_visual_line(self, display_index: int) -> bool:
        """Check if a line should be highlighted in visual mode.
        
        Args:
            display_index: Index in displayed lines
            
        Returns:
            True if line should be highlighted
        """
        if not self.visual_mode:
            return False
            
        # Cursor line is always highlighted
        if display_index == self.visual_cursor_line:
            return True
            
        # If selection is active, check if line is in range
        if self.visual_selection_active:
            start, end = self._get_selection_range()
            return start <= display_index <= end
            
        return False
    
    def _get_selection_range(self) -> Tuple[int, int]:
        """Get the normalized selection range.
        
        Returns:
            Tuple of (start, end) indices, where start <= end
        """
        if not self.visual_selection_active:
            return (-1, -1)
        return (
            min(self.visual_start_line, self.visual_end_line),
            max(self.visual_start_line, self.visual_end_line)
        )
        
    def update_search(self, search_term: str) -> None:
        """Update the search term and refresh display.
        
        Args:
            search_term: New search term
        """
        self.search_term = search_term
        self.search_active = bool(search_term)
        self._refresh_display()
        
    def clear_search(self) -> None:
        """Clear the current search."""
        self.search_term = ""
        self.search_active = False
        self._refresh_display()
        
    def refresh_exclusions(self) -> None:
        """Refresh display after exclusion changes."""
        self._refresh_display()
        
    def get_status_info(self) -> dict:
        """Get status information for display.
        
        Returns:
            Dictionary with status information
        """
        return {
            'total_lines': self.total_lines,
            'visible_lines': self.visible_lines,
            'filtered_lines': self.filtered_lines,
            'search_active': self.search_active,
            'search_term': self.search_term,
            'excluded_count': self.exclusion_manager.get_excluded_count(),
            'visual_mode': self.visual_mode,
            'visual_selection_active': self.visual_selection_active,
            'selected_lines': self.get_selected_line_count() if self.visual_selection_active else 0,
            'cursor_line': self.displayed_lines[self.visual_cursor_line] if self.visual_mode and 0 <= self.visual_cursor_line < len(self.displayed_lines) else None,
        }
        
    def get_current_viewport_line(self) -> int:
        """Get the line index that's currently in the middle of the viewport.
        
        Returns:
            Index in displayed_lines, or 0 if cannot determine
        """
        if not self.displayed_lines:
            return 0
            
        # Get the current scroll position
        scroll_y = self.scroll_offset.y
        
        # Get the visible height of the widget
        visible_height = self.size.height
        
        # Calculate the middle line of the viewport
        middle_line = scroll_y + (visible_height // 2)
        
        # Ensure it's within valid bounds
        if middle_line >= len(self.displayed_lines):
            return len(self.displayed_lines) - 1
        elif middle_line < 0:
            return 0
            
        return middle_line
        
    def enter_visual_mode(self, line_index: Optional[int] = None) -> None:
        """Enter visual line mode.
        
        Args:
            line_index: Optional starting line index (0-based). If None, uses current viewport position.
        """
        if not self.displayed_lines:
            return
            
        # Use current viewport position if not specified
        if line_index is None:
            line_index = self.get_current_viewport_line()
            
        if 0 <= line_index < len(self.displayed_lines):
            self.visual_mode = True
            self.visual_cursor_line = line_index
            self.visual_selection_active = False
            self.visual_start_line = -1
            self.visual_end_line = -1
            
            # Ensure the cursor line is visible
            self._ensure_line_visible(line_index)
            
            self._refresh_display()
            
    def exit_visual_mode(self) -> None:
        """Exit visual line mode."""
        self.visual_mode = False
        self.visual_cursor_line = -1
        self.visual_selection_active = False
        self.visual_start_line = -1
        self.visual_end_line = -1
        self._refresh_display()
        
    def move_visual_cursor(self, direction: int) -> None:
        """Move visual cursor up or down.
        
        Args:
            direction: -1 for up, 1 for down
        """
        if not self.visual_mode or not self.displayed_lines:
            return
            
        new_cursor = self.visual_cursor_line + direction
        if 0 <= new_cursor < len(self.displayed_lines):
            self.visual_cursor_line = new_cursor
            
            # If selection is active, update the end position
            if self.visual_selection_active:
                self.visual_end_line = new_cursor
            
            # Ensure cursor is visible by scrolling if needed
            self._ensure_line_visible(new_cursor)
                
            self._refresh_display()
            
    def _ensure_line_visible(self, line_index: int) -> None:
        """Ensure a line is visible in the viewport by scrolling if necessary.
        
        Args:
            line_index: Index of line in displayed_lines to make visible
        """
        if not 0 <= line_index < len(self.displayed_lines):
            return
            
        # Get current scroll position and viewport height
        scroll_y = self.scroll_offset.y
        visible_height = self.size.height
        
        # Calculate the visible range
        visible_start = scroll_y
        visible_end = scroll_y + visible_height - 1
        
        # If line is above visible area, scroll up
        if line_index < visible_start:
            self.scroll_to(0, line_index)
        # If line is below visible area, scroll down
        elif line_index > visible_end:
            # Scroll so the line is at the bottom of the viewport
            new_scroll_y = line_index - visible_height + 1
            self.scroll_to(0, max(0, new_scroll_y))
        
    def start_visual_selection(self) -> None:
        """Start selection from current cursor position."""
        if not self.visual_mode:
            return
            
        self.visual_selection_active = True
        self.visual_start_line = self.visual_cursor_line
        self.visual_end_line = self.visual_cursor_line
        self._refresh_display()
        
    def get_selected_line_count(self) -> int:
        """Get the number of selected lines in visual mode."""
        if not self.visual_mode or not self.visual_selection_active:
            return 0
        start, end = self._get_selection_range()
        return end - start + 1
        
    def copy_selected_lines(self) -> bool:
        """Copy selected lines to clipboard.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.visual_mode or not self.visual_selection_active or not self.displayed_lines:
            return False
            
        if not HAS_CLIPBOARD:
            self.app.notify("Clipboard support not available. Install pyperclip.", severity="warning")
            return False
            
        # Get the range of selected lines
        start, end = self._get_selection_range()
        
        # Collect the content of selected lines
        selected_content = []
        for i in range(start, end + 1):
            if i < len(self.displayed_lines):
                line_num = self.displayed_lines[i]
                # Find the corresponding LogLine
                for line in self.all_lines:
                    if line.line_number == line_num:
                        selected_content.append(line.content)
                        break
                        
        if selected_content:
            try:
                clipboard_text = '\n'.join(selected_content)
                pyperclip.copy(clipboard_text)
                return True
            except Exception as e:
                self.app.notify(f"Failed to copy to clipboard: {e}", severity="error")
                return False
        return False 