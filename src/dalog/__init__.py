"""
dalog - Your friendly terminal logs viewer

A high-performance, terminal-based log viewing application built with Python and Textual.
"""

try:
    from importlib.metadata import version

    __version__ = version("dalog")
except Exception:
    # Fallback for development/editable installs
    __version__ = "0.1.1"

__author__ = "Mike Wassmer"
__email__ = "mikewassmer@protonmail.com"

# Export main application class for easier imports
from .app import DaLogApp

__all__ = ["DaLogApp", "__version__"]
