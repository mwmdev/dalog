"""
Main Textual application for DaLog.
"""

from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Footer, Input, Static

from .config import ConfigLoader, DaLogConfig
from .core import AsyncFileWatcher, LogProcessor
from .widgets import ExclusionModal, LogViewerWidget


class DaLogApp(App):
    """Main DaLog application class."""

    CSS_PATH = Path(__file__).parent / "styles" / "app.css"

    BINDINGS = [
        Binding("/", "toggle_search", "Search"),
        Binding("r", "reload_logs", "Reload"),
        Binding("L", "toggle_live_reload", "Live Reload"),
        Binding("e", "show_exclusions", "Exclusions"),
        Binding("w", "toggle_wrap", "Wrap"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        # Vim-style navigation
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("h", "scroll_left", "Left", show=False),
        Binding("l", "scroll_right", "Right", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G", "scroll_end", "Bottom", show=False),
        # Visual mode
        Binding("V", "toggle_visual_mode", "Visual Mode"),
        Binding("v", "start_selection", "Start Selection", show=False),
        Binding("y", "yank_lines", "Yank", show=False),
        # Page scrolling
        Binding("ctrl+u", "scroll_page_up", "Page Up", show=False),
        Binding("ctrl+d", "scroll_page_down", "Page Down", show=False),
    ]

    # Reactive variables for state management
    search_mode = reactive(False)
    live_reload = reactive(True)
    current_search = reactive("")
    current_file = reactive("")

    def __init__(
        self,
        log_file: str,
        config_path: Optional[str] = None,
        initial_search: Optional[str] = None,
        tail_lines: Optional[int] = None,
        theme: Optional[str] = None,
        live_reload: Optional[bool] = None,
        **kwargs,
    ):
        """Initialize the DaLog application.

        Args:
            log_file: Path to the log file to display
            config_path: Optional path to configuration file
            initial_search: Optional initial search term
            tail_lines: Optional number of lines to tail from end of file
            theme: Optional Textual theme name to apply
            live_reload: Optional override for live reload setting
        """
        super().__init__(**kwargs)
        self.log_file = Path(log_file)
        self.config_path = config_path
        self.initial_search = initial_search
        self.tail_lines = tail_lines
        self.theme_name = theme
        # Load configuration early, before widgets are created
        self._load_config()

        # Override live_reload if specified
        if live_reload is not None:
            self.live_reload = live_reload

        self.log_processor = None
        self.log_viewer = None
        self.search_input = None
        self.file_watcher = AsyncFileWatcher()

        # Set the initial file
        self.current_file = str(self.log_file)

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        # Main container with log viewer
        with Container(id="main-container"):
            # Enhanced log viewer
            self.log_viewer = LogViewerWidget(
                config=self.config,  # Now self.config is already loaded
                id="log-viewer",
            )
            yield self.log_viewer

            # Search input (initially hidden)
            self.search_input = Input(
                id="search-input",
                placeholder="Search...",
                classes="hidden",
            )
            yield self.search_input

        # Footer with keybindings
        yield Footer()

    async def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Config is already loaded in __init__, no need to load again

        # Apply theme if provided
        if self.theme_name:
            try:
                # Set the theme property inherited from App
                self.theme = self.theme_name
                self.notify(f"Applied theme: {self.theme_name}", timeout=3)
            except Exception as e:
                self.notify(
                    f"Failed to apply theme '{self.theme_name}': {e}",
                    severity="error",
                    timeout=5,
                )

        # Start file watcher if live reload is enabled
        if self.live_reload:
            await self.file_watcher.start(self._on_file_changed)

        # Load initial log file
        await self._load_log_file(self.log_file)

        # Apply initial search if provided
        if self.initial_search:
            self.current_search = self.initial_search
            await self.action_toggle_search()

    async def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        # Stop file watcher
        await self.file_watcher.stop()

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            self.config = ConfigLoader.load(self.config_path)

            # Validate configuration
            errors = ConfigLoader.validate_config(self.config)
            if errors:
                for error in errors:
                    self.notify(f"Config error: {error}", severity="warning", timeout=5)

            # Apply configuration to app state
            self.live_reload = self.config.app.live_reload

            # Set default tail lines if not overridden by CLI
            if self.tail_lines is None and self.config.app.default_tail_lines > 0:
                self.tail_lines = self.config.app.default_tail_lines

        except Exception as e:
            self.notify(f"Failed to load config: {e}", severity="error", timeout=5)
            # Use default config on error
            self.config = ConfigLoader.load()

    async def _load_log_file(self, file_path: Path) -> None:
        """Load a log file into the viewer using LogProcessor."""
        # Check if file exists
        if not file_path.exists():
            self.notify(f"File not found: {file_path}", severity="error")
            return

        try:
            # Create log processor
            processor = LogProcessor(file_path, tail_lines=self.tail_lines)

            # Load file using processor
            with processor:
                # Get file info
                file_info = processor.get_file_info()

                # Load lines into viewer
                self.log_viewer.load_from_processor(processor)

            self.log_processor = processor
            self.current_file = str(file_path)

            # Add to file watcher if live reload is enabled
            if self.live_reload:
                self.file_watcher.add_file(file_path)

        except Exception as e:
            self.notify(f"Error loading file: {e}", severity="error")

    async def _on_file_changed(self, file_path: Path) -> None:
        """Handle file change events from file watcher.

        Args:
            file_path: Path to the changed file
        """
        # Only reload if it's the current file
        if str(file_path) == self.current_file:
            await self._load_log_file(file_path)
            self.notify(f"File updated: {file_path.name}", timeout=2)

    # Actions
    async def action_toggle_search(self) -> None:
        """Toggle search mode."""
        if self.search_mode:
            # Hide search
            self.search_input.add_class("hidden")
            self.search_input.value = ""
            self.search_mode = False
            self.current_search = ""

            # Clear search in log viewer
            self.log_viewer.clear_search()
        else:
            # Show search
            self.search_input.remove_class("hidden")
            self.search_mode = True
            self.search_input.focus()

            # Pre-fill with initial search if available
            if self.initial_search and not self.search_input.value:
                self.search_input.value = self.initial_search

    async def action_reload_logs(self) -> None:
        """Reload the current log file."""
        await self._load_log_file(self.log_file)
        self.notify("Log file reloaded", timeout=2)

    async def action_toggle_live_reload(self) -> None:
        """Toggle live reload mode."""
        self.live_reload = not self.live_reload

        if self.live_reload:
            # Start file watcher
            await self.file_watcher.start(self._on_file_changed)
            # Add current file to watcher
            self.file_watcher.add_file(self.log_file)
            self.notify("Live reload enabled", timeout=2)
        else:
            # Stop file watcher
            await self.file_watcher.stop()
            self.notify("Live reload disabled", timeout=2)

    async def action_toggle_wrap(self) -> None:
        """Toggle text wrapping."""
        # Toggle wrap property on the log viewer
        self.log_viewer.wrap = not self.log_viewer.wrap

        # Update the config to persist the change
        self.config.display.wrap_lines = self.log_viewer.wrap

        # Notify the user
        status = "enabled" if self.log_viewer.wrap else "disabled"
        self.notify(f"Text wrapping {status}", timeout=2)

        # Refresh the display to apply wrapping
        self.log_viewer._refresh_display()

    async def action_show_exclusions(self) -> None:
        """Show exclusion management modal."""

        def handle_exclusion_modal(result: bool) -> None:
            """Handle exclusion modal result."""
            # Always refresh the log viewer when modal closes
            # because exclusions may have been added/removed
            self.log_viewer.refresh_exclusions()

            # Show notification about excluded lines
            excluded_count = self.log_viewer.exclusion_manager.get_excluded_count()
            if excluded_count > 0:
                self.notify(f"Excluding {excluded_count} lines", timeout=2)

        # Show the exclusion modal
        modal = ExclusionModal(self.log_viewer.exclusion_manager)
        await self.push_screen(modal, handle_exclusion_modal)

    # Vim-style navigation
    async def action_scroll_down(self) -> None:
        """Scroll down one line."""
        if self.log_viewer.visual_mode:
            # In visual mode, move cursor
            self.log_viewer.move_visual_cursor(1)
        else:
            self.log_viewer.scroll_down()

    async def action_scroll_up(self) -> None:
        """Scroll up one line."""
        if self.log_viewer.visual_mode:
            # In visual mode, move cursor
            self.log_viewer.move_visual_cursor(-1)
        else:
            self.log_viewer.scroll_up()

    async def action_scroll_left(self) -> None:
        """Scroll left."""
        self.log_viewer.scroll_left()

    async def action_scroll_right(self) -> None:
        """Scroll right."""
        self.log_viewer.scroll_right()

    async def action_scroll_home(self) -> None:
        """Scroll to top."""
        self.log_viewer.scroll_home()

    async def action_scroll_end(self) -> None:
        """Scroll to bottom."""
        self.log_viewer.scroll_end()

    # Page scrolling
    async def action_scroll_page_up(self) -> None:
        """Scroll up one page."""
        self.log_viewer.scroll_page_up()

    async def action_scroll_page_down(self) -> None:
        """Scroll down one page."""
        self.log_viewer.scroll_page_down()

    # Visual mode actions
    async def action_toggle_visual_mode(self) -> None:
        """Toggle visual line mode."""
        if self.log_viewer.visual_mode:
            self.log_viewer.exit_visual_mode()
            self.notify("Exited visual mode", timeout=2)
        else:
            self.log_viewer.enter_visual_mode()
            self.notify(
                "Visual mode: j/k to navigate, v to start selection, y to copy",
                timeout=3,
            )

    async def action_start_selection(self) -> None:
        """Start selection in visual mode."""
        if not self.log_viewer.visual_mode:
            return

        if not self.log_viewer.visual_selection_active:
            self.log_viewer.start_visual_selection()
            self.notify("Selection started - use j/k to extend", timeout=2)

    async def action_yank_lines(self) -> None:
        """Copy selected lines to clipboard (yank in vi terms)."""
        if not self.log_viewer.visual_mode:
            return

        if not self.log_viewer.visual_selection_active:
            self.notify("No selection - press 'v' to start selection", timeout=2)
            return

        if self.log_viewer.copy_selected_lines():
            num_lines = self.log_viewer.get_selected_line_count()
            self.notify(f"Copied {num_lines} line(s) to clipboard", timeout=2)
            self.log_viewer.exit_visual_mode()
        else:
            self.notify("Failed to copy to clipboard", severity="error", timeout=2)

    # Event handlers
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes for live filtering."""
        if event.input.id == "search-input":
            self.current_search = event.value

            # Update log viewer with search term
            self.log_viewer.update_search(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission."""
        if event.input.id == "search-input":
            # Keep search active on Enter (don't close)
            # User must press ESC to close search
            pass

    async def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "escape":
            if self.search_mode:
                # Cancel search
                await self.action_toggle_search()
            elif self.log_viewer.visual_mode:
                # Exit visual mode
                self.log_viewer.exit_visual_mode()
                self.notify("Exited visual mode", timeout=2)
