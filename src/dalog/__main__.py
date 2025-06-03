"""
Entry point for running DaLog as a module.

Usage:
    python -m dalog [OPTIONS] [LOG_FILES...]
"""

from .cli import main

if __name__ == "__main__":
    main()
