"""
Custom header widget for DaLog.
"""

from pathlib import Path

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class HeaderWidget(Static):
    """Custom header displaying file info and status."""

    # Reactive properties
    current_file = reactive("")
    live_reload_status = reactive(True)
    total_lines = reactive(0)
    visible_lines = reactive(0)
    filtered_lines = reactive(0)
    search_active = reactive(False)
    search_term = reactive("")
    file_size_mb = reactive(0.0)

    def __init__(self, **kwargs):
        """Initialize the header widget."""
        super().__init__("", **kwargs)

    def render(self) -> Text:
        """Render the header content."""
        # Build status line
        parts = []

        # Live reload indicator
        if self.live_reload_status:
            parts.append(("🔄", "green"))
        else:
            parts.append(("⏸️ ", "dim"))

        # File name
        if self.current_file:
            file_name = Path(self.current_file).name
            parts.append((f" {file_name}", "bold cyan"))

            # File size
            if self.file_size_mb > 0:
                parts.append((f" ({self.file_size_mb:.1f} MB)", "dim"))
        else:
            parts.append((" No file loaded", "dim"))

        # Separator
        parts.append((" │ ", "dim"))

        # Line counts
        if self.search_active:
            parts.append((f"🔍 '{self.search_term}' ", "yellow"))
            parts.append((f"{self.visible_lines}/{self.total_lines} lines", ""))
            if self.filtered_lines > 0:
                parts.append((f" ({self.filtered_lines} filtered)", "dim yellow"))
        else:
            parts.append((f"{self.visible_lines}/{self.total_lines} lines", ""))

        # Build the text
        text = Text()
        for content, style in parts:
            text.append(content, style=style)

        return text

    def update_file_info(
        self, file_path: str, size_mb: float, total_lines: int
    ) -> None:
        """Update file information.

        Args:
            file_path: Path to the current file
            size_mb: File size in MB
            total_lines: Total number of lines
        """
        self.current_file = file_path
        self.file_size_mb = size_mb
        self.total_lines = total_lines
        self.visible_lines = total_lines

    def update_search_info(
        self, active: bool, term: str, visible: int, filtered: int
    ) -> None:
        """Update search information.

        Args:
            active: Whether search is active
            term: Current search term
            visible: Number of visible lines
            filtered: Number of filtered lines
        """
        self.search_active = active
        self.search_term = term
        self.visible_lines = visible
        self.filtered_lines = filtered
