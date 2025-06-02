"""
Core functionality for DaLog.
"""

from .log_processor import LogProcessor, LogLine
from .file_watcher import AsyncFileWatcher
from .styling import StylingEngine
from .exclusions import ExclusionManager
from .html_processor import HTMLProcessor

__all__ = [
    "LogProcessor",
    "LogLine",
    "AsyncFileWatcher",
    "StylingEngine",
    "ExclusionManager",
    "HTMLProcessor",
]
