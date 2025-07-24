"""
Main Textual application for DaLog.
"""

from pathlib import Path
from typing import List, Optional, Union

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, Label, Static

from .config import ConfigLoader, DaLogConfig
from .core import AsyncFileWatcher, LogProcessor
from .core.log_reader import create_unified_log_reader
from .core.remote_reader import is_ssh_url
from .core.ssh_file_watcher import AsyncSSHFileWatcher
from .widgets import ExclusionModal, LogViewerWidget


class HelpScreen(ModalScreen):
    """Modal screen for displaying help information."""

    def __init__(self, keybindings):
        """Initialize the help screen with keybindings configuration."""
        super().__init__()
        self.keybindings = keybindings

    def compose(self) -> ComposeResult:
        """Compose the help screen layout."""
        kb = self.keybindings

        with Container():
            yield Label("Help")

            # General commands first
            yield Static("▸ General", classes="section-header")
            general_table = DataTable(
                show_header=False, cursor_type="none", zebra_stripes=False
            )
            general_table.add_column("Key", width=12)
            general_table.add_column("Action", width=40)

            general_table.add_row(kb.search, "Search")
            general_table.add_row(kb.reload, "Reload file")
            general_table.add_row(kb.toggle_live_reload, "Toggle live reload")
            general_table.add_row(kb.show_exclusions, "Manage exclusions")
            general_table.add_row(kb.toggle_wrap, "Toggle line wrapping")
            general_table.add_row(kb.show_help, "Show this help")
            general_table.add_row(kb.quit, "Quit")

            yield general_table

            # Navigation section
            yield Static("▸ Navigation", classes="section-header")
            nav_table = DataTable(
                show_header=False, cursor_type="none", zebra_stripes=False
            )
            nav_table.add_column("Key", width=12)
            nav_table.add_column("Action", width=40)

            nav_table.add_row(
                f"{kb.scroll_up}/{kb.scroll_down}", "Move one line up/down"
            )
            nav_table.add_row(
                f"{kb.scroll_left}/{kb.scroll_right}", "Scroll left/right"
            )
            nav_table.add_row(f"{kb.scroll_home}/{kb.scroll_end}", "Go to top/bottom")
            nav_table.add_row(
                f"{kb.scroll_page_up}/{kb.scroll_page_down}", "Page up/down"
            )

            yield nav_table

            # Visual mode section
            yield Static("▸ Visual Mode", classes="section-header")
            visual_table = DataTable(
                show_header=False, cursor_type="none", zebra_stripes=False
            )
            visual_table.add_column("Key", width=12)
            visual_table.add_column("Action", width=40)

            visual_table.add_row(
                kb.enter_visual_mode, "Enter visual mode at current line"
            )
            visual_table.add_row(
                f"123{kb.enter_visual_mode}", "Enter visual mode at line 123"
            )
            visual_table.add_row(kb.start_selection, "Start selection")
            visual_table.add_row(kb.yank_lines, "Copy selected lines")
            visual_table.add_row("Esc", "Exit visual mode")

            yield visual_table

            # Exclusions modal section
            yield Static("▸ Exclusions Modal", classes="section-header")
            exclusions_table = DataTable(
                show_header=False, cursor_type="none", zebra_stripes=False
            )
            exclusions_table.add_column("Key", width=12)
            exclusions_table.add_column("Action", width=40)

            exclusions_table.add_row("Enter", "Add pattern")
            exclusions_table.add_row("Tab", "Navigate between fields")
            exclusions_table.add_row(
                f"{kb.exclusion_list_up}/{kb.exclusion_list_down}", 
                "Navigate pattern list"
            )
            exclusions_table.add_row(kb.exclusion_delete, "Delete selected pattern")
            exclusions_table.add_row("Checkbox", "Toggle regex mode")
            exclusions_table.add_row("Esc", "Close modal")

            yield exclusions_table

    def on_mount(self) -> None:
        """Focus first table on mount."""
        self.query_one(DataTable).focus()

    def on_key(self, event) -> None:
        """Close help on any key press."""
        self.dismiss()


def create_dalog_app(config_path: Optional[str] = None):
    """Factory function to create DaLogApp with dynamic bindings based on config."""
    # Load config first to get keybindings
    from .config import ConfigLoader

    config = ConfigLoader.load(config_path)
    kb = config.keybindings
    footer_actions = set(kb.display_in_footer)

    # Create bindings list based on config
    bindings = [
        # General commands
        Binding(kb.search, "toggle_search", "Search", show="search" in footer_actions),
        Binding(kb.reload, "reload_logs", "Reload", show="reload" in footer_actions),
        Binding(
            kb.toggle_live_reload,
            "toggle_live_reload",
            "Live Reload",
            show="toggle_live_reload" in footer_actions,
        ),
        Binding(
            kb.show_exclusions,
            "show_exclusions",
            "Exclusions",
            show="show_exclusions" in footer_actions,
        ),
        Binding(
            kb.toggle_wrap, "toggle_wrap", "Wrap", show="toggle_wrap" in footer_actions
        ),
        Binding(kb.quit, "quit", "Quit", show="quit" in footer_actions),
        Binding("ctrl+c", "quit", "Quit", show=False),  # Always keep Ctrl+C hidden
        Binding(kb.show_help, "show_help", "Help", show="show_help" in footer_actions),
        # Navigation - typically hidden
        Binding(
            kb.scroll_down, "scroll_down", "Down", show="scroll_down" in footer_actions
        ),
        Binding(kb.scroll_up, "scroll_up", "Up", show="scroll_up" in footer_actions),
        Binding(
            kb.scroll_left, "scroll_left", "Left", show="scroll_left" in footer_actions
        ),
        Binding(
            kb.scroll_right,
            "scroll_right",
            "Right",
            show="scroll_right" in footer_actions,
        ),
        Binding(
            kb.scroll_home, "scroll_home", "Top", show="scroll_home" in footer_actions
        ),
        Binding(
            kb.scroll_end, "scroll_end", "Bottom", show="scroll_end" in footer_actions
        ),
        Binding(
            kb.scroll_page_up,
            "scroll_page_up",
            "Page Up",
            show="scroll_page_up" in footer_actions,
        ),
        Binding(
            kb.scroll_page_down,
            "scroll_page_down",
            "Page Down",
            show="scroll_page_down" in footer_actions,
        ),
        # Visual mode - typically hidden
        Binding(
            kb.enter_visual_mode,
            "toggle_visual_mode",
            "Visual Mode",
            show="enter_visual_mode" in footer_actions,
        ),
        Binding(
            kb.start_selection,
            "start_selection",
            "Start Selection",
            show="start_selection" in footer_actions,
        ),
        Binding(
            kb.yank_lines, "yank_lines", "Yank", show="yank_lines" in footer_actions
        ),
    ]

    class DaLogApp(App):
        """Main DaLog application class."""

        CSS_PATH = Path(__file__).parent / "styles" / "app.css"

        # Set BINDINGS at class level with config values
        BINDINGS = bindings

        # Reactive variables for state management
        search_mode = reactive(False)
        live_reload = reactive(True)
        current_search = reactive("")
        current_file = reactive("")

        # Line number input state (vim-style)
        line_number_input = reactive("")
        line_number_mode = reactive(False)

        def __init__(
            self,
            log_file: str,
            config_path: Optional[str] = None,
            initial_search: Optional[str] = None,
            tail_lines: Optional[int] = None,
            theme: Optional[str] = None,
            live_reload: Optional[bool] = None,
            exclude_patterns: Optional[List[str]] = None,
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
                exclude_patterns: Optional list of exclusion patterns from CLI (case-sensitive regex)
            """
            # Store parameters
            self.log_file = log_file  # Keep as string to support SSH URLs
            self.config_path = config_path
            self.initial_search = initial_search
            self.tail_lines = tail_lines
            self.theme_name = theme

            # Store CLI exclusion parameters (case sensitive regex by default)
            self.cli_exclude_patterns = exclude_patterns or []

            # Load configuration BEFORE calling super().__init__() (but don't set reactives yet)
            self._load_config_only()

            # Now call super().__init__() - bindings are already set at class level
            super().__init__(**kwargs)

            # Apply configuration to reactive attributes AFTER super().__init__()
            self._apply_config_settings()

            # Override live_reload if specified
            if live_reload is not None:
                self.live_reload = live_reload

            self.log_processor: Optional[LogProcessor] = None
            self.log_viewer: Optional[LogViewerWidget] = None
            self.search_input: Optional[Input] = None
            self.status_label: Optional[Label] = None
            self.file_watcher = AsyncFileWatcher()
            self.ssh_file_watcher = AsyncSSHFileWatcher()

            # Set the initial file
            self.current_file = str(self.log_file)

        def compose(self) -> ComposeResult:
            """Compose the application layout."""
            # Main container with log viewer
            with Container(id="main-container"):
                # Connection status label (initially hidden)
                self.status_label = Label(
                    "",
                    id="status-label",
                    classes="hidden",
                )
                yield self.status_label

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

            # At this point, widgets are initialized and not None
            assert self.log_viewer is not None
            assert self.search_input is not None
            assert self.status_label is not None

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

            # Start file watchers if live reload is enabled
            if self.live_reload:
                await self.file_watcher.start(self._on_file_changed)
                await self.ssh_file_watcher.start(self._on_ssh_file_changed)

            # Load initial log file
            await self._load_log_file(self.log_file)

            # Apply CLI exclusions if provided
            self._apply_cli_exclusions()

            # Apply initial search if provided
            if self.initial_search:
                self.current_search = self.initial_search
                await self.action_toggle_search()

            # Refresh footer to show dynamic bindings
            try:
                footer = self.query_one(Footer)
                footer.refresh()
            except Exception:
                # Footer might not be ready yet, ignore
                pass

        async def on_unmount(self) -> None:
            """Called when the app is unmounted."""
            # Stop file watchers
            await self.file_watcher.stop()
            await self.ssh_file_watcher.stop()

            # Close SSH log reader connection if exists
            if (
                hasattr(self, "log_reader")
                and self.log_reader
                and hasattr(self.log_reader, "close")
            ):
                try:
                    self.log_reader.close()
                except:
                    pass

        def _load_config_only(self) -> None:
            """Load configuration from file without setting reactive attributes."""
            try:
                self.config = ConfigLoader.load(self.config_path)

                # Set default tail lines if not overridden by CLI
                if self.tail_lines is None and self.config.app.default_tail_lines > 0:
                    self.tail_lines = self.config.app.default_tail_lines

            except Exception as e:
                # Use default config on error - can't notify yet as app not initialized
                self.config = ConfigLoader.load()

        def _apply_config_settings(self) -> None:
            """Apply configuration to reactive attributes after app initialization."""
            try:
                # Validate configuration
                errors = ConfigLoader.validate_config(self.config)
                if errors:
                    for error in errors:
                        self.notify(
                            f"Config error: {error}", severity="warning", timeout=5
                        )

                # Apply configuration to app state (now safe to set reactive attributes)
                self.live_reload = self.config.app.live_reload

            except Exception as e:
                import traceback

                self.notify(f"Failed to apply config: {e}", severity="error", timeout=5)
                # Log the full traceback for debugging
                print(f"Config error: {e}")
                traceback.print_exc()

        async def _load_log_file(
            self, file_source: Union[str, Path], is_reload: bool = False
        ) -> None:
            """Load a log file into the viewer using unified log reader.

            Args:
                file_source: Path or SSH URL to the log file
                is_reload: True if this is a reload triggered by file change
            """
            file_source_str = str(file_source)

            # Close existing log reader connection if switching files (not just reloading)
            if (
                not is_reload
                and hasattr(self, "log_reader")
                and self.log_reader
                and hasattr(self.log_reader, "close")
            ):
                try:
                    self.log_reader.close()
                except:
                    pass
                self.log_reader = None

            # For local files, check if file exists
            if not is_ssh_url(file_source_str):
                file_path = Path(file_source_str)
                if not file_path.exists():
                    self.notify(f"File not found: {file_path}", severity="error")
                    return

            try:
                # Show immediate connection status for SSH URLs (only if not reloading)
                if is_ssh_url(file_source_str) and not is_reload:
                    self.status_label.update(f"Connecting to {file_source_str}...")
                    self.status_label.remove_class("hidden")

                # For SSH reloads, try to reuse existing connection if available
                if (
                    is_reload
                    and is_ssh_url(file_source_str)
                    and hasattr(self, "log_reader")
                    and self.log_reader
                ):
                    try:
                        # Reuse existing reader connection for reload
                        reader = self.log_reader

                        # Get file info and reload content
                        file_info = reader.get_file_info()

                        # Load lines into viewer - auto_scroll will handle staying at bottom
                        if self.log_viewer is not None:
                            self.log_viewer.load_from_reader(reader, scroll_to_end=True)

                        # Connection reused successfully, exit early
                        return

                    except Exception:
                        # If reusing connection fails, fall back to creating new connection
                        reader = create_unified_log_reader(
                            file_source_str, tail_lines=self.tail_lines
                        )
                        reader.open()
                        try:
                            # Get file info
                            file_info = reader.get_file_info()

                            # Load lines into viewer - auto_scroll will handle staying at bottom
                            if self.log_viewer is not None:
                                self.log_viewer.load_from_reader(
                                    reader, scroll_to_end=True
                                )

                            self.log_reader = reader
                            self.current_file = file_source_str
                        except Exception:
                            # Close reader on error
                            reader.close()
                            raise
                else:
                    # Create unified log reader (handles both local and SSH)
                    reader = create_unified_log_reader(
                        file_source_str, tail_lines=self.tail_lines
                    )

                    # Load file using reader but keep connection open for reuse
                    reader.open()
                    try:
                        # Get file info
                        file_info = reader.get_file_info()

                        # Load lines into viewer - auto_scroll will handle staying at bottom
                        if self.log_viewer is not None:
                            self.log_viewer.load_from_reader(reader, scroll_to_end=True)

                        self.log_reader = reader
                        self.current_file = file_source_str

                        # Hide connection status after successful load
                        if is_ssh_url(file_source_str):
                            self.status_label.add_class("hidden")

                        # Add to appropriate file watcher if live reload is enabled
                        if (
                            self.live_reload and not is_reload
                        ):  # Only add watcher on initial load
                            if is_ssh_url(file_source_str):
                                # Pass the existing SSH connection to the file watcher to reuse it
                                if (
                                    hasattr(reader, "_ssh_client")
                                    and reader._ssh_client
                                ):
                                    if self.ssh_file_watcher.add_ssh_file_with_connection(
                                        file_source_str,
                                        reader._ssh_client,
                                        reader.remote_path,
                                        poll_interval=self.config.ssh.poll_interval,
                                        max_poll_interval=self.config.ssh.max_poll_interval,
                                    ):
                                        self.notify(
                                            "Live reload enabled for SSH file",
                                            timeout=2,
                                        )
                                    else:
                                        self.notify(
                                            "Failed to enable live reload for SSH file",
                                            severity="warning",
                                            timeout=3,
                                        )
                                else:
                                    # Fallback to original method if no connection available
                                    if self.ssh_file_watcher.add_ssh_file(
                                        file_source_str,
                                        poll_interval=self.config.ssh.poll_interval,
                                        max_poll_interval=self.config.ssh.max_poll_interval,
                                    ):
                                        self.notify(
                                            "Live reload enabled for SSH file",
                                            timeout=2,
                                        )
                                    else:
                                        self.notify(
                                            "Failed to enable live reload for SSH file",
                                            severity="warning",
                                            timeout=3,
                                        )
                            else:
                                # Add to local file watcher
                                self.file_watcher.add_file(Path(file_source_str))
                    except Exception:
                        # Close reader on error
                        reader.close()
                        raise

            except Exception as e:
                error_msg = str(e)

                # Hide connection status on error
                if is_ssh_url(file_source_str):
                    self.status_label.add_class("hidden")

                # Provide more specific error messages for SSH issues
                if "Host key verification failed" in error_msg:
                    self.notify(
                        f"SSH Host Key Error: {e}", severity="error", timeout=10
                    )
                elif "SSH authentication failed" in error_msg:
                    self.notify(
                        f"SSH Authentication Error: {e}", severity="error", timeout=8
                    )
                elif "Unable to connect" in error_msg:
                    self.notify(
                        f"SSH Connection Error: {e}", severity="error", timeout=8
                    )
                else:
                    self.notify(f"Error loading file: {e}", severity="error")

        async def _on_file_changed(self, file_path: Path) -> None:
            """Handle file change events from file watcher.

            Args:
                file_path: Path to the changed file
            """
            # Only reload if it's the current file
            if str(file_path) == self.current_file:
                await self._load_log_file(str(file_path), is_reload=True)
                # self.notify(f"File updated: {file_path.name}", timeout=2)

        async def _on_ssh_file_changed(self, ssh_url: str) -> None:
            """Handle SSH file change events.

            Args:
                ssh_url: SSH URL of the changed file
            """
            # Only reload if it's the current file
            if ssh_url == self.current_file:
                await self._load_log_file(ssh_url, is_reload=True)
                # self.notify(f"SSH file updated", timeout=2)

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
                # Start both file watchers
                await self.file_watcher.start(self._on_file_changed)
                await self.ssh_file_watcher.start(self._on_ssh_file_changed)

                # Add current file to appropriate watcher
                if is_ssh_url(self.current_file):
                    # For SSH files, we need to get the connection from the current reader
                    if (
                        self.log_reader
                        and hasattr(self.log_reader, "_ssh_client")
                        and self.log_reader._ssh_client
                    ):
                        if self.ssh_file_watcher.add_ssh_file_with_connection(
                            self.current_file,
                            self.log_reader._ssh_client,
                            self.log_reader.remote_path,
                            poll_interval=self.config.ssh.poll_interval,
                            max_poll_interval=self.config.ssh.max_poll_interval,
                        ):
                            self.notify("Live reload enabled for SSH file", timeout=2)
                        else:
                            self.notify(
                                "Failed to enable live reload for SSH file", timeout=2
                            )
                    else:
                        self.notify(
                            "No SSH connection available for live reload", timeout=2
                        )
                else:
                    self.file_watcher.add_file(self.log_file)
                    self.notify("Live reload enabled", timeout=2)
            else:
                # Stop both file watchers
                await self.file_watcher.stop()
                await self.ssh_file_watcher.stop()
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
            modal = ExclusionModal(self.log_viewer.exclusion_manager, self.config)
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
                # Check if we have a line number input
                if self.line_number_input:
                    try:
                        target_line = int(self.line_number_input)
                        success, message = self.log_viewer.enter_visual_mode(
                            target_line_number=target_line
                        )

                        if success:
                            self.notify(
                                f"{message}: j/k to navigate, v to start selection, y to copy",
                                timeout=3,
                            )
                        else:
                            # Check if line exists but is filtered
                            if "hidden by current filters" in message:
                                # Try to automatically show the line by clearing filters
                                if self.log_viewer.temporarily_show_line(target_line):
                                    # Now try visual mode again
                                    success, new_message = (
                                        self.log_viewer.enter_visual_mode(
                                            target_line_number=target_line
                                        )
                                    )
                                    if success:
                                        self.notify(
                                            f"Cleared filters to show {new_message}: j/k to navigate, v to start selection, y to copy",
                                            timeout=5,
                                        )
                                    else:
                                        self.notify(
                                            f"Failed to enter visual mode: {new_message}",
                                            severity="error",
                                            timeout=3,
                                        )
                                else:
                                    self.notify(
                                        f"{message}. Press 'e' to manage exclusions or clear search with Esc",
                                        severity="warning",
                                        timeout=5,
                                    )
                            else:
                                self.notify(message, severity="error", timeout=3)

                    except ValueError:
                        self.notify("Invalid line number", severity="error", timeout=2)

                    # Clear line number input after use
                    self.line_number_input = ""
                    self.line_number_mode = False
                else:
                    # No line number specified, start visual mode at current viewport center
                    center_line = self.log_viewer.get_current_viewport_line()
                    success, message = self.log_viewer.enter_visual_mode(
                        line_index=center_line
                    )

                    if success:
                        self.notify(
                            f"{message}: j/k to navigate, v to start selection, y to copy",
                            timeout=3,
                        )
                    else:
                        self.notify(message, severity="error", timeout=2)

        async def action_start_selection(self) -> None:
            """Start selection in visual mode."""
            if not self.log_viewer.visual_mode:
                return

            if not self.log_viewer.visual_selection_active:
                self.log_viewer.start_visual_selection()
                self.notify("Selection started - use j/k to extend", timeout=2)

        async def action_yank_lines(self) -> None:
            """Copy selected lines or current line to clipboard (yank in vi terms)."""
            if not self.log_viewer.visual_mode:
                return

            if self.log_viewer.copy_selected_lines():
                num_lines = self.log_viewer.get_selected_line_count()
                if self.log_viewer.visual_selection_active:
                    self.notify(
                        f"Copied {num_lines} selected line(s) to clipboard", timeout=2
                    )
                else:
                    self.notify(f"Copied current line to clipboard", timeout=2)
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
            # Don't intercept keys if search mode is active (let search input handle them)
            if self.search_mode:
                if event.key == "escape":
                    # Cancel search
                    await self.action_toggle_search()
                return

            if event.key == "escape":
                if self.log_viewer.visual_mode:
                    # Exit visual mode
                    self.log_viewer.exit_visual_mode()
                    self.notify("Exited visual mode", timeout=2)
                elif self.line_number_mode:
                    # Cancel line number input
                    self._clear_line_number_input()

            # Handle line number input (digits 0-9)
            elif event.key.isdigit():
                self.line_number_input += event.key
                self.line_number_mode = True
                # Show current input in status
                # self.notify(f"Line: {self.line_number_input}_", timeout=1)

            # Handle visual mode key (either standalone or after line number)
            # NOTE: This needs special handling for line number input mode
            elif event.key == self.config.keybindings.enter_visual_mode:
                await self.action_toggle_visual_mode()
                event.prevent_default()  # Prevent Textual binding from also triggering

            # Clear line number input on any other key
            elif self.line_number_mode:
                self._clear_line_number_input()

        def _clear_line_number_input(self) -> None:
            """Clear line number input state."""
            self.line_number_input = ""
            self.line_number_mode = False

        def _apply_cli_exclusions(self) -> None:
            """Apply CLI exclusion patterns to the log viewer."""
            if not self.cli_exclude_patterns or not self.log_viewer:
                return

            exclusion_manager = self.log_viewer.exclusion_manager
            added_count = 0

            for pattern in self.cli_exclude_patterns:
                if exclusion_manager.add_pattern(
                    pattern=pattern,
                    is_regex=True,
                    case_sensitive=True,
                ):
                    added_count += 1

            if added_count > 0:
                # Refresh the display to apply exclusions
                self.log_viewer.refresh_exclusions()

                # Show notification about applied exclusions
                self.notify(
                    f"Applied {added_count} CLI exclusion pattern(s)",
                    timeout=3,
                )

        async def action_show_help(self) -> None:
            """Show help information."""
            await self.push_screen(HelpScreen(self.config.keybindings))

        # Return the dynamically created class

    return DaLogApp
