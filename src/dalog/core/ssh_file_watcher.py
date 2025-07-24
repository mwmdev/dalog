"""
SSH file watching functionality for remote log monitoring.
"""

import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional, Union

import paramiko
from paramiko import SSHClient

from .remote_reader import RemoteFileWatcher, SSHLogReader, create_secure_ssh_client


class SSHFileWatcherThread(threading.Thread):
    """Background thread for monitoring SSH files."""

    def __init__(
        self,
        ssh_url: str,
        callback: Callable[[str], None],
        poll_interval: float = 1.0,  # Fast polling for real-time updates
        max_poll_interval: float = 2.0,  # Back off to this when idle
        strict_host_key_checking: bool = True,
        connection_timeout: int = 30,
        known_hosts_file: Optional[str] = None,
    ):
        """Initialize SSH file watcher thread with security options.

        Args:
            ssh_url: SSH URL to monitor
            callback: Function to call when file changes
            poll_interval: Initial seconds between checks (fast polling)
            max_poll_interval: Maximum interval when backing off during idle periods
            strict_host_key_checking: Whether to enforce strict host key checking
            connection_timeout: SSH connection timeout in seconds
            known_hosts_file: Optional path to known_hosts file
        """
        super().__init__(daemon=True)
        self.ssh_url = ssh_url
        self.callback = callback
        self.min_poll_interval = poll_interval
        self.max_poll_interval = max_poll_interval
        self.current_poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._consecutive_no_changes = 0

        # Create SSH reader with security options
        self._ssh_reader = SSHLogReader(
            ssh_url,
            strict_host_key_checking=strict_host_key_checking,
            connection_timeout=connection_timeout,
            known_hosts_file=known_hosts_file,
        )
        self._remote_watcher = None

    def stop(self):
        """Stop the watcher thread."""
        self._stop_event.set()

        # Clean up remote watcher if it exists
        if self._remote_watcher:
            try:
                self._remote_watcher.close()
            except:
                pass

    def run(self):
        """Run the polling loop with secure SSH connection."""
        ssh_client = None
        try:
            # Parse SSH connection details (validation happens in constructor)
            self._ssh_reader._parse_ssh_url()

            # Create secure SSH connection
            ssh_client = create_secure_ssh_client(
                self._ssh_reader.host,
                self._ssh_reader.port,
                self._ssh_reader.user,
                strict_host_key_checking=self._ssh_reader.strict_host_key_checking,
                known_hosts_file=self._ssh_reader.known_hosts_file,
                connection_timeout=self._ssh_reader.connection_timeout,
            )

            # Connect with secure settings
            ssh_client.connect(
                hostname=self._ssh_reader.host,
                port=self._ssh_reader.port,
                username=self._ssh_reader.user,
                look_for_keys=True,
                allow_agent=True,
                timeout=self._ssh_reader.connection_timeout,
                # Disable less secure authentication methods
                disabled_algorithms={
                    "pubkeys": ["ssh-dss"],  # Disable weak DSA keys
                    "kex": ["diffie-hellman-group1-sha1"],  # Disable weak key exchange
                },
            )

            # Create remote file watcher
            self._remote_watcher = RemoteFileWatcher(
                ssh_client, self._ssh_reader.remote_path
            )

            # Initialize watcher state
            self._remote_watcher.check_for_changes()

            # Poll for changes with adaptive intervals
            while not self._stop_event.is_set():
                if self._remote_watcher.check_for_changes():
                    # File changed, invoke callback
                    self.callback(self.ssh_url)
                    # Reset to fast polling when activity detected
                    self.current_poll_interval = self.min_poll_interval
                    self._consecutive_no_changes = 0
                else:
                    # No changes - gradually increase poll interval to reduce overhead
                    self._consecutive_no_changes += 1
                    if self._consecutive_no_changes >= 5:  # After 5 no-change cycles
                        # Exponentially back off up to max_poll_interval
                        self.current_poll_interval = min(
                            self.current_poll_interval * 1.5, self.max_poll_interval
                        )

                # Wait before next check using adaptive interval
                self._stop_event.wait(self.current_poll_interval)

        except Exception as e:
            # Don't expose detailed error information that might leak sensitive details
            print(f"Error in SSH file watcher: connection failed")
        finally:
            # Clean up resources properly
            if self._remote_watcher:
                try:
                    self._remote_watcher.close()
                except:
                    pass
            if ssh_client:
                try:
                    ssh_client.close()
                except:
                    pass


class SSHFileWatcherThreadWithConnection(threading.Thread):
    """Background thread for monitoring SSH files using an existing SSH connection."""

    def __init__(
        self,
        ssh_url: str,
        existing_ssh_client: SSHClient,
        remote_path: str,
        callback: Callable[[str], None],
        poll_interval: float = 1.0,
        max_poll_interval: float = 2.0,
    ):
        """Initialize SSH file watcher thread with existing connection.

        Args:
            ssh_url: SSH URL to monitor (for identification)
            existing_ssh_client: Existing SSH client connection to reuse
            remote_path: Path to remote file
            callback: Function to call when file changes
            poll_interval: Initial seconds between checks (fast polling)
            max_poll_interval: Maximum interval when backing off during idle periods
        """
        super().__init__(daemon=True)
        self.ssh_url = ssh_url
        self.existing_ssh_client = existing_ssh_client
        self.remote_path = remote_path
        self.callback = callback
        self.min_poll_interval = poll_interval
        self.max_poll_interval = max_poll_interval
        self.current_poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._remote_watcher = None
        self._consecutive_no_changes = 0

    def stop(self):
        """Stop the watcher thread."""
        self._stop_event.set()

        # Clean up remote watcher if it exists
        if self._remote_watcher:
            try:
                self._remote_watcher.close()
            except:
                pass

    def run(self):
        """Run the polling loop using existing SSH connection."""
        try:
            # Create remote file watcher using existing SSH connection
            self._remote_watcher = RemoteFileWatcher(
                self.existing_ssh_client, self.remote_path
            )

            # Initialize watcher state
            self._remote_watcher.check_for_changes()

            # Poll for changes with adaptive intervals
            while not self._stop_event.is_set():
                if self._remote_watcher.check_for_changes():
                    # File changed, invoke callback
                    self.callback(self.ssh_url)
                    # Reset to fast polling when activity detected
                    self.current_poll_interval = self.min_poll_interval
                    self._consecutive_no_changes = 0
                else:
                    # No changes - gradually increase poll interval to reduce overhead
                    self._consecutive_no_changes += 1
                    if self._consecutive_no_changes >= 5:  # After 5 no-change cycles
                        # Exponentially back off up to max_poll_interval
                        self.current_poll_interval = min(
                            self.current_poll_interval * 1.5, self.max_poll_interval
                        )

                # Wait before next check using adaptive interval
                self._stop_event.wait(self.current_poll_interval)

        except Exception as e:
            # Don't expose detailed error information that might leak sensitive details
            print(f"Error in SSH file watcher (existing connection): connection failed")
        finally:
            # Clean up resources properly
            if self._remote_watcher:
                try:
                    self._remote_watcher.close()
                except:
                    pass


class AsyncSSHFileWatcher:
    """Async SSH file watcher for Textual compatibility."""

    def __init__(self):
        """Initialize the async SSH file watcher."""
        self._watchers: Dict[
            str, Union[SSHFileWatcherThread, SSHFileWatcherThreadWithConnection]
        ] = {}
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

    def add_ssh_file_with_connection(
        self,
        ssh_url: str,
        existing_ssh_client: SSHClient,
        remote_path: str,
        poll_interval: float = 1.0,
        max_poll_interval: float = 2.0,
    ) -> bool:
        """Add an SSH file to monitor using an existing SSH connection.

        Args:
            ssh_url: SSH URL to monitor
            existing_ssh_client: Existing SSH client connection to reuse
            remote_path: Remote file path
            poll_interval: Initial seconds between checks (fast polling)
            max_poll_interval: Maximum interval when backing off during idle periods

        Returns:
            True if file was added successfully
        """
        if ssh_url in self._watchers:
            return True  # Already watching

        try:
            # Create and start watcher thread with existing connection
            watcher = SSHFileWatcherThreadWithConnection(
                ssh_url,
                existing_ssh_client,
                remote_path,
                self._queue_event,
                poll_interval,
                max_poll_interval,
            )
            watcher.start()
            self._watchers[ssh_url] = watcher
            return True
        except Exception:
            # Don't expose detailed error information
            print(f"Error adding SSH file to watcher: connection reuse failed")
            return False

    def add_ssh_file(
        self,
        ssh_url: str,
        poll_interval: float = 1.0,  # Fast polling for real-time updates
        max_poll_interval: float = 2.0,  # Back off to this when idle
        strict_host_key_checking: bool = True,
        connection_timeout: int = 30,
        known_hosts_file: Optional[str] = None,
    ) -> bool:
        """Add an SSH file to monitor with security options.

        Args:
            ssh_url: SSH URL to monitor
            poll_interval: Initial seconds between checks (fast polling)
            max_poll_interval: Maximum interval when backing off during idle periods
            strict_host_key_checking: Whether to enforce strict host key checking
            connection_timeout: SSH connection timeout in seconds
            known_hosts_file: Optional path to known_hosts file

        Returns:
            True if file was added successfully
        """
        if ssh_url in self._watchers:
            return True  # Already watching

        try:
            # Create and start watcher thread with security options
            watcher = SSHFileWatcherThread(
                ssh_url,
                self._queue_event,
                poll_interval,
                max_poll_interval,
                strict_host_key_checking=strict_host_key_checking,
                connection_timeout=connection_timeout,
                known_hosts_file=known_hosts_file,
            )
            watcher.start()
            self._watchers[ssh_url] = watcher
            return True
        except Exception:
            # Don't expose detailed error information
            print(f"Error adding SSH file to watcher: connection failed")
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
