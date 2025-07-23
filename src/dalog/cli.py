#!/usr/bin/env python3
"""
Command-line interface for DaLog.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click

from . import __version__
from .app import create_dalog_app


def print_version(ctx, param, value):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()


def validate_log_source(ctx, param, value):
    """Validate log source (local file or SSH URL)."""
    from .core.remote_reader import is_ssh_url

    if is_ssh_url(value):
        # It's an SSH URL, no need to check if file exists locally
        return value

    # It's a local file, check if it exists
    path = Path(value)
    if not path.exists():
        raise click.BadParameter(f"File not found: {value}")
    if not path.is_file():
        raise click.BadParameter(f"Not a file: {value}")

    return str(path.resolve())


@click.command()
@click.argument(
    "log_file",
    required=True,
    callback=validate_log_source,
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
    Supports both local files and remote files via SSH.

    Examples:

        dalog app.log

        dalog user@host:/var/log/app.log

        dalog --search ERROR app.log

        dalog --tail 1000 user@host:/var/log/large-app.log

        dalog --config ~/.config/dalog/custom.toml app.log

        dalog --exclude "DEBUG" --exclude "INFO" app.log

        dalog --exclude "ERROR.*timeout" user@host:/var/log/app.log
    """
    # Use log_file directly since it's already validated
    log_file_path = log_file

    # Convert exclude tuple to list
    exclude_patterns = list(exclude) if exclude else []

    # Create and run the application
    try:
        # Create the app class with dynamic bindings
        DaLogApp = create_dalog_app(config)

        # Create app instance
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
