"""
Enhanced log viewer widget with search and styling capabilities.
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from rich.highlighter import Highlighter
from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import RichLog

try:
    import pyperclip

    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

from ..config import DaLogConfig
from ..core.exclusions import ExclusionManager
from ..core.html_processor import HTMLProcessor
from ..core.log_processor import LogLine, LogProcessor
from ..core.remote_reader import LogReader
from ..core.styling import StylingEngine


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

    def __init__(self, config: DaLogConfig, **kwargs):
        """Initialize the log viewer.

        Args:
            config: Application configuration
            **kwargs: Additional arguments for RichLog
        """
        super().__init__(
            highlight=True,
            markup=True,
            wrap=config.display.wrap_lines,
            auto_scroll=True,  # Enable auto-scroll to always stay at bottom
            **kwargs,
        )
        self.config = config
        self.all_lines: List[LogLine] = []
        self.displayed_lines: List[int] = []  # Line numbers of displayed lines
        self.search_matches: List[SearchMatch] = []

        # Initialize styling engine
        self.styling_engine = StylingEngine(config.styling)

        # Initialize HTML processor
        self.html_processor = HTMLProcessor(config.html)

        # Initialize exclusion manager
        self.exclusion_manager = ExclusionManager(
            patterns=config.exclusions.patterns,
            is_regex=config.exclusions.regex,
        )

    def debug_scroll_state(self) -> dict:
        """Get debug information about scroll state."""
        height = getattr(self.size, "height", 0) if hasattr(self, "size") else 0
        current_scroll = (
            getattr(self.scroll_offset, "y", 0) if hasattr(self, "scroll_offset") else 0
        )
        max_scroll = max(0, len(self.displayed_lines) - height) if height > 0 else 0

        return {
            "displayed_lines": len(self.displayed_lines),
            "total_lines": self.total_lines,
            "widget_height": height,
            "current_scroll_y": current_scroll,
            "max_scroll": max_scroll,
            "is_at_bottom": (
                current_scroll >= max_scroll - 1 if max_scroll > 0 else True
            ),
        }

    def load_from_processor(
        self, processor: LogProcessor, scroll_to_end: bool = True
    ) -> None:
        """Load lines from a log processor.

        Args:
            processor: LogProcessor instance
            scroll_to_end: Whether to scroll to end after loading (useful for tail mode)
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

        # Apply initial display - auto_scroll will handle scrolling to end
        self._refresh_display(preserve_scroll=False)

    def load_from_reader(self, reader: LogReader, scroll_to_end: bool = True) -> None:
        """Load lines from a unified log reader (supports both local and SSH).

        Args:
            reader: LogReader instance (LocalLogReader or SSHLogReader)
            scroll_to_end: Whether to scroll to end after loading (useful for tail mode)
        """
        # Clear existing content
        self.clear()
        self.all_lines.clear()
        self.displayed_lines.clear()
        self.search_matches.clear()

        # Load all lines
        for line in reader.read_lines():
            self.all_lines.append(line)

        self.total_lines = len(self.all_lines)

        # Apply initial display - auto_scroll will handle scrolling to end
        self._refresh_display(preserve_scroll=False)

    def _refresh_display(self, preserve_scroll: bool = True) -> None:
        """Refresh the display based on current filters and search.

        Args:
            preserve_scroll: Whether to preserve current scroll position
        """
        # Store current scroll position to preserve view
        current_scroll_y = (
            self.scroll_offset.y
            if (preserve_scroll and hasattr(self, "scroll_offset"))
            else 0
        )

        self.clear()
        self.displayed_lines.clear()

        # Reset excluded lines counter for accurate counts
        self.exclusion_manager.reset_excluded_count()

        line_index = 0
        for line in self.all_lines:
            # Check exclusion patterns
            if self.exclusion_manager.should_exclude(line.content):
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

        # Restore scroll position after refresh if requested and not in visual mode
        if preserve_scroll and not self.visual_mode and current_scroll_y > 0:
            # Temporarily disable auto-scroll to restore position
            old_auto_scroll = self.auto_scroll
            self.auto_scroll = False
            max_scroll = max(0, len(self.displayed_lines) - self.size.height)
            target_scroll = min(current_scroll_y, max_scroll)
            if target_scroll >= 0:
                self.scroll_to(0, target_scroll)
            self.auto_scroll = old_auto_scroll

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
        try:
            # Try to use the public API first
            if hasattr(pattern_text, "spans"):
                for span in pattern_text.spans:
                    if span.style:
                        text.stylize(span.style, span.start, span.end)
            elif hasattr(pattern_text, "_spans"):
                # Fallback to private API for older versions
                for start, end, style in pattern_text._spans:
                    if style:
                        text.stylize(style, start, end)
        except (AttributeError, TypeError):
            # If span access fails, skip merging pattern styles
            pass

        # Add line number if configured
        if self.config.display.show_line_numbers:
            line_num_text = Text(f"{line.line_number:6d} │ ", style="dim")
            text = line_num_text + text

        # Apply visual mode highlighting if applicable
        if self.visual_mode and display_index is not None:
            if self._is_visual_line(display_index):
                bg_color = self.config.display.visual_mode_bg
                # Use a more contrasting style to ensure visibility
                # and ensure it overrides any existing styles
                text.stylize(f"bold white on {bg_color}", 0, len(text))

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
            max(self.visual_start_line, self.visual_end_line),
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
            "total_lines": self.total_lines,
            "visible_lines": self.visible_lines,
            "filtered_lines": self.filtered_lines,
            "search_active": self.search_active,
            "search_term": self.search_term,
            "excluded_count": self.exclusion_manager.get_excluded_count(),
            "visual_mode": self.visual_mode,
            "visual_selection_active": self.visual_selection_active,
            "selected_lines": (
                self.get_selected_line_count() if self.visual_mode else 0
            ),
            "cursor_line": (
                self.displayed_lines[self.visual_cursor_line]
                if self.visual_mode
                and 0 <= self.visual_cursor_line < len(self.displayed_lines)
                else None
            ),
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

    def line_exists_in_file(self, target_line_number: int) -> bool:
        """Check if a line number exists in the original file (before filtering).

        Args:
            target_line_number: The actual line number from the file

        Returns:
            True if the line exists in the original file
        """
        for line in self.all_lines:
            if line.line_number == target_line_number:
                return True
        return False

    def find_display_index_for_line_number(
        self, target_line_number: int
    ) -> Optional[int]:
        """Find the display index for a given actual line number.

        Args:
            target_line_number: The actual line number from the file

        Returns:
            Index in displayed_lines, or None if line is not visible
        """
        for i, line_number in enumerate(self.displayed_lines):
            if line_number == target_line_number:
                return i
        return None

    def enter_visual_mode(
        self, line_index: Optional[int] = None, target_line_number: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Enter visual line mode.

        Args:
            line_index: Optional starting line index (0-based in displayed_lines). If None, uses current viewport position.
            target_line_number: Optional actual line number from file. Takes precedence over line_index.

        Returns:
            Tuple of (success, message) indicating result
        """
        if not self.displayed_lines:
            return False, "No lines to display"

        # If target_line_number is specified, check if it exists and is visible
        if target_line_number is not None:
            # First check if the line exists in the original file
            if not self.line_exists_in_file(target_line_number):
                return (
                    False,
                    f"Line {target_line_number} does not exist in file (max: {len(self.all_lines)})",
                )

            # Check if it's visible in current filtered view
            line_index = self.find_display_index_for_line_number(target_line_number)
            if line_index is None:
                # Line exists but is filtered out
                return (
                    False,
                    f"Line {target_line_number} is hidden by current filters/exclusions",
                )

        # Use current viewport position if not specified
        if line_index is None:
            line_index = self.get_current_viewport_line()

        if 0 <= line_index < len(self.displayed_lines):
            self.visual_mode = True
            self.visual_cursor_line = line_index
            self.visual_selection_active = False
            self.visual_start_line = -1
            self.visual_end_line = -1

            # First ensure the cursor line is visible before refreshing display
            self._ensure_line_visible(line_index)

            # Now refresh the display to show visual mode highlighting
            self._refresh_display()

            actual_line_num = self.displayed_lines[line_index]
            return True, f"Visual mode at line {actual_line_num}"

        return False, "Invalid line index"

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
        scroll_y = self.scroll_offset.y if hasattr(self, "scroll_offset") else 0
        visible_height = self.size.height

        # Calculate the visible range with some padding
        padding = 2  # Lines of padding from edges
        visible_start = scroll_y + padding
        visible_end = scroll_y + visible_height - padding - 1

        # Only scroll if the line is actually outside the comfortable viewing area
        if line_index < visible_start:
            # Line is above visible area - scroll up to center it
            new_scroll_y = max(0, line_index - (visible_height // 2))
            self.scroll_to(0, new_scroll_y)
        elif line_index > visible_end:
            # Line is below visible area - scroll down to center it
            new_scroll_y = max(0, line_index - (visible_height // 2))
            max_scroll = max(0, len(self.displayed_lines) - visible_height)
            new_scroll_y = min(new_scroll_y, max_scroll)
            self.scroll_to(0, new_scroll_y)
        # If line is already comfortably visible, don't scroll at all

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
        if not self.visual_mode:
            return 0
        if self.visual_selection_active:
            start, end = self._get_selection_range()
            return end - start + 1
        else:
            # When in visual mode but no selection active, we have the cursor line
            return 1

    def copy_selected_lines(self) -> bool:
        """Copy selected lines or current line to clipboard.

        In visual mode:
        - If selection is active, copy the selected range
        - If no selection is active, copy the current cursor line

        Returns:
            True if successful, False otherwise
        """
        if not self.visual_mode or not self.displayed_lines:
            return False

        if not HAS_CLIPBOARD:
            self.app.notify(
                "Clipboard support not available. Install pyperclip.",
                severity="warning",
            )
            return False

        selected_content = []

        if self.visual_selection_active:
            # Copy selected range
            start, end = self._get_selection_range()
            for i in range(start, end + 1):
                if i < len(self.displayed_lines):
                    line_num = self.displayed_lines[i]
                    # Find the corresponding LogLine
                    for line in self.all_lines:
                        if line.line_number == line_num:
                            selected_content.append(line.content)
                            break
        else:
            # Copy current cursor line
            if 0 <= self.visual_cursor_line < len(self.displayed_lines):
                line_num = self.displayed_lines[self.visual_cursor_line]
                # Find the corresponding LogLine
                for line in self.all_lines:
                    if line.line_number == line_num:
                        selected_content.append(line.content)
                        break

        if selected_content:
            try:
                clipboard_text = "\n".join(selected_content)
                pyperclip.copy(clipboard_text)
                return True
            except Exception as e:
                self.app.notify(f"Failed to copy to clipboard: {e}", severity="error")
                return False
        return False

    def temporarily_show_line(self, target_line_number: int) -> bool:
        """Temporarily clear filters and search to show a specific line.

        Args:
            target_line_number: The line number to make visible

        Returns:
            True if line was made visible
        """
        # Check if line exists in file
        if not self.line_exists_in_file(target_line_number):
            return False

        # Store current state
        original_search_term = self.search_term
        original_search_active = self.search_active

        # Clear search temporarily
        self.search_term = ""
        self.search_active = False

        # Store original exclusion patterns
        original_patterns = self.exclusion_manager.patterns.copy()

        # Clear exclusions temporarily
        self.exclusion_manager.clear_patterns()

        # Refresh display without filters
        self._refresh_display()

        # Check if line is now visible
        line_index = self.find_display_index_for_line_number(target_line_number)

        if line_index is not None:
            # Success - keep filters cleared and enter visual mode
            return True
        else:
            # Restore original state if still not visible
            self.search_term = original_search_term
            self.search_active = original_search_active

            # Restore exclusions
            for pattern in original_patterns:
                self.exclusion_manager.add_pattern(
                    pattern.pattern, pattern.is_regex, pattern.case_sensitive
                )

            self._refresh_display()
            return False
