"""
SSH file watching functionality for remote log monitoring.
"""

import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional

import paramiko
from paramiko import SSHClient

from .remote_reader import RemoteFileWatcher, SSHLogReader


class SSHFileWatcherThread(threading.Thread):
    """Background thread for monitoring SSH files."""

    def __init__(
        self, ssh_url: str, callback: Callable[[str], None], poll_interval: float = 2.0
    ):
        """Initialize SSH file watcher thread.

        Args:
            ssh_url: SSH URL to monitor
            callback: Function to call when file changes
            poll_interval: Seconds between checks
        """
        super().__init__(daemon=True)
        self.ssh_url = ssh_url
        self.callback = callback
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._ssh_reader = SSHLogReader(ssh_url)
        self._remote_watcher = None

    def stop(self):
        """Stop the watcher thread."""
        self._stop_event.set()

    def run(self):
        """Run the polling loop."""
        try:
            # Parse SSH connection details
            self._ssh_reader._parse_ssh_url()

            # Create SSH connection
            ssh_client = SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                hostname=self._ssh_reader.host,
                port=self._ssh_reader.port,
                username=self._ssh_reader.user,
                look_for_keys=True,
                allow_agent=True,
            )

            # Create remote file watcher
            self._remote_watcher = RemoteFileWatcher(
                ssh_client, self._ssh_reader.remote_path
            )

            # Initialize watcher state
            self._remote_watcher.check_for_changes()

            # Poll for changes
            while not self._stop_event.is_set():
                if self._remote_watcher.check_for_changes():
                    # File changed, invoke callback
                    self.callback(self.ssh_url)

                # Wait before next check
                self._stop_event.wait(self.poll_interval)

        except Exception as e:
            print(f"Error in SSH file watcher: {e}")
        finally:
            if hasattr(self, "ssh_client"):
                try:
                    ssh_client.close()
                except:
                    pass


class AsyncSSHFileWatcher:
    """Async SSH file watcher for Textual compatibility."""

    def __init__(self):
        """Initialize the async SSH file watcher."""
        self._watchers: Dict[str, SSHFileWatcherThread] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._process_task: Optional[asyncio.Task] = None
        self._callback = None

    async def start(self, callback: Callable[[str], Coroutine[Any, Any, None]]) -> None:
        """Start the async SSH file watcher.

        Args:
            callback: Async function to call when files change
        """
        self._callback = callback

        # Start the event processing task
        if self._process_task is None or self._process_task.done():
            self._process_task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop the async SSH file watcher."""
        # Stop all watcher threads
        for watcher in self._watchers.values():
            watcher.stop()

        # Wait for threads to finish
        for watcher in self._watchers.values():
            watcher.join(timeout=2.0)

        self._watchers.clear()

        # Cancel the processing task
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        # Clear the event queue
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def add_ssh_file(self, ssh_url: str, poll_interval: float = 2.0) -> bool:
        """Add an SSH file to monitor.

        Args:
            ssh_url: SSH URL to monitor
            poll_interval: Seconds between checks

        Returns:
            True if file was added successfully
        """
        if ssh_url in self._watchers:
            return True  # Already watching

        try:
            # Create and start watcher thread
            watcher = SSHFileWatcherThread(ssh_url, self._queue_event, poll_interval)
            watcher.start()
            self._watchers[ssh_url] = watcher
            return True
        except Exception as e:
            print(f"Error adding SSH file to watcher: {e}")
            return False

    def remove_ssh_file(self, ssh_url: str) -> bool:
        """Remove an SSH file from monitoring.

        Args:
            ssh_url: SSH URL to stop monitoring

        Returns:
            True if file was removed
        """
        if ssh_url in self._watchers:
            watcher = self._watchers[ssh_url]
            watcher.stop()
            watcher.join(timeout=2.0)
            del self._watchers[ssh_url]
            return True
        return False

    def _queue_event(self, ssh_url: str) -> None:
        """Queue a file change event.

        Args:
            ssh_url: SSH URL that changed
        """
        try:
            self._event_queue.put_nowait(ssh_url)
        except asyncio.QueueFull:
            # Queue is full, skip this event
            pass

    async def _process_events(self) -> None:
        """Process queued file change events."""
        while True:
            try:
                # Wait for events with timeout
                ssh_url = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)

                # Call the async callback
                if self._callback:
                    try:
                        await self._callback(ssh_url)
                    except Exception as e:
                        print(f"Error in async SSH file watcher callback: {e}")

            except asyncio.TimeoutError:
                # No events, continue
                continue
            except asyncio.CancelledError:
                # Task cancelled, exit
                break
            except Exception as e:
                print(f"Error processing SSH file events: {e}")
