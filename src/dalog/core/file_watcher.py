"""
File watching functionality for live reload.
"""

import asyncio
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Set

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer


class LogFileHandler(FileSystemEventHandler):
    """Handler for log file changes."""

    def __init__(self, callback: Callable[[Path], None], debounce_seconds: float = 0.5):
        """Initialize the handler.

        Args:
            callback: Function to call when file changes
            debounce_seconds: Minimum time between callbacks for same file
        """
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_modified: dict[Path, datetime] = {}
        self._pending_callbacks: Set[Path] = set()

    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Check debounce
        now = datetime.now()
        last_modified = self._last_modified.get(file_path)

        if last_modified and (now - last_modified) < timedelta(
            seconds=self.debounce_seconds
        ):
            # Too soon, add to pending
            self._pending_callbacks.add(file_path)
            return

        # Update last modified time
        self._last_modified[file_path] = now
        self._pending_callbacks.discard(file_path)

        # Call the callback
        try:
            self.callback(file_path)
        except Exception as e:
            print(f"Error in file watcher callback: {e}")


class FileWatcher:
    """Watches log files for changes."""

    def __init__(self):
        """Initialize the file watcher."""
        self.observer: Optional[Observer] = None
        self.watched_files: Set[Path] = set()
        self.callback: Optional[Callable[[Path], None]] = None
        self._lock = threading.Lock()

    def start(self, callback: Callable[[Path], None]) -> None:
        """Start the file watcher.

        Args:
            callback: Function to call when files change
        """
        with self._lock:
            if self.observer and self.observer.is_alive():
                return

            self.callback = callback
            self.observer = Observer()
            self.observer.start()

    def stop(self) -> None:
        """Stop the file watcher."""
        with self._lock:
            if self.observer and self.observer.is_alive():
                self.observer.stop()
                self.observer.join(timeout=2.0)
                self.observer = None

    def add_file(self, file_path: Path) -> bool:
        """Add a file to watch.

        Args:
            file_path: Path to file to watch

        Returns:
            True if file was added successfully
        """
        with self._lock:
            if not self.observer or not self.observer.is_alive():
                return False

            if file_path in self.watched_files:
                return True

            try:
                # Watch the parent directory
                parent_dir = file_path.parent
                handler = LogFileHandler(self._handle_file_change)

                # Schedule watching
                watch = self.observer.schedule(
                    handler, str(parent_dir), recursive=False
                )

                self.watched_files.add(file_path)
                return True

            except Exception as e:
                print(f"Error adding file to watcher: {e}")
                return False

    def remove_file(self, file_path: Path) -> bool:
        """Remove a file from watching.

        Args:
            file_path: Path to file to stop watching

        Returns:
            True if file was removed
        """
        with self._lock:
            if file_path in self.watched_files:
                self.watched_files.remove(file_path)

                # If no more files in this directory, could unschedule
                # but for simplicity we'll leave it scheduled
                return True
            return False

    def _handle_file_change(self, file_path: Path) -> None:
        """Handle file change events.

        Args:
            file_path: Path to changed file
        """
        # Only process if we're watching this specific file
        if file_path in self.watched_files and self.callback:
            self.callback(file_path)

    def is_watching(self, file_path: Path) -> bool:
        """Check if a file is being watched.

        Args:
            file_path: Path to check

        Returns:
            True if file is being watched
        """
        return file_path in self.watched_files

    def get_watched_files(self) -> Set[Path]:
        """Get set of watched files.

        Returns:
            Set of file paths being watched
        """
        return self.watched_files.copy()


class AsyncFileWatcher:
    """Async file watcher using threading for Textual compatibility."""

    def __init__(self):
        """Initialize the async file watcher."""
        self._file_watcher = FileWatcher()
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._process_task: Optional[asyncio.Task] = None
        self._watched_files: Set[Path] = set()
        self._observer = None  # For compatibility with tests
        self._callback = None  # For compatibility with tests

    async def start(
        self, callback: Callable[[Path], Coroutine[Any, Any, None]]
    ) -> None:
        """Start the async file watcher.

        Args:
            callback: Async function to call when files change
        """
        # Start the underlying file watcher
        self._file_watcher.start(self._queue_event)

        # Start the event processing task
        if self._process_task is None or self._process_task.done():
            self._process_task = asyncio.create_task(self._process_events(callback))

    async def stop(self) -> None:
        """Stop the async file watcher."""
        # Cancel the processing task
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        # Stop the underlying file watcher
        self._file_watcher.stop()

        # Clear the event queue
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def add_file(self, file_path: Path) -> None:
        """Add a file to the watch list.
        
        Args:
            file_path: Path to the file to watch
        """
        self._watched_files.add(file_path)
        # Also add to the underlying file watcher if it exists
        if hasattr(self._file_watcher, 'add_file'):
            self._file_watcher.add_file(file_path)

    def remove_file(self, file_path: Path) -> bool:
        """Remove a file from the watch list.
        
        Args:
            file_path: Path to the file to stop watching
            
        Returns:
            True if file was removed, False if not found
        """
        if file_path in self._watched_files:
            self._watched_files.remove(file_path)
            # Also remove from underlying file watcher if it exists
            if hasattr(self._file_watcher, 'remove_file'):
                self._file_watcher.remove_file(file_path)
            return True
        return False

    def _queue_event(self, file_path: Path) -> None:
        """Queue a file change event.

        Args:
            file_path: Path that changed
        """
        try:
            self._event_queue.put_nowait(file_path)
        except asyncio.QueueFull:
            # Queue is full, skip this event
            pass

    async def _process_events(
        self, callback: Callable[[Path], Coroutine[Any, Any, None]]
    ) -> None:
        """Process queued file change events.

        Args:
            callback: Async function to call for each change
        """
        while True:
            try:
                # Wait for events with timeout
                file_path = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)

                # Call the async callback
                try:
                    await callback(file_path)
                except Exception as e:
                    print(f"Error in async file watcher callback: {e}")

            except asyncio.TimeoutError:
                # No events, continue
                continue
            except asyncio.CancelledError:
                # Task cancelled, exit
                break
            except Exception as e:
                print(f"Error processing file events: {e}")
