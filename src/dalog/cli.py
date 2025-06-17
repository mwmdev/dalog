#!/usr/bin/env python3
"""
Command-line interface for DaLog.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click

from . import __version__
from .app import DaLogApp


def print_version(ctx, param, value):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()


@click.command()
@click.argument(
    "log_file",
    required=True,
    type=click.Path(exists=True, readable=True),
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, readable=True),
    help="Path to configuration file",
)
@click.option(
    "--search",
    "-s",
    type=str,
    help="Initial search term to filter logs",
)
@click.option(
    "--tail",
    "-t",
    type=int,
    help="Load only last N lines of the file",
)
@click.option(
    "--theme",
    type=str,
    help="Set the Textual theme (e.g., nord, gruvbox, tokyo-night, textual-dark)",
)
@click.option(
    "--exclude",
    "-e",
    type=str,
    multiple=True,
    help="Exclude lines matching pattern (can be used multiple times). Supports regex patterns and is case-sensitive.",
)
@click.option(
    "--version",
    "-V",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Show the version and exit.",
)
def main(
    log_file: str,
    config: Optional[str],
    search: Optional[str],
    tail: Optional[int],
    theme: Optional[str],
    exclude: Tuple[str, ...],
) -> None:
    """
    dalog - Your friendly terminal logs viewer

    View and search a log file with a modern terminal interface.

    Examples:

        dalog app.log

        dalog --search ERROR app.log

        dalog --tail 1000 large-app.log

        dalog --config ~/.config/dalog/custom.toml app.log

        dalog --exclude "DEBUG" --exclude "INFO" app.log

        dalog --exclude "ERROR.*timeout" app.log
    """
    # Convert path to string
    log_file_path = str(Path(log_file).resolve())

    # Convert exclude tuple to list
    exclude_patterns = list(exclude) if exclude else []

    # Create and run the application
    try:
        app = DaLogApp(
            log_file=log_file_path,
            config_path=config,
            initial_search=search,
            tail_lines=tail,
            theme=theme,
            exclude_patterns=exclude_patterns,
        )

        # Run the app
        app.run()

    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        pass
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
