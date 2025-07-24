"""
SSH connection pooling for efficient connection management.
"""

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from paramiko import SFTPClient, SSHClient


@dataclass
class PooledConnection:
    """A pooled SSH connection with metadata."""

    ssh_client: SSHClient
    sftp_client: Optional[SFTPClient]
    created_at: float
    last_used: float
    is_healthy: bool = True
    reference_count: int = 0

    def mark_used(self) -> None:
        """Mark connection as recently used."""
        self.last_used = time.time()

    def acquire(self) -> None:
        """Acquire a reference to this connection."""
        self.reference_count += 1
        self.mark_used()

    def release(self) -> None:
        """Release a reference to this connection."""
        self.reference_count = max(0, self.reference_count - 1)

    def is_expired(self, max_age: float) -> bool:
        """Check if connection has exceeded maximum age."""
        return time.time() - self.created_at > max_age

    def is_idle_expired(self, max_idle: float) -> bool:
        """Check if connection has been idle too long."""
        return time.time() - self.last_used > max_idle


class SSHConnectionPool:
    """Thread-safe SSH connection pool with automatic cleanup and health checking."""

    def __init__(
        self,
        max_connections_per_host: int = 5,
        max_connection_age: float = 3600.0,  # 1 hour
        max_idle_time: float = 300.0,  # 5 minutes
        health_check_interval: float = 60.0,  # 1 minute
    ):
        """Initialize the SSH connection pool.

        Args:
            max_connections_per_host: Maximum connections per (host, port, user) tuple
            max_connection_age: Maximum age of connections in seconds
            max_idle_time: Maximum idle time before closing connections
            health_check_interval: How often to run health checks
        """
        self.max_connections_per_host = max_connections_per_host
        self.max_connection_age = max_connection_age
        self.max_idle_time = max_idle_time
        self.health_check_interval = health_check_interval

        # Pool storage: (host, port, user) -> List[PooledConnection]
        self._pools: Dict[Tuple[str, int, str], list[PooledConnection]] = {}
        self._lock = threading.RLock()

        # Performance metrics
        self.connections_created = 0
        self.connections_reused = 0
        self.connections_closed = 0
        self.pool_hits = 0
        self.pool_misses = 0

        # Health check tracking
        self._last_health_check = time.time()

    def _get_pool_key(self, host: str, port: int, user: str) -> Tuple[str, int, str]:
        """Generate pool key for a connection."""
        return (host, port, user)

    def _cleanup_expired_connections(self) -> None:
        """Remove expired connections from all pools."""
        current_time = time.time()

        for pool_key, connections in list(self._pools.items()):
            expired_connections = []

            for conn in connections[:]:  # Create a copy to iterate over
                if conn.reference_count == 0 and (
                    conn.is_expired(self.max_connection_age)
                    or conn.is_idle_expired(self.max_idle_time)
                ):
                    expired_connections.append(conn)
                    connections.remove(conn)

            # Close expired connections
            for conn in expired_connections:
                try:
                    if conn.sftp_client:
                        conn.sftp_client.close()
                    conn.ssh_client.close()
                    self.connections_closed += 1
                except Exception:
                    pass  # Ignore errors during cleanup

            # Remove empty pools
            if not connections:
                del self._pools[pool_key]

    def _health_check_if_needed(self) -> None:
        """Run health check if enough time has passed."""
        if time.time() - self._last_health_check > self.health_check_interval:
            self._cleanup_expired_connections()
            self._last_health_check = time.time()

    def _test_connection_health(self, conn: PooledConnection) -> bool:
        """Test if a connection is still healthy."""
        try:
            # Simple health check - execute a basic command
            stdin, stdout, stderr = conn.ssh_client.exec_command("echo test")
            stdout.read()  # Consume output
            return True
        except Exception:
            conn.is_healthy = False
            return False

    def get_connection(
        self,
        host: str,
        port: int,
        user: str,
        connection_factory,  # Callable that creates new SSH connections
    ) -> Optional[PooledConnection]:
        """Get a connection from the pool or create a new one.

        Args:
            host: SSH hostname
            port: SSH port
            user: SSH username
            connection_factory: Function to create new SSH connections

        Returns:
            PooledConnection if available or created, None if failed
        """
        with self._lock:
            self._health_check_if_needed()

            pool_key = self._get_pool_key(host, port, user)

            # Try to reuse existing connection
            if pool_key in self._pools:
                connections = self._pools[pool_key]

                for conn in connections:
                    if (
                        conn.reference_count == 0
                        and conn.is_healthy
                        and not conn.is_expired(self.max_connection_age)
                    ):

                        # Test connection health
                        if self._test_connection_health(conn):
                            conn.acquire()
                            self.connections_reused += 1
                            self.pool_hits += 1
                            return conn
                        else:
                            # Remove unhealthy connection
                            connections.remove(conn)
                            try:
                                if conn.sftp_client:
                                    conn.sftp_client.close()
                                conn.ssh_client.close()
                                self.connections_closed += 1
                            except Exception:
                                pass

            # No suitable connection found - create new one if under limit
            pool = self._pools.get(pool_key, [])
            if len(pool) < self.max_connections_per_host:
                try:
                    ssh_client = connection_factory()
                    new_conn = PooledConnection(
                        ssh_client=ssh_client,
                        sftp_client=None,  # Create SFTP on demand
                        created_at=time.time(),
                        last_used=time.time(),
                    )
                    new_conn.acquire()

                    # Add to pool
                    if pool_key not in self._pools:
                        self._pools[pool_key] = []
                    self._pools[pool_key].append(new_conn)

                    self.connections_created += 1
                    self.pool_misses += 1
                    return new_conn

                except Exception:
                    self.pool_misses += 1
                    return None

            # Pool is full
            self.pool_misses += 1
            return None

    def return_connection(self, conn: PooledConnection) -> None:
        """Return a connection to the pool.

        Args:
            conn: Connection to return
        """
        with self._lock:
            conn.release()

    def get_sftp_client(self, conn: PooledConnection) -> Optional[SFTPClient]:
        """Get SFTP client for a connection, creating it if needed.

        Args:
            conn: SSH connection

        Returns:
            SFTP client or None if failed
        """
        if conn.sftp_client is None:
            try:
                conn.sftp_client = conn.ssh_client.open_sftp()
            except Exception:
                conn.is_healthy = False
                return None

        return conn.sftp_client

    def close_all_connections(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            for connections in self._pools.values():
                for conn in connections:
                    try:
                        if conn.sftp_client:
                            conn.sftp_client.close()
                        conn.ssh_client.close()
                        self.connections_closed += 1
                    except Exception:
                        pass

            self._pools.clear()

    def get_pool_stats(self) -> Dict[str, any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool metrics
        """
        with self._lock:
            total_connections = sum(len(pool) for pool in self._pools.values())
            active_connections = sum(
                sum(1 for conn in pool if conn.reference_count > 0)
                for pool in self._pools.values()
            )

            pool_efficiency = (
                self.pool_hits / (self.pool_hits + self.pool_misses)
                if (self.pool_hits + self.pool_misses) > 0
                else 0.0
            )

            return {
                "total_connections": total_connections,
                "active_connections": active_connections,
                "idle_connections": total_connections - active_connections,
                "unique_hosts": len(self._pools),
                "connections_created": self.connections_created,
                "connections_reused": self.connections_reused,
                "connections_closed": self.connections_closed,
                "pool_hits": self.pool_hits,
                "pool_misses": self.pool_misses,
                "pool_efficiency": pool_efficiency,
                "max_connections_per_host": self.max_connections_per_host,
            }


# Global SSH connection pool instance
_ssh_connection_pool = SSHConnectionPool()


def get_ssh_connection_pool() -> SSHConnectionPool:
    """Get the global SSH connection pool instance."""
    return _ssh_connection_pool
