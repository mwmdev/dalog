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
from textual.widgets import Checkbox, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from ..core.exclusions import ExclusionManager
from ..config.models import DaLogConfig


class ExclusionModal(ModalScreen):
    """Modal screen for managing exclusion patterns."""

    def __init__(self, exclusion_manager: ExclusionManager, config: DaLogConfig, **kwargs):
        """Initialize the exclusion modal.

        Args:
            exclusion_manager: The exclusion manager instance
            config: Application configuration with keybindings
        """
        super().__init__(**kwargs)
        self.exclusion_manager = exclusion_manager
        self.config = config
        self.selected_pattern: Optional[str] = None
        self.validation_message = reactive("")

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "add", "Add Pattern"),
    ]

    def get_bindings(self):
        """Get dynamic bindings including configurable ones."""
        bindings = list(self.BINDINGS)
        # Add the configurable delete binding
        bindings.append(Binding(self.config.keybindings.exclusion_delete, "delete", "Delete Selected"))
        return bindings

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

            # Pattern list with built-in keyboard navigation
            yield OptionList(id="pattern-list")

    def on_mount(self) -> None:
        """Called when modal is mounted."""
        self._refresh_pattern_list()
        
        # Set initial focus to the input field
        self.query_one("#pattern-input", Input).focus()

    def _refresh_pattern_list(self) -> None:
        """Refresh the pattern list display."""
        option_list = self.query_one("#pattern-list", OptionList)
        option_list.clear_options()

        patterns = self.exclusion_manager.get_patterns_list()
        for pattern_info in patterns:
            pattern = pattern_info["pattern"]
            count = pattern_info["excluded_count"]
            is_regex = pattern_info["is_regex"]

            # Build rich text display
            text = Text()
            text.append(pattern, style="bold")

            # Add flags
            if is_regex:
                text.append(" [regex]", style="dim")

            # Add exclusion count
            if count > 0:
                text.append(f" ({count} excluded)", style="yellow")

            # Add option with pattern as ID for easy retrieval
            option_list.add_option(Option(text, id=pattern))


    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle pattern selection for deletion."""
        if event.option.id:
            self.selected_pattern = event.option.id
    
    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Update selected pattern when highlighted changes."""
        if event.option and event.option.id:
            self.selected_pattern = event.option.id

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
        if self.selected_pattern:
            if self.exclusion_manager.remove_pattern(self.selected_pattern):
                self._refresh_pattern_list()
                self.notify(f"Removed pattern: {self.selected_pattern}", timeout=2)
                self.selected_pattern = None


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

    async def on_key(self, event) -> None:
        """Handle configurable navigation and delete keys for the OptionList."""
        # Check if the OptionList is focused
        option_list = self.query_one("#pattern-list", OptionList)
        if self.app.focused == option_list:
            # Handle configurable navigation keys
            if event.key == self.config.keybindings.exclusion_list_up:
                option_list.action_cursor_up()
                event.prevent_default()
            elif event.key == self.config.keybindings.exclusion_list_down:
                option_list.action_cursor_down()
                event.prevent_default()
            # Handle configurable delete key
            elif event.key == self.config.keybindings.exclusion_delete:
                self._delete_selected()
                event.prevent_default()

