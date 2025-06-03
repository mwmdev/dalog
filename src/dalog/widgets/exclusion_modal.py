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
from textual.widgets import Button, Checkbox, Input, Label, ListItem, ListView, Static

from ..core.exclusions import ExclusionManager


class ExclusionModal(ModalScreen):
    """Modal screen for managing exclusion patterns."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+d", "delete", "Delete Selected"),
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
        with Container(id="exclusion-container"):
            # Header
            yield Static("Exclusion Patterns", id="exclusion-header")

            # Pattern input section
            with Vertical():
                # Input and options on same line
                with Horizontal(classes="input-row"):
                    yield Input(placeholder="Enter pattern", id="pattern-input")
                    yield Checkbox("Regex", id="regex-checkbox", value=False)
                    yield Checkbox("Case Sensitive", id="case-checkbox", value=False)

                # Validation message
                yield Static("", id="validation-message")

                # Pattern list
                yield ListView(id="pattern-list")

                # Help text
                yield Static(
                    "Tip: Use ↑/↓ to select, Delete button or Ctrl+D to remove",
                    classes="help-text",
                )

                # Buttons
                with Horizontal(id="button-container"):
                    yield Button(
                        "Add", variant="primary", id="add-button", compact=True
                    )
                    yield Button(
                        "Delete (Ctrl+D)",
                        variant="warning",
                        id="delete-button",
                        compact=True,
                    )
                    yield Button(
                        "Clear All", variant="error", id="clear-button", compact=True
                    )
                    yield Button(
                        "Close", variant="default", id="close-button", compact=True
                    )

    def on_mount(self) -> None:
        """Called when modal is mounted."""
        self._refresh_pattern_list()
        self.query_one("#pattern-input", Input).focus()

    def _refresh_pattern_list(self) -> None:
        """Refresh the pattern list display."""
        list_view = self.query_one("#pattern-list", ListView)
        list_view.clear()

        patterns = self.exclusion_manager.get_patterns_list()
        for pattern_info in patterns:
            pattern = pattern_info["pattern"]
            count = pattern_info["excluded_count"]
            is_regex = pattern_info["is_regex"]
            case_sensitive = pattern_info["case_sensitive"]

            # Build pattern display
            text = Text()
            text.append(pattern, style="bold")

            # Add flags
            flags = []
            if is_regex:
                flags.append("regex")
            if case_sensitive:
                flags.append("case")
            if flags:
                text.append(f" [{', '.join(flags)}]", style="dim")

            # Add exclusion count
            if count > 0:
                text.append(f" ({count} excluded)", style="yellow")

            # Wrap the Text object in a Label widget
            list_item = ListItem(Label(text))
            list_item.data = pattern  # Store pattern for later reference
            list_view.append(list_item)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "add-button":
            self._add_pattern()
        elif button_id == "delete-button":
            self._delete_selected()
        elif button_id == "clear-button":
            self._clear_all()
        elif button_id == "close-button":
            self.dismiss(False)

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
        case_sensitive = self.query_one("#case-checkbox", Checkbox).value

        # Debug logging
        self.notify(
            f"Adding: '{pattern}' | regex={is_regex} | case_sensitive={case_sensitive}",
            timeout=5,
        )

        # Validate pattern
        is_valid, error = self.exclusion_manager.validate_pattern(pattern, is_regex)
        if not is_valid:
            self._show_validation_error(error)
            return

        # Add pattern
        if self.exclusion_manager.add_pattern(pattern, is_regex, case_sensitive):
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

    def _clear_all(self) -> None:
        """Clear all patterns."""
        if self.exclusion_manager.patterns:
            self.exclusion_manager.clear_patterns()
            self._refresh_pattern_list()
            self.notify("Cleared all patterns", timeout=2)

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
