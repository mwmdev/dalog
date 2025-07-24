"""
Exclusion modal widget for managing exclusion patterns.
"""

from typing import Dict, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Input, Label, ListItem, ListView, Static
from textual.events import Focus

from ..core.exclusions import ExclusionManager


class ExclusionModal(ModalScreen):
    """Modal screen for managing exclusion patterns."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+d", "delete", "Delete Selected"),
        Binding("enter", "add", "Add Pattern"),
    ]

    def __init__(self, exclusion_manager: ExclusionManager, **kwargs):
        """Initialize the exclusion modal.

        Args:
            exclusion_manager: The exclusion manager instance
        """
        super().__init__(**kwargs)
        self.exclusion_manager = exclusion_manager
        self.selected_pattern: Optional[str] = None
        self.validation_message = reactive("")

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            # Header
            yield Label("Exclusion Patterns")

            # Input takes full width
            yield Input(placeholder="Enter pattern", id="pattern-input")
            
            # Checkbox aligned to the right below input
            with Horizontal(classes="checkbox-row"):
                yield Checkbox("Regex", id="regex-checkbox", value=False)

            # Validation message
            yield Static("", id="validation-message")

            # Pattern list (enable focus for tab navigation)
            # Create a focusable ListView with a fixed height
            yield ListView(id="pattern-list")

    def on_mount(self) -> None:
        """Called when modal is mounted."""
        self._refresh_pattern_list()
        
        # Ensure ListView is focusable after mount
        pattern_list = self.query_one("#pattern-list", ListView)
        pattern_list.can_focus = True
        
        # Set initial focus to the input field
        self.query_one("#pattern-input", Input).focus()

    def _refresh_pattern_list(self) -> None:
        """Refresh the pattern list display."""
        list_view = self.query_one("#pattern-list", ListView)
        list_view.clear()

        patterns = self.exclusion_manager.get_patterns_list()
        for i, pattern_info in enumerate(patterns):
            pattern = pattern_info["pattern"]
            count = pattern_info["excluded_count"]
            is_regex = pattern_info["is_regex"]

            # Build pattern display
            text = Text()
            text.append(pattern, style="bold")

            # Add flags
            flags = []
            if is_regex:
                flags.append("regex")
            if flags:
                text.append(f" [{', '.join(flags)}]", style="dim")

            # Add exclusion count
            if count > 0:
                text.append(f" ({count} excluded)", style="yellow")

            # Wrap the Text object in a Label widget
            list_item = ListItem(Label(text))
            list_item.data = pattern  # type: ignore  # Store pattern for later reference
            list_item.can_focus = True  # Ensure ListItems are focusable
            list_view.append(list_item)


    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle pattern selection."""
        if event.item and hasattr(event.item, "data"):
            self.selected_pattern = event.item.data

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        if event.input.id == "pattern-input":
            self._add_pattern()

    def _add_pattern(self) -> None:
        """Add a new exclusion pattern."""
        input_widget = self.query_one("#pattern-input", Input)
        pattern = input_widget.value.strip()

        if not pattern:
            self._show_validation_error("Pattern cannot be empty")
            return

        # Get options
        is_regex = self.query_one("#regex-checkbox", Checkbox).value

        # Debug logging
        self.notify(
            f"Adding: '{pattern}' | regex={is_regex}",
            timeout=5,
        )

        # Validate pattern
        is_valid, error = self.exclusion_manager.validate_pattern(pattern, is_regex)
        if not is_valid:
            self._show_validation_error(error or "Invalid pattern")
            return

        # Add pattern (always case sensitive)
        if self.exclusion_manager.add_pattern(pattern, is_regex, True):
            input_widget.value = ""
            self._refresh_pattern_list()
            self._clear_validation_error()
            self.notify(f"Added pattern: {pattern}", timeout=2)
        else:
            self._show_validation_error("Pattern already exists")

    def _delete_selected(self) -> None:
        """Delete the selected pattern."""
        list_view = self.query_one("#pattern-list", ListView)

        if list_view.highlighted_child and hasattr(list_view.highlighted_child, "data"):
            pattern = list_view.highlighted_child.data
            if self.exclusion_manager.remove_pattern(pattern):
                self._refresh_pattern_list()
                self.notify(f"Removed pattern: {pattern}", timeout=2)


    def _show_validation_error(self, message: str) -> None:
        """Show validation error message."""
        validation_widget = self.query_one("#validation-message", Static)
        validation_widget.update(message)

    def _clear_validation_error(self) -> None:
        """Clear validation error message."""
        validation_widget = self.query_one("#validation-message", Static)
        validation_widget.update("")

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(False)

    def action_delete(self) -> None:
        """Delete selected pattern."""
        self._delete_selected()

    def action_add(self) -> None:
        """Add pattern."""
        self._add_pattern()

    def on_focus(self, event: Focus) -> None:
        """Handle focus events."""
        # Check if the focused widget is our pattern list
        if event.widget.id == "pattern-list":
            pattern_list = self.query_one("#pattern-list", ListView)
            if pattern_list.children:
                # Focus the first ListItem
                first_item = pattern_list.children[0]
                if isinstance(first_item, ListItem):
                    first_item.focus()
