"""
Core functionality for DaLog.
"""

from .exclusions import ExclusionManager
from .file_watcher import AsyncFileWatcher
from .html_processor import HTMLProcessor
from .log_processor import LogLine, LogProcessor
from .log_reader import LocalLogReader, create_unified_log_reader
from .remote_reader import LogReader, SSHLogReader, create_log_reader, is_ssh_url
from .styling import StylingEngine

__all__ = [
    "LogProcessor",
    "LogLine",
    "AsyncFileWatcher",
    "StylingEngine",
    "ExclusionManager",
    "HTMLProcessor",
    "SSHLogReader",
    "LocalLogReader",
    "LogReader",
    "is_ssh_url",
    "create_log_reader",
    "create_unified_log_reader",
]
